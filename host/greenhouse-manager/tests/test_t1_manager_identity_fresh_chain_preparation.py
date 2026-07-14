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
    extra_bridge_adjacent_output_root: bool = False,
) -> dict[str, Path]:
    search = _directory(tmp_path / "private-search")
    bridge = _directory(search / "bridges" / BRIDGE_NAME)
    _write(
        bridge / "manifest.json",
        b'{"created_at":"2026-07-14T17:00:00Z"}\n',
    )

    postactivation = _directory(search / "handoffs" / "greenhouse-ha-postactivation-handoff-current")
    _write(postactivation / "manifest.json", b"postactivation\n")
    if duplicate_postactivation:
        duplicate = _directory(search / "handoffs" / "greenhouse-ha-postactivation-handoff-other")
        _write(duplicate / "manifest.json", b"postactivation-other\n")

    stage = _directory(search / "stages" / "greenhouse-t1-auth-stage-current")
    _write(stage / "stage-manifest.json", b"stage\n")

    output = _directory(search / "preparations")
    previous = _directory(output / "greenhouse-manager-migration-preparation-old")
    _write(
        previous / "manifest.json",
        b'{"schema":"gh.m2.t1-manager-identity-migration-preparation/1"}\n',
    )
    if extra_output_root:
        archived_output = _directory(search / "archive" / "preparations")
        archived = _directory(archived_output / "greenhouse-manager-migration-preparation-archived")
        _write(
            archived / "manifest.json",
            b'{"schema":"gh.m2.t1-manager-identity-migration-preparation/1"}\n',
        )
    if extra_bridge_adjacent_output_root:
        adjacent_output = _directory(search / "preparations-other")
        adjacent = _directory(adjacent_output / "greenhouse-manager-migration-preparation-other")
        _write(
            adjacent / "manifest.json",
            b'{"schema":"gh.m2.t1-manager-identity-migration-preparation/1"}\n',
        )
    return {
        "search": search,
        "bridge": bridge,
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
    }


def test_discovery_returns_only_redacted_unique_sources(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["status"] == "fresh_chain_sources_discovered"
    assert report["ready_for_fresh_preparation"] is True
    assert len(report["postactivation_candidates"]) == 1
    assert len(report["migration_stage_candidates"]) == 1
    assert report["output_root_candidate_count"] == 1
    assert report["bridge_adjacent_output_root_candidate_count"] == 1
    assert report["output_root_selection_rule"] == "unique_bridge_workspace_sibling"
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


def test_discovery_ignores_nonadjacent_archived_output_root_for_readiness(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, extra_output_root=True)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["output_root_candidate_count"] == 2
    assert report["bridge_adjacent_output_root_candidate_count"] == 1
    assert report["ready_for_fresh_preparation"] is True


def test_discovery_fails_closed_for_multiple_bridge_adjacent_output_roots(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, extra_bridge_adjacent_output_root=True)

    report = discover_fresh_chain_sources(paths["search"], **_common(paths))

    assert report["output_root_candidate_count"] == 2
    assert report["bridge_adjacent_output_root_candidate_count"] == 2
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


def test_preparation_selects_unique_bridge_adjacent_output_root(tmp_path: Path) -> None:
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
