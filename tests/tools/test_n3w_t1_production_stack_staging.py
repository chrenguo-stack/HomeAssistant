from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_production_stack_staging.py"


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

    source.write_text("drift\n", encoding="utf-8")
    with pytest.raises(tool.StagingError, match="payload_source_sha_drift"):
        tool._payload_report(tmp_path)


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
