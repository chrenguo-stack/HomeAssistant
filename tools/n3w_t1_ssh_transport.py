#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import os
import shlex
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


class SSHTransportError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        interactive: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            tuple(argv),
            check=check,
            text=True,
            stdin=None if interactive else subprocess.DEVNULL,
            stdout=None if interactive else subprocess.PIPE,
            stderr=None if interactive else subprocess.PIPE,
            timeout=timeout,
        )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _host_name(target: str) -> str:
    return target.rsplit("@", 1)[-1]


def known_host_key_sha256(path: Path, target: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise SSHTransportError("known_hosts_invalid")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
        raise SSHTransportError("known_hosts_metadata_invalid")
    expected = _host_name(target)
    matches: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("|"):
            continue
        fields = line.split()
        if len(fields) < 3 or expected not in fields[0].split(","):
            continue
        try:
            blob = base64.b64decode(fields[2], validate=True)
        except ValueError as error:
            raise SSHTransportError("known_hosts_key_invalid") from error
        matches.append(_sha256_bytes(blob))
    if len(matches) != 1:
        raise SSHTransportError("known_hosts_target_binding_invalid")
    return matches[0]


class SSHTransport:
    def __init__(
        self,
        *,
        target: str,
        known_hosts: Path,
        expected_host_key_sha256: str,
        runner: Runner | None = None,
        work_root: Path | None = None,
    ) -> None:
        if not target or any(character.isspace() for character in target):
            raise SSHTransportError("target_invalid")
        if (
            len(expected_host_key_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_host_key_sha256
            )
        ):
            raise SSHTransportError("host_key_sha256_invalid")
        observed = known_host_key_sha256(known_hosts, target)
        if observed != expected_host_key_sha256:
            raise SSHTransportError("host_key_binding_mismatch")
        self.target = target
        self.known_hosts = known_hosts.resolve()
        self.expected_host_key_sha256 = expected_host_key_sha256
        self.runner = runner or Runner()
        self.work_root = work_root
        self._epoch = 0
        self._directory: Path | None = None
        self._control_path: Path | None = None
        self._active = False

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def control_path(self) -> Path:
        if self._control_path is None:
            raise SSHTransportError("ssh_epoch_not_started")
        return self._control_path

    def _base_options(self) -> tuple[str, ...]:
        return (
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={self.known_hosts}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            "HashKnownHosts=no",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "IdentityAgent=none",
        )

    def _new_directory(self) -> Path:
        root = self.work_root
        if root is None:
            root = Path("/private/tmp")
            if not root.is_dir():
                root = Path(tempfile.gettempdir())
        if root.is_symlink() or not root.is_dir():
            raise SSHTransportError("ssh_work_root_invalid")
        directory = Path(tempfile.mkdtemp(prefix="n3w-f5-", dir=root))
        os.chmod(directory, 0o700)
        metadata = directory.stat()
        if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
            shutil.rmtree(directory, ignore_errors=True)
            raise SSHTransportError("ssh_work_directory_invalid")
        return directory

    def assert_master(self) -> None:
        completed = self.runner.run(
            (
                "ssh",
                "-S",
                str(self.control_path),
                "-O",
                "check",
                self.target,
            ),
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            raise SSHTransportError("ssh_master_unavailable")

    def start_epoch(self) -> dict[str, object]:
        if self._active or self._directory is not None:
            raise SSHTransportError("ssh_epoch_already_started")
        directory = self._new_directory()
        control = directory / "ctl"
        if len(str(control)) > 90:
            shutil.rmtree(directory, ignore_errors=True)
            raise SSHTransportError("ssh_control_path_too_long")
        self._directory = directory
        self._control_path = control
        try:
            self.runner.run(
                (
                    "ssh",
                    "-MNf",
                    *self._base_options(),
                    "-o",
                    "ControlMaster=yes",
                    "-o",
                    "ControlPersist=no",
                    "-o",
                    f"ControlPath={control}",
                    "-o",
                    "PubkeyAuthentication=no",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    "KbdInteractiveAuthentication=yes",
                    "-o",
                    "PreferredAuthentications=keyboard-interactive,password",
                    self.target,
                ),
                timeout=180,
                interactive=True,
            )
            self.assert_master()
        except Exception:
            self._cleanup_local()
            raise
        self._active = True
        self._epoch += 1
        return {
            "status": "PASS",
            "epoch": self._epoch,
            "host_key_sha256": self.expected_host_key_sha256,
            "password_persisted": False,
            "new_login_key": False,
        }

    def _child_options(self) -> tuple[str, ...]:
        self.assert_master()
        return (
            *self._base_options(),
            "-o",
            "ControlMaster=no",
            "-o",
            "ControlPersist=no",
            "-o",
            f"ControlPath={self.control_path}",
            "-o",
            "BatchMode=yes",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "KbdInteractiveAuthentication=no",
            "-o",
            "PreferredAuthentications=none",
        )

    def run_remote(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 300,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not argv:
            raise SSHTransportError("remote_command_empty")
        return self.runner.run(
            (
                "ssh",
                "-n",
                *self._child_options(),
                self.target,
                shlex.join(tuple(argv)),
            ),
            timeout=timeout,
            check=check,
        )

    def scp_to(
        self,
        source: Path,
        remote_path: str,
        *,
        timeout: float = 1800,
    ) -> subprocess.CompletedProcess[str]:
        if source.is_symlink() or not source.is_file():
            raise SSHTransportError("scp_source_invalid")
        if not remote_path.startswith("/") or "\n" in remote_path:
            raise SSHTransportError("scp_remote_path_invalid")
        return self.runner.run(
            (
                "scp",
                *self._child_options(),
                str(source),
                f"{self.target}:{remote_path}",
            ),
            timeout=timeout,
        )

    def legacy_environment(self) -> dict[str, str]:
        self.assert_master()
        return {
            "N3W_T1_SSH_CONTROL_PATH": str(self.control_path),
            "N3W_T1_SSH_KNOWN_HOSTS": str(self.known_hosts),
            "N3W_T1_SSH_TARGET": self.target,
            "N3W_T1_SSH_CONNECTION_EPOCH": str(self._epoch),
        }

    def _cleanup_local(self) -> None:
        directory = self._directory
        self._control_path = None
        self._directory = None
        self._active = False
        if directory is not None and directory.exists():
            shutil.rmtree(directory)

    def close_epoch(self, *, expected_disconnect: bool = False) -> dict[str, object]:
        if self._directory is None:
            return {"status": "PASS", "session_closed": True, "epoch": self._epoch}
        cleanup_error: Exception | None = None
        if self._active and not expected_disconnect:
            try:
                self.runner.run(
                    (
                        "ssh",
                        "-S",
                        str(self.control_path),
                        "-O",
                        "exit",
                        self.target,
                    ),
                    timeout=20,
                    check=False,
                )
            except Exception as error:
                cleanup_error = error
        try:
            self._cleanup_local()
        except Exception as error:
            cleanup_error = cleanup_error or error
        if cleanup_error is not None:
            raise SSHTransportError(
                f"ssh_cleanup_failed:{type(cleanup_error).__name__}"
            ) from cleanup_error
        return {"status": "PASS", "session_closed": True, "epoch": self._epoch}

    def start_post_reboot_epoch(self) -> dict[str, object]:
        self.close_epoch(expected_disconnect=True)
        return self.start_epoch()
