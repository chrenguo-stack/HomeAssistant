from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_ca_private_key_authority_probe.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_ca_private_key_authority_probe",
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


def make_ca(root: Path, *, stem: str = "ca") -> tuple[Path, Path]:
    key = root / f"{stem}.key"
    cert = root / f"{stem}.pem"
    config = root / f"{stem}.cnf"
    config.write_text(
        "\n".join(
            (
                "[req]",
                "prompt=no",
                "distinguished_name=dn",
                "x509_extensions=ca_ext",
                "[dn]",
                "O=Greenhouse Probe Test",
                f"CN={stem}",
                "[ca_ext]",
                "basicConstraints=critical,CA:TRUE,pathlen:0",
                "keyUsage=critical,keyCertSign,cRLSign",
                "",
            )
        ),
        encoding="utf-8",
    )
    openssl(
        "genpkey",
        "-algorithm",
        "EC",
        "-pkeyopt",
        "ec_paramgen_curve:P-256",
        "-out",
        str(key),
    )
    os.chmod(key, 0o600)
    openssl(
        "req",
        "-new",
        "-x509",
        "-key",
        str(key),
        "-config",
        str(config),
        "-days",
        "3650",
        "-sha256",
        "-out",
        str(cert),
    )
    return cert, key


def broker_inspect(ca_source: Path) -> dict[str, object]:
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
                "Source": str(ca_source),
                "Type": "bind",
                "RW": False,
            }
        ],
    }


def prepare_probe_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    durable = tmp_path / "durable"
    tls = durable / "broker" / "tls"
    tls.mkdir(parents=True)
    cert, key = make_ca(tls)
    return durable, cert, key


def patch_runtime(tool, monkeypatch: pytest.MonkeyPatch, cert: Path, root: Path) -> None:
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        tool,
        "EXPECTED_CA_SHA256_FINGERPRINT",
        tool._certificate_fingerprint(cert),
    )
    monkeypatch.setattr(tool, "_running_broker_container", lambda: "container-id")
    monkeypatch.setattr(
        tool,
        "_broker_inspect",
        lambda _container_id: broker_inspect(cert),
    )
    monkeypatch.setattr(tool, "_active_ca_source", lambda _inspect: cert)
    monkeypatch.setattr(tool, "_search_roots", lambda _ca_source: (root,))


def root_owner_mode(tool, path: Path):
    return (
        (path.stat().st_mode & 0o077) == 0,
        0,
        path.stat().st_gid,
        format(path.stat().st_mode & 0o7777, "04o"),
    )


def test_unique_root_owned_safe_key_is_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    root, cert, key = prepare_probe_tree(tmp_path)
    patch_runtime(tool, monkeypatch, cert, root)
    monkeypatch.setattr(tool, "_mode_safe", lambda path: root_owner_mode(tool, path))

    document = tool.probe(max_files=100, max_depth=8)

    assert document["result"] == "PASS"
    assert document["read_only"] is True
    assert document["t1_mutation"] is False
    assert document["search_root_count"] == 1
    assert document["private_key_candidate_count"] >= 1
    assert document["ca_private_key_match_count"] == 1
    assert document["ca_private_key_safe_permission_match_count"] == 1
    assert document["ca_private_key_root_owned_match_count"] == 1
    assert document["ca_private_key_authority_exact_unique"] is True
    assert document["ca_private_key_match_modes"] == ["0600"]
    assert len(document["ca_private_key_match_path_tokens"]) == 1
    assert str(key) not in json.dumps(document)


def test_duplicate_matching_key_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    root, cert, key = prepare_probe_tree(tmp_path)
    duplicate = root / "backup" / "duplicate.key"
    duplicate.parent.mkdir()
    duplicate.write_bytes(key.read_bytes())
    os.chmod(duplicate, 0o600)
    patch_runtime(tool, monkeypatch, cert, root)
    monkeypatch.setattr(tool, "_mode_safe", lambda path: root_owner_mode(tool, path))

    document = tool.probe(max_files=100, max_depth=8)

    assert document["result"] == "STOP"
    assert document["ca_private_key_match_count"] == 2
    assert document["ca_private_key_authority_exact_unique"] is False
    assert len(document["ca_private_key_match_path_tokens"]) == 2


def test_unsafe_permissions_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    root, cert, key = prepare_probe_tree(tmp_path)
    os.chmod(key, 0o640)
    patch_runtime(tool, monkeypatch, cert, root)
    monkeypatch.setattr(tool, "_mode_safe", lambda path: root_owner_mode(tool, path))

    document = tool.probe(max_files=100, max_depth=8)

    assert document["result"] == "STOP"
    assert document["ca_private_key_match_count"] == 1
    assert document["ca_private_key_safe_permission_match_count"] == 0
    assert document["ca_private_key_authority_exact_unique"] is False


def test_nonmatching_private_key_is_not_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    root, cert, _key = prepare_probe_tree(tmp_path)
    other_dir = root / "other"
    other_dir.mkdir()
    _other_cert, other_key = make_ca(other_dir, stem="other")
    patch_runtime(tool, monkeypatch, cert, root)
    monkeypatch.setattr(tool, "_mode_safe", lambda path: root_owner_mode(tool, path))

    document = tool.probe(max_files=100, max_depth=8)

    assert document["result"] == "PASS"
    assert document["parseable_private_key_count"] >= 2
    assert document["ca_private_key_match_count"] == 1
    assert str(other_key) not in json.dumps(document)


def test_irrelevant_files_are_prefiltered_before_openssl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    root, cert, _key = prepare_probe_tree(tmp_path)
    for index in range(40):
        (root / f"state-{index}.json").write_text(
            '{"value":"not a key"}',
            encoding="utf-8",
        )
    patch_runtime(tool, monkeypatch, cert, root)
    monkeypatch.setattr(tool, "_mode_safe", lambda path: root_owner_mode(tool, path))
    calls: list[Path] = []
    original = tool._private_public_key_der

    def counted(path: Path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(tool, "_private_public_key_der", counted)
    document = tool.probe(max_files=100, max_depth=8)

    assert document["search_file_count"] >= 40
    assert len(calls) == document["private_key_candidate_count"]
    assert len(calls) < document["search_file_count"]


def test_file_limit_fails_closed(tmp_path: Path) -> None:
    tool = load_tool()
    for index in range(3):
        (tmp_path / f"file-{index}").write_text("x", encoding="utf-8")
    with pytest.raises(tool.ProbeError, match="search_file_limit_exceeded"):
        tool._walk_files((tmp_path,), max_files=2, max_depth=2)


def test_active_ca_mount_must_be_read_only(tmp_path: Path) -> None:
    tool = load_tool()
    cert, _key = make_ca(tmp_path)
    inspect = broker_inspect(cert)
    inspect["Mounts"][0]["RW"] = True
    with pytest.raises(tool.ProbeError, match="broker_ca_mount_not_read_only"):
        tool._active_ca_source(inspect)


def test_persistent_search_root_never_becomes_filesystem_root() -> None:
    tool = load_tool()
    with pytest.raises(tool.ProbeError, match="derived_search_root_too_broad"):
        tool._persistent_search_root(Path("/ca.pem"))


def test_search_roots_can_include_private_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    durable, cert, _key = prepare_probe_tree(tmp_path)
    private_root = tmp_path / "private-materialization"
    private_root.mkdir()
    monkeypatch.setattr(
        tool,
        "_persistent_search_root",
        lambda _ca_source: durable,
    )
    monkeypatch.setattr(
        tool,
        "_private_materialization_roots",
        lambda: (private_root,),
    )

    roots = tool._search_roots(cert)

    assert roots == (durable, private_root)


def test_source_has_no_write_or_mutation_commands() -> None:
    source = TOOL.read_text(encoding="utf-8")
    forbidden = (
        "systemctl restart",
        "systemctl start",
        "systemctl stop",
        "docker restart",
        "docker exec",
        "docker compose",
        "os.replace(",
        "write_text(",
        "write_bytes(",
        "unlink(",
        "mkdir(",
    )
    for token in forbidden:
        assert token not in source


def test_main_rejects_invalid_limits_without_probe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "probe",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert tool.main(["--max-files", "0"]) == 2
    document = json.loads(capsys.readouterr().out)
    assert document["result"] == "STOP"
    assert document["reason"] == "max_files_invalid"


def test_active_ca_fingerprint_drift_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    root, cert, _key = prepare_probe_tree(tmp_path)
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(tool, "_running_broker_container", lambda: "container-id")
    monkeypatch.setattr(
        tool,
        "_broker_inspect",
        lambda _container_id: broker_inspect(cert),
    )
    monkeypatch.setattr(tool, "_active_ca_source", lambda _inspect: cert)
    monkeypatch.setattr(tool, "_search_roots", lambda _ca_source: (root,))
    monkeypatch.setattr(
        tool,
        "EXPECTED_CA_SHA256_FINGERPRINT",
        "0" * 64,
    )

    with pytest.raises(
        tool.ProbeError,
        match="active_broker_ca_fingerprint_drift",
    ):
        tool.probe(max_files=100, max_depth=8)
