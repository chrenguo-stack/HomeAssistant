from __future__ import annotations

import base64
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_ssh_transport.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("ssh_transport_test", TOOL)
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    sys.modules["ssh_transport_test"] = tool
    spec.loader.exec_module(tool)
    return tool


def known_hosts(tmp_path):
    blob = b"n3w-test-key"
    encoded = base64.b64encode(blob).decode()
    path = tmp_path / "known_hosts"
    path.write_text(f"t1.local ssh-ed25519 {encoded}\n", encoding="utf-8")
    path.chmod(0o600)
    return path, hashlib.sha256(blob).hexdigest()


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.master_available = True
        self.exit_fails = False

    def run(self, argv, *, timeout, interactive=False, check=True):
        command = tuple(argv)
        self.calls.append((command, interactive))
        returncode = 0
        if interactive and command[0] == "ssh" and "-MNf" in command:
            self.master_available = True
        if "-O" in command and "exit" in command:
            if self.exit_fails:
                returncode = 255
            else:
                self.master_available = False
        elif "-O" in command and "check" in command and not self.master_available:
            returncode = 255
        result = subprocess.CompletedProcess(command, returncode, "", "")
        if check and returncode:
            raise RuntimeError("command_failed")
        return result


def test_mismatch_stops_before_authentication(tmp_path):
    tool = load_tool()
    path, _digest = known_hosts(tmp_path)
    runner = FakeRunner()
    with pytest.raises(tool.SSHTransportError, match="host_key_binding_mismatch"):
        tool.SSHTransport(
            target="root@t1.local",
            known_hosts=path,
            expected_host_key_sha256="f" * 64,
            runner=runner,
            work_root=tmp_path,
        )
    assert runner.calls == []


def test_children_reuse_master_and_disable_fallback(tmp_path):
    tool = load_tool()
    path, digest = known_hosts(tmp_path)
    runner = FakeRunner()
    transport = tool.SSHTransport(
        target="root@t1.local",
        known_hosts=path,
        expected_host_key_sha256=digest,
        runner=runner,
        work_root=tmp_path,
    )
    transport.start_epoch()
    transport.run_remote(("true",))
    source = tmp_path / "payload"
    source.write_text("x")
    transport.scp_to(source, "/var/tmp/payload")
    interactive = [command for command, flag in runner.calls if flag]
    assert len(interactive) == 1
    assert "NumberOfPasswordPrompts=1" in interactive[0]
    for command, flag in runner.calls:
        if not flag and command[0] in {"ssh", "scp"} and "BatchMode=yes" in command:
            assert "PasswordAuthentication=no" in command
            assert "KbdInteractiveAuthentication=no" in command
            assert "PubkeyAuthentication=no" in command
            assert "ProxyCommand=/usr/bin/false" in command
            assert "-F" in command
            assert "/dev/null" in command
    transport.close_epoch()


def test_master_loss_never_opens_new_connection(tmp_path):
    tool = load_tool()
    path, digest = known_hosts(tmp_path)
    runner = FakeRunner()
    transport = tool.SSHTransport(
        target="root@t1.local",
        known_hosts=path,
        expected_host_key_sha256=digest,
        runner=runner,
        work_root=tmp_path,
    )
    transport.start_epoch()
    runner.master_available = False
    before = len(runner.calls)
    with pytest.raises(tool.SSHTransportError, match="ssh_master_unavailable"):
        transport.run_remote(("true",))
    assert len(runner.calls) == before + 1
    assert "-O" in runner.calls[-1][0]
    transport.close_epoch(expected_disconnect=True)


def test_one_reboot_is_two_authentication_epochs(tmp_path):
    tool = load_tool()
    path, digest = known_hosts(tmp_path)
    runner = FakeRunner()
    transport = tool.SSHTransport(
        target="root@t1.local",
        known_hosts=path,
        expected_host_key_sha256=digest,
        runner=runner,
        work_root=tmp_path,
    )
    first = transport.start_epoch()
    runner.master_available = False
    second = transport.start_post_reboot_epoch()
    assert first["epoch"] == 1
    assert second["epoch"] == 2
    assert len([1 for _command, interactive in runner.calls if interactive]) == 2
    transport.close_epoch()


def test_cleanup_fails_if_master_exit_cannot_be_proven(tmp_path):
    tool = load_tool()
    path, digest = known_hosts(tmp_path)
    runner = FakeRunner()
    transport = tool.SSHTransport(
        target="root@t1.local",
        known_hosts=path,
        expected_host_key_sha256=digest,
        runner=runner,
        work_root=tmp_path,
    )
    transport.start_epoch()
    runner.exit_fails = True
    with pytest.raises(tool.SSHTransportError, match="ssh_cleanup_failed"):
        transport.close_epoch()


def test_expected_disconnect_requires_master_to_be_gone(tmp_path):
    tool = load_tool()
    path, digest = known_hosts(tmp_path)
    runner = FakeRunner()
    transport = tool.SSHTransport(
        target="root@t1.local",
        known_hosts=path,
        expected_host_key_sha256=digest,
        runner=runner,
        work_root=tmp_path,
    )
    transport.start_epoch()
    with pytest.raises(tool.SSHTransportError, match="ssh_cleanup_failed"):
        transport.close_epoch(expected_disconnect=True)



def test_managed_environment_prepends_fail_closed_ssh_wrappers(tmp_path):
    tool = load_tool()
    path, digest = known_hosts(tmp_path)
    runner = FakeRunner()
    transport = tool.SSHTransport(
        target="root@t1.local",
        known_hosts=path,
        expected_host_key_sha256=digest,
        runner=runner,
        work_root=tmp_path,
    )
    transport.start_epoch()
    environment = transport.managed_environment({"PATH": "/usr/bin:/bin"})
    wrapper_root = Path(environment["PATH"].split(os.pathsep)[0])
    assert environment["N3W_T1_SSH_MANAGED_REQUIRED"] == "1"
    assert environment["N3W_T1_SSH_TARGET"] == "root@t1.local"
    assert (wrapper_root / "ssh").is_file()
    assert (wrapper_root / "scp").is_file()
    for name in ("ssh", "scp"):
        body = (wrapper_root / name).read_text(encoding="utf-8")
        assert "ControlPath=$N3W_T1_SSH_CONTROL_PATH" in body
        assert "PasswordAuthentication=no" in body
        assert "PubkeyAuthentication=no" in body
        assert "ProxyCommand=/usr/bin/false" in body
    transport.close_epoch()


@pytest.mark.skipif(
    os.environ.get("N3W_REAL_SSHD_INTEGRATION") != "1",
    reason="real sshd integration is enabled only by the dedicated CI step",
)
def test_real_sshd_reuses_master_and_requires_one_password_per_epoch(tmp_path):
    tool = load_tool()
    target = os.environ["N3W_REAL_SSHD_TARGET"]
    known_hosts_path = Path(os.environ["N3W_REAL_SSHD_KNOWN_HOSTS"])
    password = os.environ["N3W_REAL_SSHD_PASSWORD"]
    expected = tool.known_host_key_sha256(known_hosts_path, target)

    counter = tmp_path / "askpass-count"
    askpass = tmp_path / "askpass.sh"
    askpass.write_text(
        "#!/bin/sh\n"
        "printf '1\\n' >> \"$N3W_ASKPASS_COUNTER\"\n"
        "printf '%s\\n' \"$N3W_ASKPASS_PASSWORD\"\n",
        encoding="utf-8",
    )
    askpass.chmod(0o700)

    class AskpassRunner(tool.Runner):
        def run(self, argv, *, timeout, interactive=False, check=True):
            if not interactive:
                return super().run(
                    argv,
                    timeout=timeout,
                    interactive=False,
                    check=check,
                )
            environment = os.environ.copy()
            environment["SSH_ASKPASS"] = str(askpass)
            environment["SSH_ASKPASS_REQUIRE"] = "force"
            environment["DISPLAY"] = "n3w-ci:0"
            environment["N3W_ASKPASS_COUNTER"] = str(counter)
            environment["N3W_ASKPASS_PASSWORD"] = password
            return subprocess.run(
                tuple(argv),
                check=check,
                text=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=environment,
                start_new_session=True,
            )

    transport = tool.SSHTransport(
        target=target,
        known_hosts=known_hosts_path,
        expected_host_key_sha256=expected,
        runner=AskpassRunner(),
        work_root=tmp_path,
    )
    first = transport.start_epoch()
    assert first["epoch"] == 1
    assert counter.read_text(encoding="utf-8").splitlines() == ["1"]

    command = transport.run_remote(("printf", "n3w-real-ssh-ok"))
    assert command.stdout == "n3w-real-ssh-ok"

    managed = transport.managed_environment(os.environ.copy())
    managed_command = subprocess.run(
        ("ssh", "-n", target, "printf n3w-managed-ssh-ok"),
        check=True,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        env=managed,
    )
    assert managed_command.stdout == "n3w-managed-ssh-ok"

    source = tmp_path / "payload"
    source.write_text("n3w-real-scp-ok", encoding="utf-8")
    remote_path = "/tmp/n3w-f5-real-ssh-payload"
    transport.scp_to(source, remote_path)
    copied = transport.run_remote(("cat", remote_path))
    assert copied.stdout == "n3w-real-scp-ok"

    transport.runner.run(
        (
            "ssh",
            "-S",
            str(transport.control_path),
            "-O",
            "exit",
            target,
        ),
        timeout=20,
    )
    second = transport.start_post_reboot_epoch()
    assert second["epoch"] == 2
    assert counter.read_text(encoding="utf-8").splitlines() == ["1", "1"]
    transport.run_remote(("rm", "-f", remote_path))
    transport.close_epoch()
