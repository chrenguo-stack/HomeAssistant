from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_fresh_chain_preparation import (
    ManagerIdentityFreshChainPreparationError,
    discover_fresh_chain_sources,
    prepare_fresh_manager_identity_chain,
    validate_repository_binding,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
REPOSITORY_SHA = "f" * 64
MANAGER_VERSION = "0.4.71"
BRIDGE_NAME = "greenhouse-manager-legacy-review-bridge-20260714T162130Z-a874f12a"
BRIDGE_SHA = "a" * 64
EXECUTION_NAME = "greenhouse-manager-execution-preparation-20260714T160000Z-retired"


def _write(path: Path, value: bytes = b"{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(value)
    path.chmod(0o600)


def _directory(path: Path) -> Path:
    path.mkdir(parents=True, mode=0o700)
    path.chmod(0o700)
    return path


def _fixture(
    tmp_path: Path,
    *,
    duplicate_postactivation: bool = False,
    extra_output_root: bool = False,
    duplicate_bound_preparation: bool = False,
    duplicate_rollback_pair: bool = False,
) -> dict[str, Path]:
    search = _directory(tmp_path / "private-search")

    output = _directory(search / "preparations")
    previous = _directory(output / "greenhouse-manager-migration-preparation-old")
    preparation_document = {
        "schema": "gh.m2.t1-manager-identity-migration-preparation/1",
        "created_at": "2026-07-14T15:00:00Z",
    }
    preparation_bytes = (
        json.dumps(preparation_document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    _write(previous / "manifest.json", preparation_bytes)
    preparation_sha = hashlib.sha256(preparation_bytes).hexdigest()

    execution = _directory(search / "retired-executions" / EXECUTION_NAME)
    rollback_document = {
        "schema": "gh.m2.t1-manager-identity-fresh-rollback/1",
        "manager_only": True,
        "restart_scope": ["greenhouse-manager"],
        "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "preparation_manifest_sha256": preparation_sha,
    }
    rollback_bytes = (
        json.dumps(rollback_document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    rollback_manifest = execution / "fresh-rollback-manifest.json"
    rollback_archive = execution / "fresh-manager-rollback.tar.gz"
    _write(rollback_manifest, rollback_bytes)
    _write(rollback_archive, b"test-archive\n")
    if duplicate_rollback_pair:
        duplicate_execution = _directory(
            search
            / "retired-executions-copy"
            / "greenhouse-manager-execution-preparation-20260714T160000Z-copy"
        )
        _write(duplicate_execution / "fresh-rollback-manifest.json", rollback_bytes)
        _write(duplicate_execution / "fresh-manager-rollback.tar.gz", b"test-archive\n")

    bridge = _directory(search / "operator-decisions" / BRIDGE_NAME)
    bridge_document = {
        "created_at": "2026-07-14T17:00:00Z",
        "bindings": {
            "fresh_rollback_manifest_sha256": hashlib.sha256(rollback_bytes).hexdigest(),
            "fresh_rollback_archive_sha256": hashlib.sha256(b"test-archive\n").hexdigest(),
        },
    }
    _write(
        bridge / "manifest.json",
        (json.dumps(bridge_document, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )

    postactivation = _directory(search / "handoffs" / "greenhouse-ha-postactivation-handoff-current")
    _write(postactivation / "manifest.json", b"postactivation\n")
    if duplicate_postactivation:
        duplicate = _directory(search / "handoffs" / "greenhouse-ha-postactivation-handoff-other")
        _write(duplicate / "manifest.json", b"postactivation-other\n")

    stage = _directory(search / "stages" / "greenhouse-t1-auth-stage-current")
    _write(stage / "stage-manifest.json", b"stage\n")

    if extra_output_root:
        archived_output = _directory(search / "archive" / "preparations")
        archived = _directory(archived_output / "greenhouse-manager-migration-preparation-archived")
        _write(
            archived / "manifest.json",
            (
                b'{"created_at":"2026-07-13T00:00:00Z","schema":'
                b'"gh.m2.t1-manager-identity-migration-preparation/1"}\n'
            ),
        )
    if duplicate_bound_preparation:
        duplicate_output = _directory(search / "duplicate" / "preparations")
        duplicate = _directory(
            duplicate_output / "greenhouse-manager-migration-preparation-duplicate"
        )
        _write(
            duplicate / "manifest.json",
            preparation_bytes,
        )
    return {
        "search": search,
        "bridge": bridge,
        "execution": execution,
        "postactivation": postactivation,
        "stage": stage,
        "output": output,
    }


def _repository_binding_builder(**_kwargs: object) -> dict[str, str]:
    return {
        "repository_sha": REPOSITORY_SHA,
        "manager_version": MANAGER_VERSION,
    }


def _bridge_validator(path: Path) -> dict[str, object]:
    return {
        "verified": True,
        "manifest_sha256": hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
        "expected_retained_topic_sha256": hashlib.sha256(TOPIC.encode()).hexdigest(),
        "future_baseline_waiver_enabled": False,
        "ready_for_fresh_evidence_chain": True,
        "ready_for_production_execution": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }


def _postactivation_validator(path: Path) -> tuple[Path, dict[str, Any]]:
    manifest = path / "manifest.json"
    return manifest, {
        "created_at": "2026-07-14T17:00:00Z",
        "bindings": {"expected_retained_topic_sha256": hashlib.sha256(TOPIC.encode()).hexdigest()},
    }


def _stage_validator(path: Path) -> dict[str, Any]:
    return {
        "created_at": "2026-07-14T17:00:00Z",
        "readiness_binding": {"expected_retained_topic": TOPIC},
    }


def _preparation_validator(path: Path) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }


def _rollback_archive_validator(path: Path) -> dict[str, Any]:
    return json.loads((path.parent / "fresh-rollback-manifest.json").read_text(encoding="utf-8"))


def _common(paths: dict[str, Path]) -> dict[str, object]:
    return {
        "expected_repository_sha": REPOSITORY_SHA,
        "expected_manager_version": MANAGER_VERSION,
        "expected_retained_topic": TOPIC,
        "legacy_review_bridge_name": BRIDGE_NAME,
        "legacy_review_bridge_manifest_sha256": hashlib.sha256(
            (paths["bridge"] / "manifest.json").read_bytes()
        ).hexdigest(),
        "repository_binding_builder": _repository_binding_builder,
        "bridge_validator": _bridge_validator,
        "postactivation_validator": _postactivation_validator,
        "stage_validator": _stage_validator,
        "preparation_validator": _preparation_validator,
        "rollback_archive_validator": _rollback_archive_validator,
    }


def test_discovery_returns_only_redacted_unique_sources(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["status"] == "fresh_chain_sources_discovered"
    assert report["ready_for_fresh_preparation"] is True
    assert len(report["postactivation_candidates"]) == 1
    assert len(report["migration_stage_candidates"]) == 1
    assert report["output_root_candidate_count"] == 1
    assert report["bridge_bound_rollback_pair_location_count"] == 1
    assert report["bridge_bound_rollback_content_identity_count"] == 1
    assert report["bridge_bound_rollback_archive_verified"] is True
    assert report["bridge_bound_preparation_candidate_count"] == 1
    assert report["bridge_bound_output_root_candidate_count"] == 1
    assert report["output_root_selection_rule"] == (
        "bridge_rollback_content_pair_then_embedded_preparation_manifest"
    )
    assert report["historical_execution_package_manifest_used_for_lineage"] is False
    assert report["historical_authorization_or_execution_replay_allowed"] is False
    assert report["authorization_created"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["source_paths_included"] is False
    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized
    assert TOPIC not in serialized


def test_discovery_fails_closed_when_bridge_hash_is_wrong(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    common = _common(paths)
    common["legacy_review_bridge_manifest_sha256"] = BRIDGE_SHA

    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="legacy_review_bridge_not_unique",
    ):
        discover_fresh_chain_sources(paths["search"], **common)


def test_discovery_fails_closed_when_bridge_topic_is_wrong(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    def wrong_topic_bridge(path: Path) -> dict[str, object]:
        report = _bridge_validator(path)
        report["expected_retained_topic_sha256"] = "0" * 64
        return report

    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="legacy_review_bridge_not_unique",
    ):
        discover_fresh_chain_sources(
            paths["search"],
            bridge_validator=wrong_topic_bridge,
            **{key: value for key, value in _common(paths).items() if key != "bridge_validator"},
        )


def test_duplicate_sources_are_reported_but_not_ready(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, duplicate_postactivation=True)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert len(report["postactivation_candidates"]) == 2
    assert report["ready_for_fresh_preparation"] is False


def test_discovery_ignores_unbound_archived_output_root_for_readiness(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, extra_output_root=True)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["output_root_candidate_count"] == 2
    assert report["bridge_bound_output_root_candidate_count"] == 1
    assert report["ready_for_fresh_preparation"] is True


def test_duplicate_rollback_locations_are_one_bound_content_identity(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, duplicate_rollback_pair=True)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["bridge_bound_rollback_pair_location_count"] == 2
    assert report["bridge_bound_rollback_content_identity_count"] == 1
    assert report["bridge_bound_preparation_candidate_count"] == 1
    assert report["ready_for_fresh_preparation"] is True


def test_discovery_is_not_ready_without_exact_bridge_bound_rollback_pair(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    _write(paths["execution"] / "fresh-manager-rollback.tar.gz", b"tampered\n")

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["bridge_bound_rollback_pair_location_count"] == 0
    assert report["bridge_bound_rollback_archive_verified"] is False
    assert report["bridge_bound_output_root_candidate_count"] == 0
    assert report["ready_for_fresh_preparation"] is False


def test_discovery_rejects_invalid_bridge_bound_rollback_archive(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)

    def invalid_archive(_path: Path) -> dict[str, Any]:
        raise ValueError("invalid fixture archive")

    common = _common(paths)
    common["rollback_archive_validator"] = invalid_archive
    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="bridge_bound_rollback_archive_invalid",
    ):
        discover_fresh_chain_sources(paths["search"], **common)


def test_discovery_fails_closed_for_duplicate_bridge_bound_preparation(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, duplicate_bound_preparation=True)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["output_root_candidate_count"] == 2
    assert report["bridge_bound_preparation_candidate_count"] == 2
    assert report["bridge_bound_output_root_candidate_count"] == 2
    assert report["ready_for_fresh_preparation"] is False


def test_preparation_binds_exact_sources_without_authorization(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    calls: list[dict[str, object]] = []

    def prepare(
        postactivation: Path,
        stage: Path,
        output: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        calls.append(
            {
                "postactivation": postactivation,
                "stage": stage,
                "output": output,
                **kwargs,
            }
        )
        return {
            "prepared": True,
            "preparation_name": "greenhouse-manager-migration-preparation-fresh",
            "manifest_sha256": "b" * 64,
            "read_only_live_services": True,
            "current_services_modified": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "ready_for_manager_migration_authorization": True,
            "ready_for_manager_migration_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "legacy_review_bridge_bound": True,
            "future_baseline_waiver_enabled": False,
            "secret_values_included": False,
            "source_paths_included": False,
        }

    report = prepare_fresh_manager_identity_chain(
        paths["search"],
        preparation_builder=prepare,
        **_common(paths),
    )

    assert len(calls) == 1
    assert calls[0]["postactivation"] == paths["postactivation"]
    assert calls[0]["stage"] == paths["stage"]
    assert calls[0]["output"] == paths["output"]
    assert calls[0]["legacy_review_bridge_directory"] == paths["bridge"]
    assert report["status"] == "fresh_chain_preparation_succeeded"
    assert report["legacy_review_bridge_bound"] is True
    assert report["future_baseline_waiver_enabled"] is False
    assert report["authorization_created"] is False
    assert report["authorization_claimed"] is False
    assert report["ready_for_production_execution"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized
    assert TOPIC not in serialized


def test_preparation_selects_unique_bridge_bound_output_root(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, extra_output_root=True)
    selected: list[Path] = []

    def prepare(
        _postactivation: Path,
        _stage: Path,
        output: Path,
        **_kwargs: object,
    ) -> dict[str, object]:
        selected.append(output)
        return {
            "prepared": True,
            "preparation_name": "greenhouse-manager-migration-preparation-fresh",
            "manifest_sha256": "b" * 64,
            "read_only_live_services": True,
            "current_services_modified": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "ready_for_manager_migration_authorization": True,
            "ready_for_manager_migration_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "legacy_review_bridge_bound": True,
            "future_baseline_waiver_enabled": False,
            "secret_values_included": False,
            "source_paths_included": False,
        }

    prepare_fresh_manager_identity_chain(
        paths["search"],
        preparation_builder=prepare,
        **_common(paths),
    )

    assert selected == [paths["output"]]


def test_explicit_output_root_must_be_a_verified_candidate(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    unrelated = _directory(paths["search"] / "unrelated-private-directory")

    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="output_root_invalid",
    ):
        prepare_fresh_manager_identity_chain(
            paths["search"],
            output_root=unrelated,
            preparation_builder=lambda *_args, **_kwargs: {},
            **_common(paths),
        )


def test_explicit_output_root_rejects_symlink_alias(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    alias = paths["search"] / "output-root-alias"
    alias.symlink_to(paths["output"], target_is_directory=True)

    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="output_root_invalid",
    ):
        prepare_fresh_manager_identity_chain(
            paths["search"],
            output_root=alias,
            preparation_builder=lambda *_args, **_kwargs: {},
            **_common(paths),
        )


def test_preparation_requires_explicit_name_for_duplicate_source(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, duplicate_postactivation=True)

    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="postactivation_handoff_not_unique",
    ):
        prepare_fresh_manager_identity_chain(
            paths["search"],
            preparation_builder=lambda *_args, **_kwargs: {},
            **_common(paths),
        )


def test_repository_binding_requires_exact_source_commit_and_version(
    tmp_path: Path,
) -> None:
    repository = _directory(tmp_path / "repository")
    pyproject = repository / "host/greenhouse-manager/pyproject.toml"
    _write(pyproject, b'[project]\nname="greenhouse-manager"\nversion="0.4.71"\n')
    running_module = Path(validate_repository_binding.__code__.co_filename).resolve()
    committed_module = (
        repository / "host/greenhouse-manager/src/greenhouse_manager/"
        "t1_manager_identity_fresh_chain_preparation.py"
    )
    _write(committed_module, running_module.read_bytes())
    for command in (
        ("git", "init", "-q"),
        ("git", "config", "user.name", "Test"),
        ("git", "config", "user.email", "test@example.invalid"),
        ("git", "add", "."),
        ("git", "commit", "-qm", "fixture"),
    ):
        subprocess.run(command, cwd=repository, check=True)
    repository_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert validate_repository_binding(
        expected_repository_sha=repository_sha,
        expected_manager_version=MANAGER_VERSION,
        source_root=repository,
        running_module_path=running_module,
    ) == {
        "repository_sha": repository_sha,
        "manager_version": MANAGER_VERSION,
    }

    with pytest.raises(
        ManagerIdentityFreshChainPreparationError,
        match="source_repository_sha_mismatch",
    ):
        validate_repository_binding(
            expected_repository_sha="0" * 64,
            expected_manager_version=MANAGER_VERSION,
            source_root=repository,
            running_module_path=running_module,
        )
