from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_certificate_lifecycle_deployment_preflight.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_certificate_lifecycle_deployment_preflight",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def openssl(*argv: str) -> None:
    subprocess.run(
        ("openssl", *argv),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def make_material(root: Path, *, server_name: str = "armbian") -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    ca_key = root / "ca.key"
    ca_cert = root / "ca.pem"
    server_key = root / "server.key"
    server_csr = root / "server.csr"
    server_cert = root / "server.pem"
    ca_config = root / "ca.cnf"
    server_ext = root / "server.ext"

    ca_config.write_text(
        "\n".join(
            (
                "[req]",
                "prompt=no",
                "distinguished_name=dn",
                "x509_extensions=ca_ext",
                "[dn]",
                "O=Greenhouse Test",
                "CN=Greenhouse Test CA",
                "[ca_ext]",
                "basicConstraints=critical,CA:TRUE,pathlen:0",
                "keyUsage=critical,keyCertSign,cRLSign",
                "",
            )
        ),
        encoding="utf-8",
    )
    server_ext.write_text(
        "\n".join(
            (
                "[server_ext]",
                "basicConstraints=critical,CA:FALSE",
                "extendedKeyUsage=serverAuth",
                f"subjectAltName=DNS:{server_name}",
                "",
            )
        ),
        encoding="utf-8",
    )
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(ca_key))
    os.chmod(ca_key, 0o600)
    openssl(
        "req",
        "-new",
        "-x509",
        "-key",
        str(ca_key),
        "-config",
        str(ca_config),
        "-days",
        "3650",
        "-sha256",
        "-out",
        str(ca_cert),
    )
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(server_key))
    os.chmod(server_key, 0o600)
    openssl(
        "req",
        "-new",
        "-key",
        str(server_key),
        "-subj",
        f"/O=Greenhouse Test/CN={server_name}",
        "-out",
        str(server_csr),
    )
    openssl(
        "x509",
        "-req",
        "-in",
        str(server_csr),
        "-CA",
        str(ca_cert),
        "-CAkey",
        str(ca_key),
        "-set_serial",
        "0x2001",
        "-days",
        "825",
        "-sha256",
        "-extfile",
        str(server_ext),
        "-extensions",
        "server_ext",
        "-out",
        str(server_cert),
    )
    return {
        "ca_key": ca_key,
        "ca_cert": ca_cert,
        "server_key": server_key,
        "server_cert": server_cert,
    }


def inspect_for(material: dict[str, Path]) -> dict[str, object]:
    return {
        "State": {"Running": True},
        "Config": {
            "Labels": {
                "com.docker.compose.project": "n3wfc4",
                "com.docker.compose.service": "broker",
            }
        },
        "Mounts": [
            {
                "Destination": "/mosquitto/tls/ca.pem",
                "Source": str(material["ca_cert"]),
                "Type": "bind",
                "RW": False,
            },
            {
                "Destination": "/mosquitto/tls/server.pem",
                "Source": str(material["server_cert"]),
                "Type": "bind",
                "RW": False,
            },
            {
                "Destination": "/mosquitto/tls/server.key",
                "Source": str(material["server_key"]),
                "Type": "bind",
                "RW": False,
            },
        ],
    }


def patch_happy_runtime(
    tool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    material: dict[str, Path],
) -> None:
    system = tmp_path / "system"
    system_material = make_material(system, server_name="unused.test")

    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(tool, "_broker_container", lambda: "broker-id")
    monkeypatch.setattr(tool, "_broker_inspect", lambda _cid: inspect_for(material))
    monkeypatch.setattr(tool, "SYSTEM_CA_PATH", system_material["ca_cert"])
    monkeypatch.setattr(
        tool,
        "EXPECTED_CA_FINGERPRINT",
        tool._fingerprint(material["ca_cert"]),
    )
    monkeypatch.setattr(
        tool,
        "EXPECTED_SERVER_FINGERPRINT",
        tool._fingerprint(material["server_cert"]),
    )
    monkeypatch.setattr(
        tool,
        "EXPECTED_SYSTEM_CA_FINGERPRINT",
        tool._fingerprint(system_material["ca_cert"]),
    )
    monkeypatch.setattr(
        tool,
        "_tls_endpoint_fingerprint",
        lambda _ca, _name: tool._fingerprint(material["server_cert"]),
    )
    monkeypatch.setattr(tool, "_search_roots", lambda _ca: (tmp_path,))
    monkeypatch.setattr(
        tool,
        "_key_mode",
        lambda path: (
            True,
            (path.stat().st_mode & 0o077) == 0,
            format(path.stat().st_mode & 0o7777, "04o"),
        ),
    )

    states = {
        ("is-active", tool.EXPECTED_GUARD_UNIT): "active",
        ("is-enabled", tool.EXPECTED_GUARD_UNIT): "enabled",
        ("is-active", tool.EXPECTED_ACTIVATION_UNIT): "active",
        ("is-enabled", tool.EXPECTED_ACTIVATION_UNIT): "enabled",
        ("is-active", tool.LIFECYCLE_TIMER): "inactive",
        ("is-enabled", tool.LIFECYCLE_TIMER): "not-found",
    }
    monkeypatch.setattr(tool, "_systemctl_state", lambda mode, unit: states[(mode, unit)])

    targets = tuple(tmp_path / f"target-{index}" for index, _ in enumerate(tool.DEPLOYMENT_TARGETS))
    monkeypatch.setattr(tool, "DEPLOYMENT_TARGETS", targets)


def test_happy_preflight_is_read_only_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path / "broker")
    patch_happy_runtime(tool, monkeypatch, tmp_path, material)

    document = tool.preflight(max_files=200, max_depth=8)

    assert document["result"] == "PASS"
    assert document["read_only"] is True
    assert document["t1_mutation"] is False
    assert document["certificate_mutation"] is False
    assert document["timer_enablement"] is False
    assert document["server_certificate_key_match"] is True
    assert document["live_tls_verified"] is True
    assert document["ca_private_key_match_count"] == 1
    assert document["ca_private_key_root_owned"] is True
    assert document["ca_private_key_mode_safe"] is True
    assert document["deployment_target_present_count"] == 0


def test_timer_already_enabled_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path / "broker")
    patch_happy_runtime(tool, monkeypatch, tmp_path, material)
    original = tool._systemctl_state

    def state(mode: str, unit: str) -> str:
        if mode == "is-enabled" and unit == tool.LIFECYCLE_TIMER:
            return "enabled"
        return original(mode, unit)

    monkeypatch.setattr(tool, "_systemctl_state", state)
    with pytest.raises(tool.PreflightError, match="lifecycle_timer_already_enabled"):
        tool.preflight(max_files=200, max_depth=8)


def test_existing_deployment_target_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path / "broker")
    patch_happy_runtime(tool, monkeypatch, tmp_path, material)
    target = tool.DEPLOYMENT_TARGETS[0]
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(
        tool.PreflightError,
        match="lifecycle_deployment_target_already_present",
    ):
        tool.preflight(max_files=200, max_depth=8)


def test_ca_fingerprint_drift_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path / "broker")
    patch_happy_runtime(tool, monkeypatch, tmp_path, material)
    monkeypatch.setattr(tool, "EXPECTED_CA_FINGERPRINT", "0" * 64)

    with pytest.raises(tool.PreflightError, match="active_ca_fingerprint_drift"):
        tool.preflight(max_files=200, max_depth=8)


def test_server_key_mismatch_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path / "broker")
    other = make_material(tmp_path / "other")
    material["server_key"] = other["server_key"]
    patch_happy_runtime(tool, monkeypatch, tmp_path, material)

    with pytest.raises(tool.PreflightError, match="server_key_mismatch"):
        tool.preflight(max_files=200, max_depth=8)


def test_duplicate_ca_key_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path / "broker")
    duplicate = tmp_path / "duplicate.key"
    duplicate.write_bytes(material["ca_key"].read_bytes())
    os.chmod(duplicate, 0o600)
    patch_happy_runtime(tool, monkeypatch, tmp_path, material)

    with pytest.raises(tool.PreflightError, match="ca_private_key_not_unique"):
        tool.preflight(max_files=200, max_depth=8)


def test_source_contains_no_live_mutation_primitives() -> None:
    source = TOOL.read_text(encoding="utf-8")
    forbidden = (
        "systemctl restart",
        "systemctl start",
        "systemctl stop",
        "systemctl enable",
        "docker restart",
        "docker exec",
        "docker compose",
        "os.replace(",
        ".write_text(",
        ".write_bytes(",
        ".mkdir(",
        ".unlink(",
        "subprocess.Popen",
    )
    for token in forbidden:
        assert token not in source


def test_invalid_limit_stops_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "preflight",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert tool.main(["--max-files", "0"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "limit_invalid"
