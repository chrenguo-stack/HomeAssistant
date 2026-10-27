from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_production_stack_staging.py"
PAYLOAD_WORKFLOW = ROOT / ".github/workflows/n3w-t1-production-stack-staging-payload-ci.yml"


def load_tool():
    name = "n3w_t1_production_stack_staging"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_frozen_source_hashes_match_repository() -> None:
    tool = load_tool()

    for relative, (_target, _mode, expected_sha) in tool.SOURCE_FILES.items():
        assert tool._sha256_file(ROOT / relative) == expected_sha

    for relative, (_target, _mode, expected_sha) in tool.INSTALL_FILES.items():
        assert tool._sha256_file(ROOT / relative) == expected_sha


def test_listener_count_handles_ipv4_and_ipv6() -> None:
    tool = load_tool()
    output = "\n".join(
        (
            "LISTEN 0 4096 0.0.0.0:8883 0.0.0.0:*",
            "LISTEN 0 4096 [::]:8883 [::]:*",
            "LISTEN 0 4096 127.0.0.1:1883 0.0.0.0:*",
        )
    )

    assert tool._listener_count(output, 8883) == 2
    assert tool._listener_count(output, 1883) == 1
    assert tool._listener_count(output, 8123) == 0


def test_payload_report_requires_exact_sources_and_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    source = tmp_path / "source.txt"
    source.write_text("source\n", encoding="utf-8")
    artifact = tmp_path / "artifact/greenhouse-manager-arm64.tar"
    artifact.parent.mkdir()
    artifact.write_bytes(b"manager-tar")
    (artifact.parent / "homeassistant-arm64.tar").write_bytes(b"ha-tar")
    (artifact.parent / "broker-arm64.tar").write_bytes(b"broker-tar")

    monkeypatch.setattr(
        tool,
        "SOURCE_FILES",
        {
            "source.txt": (
                "/unused",
                0o644,
                tool._sha256_file(source),
            )
        },
    )
    monkeypatch.setattr(
        tool,
        "EXPECTED_MANAGER_TAR_SHA256",
        tool._sha256_file(artifact),
    )

    report = tool._payload_report(tmp_path)
    assert report["source_file_count"] == 1
    assert report["homeassistant_tar_sha256"] == tool._sha256_file(
        artifact.parent / "homeassistant-arm64.tar"
    )
    assert report["broker_tar_sha256"] == tool._sha256_file(
        artifact.parent / "broker-arm64.tar"
    )

    source.write_text("drift\n", encoding="utf-8")
    with pytest.raises(tool.StagingError, match="payload_source_sha_drift"):
        tool._payload_report(tmp_path)



def test_payload_manifest_report_accepts_exact_file_set(tmp_path: Path) -> None:
    tool = load_tool()
    source = tmp_path / "source.txt"
    source.write_text("source\n", encoding="utf-8")
    (tmp_path / "payload-manifest.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "source.txt",
                        "sha256": tool._sha256_file(source),
                        "size": source.stat().st_size,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert tool._payload_manifest_report(tmp_path) == {
        "file_count": 1,
        "exact": True,
    }


def test_payload_manifest_report_rejects_unmanifested_bytecode(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    source = tmp_path / "source.txt"
    source.write_text("source\n", encoding="utf-8")
    (tmp_path / "payload-manifest.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "source.txt",
                        "sha256": tool._sha256_file(source),
                        "size": source.stat().st_size,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pycache = tmp_path / "tools/__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "n3w_t1_production_stack_staging.cpython-312.pyc").write_bytes(
        b"unexpected-bytecode"
    )

    with pytest.raises(
        tool.StagingError,
        match="payload_manifest_file_set_drift:.*unexpected=tools/__pycache__",
    ):
        tool._payload_manifest_report(tmp_path)


def test_payload_workflow_guards_exact_manifest_file_set() -> None:
    source = PAYLOAD_WORKFLOW.read_text(encoding="utf-8")

    assert 'PYTHONDONTWRITEBYTECODE: "1"' in source
    assert "module._payload_manifest_report(root)" in source
    assert 'print("PAYLOAD_MANIFEST_FILE_SET=PASS")' in source

def test_write_new_file_refuses_overwrite(tmp_path: Path) -> None:
    tool = load_tool()
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_text("new", encoding="utf-8")
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        tool._write_new_file(source, target, 0o600)

    assert target.read_text(encoding="utf-8") == "existing"


def test_activation_unit_must_be_inactive_and_disabled() -> None:
    tool = load_tool()

    class FakeRunner:
        def run(self, command, **_kwargs):
            if command[1] == "is-active":
                return "inactive\n"
            return "disabled\n"

    assert tool._unit_stopped_disabled(FakeRunner(), "example.service") == {
        "active": "inactive",
        "enabled": "disabled",
    }


def test_activation_unit_rejects_enabled_state() -> None:
    tool = load_tool()

    class FakeRunner:
        def run(self, command, **_kwargs):
            if command[1] == "is-active":
                return "inactive\n"
            return "enabled\n"

    with pytest.raises(tool.StagingError, match="activation_unit_state_invalid"):
        tool._unit_stopped_disabled(FakeRunner(), "example.service")


def test_apply_rolls_back_after_first_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    manager = tmp_path / "manager"
    manager.mkdir()
    collision = manager / "registration.sqlite3"
    collision.mkdir()
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not-a-directory", encoding="utf-8")

    monkeypatch.setattr(tool, "LEGACY_COLLISION", collision)
    monkeypatch.setattr(tool, "N3W_ROOT", blocked_parent / "n3w")
    monkeypatch.setattr(tool, "_verify_collision_directory", lambda: None)
    monkeypatch.setattr(tool, "_event", lambda *_args: None)
    monkeypatch.setattr(
        tool,
        "preflight",
        lambda _runner, _payload_root: {
            "manager_database": {"sha256": "manager-sha"},
            "secret_bundle": {"aggregate_sha256": "secret-sha"},
        },
    )

    rollback_calls: list[dict[str, str]] = []

    def fake_rollback(
        _runner,
        _payload_root,
        *,
        manager_sha_before: str,
        secret_aggregate_before: str,
    ):
        rollback_calls.append(
            {
                "manager": manager_sha_before,
                "secret": secret_aggregate_before,
            }
        )
        return {"status": "PASS", "errors": []}

    monkeypatch.setattr(tool, "rollback", fake_rollback)

    with pytest.raises(tool.StagingError, match="rollback"):
        tool.apply_staging(object(), tmp_path)

    assert not collision.exists()
    assert rollback_calls == [
        {
            "manager": "manager-sha",
            "secret": "secret-sha",
        }
    ]


def test_rollback_opt_root_preserves_unknown_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    opt_root = tmp_path / "HomeAssistant"
    opt_root.mkdir()
    known = opt_root / "known.txt"
    unknown = opt_root / "unknown.txt"
    known.write_text("known", encoding="utf-8")
    unknown.write_text("unknown", encoding="utf-8")

    monkeypatch.setattr(tool, "OPT_ROOT", opt_root)
    monkeypatch.setattr(
        tool,
        "SOURCE_FILES",
        {
            "known-source": (
                str(known),
                0o644,
                "unused",
            )
        },
    )

    errors: list[str] = []
    tool._rollback_opt_root(errors)

    assert not known.exists()
    assert unknown.exists()
    assert opt_root.exists()
    assert any(
        item.startswith("opt_root_unexpected_or_unremoved:")
        for item in errors
    )


def test_staging_uses_h0h1_24_char_provenance_fingerprint() -> None:
    tool = load_tool()

    assert (
        tool.EXPECTED_SYSTEM_ID_PROVENANCE_FINGERPRINT
        == tool.EXPECTED_SYSTEM_ID_SHA256[:24]
    )
    assert len(tool.EXPECTED_SYSTEM_ID_PROVENANCE_FINGERPRINT) == 24


def test_staging_manager_database_accepts_h0h1_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    manager_db = tmp_path / "manager-state.sqlite3"

    connection = sqlite3.connect(manager_db)
    try:
        connection.executescript(
            """
            CREATE TABLE registrations (id INTEGER);
            CREATE TABLE pairing_sessions (id INTEGER);
            CREATE TABLE registration_events (id INTEGER);
            CREATE TABLE registration_node_history (id INTEGER);
            CREATE TABLE node_id_leases (id INTEGER);
            CREATE TABLE retirement_outbox (id INTEGER);
            CREATE TABLE credential_assignments (id INTEGER);
            CREATE TABLE h0h1_legacy_adoption_provenance (
                schema TEXT NOT NULL,
                classification_result_sha256 TEXT NOT NULL,
                system_id_fingerprint TEXT NOT NULL,
                structured_legacy_manager_state_imported INTEGER NOT NULL,
                anonymous_nodes_reconstructed INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO h0h1_legacy_adoption_provenance
            VALUES (?, ?, ?, 0, 0)
            """,
            (
                "gh.h0h1.legacy-adoption-provenance/1",
                "b" * 64,
                tool.EXPECTED_SYSTEM_ID_PROVENANCE_FINGERPRINT,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(tool, "MANAGER_DB", manager_db)
    monkeypatch.setattr(tool, "_require_regular", lambda *_args, **_kwargs: None)

    report = tool._manager_database_report()

    assert report["quick_check"] == "ok"
    assert report["business_rows"] == 0
    assert report["provenance_rows"] == 1


def test_staging_manager_database_rejects_full_sha_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    manager_db = tmp_path / "manager-state.sqlite3"

    connection = sqlite3.connect(manager_db)
    try:
        connection.executescript(
            """
            CREATE TABLE registrations (id INTEGER);
            CREATE TABLE pairing_sessions (id INTEGER);
            CREATE TABLE registration_events (id INTEGER);
            CREATE TABLE registration_node_history (id INTEGER);
            CREATE TABLE node_id_leases (id INTEGER);
            CREATE TABLE retirement_outbox (id INTEGER);
            CREATE TABLE credential_assignments (id INTEGER);
            CREATE TABLE h0h1_legacy_adoption_provenance (
                schema TEXT NOT NULL,
                classification_result_sha256 TEXT NOT NULL,
                system_id_fingerprint TEXT NOT NULL,
                structured_legacy_manager_state_imported INTEGER NOT NULL,
                anonymous_nodes_reconstructed INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO h0h1_legacy_adoption_provenance
            VALUES (?, ?, ?, 0, 0)
            """,
            (
                "gh.h0h1.legacy-adoption-provenance/1",
                "b" * 64,
                tool.EXPECTED_SYSTEM_ID_SHA256,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(tool, "MANAGER_DB", manager_db)
    monkeypatch.setattr(tool, "_require_regular", lambda *_args, **_kwargs: None)

    with pytest.raises(tool.StagingError, match="manager_database_provenance_drift"):
        tool._manager_database_report()


def test_image_report_accepts_classic_config_digest() -> None:
    tool = load_tool()

    class FakeRunner:
        def run(self, _command, **_kwargs):
            return json.dumps(
                {
                    "Id": tool.EXPECTED_MANAGER_IMAGE_CONFIG_DIGEST,
                    "Os": "linux",
                    "Architecture": "arm64",
                }
            )

    report = tool._image_report(
        FakeRunner(),
        tool.EXPECTED_MANAGER_IMAGE,
        expected_config_digest=tool.EXPECTED_MANAGER_IMAGE_CONFIG_DIGEST,
        expected_target_digest=tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
    )

    assert report["identity_mode"] == "classic_config_digest"
    assert report["platform"] == "linux/arm64"


def test_image_report_accepts_containerd_target_digest() -> None:
    tool = load_tool()

    class FakeRunner:
        def run(self, _command, **_kwargs):
            return json.dumps(
                {
                    "Id": tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
                    "Os": "linux",
                    "Architecture": "arm64",
                    "Descriptor": {
                        "digest": tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
                    },
                }
            )

    report = tool._image_report(
        FakeRunner(),
        tool.EXPECTED_MANAGER_IMAGE,
        expected_config_digest=tool.EXPECTED_MANAGER_IMAGE_CONFIG_DIGEST,
        expected_target_digest=tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
    )

    assert report["identity_mode"] == "containerd_target_digest"
    assert report["target_digest"] == tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST


def test_image_report_rejects_unknown_identity() -> None:
    tool = load_tool()

    class FakeRunner:
        def run(self, _command, **_kwargs):
            return json.dumps(
                {
                    "Id": "sha256:" + ("c" * 64),
                    "Os": "linux",
                    "Architecture": "arm64",
                }
            )

    with pytest.raises(tool.StagingError, match="image_binding_drift"):
        tool._image_report(
            FakeRunner(),
            tool.EXPECTED_MANAGER_IMAGE,
            expected_config_digest=tool.EXPECTED_MANAGER_IMAGE_CONFIG_DIGEST,
            expected_target_digest=tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
        )


def test_image_report_rejects_descriptor_drift() -> None:
    tool = load_tool()

    class FakeRunner:
        def run(self, _command, **_kwargs):
            return json.dumps(
                {
                    "Id": tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
                    "Os": "linux",
                    "Architecture": "arm64",
                    "Descriptor": {
                        "digest": "sha256:" + ("d" * 64),
                    },
                }
            )

    with pytest.raises(tool.StagingError, match="image_target_digest_drift"):
        tool._image_report(
            FakeRunner(),
            tool.EXPECTED_MANAGER_IMAGE,
            expected_config_digest=tool.EXPECTED_MANAGER_IMAGE_CONFIG_DIGEST,
            expected_target_digest=tool.EXPECTED_MANAGER_IMAGE_TARGET_DIGEST,
        )


def test_staging_authorization_id_rotated_after_consumed_attempt() -> None:
    tool = load_tool()

    assert (
        tool.AUTHORIZATION_ID
        == "N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03"
    )


def test_payload_report_rejects_missing_external_image_tar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    source = tmp_path / "source.txt"
    source.write_text("source\n", encoding="utf-8")
    artifact = tmp_path / "artifact/greenhouse-manager-arm64.tar"
    artifact.parent.mkdir()
    artifact.write_bytes(b"manager-tar")
    (artifact.parent / "homeassistant-arm64.tar").write_bytes(b"ha-tar")

    monkeypatch.setattr(
        tool,
        "SOURCE_FILES",
        {
            "source.txt": (
                "/unused",
                0o644,
                tool._sha256_file(source),
            )
        },
    )
    monkeypatch.setattr(
        tool,
        "EXPECTED_MANAGER_TAR_SHA256",
        tool._sha256_file(artifact),
    )

    with pytest.raises(tool.StagingError, match="broker_artifact_missing"):
        tool._payload_report(tmp_path)


def test_staging_apply_has_no_live_registry_pull() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '("docker", "pull"' not in source
    assert '"production_image_load"' in source
    assert "homeassistant-arm64.tar" in source
    assert "broker-arm64.tar" in source


def test_listener_inventory_includes_registration_bootstrap_port() -> None:
    tool = load_tool()
    assert 47110 in tool.PORTS_TCP
    assert 47112 in tool.PORTS_TCP
    assert 47111 in tool.PORTS_UDP


def _registration_guard_runner(tool, *, registration_active: str = "active"):
    broker_anchor = "-A INPUT -j N3WFC4-BROKER-INGRESS"
    registration_anchors = [
        "-A INPUT -p tcp -m tcp --dport 47110 "
        "-m comment --comment n3wfc4-registration-ingress-v1 "
        "-j N3WFC4-REGISTRATION-INGRESS",
        "-A INPUT -p udp -m udp --dport 47111 "
        "-m comment --comment n3wfc4-registration-ingress-v1 "
        "-j N3WFC4-REGISTRATION-INGRESS",
        "-A INPUT -p tcp -m tcp --dport 47112 "
        "-m comment --comment n3wfc4-registration-ingress-v1 "
        "-j N3WFC4-REGISTRATION-INGRESS",
    ]

    class FakeRunner:
        def run(self, command, **_kwargs):
            if command[:2] == ("systemctl", "is-active"):
                if command[2] == tool.REGISTRATION_GUARD_UNIT:
                    return registration_active + "\n"
                return "active\n"
            if command[:2] == ("systemctl", "is-enabled"):
                return "enabled\n"
            if command == ("iptables", "-S", "INPUT"):
                return "\n".join([broker_anchor, *registration_anchors]) + "\n"
            if command == ("iptables", "-S", "DOCKER-USER"):
                return "-A DOCKER-USER -j N3WFC4-BROKER-INGRESS\n"
            if command == ("iptables", "-S", "N3WFC4-BROKER-INGRESS"):
                return "-A N3WFC4-BROKER-INGRESS -j DROP\n"
            if command == ("iptables-save", "-t", "filter"):
                return (
                    "*filter\n"
                    ":INPUT ACCEPT [0:0]\n"
                    ":DOCKER-USER - [0:0]\n"
                    ":N3WFC4-BROKER-INGRESS - [0:0]\n"
                    ":N3WFC4-REGISTRATION-INGRESS - [0:0]\n"
                    + broker_anchor
                    + "\n"
                    + "\n".join(registration_anchors)
                    + "\n"
                    "-A DOCKER-USER -j N3WFC4-BROKER-INGRESS\n"
                    "-A N3WFC4-BROKER-INGRESS -j DROP\n"
                    "-A N3WFC4-REGISTRATION-INGRESS -i eth0 "
                    "-s 192.0.2.0/24 -m comment --comment "
                    "n3wfc4-registration-ingress-v1 -j RETURN\n"
                    "-A N3WFC4-REGISTRATION-INGRESS -m comment --comment "
                    "n3wfc4-registration-ingress-v1 -j DROP\n"
                    "COMMIT\n"
                )
            if command == ("iptables", "-S", tool.REGISTRATION_CHAIN):
                return (
                    "-A N3WFC4-REGISTRATION-INGRESS -i eth0 "
                    "-s 192.0.2.0/24 -m comment --comment "
                    "n3wfc4-registration-ingress-v1 -j RETURN\n"
                    "-A N3WFC4-REGISTRATION-INGRESS -m comment --comment "
                    "n3wfc4-registration-ingress-v1 -j DROP\n"
                )
            raise AssertionError(command)

    return FakeRunner()


def test_guard_contract_proves_registration_guard_without_exposing_subnet() -> None:
    tool = load_tool()
    report = tool._guard_contract(_registration_guard_runner(tool))
    assert report == {
        "active": True,
        "enabled": True,
        "exact": True,
        "registration": {
            "active": True,
            "enabled": True,
            "exact": True,
        },
    }
    assert "192.0.2.0/24" not in json.dumps(report)


def test_guard_contract_rejects_inactive_registration_guard() -> None:
    tool = load_tool()
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_state_drift",
    ):
        tool._guard_contract(
            _registration_guard_runner(
                tool,
                registration_active="inactive",
            )
        )


def test_guard_contract_rejects_registration_anchor_order_drift() -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def drifted(command, **kwargs):
        result = original(command, **kwargs)
        if command == ("iptables", "-S", "INPUT"):
            lines = result.splitlines()
            lines[1], lines[2] = lines[2], lines[1]
            return "\n".join(lines) + "\n"
        return result

    runner.run = drifted
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_input_anchor_drift",
    ):
        tool._guard_contract(runner)


def test_guard_contract_rejects_invalid_registration_allow_subnet() -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def invalid_subnet(command, **kwargs):
        result = original(command, **kwargs)
        if command == ("iptables", "-S", tool.REGISTRATION_CHAIN):
            return result.replace("192.0.2.0/24", "999.999.999.999/99")
        return result

    runner.run = invalid_subnet
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_allow_rule_drift",
    ):
        tool._guard_contract(runner)


def test_guard_contract_accepts_quoted_registration_comment_tokens() -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def quoted(command, **kwargs):
        result = original(command, **kwargs)
        if command in {
            ("iptables", "-S", "INPUT"),
            ("iptables", "-S", tool.REGISTRATION_CHAIN),
        }:
            return result.replace(
                "n3wfc4-registration-ingress-v1",
                '"n3wfc4-registration-ingress-v1"',
            )
        return result

    runner.run = quoted
    report = tool._guard_contract(runner)
    assert report["registration"]["exact"] is True


def test_guard_contract_rejects_extra_uncommented_input_jump() -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def extra_input_jump(command, **kwargs):
        result = original(command, **kwargs)
        if command == ("iptables-save", "-t", "filter"):
            return result.replace(
                "COMMIT\n",
                "-A INPUT -j N3WFC4-REGISTRATION-INGRESS\nCOMMIT\n",
            )
        return result

    runner.run = extra_input_jump
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_foreign_reference",
    ):
        tool._guard_contract(runner)


def test_guard_contract_rejects_foreign_chain_jump() -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def foreign_chain_jump(command, **kwargs):
        result = original(command, **kwargs)
        if command == ("iptables-save", "-t", "filter"):
            return result.replace(
                "COMMIT\n",
                ":FOREIGN - [0:0]\n"
                "-A FOREIGN -j N3WFC4-REGISTRATION-INGRESS\n"
                "COMMIT\n",
            )
        return result

    runner.run = foreign_chain_jump
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_foreign_reference",
    ):
        tool._guard_contract(runner)


@pytest.mark.parametrize("goto_operator", ("-g", "--goto"))
def test_guard_contract_rejects_extra_input_goto(
    goto_operator: str,
) -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def extra_input_goto(command, **kwargs):
        result = original(command, **kwargs)
        if command == ("iptables-save", "-t", "filter"):
            return result.replace(
                "COMMIT\n",
                f"-A INPUT {goto_operator} "
                "N3WFC4-REGISTRATION-INGRESS\nCOMMIT\n",
            )
        return result

    runner.run = extra_input_goto
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_foreign_reference",
    ):
        tool._guard_contract(runner)


@pytest.mark.parametrize("goto_operator", ("-g", "--goto"))
def test_guard_contract_rejects_foreign_chain_goto(
    goto_operator: str,
) -> None:
    tool = load_tool()
    runner = _registration_guard_runner(tool)
    original = runner.run

    def foreign_chain_goto(command, **kwargs):
        result = original(command, **kwargs)
        if command == ("iptables-save", "-t", "filter"):
            return result.replace(
                "COMMIT\n",
                ":FOREIGN - [0:0]\n"
                f"-A FOREIGN {goto_operator} "
                "N3WFC4-REGISTRATION-INGRESS\n"
                "COMMIT\n",
            )
        return result

    runner.run = foreign_chain_goto
    with pytest.raises(
        tool.StagingError,
        match="registration_guard_foreign_reference",
    ):
        tool._guard_contract(runner)
