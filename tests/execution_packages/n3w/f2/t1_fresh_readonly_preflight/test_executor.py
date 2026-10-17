from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[5]
EXECUTOR = (
    ROOT
    / "tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py"
)


def load():
    spec = importlib.util.spec_from_file_location(
        "n3w_f2_executor",
        EXECUTOR,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def identity():
    return {
        "os_release": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
        },
        "armbian_release": {
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
        },
        "machine_identity": {
            "etc/machine-id": {
                "valid_hex32": True,
                "content_sha256": "a" * 64,
            },
            "var/lib/dbus/machine-id": {
                "valid_hex32": True,
                "content_sha256": "a" * 64,
            },
        },
        "ssh_host_keys": [
            {
                "name": "ssh_host_ed25519_key",
                "material": "private_metadata_only",
                "kind": "regular",
                "uid": 0,
                "gid": 0,
                "mode": "0600",
            },
            {
                "name": "ssh_host_ed25519_key.pub",
                "material": "public",
                "kind": "regular",
                "uid": 0,
                "gid": 0,
                "mode": "0644",
                "public_key_parse": "PASS",
            },
        ],
    }


def supplement(*, residue=False, packages=True):
    return {
        "architecture": "aarch64",
        "ssh": {"active": "active"},
        "networkmanager": {"active": "active"},
        "armbian_firstrun": {
            "active": "inactive",
            "load_state": "loaded",
            "result": "success",
            "exec_main_status": "0",
            "exec_main_start_timestamp_monotonic": "12345",
            "unit_file_state": "disabled",
        },
        "default_route_present": True,
        "dns_resolution_present": True,
        "ntp_synchronized": "yes",
        "package_candidates": {
            "docker.io": "1" if packages else None,
            "docker-compose-v2": "2" if packages else None,
        },
        "apt": {
            "lists_file_count": 1,
            "source": {
                "ubuntu_ports": True,
                "resolute": True,
                "universe": True,
            },
        },
        "residue_paths": {
            "/var/lib/n3w-fresh-bootstrap-authorizations": residue,
        },
        "engine_residue_paths": {
            "/var/lib/docker": False,
            "/var/lib/containerd": False,
        },
        "fresh_staging_count": 0,
    }


def inventory(*, product=False, missing_docker=False):
    unknown = (
        [{"type": "firewall_visibility", "name": "iptables -S"}]
        if missing_docker
        else []
    )
    return {
        "status": "STOP" if unknown else "PASS",
        "classifications": {
            "DELETE_PRODUCT_STATE_CANDIDATE": (
                [{"type": "product_path"}] if product else []
            ),
            "UNKNOWN_STOP": unknown,
        },
        "remote": {
            "product_paths": [{"exists": product}],
            "systemd": {"units": []},
            "listeners": {"records": []},
            "docker": {
                "containers": [],
                "images": [],
                "volumes": [],
                "networks": (
                    []
                    if missing_docker
                    else [
                        {"Name": "bridge"},
                        {"Name": "host"},
                        {"Name": "none"},
                    ]
                ),
                "errors": (
                    {"info": "not found"}
                    if missing_docker
                    else {}
                ),
            },
        },
    }


def capacity(status="PASS"):
    return {
        "host_baseline": {"status": status},
        "transport": {"capacity_pass": True},
    }


def test_source_authority_binds_current_head_and_main_ancestor():
    module = load()
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    base = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "merge-base",
            head,
            "origin/main",
        ],
        text=True,
    ).strip()
    result = module.validate_source(head, base)
    assert result["head"] == head
    assert result["artifact_head"] == base


@pytest.mark.parametrize(
    "target",
    (
        "",
        " root@host",
        "root@host ",
        "root@host extra",
        "-oBad",
        "<t1>",
    ),
)
def test_invalid_targets_stop(target):
    module = load()
    with pytest.raises(module.StopExecution):
        module.validate_target(target)


def test_ssh_stream_allows_fresh_host_password_auth(monkeypatch):
    module = load()
    seen = {}

    def fake_run(argv, *, input_bytes=None, timeout=120):
        seen["argv"] = argv
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=b'{"status":"PASS"}',
            stderr=b"",
        )

    monkeypatch.setattr(module, "run", fake_run)
    result = module.ssh_stream(
        "root@192.0.2.10",
        "sudo -n python3 -B -",
        b"print('x')",
        60,
    )

    assert result["status"] == "PASS"
    assert "BatchMode=no" in seen["argv"]
    assert "NumberOfPasswordPrompts=1" in seen["argv"]
    assert "PreferredAuthentications=publickey,password" in seen["argv"]
    assert "BatchMode=yes" not in seen["argv"]


def test_clean_ready_host_passes():
    module = load()
    assert module.accept(
        identity(),
        supplement(),
        inventory(),
        capacity(),
    ) == []


def test_missing_docker_accepts_visible_packages():
    module = load()
    assert module.accept(
        identity(),
        supplement(),
        inventory(missing_docker=True),
        capacity("MISSING"),
    ) == []


def test_missing_docker_accepts_fresh_empty_apt_index_with_exact_source():
    module = load()
    report = supplement(packages=False)
    report["apt"]["lists_file_count"] = 0
    assert module.accept(
        identity(),
        report,
        inventory(missing_docker=True),
        capacity("MISSING"),
    ) == []


def test_missing_docker_without_candidate_or_exact_source_fails_closed():
    module = load()
    report = supplement(packages=False)
    report["apt"]["lists_file_count"] = 0
    report["apt"]["source"]["universe"] = False
    failures = module.accept(
        identity(),
        report,
        inventory(missing_docker=True),
        capacity("MISSING"),
    )
    assert "docker_packages" in failures


def test_disabled_successful_firstboot_allows_zero_monotonic_timestamp():
    module = load()
    report = supplement()
    report["armbian_firstrun"]["exec_main_start_timestamp_monotonic"] = "0"
    assert "firstboot" not in module.accept(
        identity(),
        report,
        inventory(),
        capacity(),
    )


def test_firstboot_must_be_disabled_after_success():
    module = load()
    report = supplement()
    report["armbian_firstrun"]["unit_file_state"] = "enabled"
    assert "firstboot" in module.accept(
        identity(),
        report,
        inventory(),
        capacity(),
    )


def test_unpaired_ssh_host_keys_fail_closed():
    module = load()
    report = identity()
    report["ssh_host_keys"][1]["name"] = "ssh_host_rsa_key.pub"
    assert "ssh_host_keys" in module.accept(
        report,
        supplement(),
        inventory(),
        capacity(),
    )


def test_product_and_authorization_residue_fail_closed():
    module = load()
    assert "product_state" in module.accept(
        identity(),
        supplement(),
        inventory(product=True),
        capacity(),
    )
    assert "product_residue" in module.accept(
        identity(),
        supplement(residue=True),
        inventory(),
        capacity(),
    )


def test_exact_armbian_drift_fails_closed():
    module = load()
    report = identity()
    report["armbian_release"]["VERSION"] = "99.0"
    assert "armbian:VERSION" in module.accept(
        report,
        supplement(),
        inventory(),
        capacity(),
    )


def test_wrong_confirmation_stops_before_evidence_root(tmp_path):
    module = load()
    args = Namespace(
        confirm="NO",
        expected_source_head="a" * 40,
        expected_artifact_source_head="b" * 40,
        evidence_root=tmp_path / "private",
        target="root@192.0.2.10",
    )
    with pytest.raises(
        module.StopExecution,
        match="readonly_confirmation_invalid",
    ):
        module.execute(args)
    assert not args.evidence_root.exists()


def test_execute_keeps_private_evidence_and_never_authorizes_f3(
    tmp_path,
    monkeypatch,
):
    module = load()
    monkeypatch.setattr(
        module,
        "validate_source",
        lambda *args: {"clean": True},
    )
    monkeypatch.setattr(
        module,
        "ssh_stream",
        lambda target, command, source, timeout: (
            identity()
            if "--root /" in command
            else supplement()
        ),
    )
    monkeypatch.setattr(
        module,
        "load_module",
        lambda *args: SimpleNamespace(
            collect=lambda target: inventory()
        ),
    )
    monkeypatch.setattr(
        module,
        "capacity_preflight",
        lambda *args: capacity(),
    )
    args = Namespace(
        confirm=module.CONFIRMATION,
        expected_source_head="a" * 40,
        expected_artifact_source_head="b" * 40,
        evidence_root=tmp_path / "private",
        target="root@192.0.2.10",
        timeout_seconds=60,
        artifact_run_id="1",
        artifact_name="artifact",
        artifact_id=2,
        artifact_zip_sha256="f" * 64,
    )
    result = module.execute(args)
    assert result["status"] == "PASS"
    assert result["f3_authorized"] is False
    assert result["authorization_claimed"] is False
    assert result["t1_file_write"] is False
    assert "root@192.0.2.10" not in json.dumps(result)
    assert stat.S_IMODE(
        args.evidence_root.stat().st_mode
    ) == 0o700
    for item in args.evidence_root.iterdir():
        assert stat.S_IMODE(item.stat().st_mode) == 0o600


def test_timeout_bounds_fail_closed():
    module = load()
    for value in (0, -1, 601, True):
        with pytest.raises(module.StopExecution, match="timeout_seconds_invalid"):
            module.validate_timeout(value)


def test_write_private_completes_partial_os_writes(tmp_path, monkeypatch):
    module = load()
    original = module.os.write

    def partial(fd, data):
        length = max(1, len(data) // 3)
        return original(fd, data[:length])

    monkeypatch.setattr(module.os, "write", partial)
    path = tmp_path / "evidence.json"
    document = {"value": "x" * 4096}
    module.write_private(path, document)
    assert json.loads(path.read_text(encoding="utf-8")) == document


def test_component_exception_becomes_structured_private_stop(
    tmp_path,
    monkeypatch,
):
    module = load()
    monkeypatch.setattr(module, "validate_source", lambda *args: {"clean": True})
    monkeypatch.setattr(
        module,
        "ssh_stream",
        lambda target, command, source, timeout: (
            identity() if "--root /" in command else supplement()
        ),
    )
    monkeypatch.setattr(
        module,
        "load_module",
        lambda *args: SimpleNamespace(collect=lambda target: inventory()),
    )

    def fail_capacity(*args):
        raise RuntimeError("simulated")

    monkeypatch.setattr(module, "capacity_preflight", fail_capacity)
    args = Namespace(
        confirm=module.CONFIRMATION,
        expected_source_head="a" * 40,
        expected_artifact_source_head="b" * 40,
        evidence_root=tmp_path / "private",
        target="root@192.0.2.10",
        timeout_seconds=60,
        artifact_run_id="1",
        artifact_name="artifact",
        artifact_id=2,
        artifact_zip_sha256="f" * 64,
    )
    with pytest.raises(
        module.StopExecution,
        match="readonly_preflight_component_failed:RuntimeError",
    ):
        module.execute(args)
    result = json.loads(
        (args.evidence_root / "result.json").read_text(encoding="utf-8")
    )
    assert result["status"] == "STOP"
    assert result["f3_authorized"] is False
    assert "root@192.0.2.10" not in json.dumps(result)


def test_source_has_no_t1_mutation_commands():
    source = EXECUTOR.read_text(encoding="utf-8").lower()
    for marker in (
        "docker rm",
        "docker rmi",
        "docker load",
        "apt-get install",
        "systemctl start",
        "systemctl stop",
        "systemctl enable",
        "systemctl disable",
        "scp ",
        "reboot",
        "shutdown",
    ):
        assert marker not in source
    assert "sudo -n python3 -b -" in source
    assert '"batchmode=no"' in source
    assert '"numberofpasswordprompts=1"' in source
    assert '"preferredauthentications=publickey,password"' in source
    assert '"batchmode=yes"' not in source



def test_production_preflight_requires_managed_ssh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load()
    args = tool.parser().parse_args(
        [
            "--execute",
            "--target",
            "root@t1.local",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--confirm",
            tool.CONFIRMATION,
            "--production-release",
            str(tmp_path / "release.json"),
            "--production-f3-artifact",
            str(tmp_path / "artifact.zip"),
        ]
    )
    monkeypatch.delenv("N3W_T1_SSH_MANAGED_REQUIRED", raising=False)
    with pytest.raises(tool.StopExecution, match="managed_ssh_transport_required"):
        tool.execute_production(args)


def test_production_package_policy_rejects_visible_version_drift() -> None:
    tool = load()
    release = {
        "environment": {
            "packages": {
                "docker.io": "1.0",
                "docker-compose-v2": "2.0",
            }
        }
    }
    supplement = {
        "package_candidates": {
            "docker.io": "1.1",
            "docker-compose-v2": "2.0",
        },
        "apt": {
            "lists_file_count": 10,
            "source": {
                "ubuntu_ports": True,
                "resolute": True,
                "universe": True,
            },
        },
    }
    capacity = {"host_baseline": {"status": "MISSING"}}
    assert tool._production_package_policy_failures(
        release,
        supplement,
        capacity,
    ) == ["approved_package_version"]
