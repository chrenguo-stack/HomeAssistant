from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_certificate_lifecycle.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_certificate_lifecycle",
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


def private(path: Path) -> Path:
    os.chmod(path, 0o600)
    return path


def make_material(
    root: Path,
    *,
    server_name: str = "broker.test",
    server_days: int = 120,
    ca_days: int = 3650,
) -> dict[str, Path]:
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
                "subjectKeyIdentifier=hash",
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
    private(ca_key)
    openssl(
        "req",
        "-new",
        "-x509",
        "-key",
        str(ca_key),
        "-config",
        str(ca_config),
        "-days",
        str(ca_days),
        "-sha256",
        "-out",
        str(ca_cert),
    )
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(server_key))
    private(server_key)
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
        "0x1001",
        "-days",
        str(server_days),
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


def config_for(tool, root: Path, material: dict[str, Path], *, server_name: str = "broker.test"):
    status_dir = root / "status"
    status_dir.mkdir(mode=0o700)
    return tool.LifecycleConfig(
        server_cert=material["server_cert"],
        server_key=material["server_key"],
        ca_cert=material["ca_cert"],
        ca_key=material["ca_key"],
        system_ca=None,
        server_name=server_name,
        status_file=status_dir / "status.json",
        allowed_roots=(root,),
    )


def test_server_state_boundaries() -> None:
    tool = load_tool()
    now = datetime(2026, 9, 29, tzinfo=UTC)

    def info(days: int):
        return tool.CertificateInfo(
            not_before=now - timedelta(days=1),
            not_after=now + timedelta(days=days),
            fingerprint="1" * 64,
            serial="01",
            subject="subject",
            issuer="issuer",
            san_dns=("broker.test",),
            is_ca=False,
            server_auth=True,
        )

    config = tool.LifecycleConfig(
        server_cert=Path("/tmp/server.pem"),
        ca_cert=Path("/tmp/ca.pem"),
        server_name="broker.test",
        status_file=Path("/tmp/status.json"),
        allowed_roots=(Path("/tmp"),),
    )
    assert tool._server_state(info(91), now, config) == "HEALTHY"
    assert tool._server_state(info(90), now, config) == "WARNING"
    assert tool._server_state(info(60), now, config) == "RENEW_DUE"
    assert tool._server_state(info(30), now, config) == "CRITICAL"
    assert tool._server_state(info(0), now, config) == "EXPIRED"


def test_ca_state_boundaries() -> None:
    tool = load_tool()
    now = datetime(2026, 9, 29, tzinfo=UTC)

    def info(days: int):
        return tool.CertificateInfo(
            not_before=now - timedelta(days=1),
            not_after=now + timedelta(days=days),
            fingerprint="2" * 64,
            serial="02",
            subject="subject",
            issuer="issuer",
            san_dns=(),
            is_ca=True,
            server_auth=False,
        )

    config = tool.LifecycleConfig(
        server_cert=Path("/tmp/server.pem"),
        ca_cert=Path("/tmp/ca.pem"),
        server_name="broker.test",
        status_file=Path("/tmp/status.json"),
        allowed_roots=(Path("/tmp"),),
    )
    assert tool._ca_state(info(731), now, config) == "HEALTHY"
    assert tool._ca_state(info(730), now, config) == "WARNING"
    assert tool._ca_state(info(365), now, config) == "CRITICAL"
    assert tool._ca_state(info(0), now, config) == "EXPIRED"


def test_audit_never_requires_private_keys(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path)
    status_dir = tmp_path / "status"
    status_dir.mkdir(mode=0o700)
    config = tool.LifecycleConfig(
        server_cert=material["server_cert"],
        ca_cert=material["ca_cert"],
        server_name="broker.test",
        status_file=status_dir / "status.json",
        allowed_roots=(tmp_path,),
    )
    document, code = tool.audit(config)
    assert code == 0
    assert document["server_state"] == "HEALTHY"
    assert document["ca_state"] == "HEALTHY"
    assert document["renewal_attempted"] is False


def test_inspect_rejects_hostname_mismatch(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_name="broker.test")
    config = config_for(tool, tmp_path, material, server_name="other.test")
    with pytest.raises(tool.LifecycleError, match="server_certificate_san_mismatch"):
        tool.audit(config)


def test_private_key_permission_guard(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    os.chmod(material["ca_key"], 0o644)
    config = config_for(tool, tmp_path, material)
    with pytest.raises(tool.LifecycleError, match="private_key_permissions_unsafe"):
        tool.auto_renew(config)


def test_symlinked_material_is_rejected(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path)
    link = tmp_path / "server-link.pem"
    link.symlink_to(material["server_cert"])
    config = config_for(tool, tmp_path, material)
    config = tool.LifecycleConfig(
        server_cert=link,
        server_key=config.server_key,
        ca_cert=config.ca_cert,
        ca_key=config.ca_key,
        server_name=config.server_name,
        status_file=config.status_file,
        allowed_roots=config.allowed_roots,
    )
    with pytest.raises(tool.LifecycleError, match="path_contains_symlink"):
        tool.audit(config)


def test_healthy_auto_renew_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=120)
    config = config_for(tool, tmp_path, material)
    before = material["server_cert"].read_bytes()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("mutation must not run")

    monkeypatch.setattr(tool, "_generate_candidate", forbidden)
    monkeypatch.setattr(tool, "_restart_activation", forbidden)
    document, code = tool.auto_renew(config)
    assert code == 0
    assert document["server_state"] == "HEALTHY"
    assert document["renewal_attempted"] is False
    assert material["server_cert"].read_bytes() == before


def test_warning_auto_renew_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=75)
    config = config_for(tool, tmp_path, material)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("mutation must not run")

    monkeypatch.setattr(tool, "_restart_activation", forbidden)
    document, code = tool.auto_renew(config)
    assert code == 0
    assert document["server_state"] == "WARNING"
    assert document["result"] == "monitoring_warning"
    assert document["renewal_attempted"] is False


def test_ca_remaining_lifetime_blocks_server_renewal(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(
        tmp_path,
        server_days=20,
        ca_days=850,
    )
    config = config_for(tool, tmp_path, material)
    before = material["server_cert"].read_bytes()
    document, code = tool.auto_renew(config)
    assert code == 2
    assert document["ca_state"] == "CA_ROLLOVER_REQUIRED"
    assert document["result"] == "ca_rollover_required"
    assert document["renewal_attempted"] is False
    assert material["server_cert"].read_bytes() == before


def test_wrong_server_private_key_fails_before_mutation(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    other = tmp_path / "other.key"
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(other))
    private(other)
    config = config_for(tool, tmp_path, material)
    config = tool.LifecycleConfig(
        server_cert=config.server_cert,
        server_key=other,
        ca_cert=config.ca_cert,
        ca_key=config.ca_key,
        server_name=config.server_name,
        status_file=config.status_file,
        allowed_roots=config.allowed_roots,
    )
    with pytest.raises(tool.LifecycleError, match="server_private_key_mismatch"):
        tool.auto_renew(config)


def test_wrong_ca_private_key_fails_before_mutation(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    other = tmp_path / "other-ca.key"
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(other))
    private(other)
    config = config_for(tool, tmp_path, material)
    config = tool.LifecycleConfig(
        server_cert=config.server_cert,
        server_key=config.server_key,
        ca_cert=config.ca_cert,
        ca_key=other,
        server_name=config.server_name,
        status_file=config.status_file,
        allowed_roots=config.allowed_roots,
    )
    with pytest.raises(tool.LifecycleError, match="ca_private_key_mismatch"):
        tool.auto_renew(config)


def test_successful_renewal_reuses_key_and_restarts_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    config = config_for(tool, tmp_path, material)
    old = tool._certificate_info(material["server_cert"])
    restarts: list[str] = []

    monkeypatch.setattr(tool, "_unit_is_active", lambda _unit: True)
    monkeypatch.setattr(
        tool,
        "_probe_unverified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )
    monkeypatch.setattr(
        tool,
        "_probe_verified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )
    monkeypatch.setattr(
        tool,
        "_restart_activation",
        lambda unit: restarts.append(unit),
    )

    document, code = tool.auto_renew(config)
    new = tool._certificate_info(material["server_cert"])
    assert code == 0
    assert document["result"] == "renewed"
    assert document["renewal_attempted"] is True
    assert old.fingerprint != new.fingerprint
    assert tool._keys_match(material["server_cert"], material["server_key"])
    assert restarts == [tool.EXPECTED_ACTIVATION_UNIT]
    assert new.server_auth is True
    assert new.is_ca is False
    assert new.san_dns == ("broker.test",)


def test_postrenew_failure_restores_old_certificate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    config = config_for(tool, tmp_path, material)
    old_bytes = material["server_cert"].read_bytes()
    old_fingerprint = tool._certificate_info(material["server_cert"]).fingerprint
    verified_calls = 0
    restarts: list[str] = []

    monkeypatch.setattr(tool, "_unit_is_active", lambda _unit: True)
    monkeypatch.setattr(
        tool,
        "_probe_unverified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )

    def probe_verified(*_args, **_kwargs):
        nonlocal verified_calls
        verified_calls += 1
        if verified_calls == 2:
            raise tool.LifecycleError("synthetic_postrenew_failure")
        return tool._certificate_info(config.server_cert).fingerprint

    monkeypatch.setattr(tool, "_probe_verified", probe_verified)
    monkeypatch.setattr(
        tool,
        "_restart_activation",
        lambda unit: restarts.append(unit),
    )

    document, code = tool.auto_renew(config)
    assert code == 2
    assert document["result"] == "renewal_failed_rolled_back"
    assert document["rollback_attempted"] is True
    assert material["server_cert"].read_bytes() == old_bytes
    assert tool._certificate_info(material["server_cert"]).fingerprint == old_fingerprint
    assert len(restarts) == 2


def test_rollback_restart_failure_stays_unproven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    config = config_for(tool, tmp_path, material)
    restart_count = 0
    verified_calls = 0

    monkeypatch.setattr(tool, "_unit_is_active", lambda _unit: True)
    monkeypatch.setattr(
        tool,
        "_probe_unverified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )

    def probe_verified(*_args, **_kwargs):
        nonlocal verified_calls
        verified_calls += 1
        if verified_calls == 2:
            raise tool.LifecycleError("synthetic_postrenew_failure")
        return tool._certificate_info(config.server_cert).fingerprint

    def restart(_unit: str):
        nonlocal restart_count
        restart_count += 1
        if restart_count == 2:
            raise tool.LifecycleError("synthetic_rollback_restart_failure")

    monkeypatch.setattr(tool, "_probe_verified", probe_verified)
    monkeypatch.setattr(tool, "_restart_activation", restart)

    document, code = tool.auto_renew(config)
    assert code == 3
    assert document["result"] == "rollback_unproven"
    assert document["rollback_attempted"] is True
    assert any(
        path.name.startswith(".n3w-certificate-lifecycle.")
        for path in tmp_path.iterdir()
        if path.is_dir()
    )


def test_generated_candidate_does_not_create_serial_side_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    config = config_for(tool, tmp_path, material)

    monkeypatch.setattr(tool, "_unit_is_active", lambda _unit: True)
    monkeypatch.setattr(
        tool,
        "_probe_unverified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )
    monkeypatch.setattr(
        tool,
        "_probe_verified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )
    monkeypatch.setattr(tool, "_restart_activation", lambda _unit: None)

    document, code = tool.auto_renew(config)
    assert code == 0
    assert document["result"] == "renewed"
    assert not list(tmp_path.glob("*.srl"))


def test_status_document_contains_no_private_paths_or_pem(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path)
    config = config_for(tool, tmp_path, material)
    document, _ = tool.audit(config)
    tool._atomic_write_status(config.status_file, document)
    raw = config.status_file.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert "BEGIN CERTIFICATE" not in raw
    assert "PRIVATE KEY" not in raw
    assert str(tmp_path) not in raw
    assert parsed["server_sha256_fingerprint"]
    assert parsed["ca_sha256_fingerprint"]
    assert stat.S_IMODE(config.status_file.stat().st_mode) == 0o600


def test_failure_status_is_reason_code_only(tmp_path: Path) -> None:
    tool = load_tool()
    status_dir = tmp_path / "status"
    status_dir.mkdir(mode=0o700)
    path = status_dir / "status.json"
    tool._write_failure_status(
        path,
        now=datetime(2026, 9, 29, tzinfo=UTC),
        code="certificate_invalid",
    )
    raw = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in raw
    assert json.loads(raw)["result"] == "certificate_invalid"


def test_system_ca_is_monitor_only(tmp_path: Path) -> None:
    tool = load_tool()
    material = make_material(tmp_path)
    system_root = tmp_path / "system"
    system_root.mkdir()
    system_material = make_material(system_root, server_name="unused.test")
    config = config_for(tool, tmp_path, material)
    config = tool.LifecycleConfig(
        server_cert=config.server_cert,
        server_key=config.server_key,
        ca_cert=config.ca_cert,
        ca_key=config.ca_key,
        system_ca=system_material["ca_cert"],
        server_name=config.server_name,
        status_file=config.status_file,
        allowed_roots=config.allowed_roots,
    )
    document, code = tool.audit(config)
    assert code == 0
    assert document["system_ca_state"] == "HEALTHY"
    assert document["system_ca_sha256_fingerprint"]


def test_systemd_timer_and_service_contract() -> None:
    service = (
        ROOT
        / "infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.service"
    ).read_text(encoding="utf-8")
    timer = (
        ROOT
        / "infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer"
    ).read_text(encoding="utf-8")
    installer = (
        ROOT / "infra/n3w-t1/install-systemd-persistence.sh"
    ).read_text(encoding="utf-8")

    assert "Type=oneshot" in service
    assert (
        "After=docker.service n3wfc4-broker-ingress-guard.service "
        "n3wfc4-broker-activation.service"
        in service
    )
    assert "auto-renew" in service
    assert "n3wfc4-broker-activation.service" in service
    assert "Restart=always" not in service
    assert "OnCalendar=daily" in timer
    assert "RandomizedDelaySec=1h" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
    assert "n3wfc4-broker-certificate-lifecycle.timer" in installer
    assert "enable --now" not in installer
    assert "systemctl start" not in installer
    assert "systemctl restart" not in installer


def test_existing_activation_and_guard_ordering_is_unchanged() -> None:
    activation = (
        ROOT / "infra/n3w-t1/systemd/n3wfc4-broker-activation.service"
    ).read_text(encoding="utf-8")
    guard = (
        ROOT / "infra/n3w-t1/systemd/n3wfc4-broker-ingress-guard.service"
    ).read_text(encoding="utf-8")
    assert "Requires=docker.service n3wfc4-broker-ingress-guard.service" in activation
    assert "After=docker.service n3wfc4-broker-ingress-guard.service" in activation
    assert "ExecStartPre=/usr/bin/systemctl reload n3wfc4-broker-ingress-guard.service" in activation
    assert "Before=n3wfc4-broker-activation.service" in guard


def test_expired_inspect_uses_no_check_time_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    server_path = tmp_path / "server.pem"
    ca_path = tmp_path / "ca.pem"
    server_path.write_text("placeholder", encoding="utf-8")
    ca_path.write_text("placeholder", encoding="utf-8")
    now = datetime(2026, 9, 29, tzinfo=UTC)
    server = tool.CertificateInfo(
        not_before=now - timedelta(days=100),
        not_after=now - timedelta(days=1),
        fingerprint="3" * 64,
        serial="03",
        subject="server",
        issuer="ca",
        san_dns=("broker.test",),
        is_ca=False,
        server_auth=True,
    )
    ca = tool.CertificateInfo(
        not_before=now - timedelta(days=100),
        not_after=now + timedelta(days=2000),
        fingerprint="4" * 64,
        serial="04",
        subject="ca",
        issuer="ca",
        san_dns=(),
        is_ca=True,
        server_auth=False,
    )
    infos = iter((server, ca))
    calls: list[bool] = []
    monkeypatch.setattr(tool, "_certificate_info", lambda _path: next(infos))
    monkeypatch.setattr(
        tool,
        "_verify_certificate",
        lambda *_args, no_check_time, **_kwargs: calls.append(no_check_time),
    )
    status_dir = tmp_path / "status"
    status_dir.mkdir(mode=0o700)
    config = tool.LifecycleConfig(
        server_cert=server_path,
        ca_cert=ca_path,
        server_name="broker.test",
        status_file=status_dir / "status.json",
        allowed_roots=(tmp_path,),
    )
    inspected_server, _, _ = tool._inspect(config, now=now)
    assert inspected_server.not_after < now
    assert calls == [True]


def test_directory_fsync_failure_after_replace_enters_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    material = make_material(tmp_path, server_days=20)
    config = config_for(tool, tmp_path, material)
    old_bytes = material["server_cert"].read_bytes()
    fsync_calls = 0
    restarts: list[str] = []

    monkeypatch.setattr(tool, "_unit_is_active", lambda _unit: True)
    monkeypatch.setattr(
        tool,
        "_probe_unverified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )
    monkeypatch.setattr(
        tool,
        "_probe_verified",
        lambda *_args, **_kwargs: tool._certificate_info(config.server_cert).fingerprint,
    )
    monkeypatch.setattr(
        tool,
        "_restart_activation",
        lambda unit: restarts.append(unit),
    )

    original_fsync = tool._fsync_directory

    def fail_first_directory_fsync(path: Path):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 1:
            raise OSError("synthetic fsync failure")
        return original_fsync(path)

    monkeypatch.setattr(tool, "_fsync_directory", fail_first_directory_fsync)

    document, code = tool.auto_renew(config)
    assert code == 2
    assert document["result"] == "renewal_failed_rolled_back"
    assert document["rollback_attempted"] is True
    assert material["server_cert"].read_bytes() == old_bytes
    assert restarts == [tool.EXPECTED_ACTIVATION_UNIT]
