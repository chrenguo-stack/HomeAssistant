from __future__ import annotations

import base64
import hashlib
import importlib.util
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
