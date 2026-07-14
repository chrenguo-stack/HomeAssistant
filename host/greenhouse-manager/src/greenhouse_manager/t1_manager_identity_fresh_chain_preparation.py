from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_legacy_review_bridge import (
    validate_manager_identity_legacy_review_bridge,
)
from .t1_manager_identity_migration_preparation import (
    _postactivation_handoff,
    prepare_manager_identity_migration,
)
from .t1_migration_stage import verify_migration_stage

SCHEMA = "gh.m2.t1-manager-identity-fresh-chain-preparation/1"
POSTACTIVATION_PREFIX = "greenhouse-ha-postactivation-handoff-"
STAGE_PREFIX = "greenhouse-t1-auth-stage-"
PREPARATION_PREFIX = "greenhouse-manager-migration-preparation-"
BRIDGE_PREFIX = "greenhouse-manager-legacy-review-bridge-"
PREPARATION_SCHEMA = "gh.m2.t1-manager-identity-migration-preparation/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SKIP_DIRECTORIES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}

PostactivationValidator = Callable[[Path], tuple[Path, dict[str, Any]]]
StageValidator = Callable[[Path], dict[str, Any]]
BridgeValidator = Callable[[Path], dict[str, object]]
PreparationBuilder = Callable[..., dict[str, object]]
RepositoryBindingBuilder = Callable[..., dict[str, str]]


class ManagerIdentityFreshChainPreparationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Candidate:
    path: Path
    name: str
    name_fingerprint: str
    manifest_sha256: str
    created_at: str | None

    def public(self) -> dict[str, object]:
        return {
            "name": self.name,
            "name_fingerprint": self.name_fingerprint,
            "manifest_sha256": self.manifest_sha256,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class Inventory:
    bridge: Candidate
    postactivation: tuple[Candidate, ...]
    stages: tuple[Candidate, ...]
    output_roots: tuple[Path, ...]


def _fail(code: str) -> None:
    raise ManagerIdentityFreshChainPreparationError(code)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))[:16]


def _private_directory(path: Path) -> bool:
    try:
        return path.is_dir() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0
    except OSError:
        return False


def _private_file(path: Path) -> bool:
    try:
        return path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o777 == 0o600
    except OSError:
        return False


def _load_private_json(path: Path) -> dict[str, Any] | None:
    if not _private_file(path):
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def _created_at(document: Mapping[str, Any]) -> str | None:
    value = document.get("created_at")
    return value if isinstance(value, str) and value else None


def _candidate(path: Path, manifest_path: Path, manifest: Mapping[str, Any]) -> Candidate:
    return Candidate(
        path=path,
        name=path.name,
        name_fingerprint=_fingerprint(path.name),
        manifest_sha256=_sha(manifest_path),
        created_at=_created_at(manifest),
    )


def _walk_candidate_directories(search_root: Path, bridge_name: str) -> dict[str, list[Path]]:
    if not search_root.is_dir() or search_root.is_symlink():
        _fail("search_root_invalid")
    discovered = {
        "bridge": [],
        "postactivation": [],
        "stage": [],
        "preparation": [],
    }
    count = 0
    for current, raw_directories, _files in os.walk(search_root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept: list[str] = []
        for name in raw_directories:
            path = current_path / name
            if name in _SKIP_DIRECTORIES or path.is_symlink():
                continue
            category: str | None = None
            if name == bridge_name:
                category = "bridge"
            elif name.startswith(POSTACTIVATION_PREFIX):
                category = "postactivation"
            elif name.startswith(STAGE_PREFIX):
                category = "stage"
            elif name.startswith(PREPARATION_PREFIX):
                category = "preparation"
            if category is None:
                kept.append(name)
                continue
            discovered[category].append(path)
            count += 1
            if count > 512:
                _fail("candidate_inventory_too_large")
        raw_directories[:] = kept
    return discovered


def _validated_bridge(
    candidates: Sequence[Path],
    *,
    expected_manifest_sha256: str,
    expected_retained_topic: str,
    validator: BridgeValidator,
) -> Candidate:
    expected_topic_sha = _sha_bytes(expected_retained_topic.encode("utf-8"))
    valid: list[Candidate] = []
    for root in candidates:
        if not _private_directory(root):
            continue
        manifest_path = root / "manifest.json"
        if not _private_file(manifest_path) or _sha(manifest_path) != expected_manifest_sha256:
            continue
        try:
            report = validator(root)
        except Exception:
            continue
        if (
            report.get("verified") is not True
            or report.get("manifest_sha256") != expected_manifest_sha256
            or report.get("expected_retained_topic_sha256") != expected_topic_sha
            or report.get("future_baseline_waiver_enabled") is not False
            or report.get("ready_for_fresh_evidence_chain") is not True
            or report.get("ready_for_production_execution") is not False
            or report.get("secret_values_included") is not False
            or report.get("source_paths_included") is not False
        ):
            continue
        manifest = _load_private_json(manifest_path)
        if manifest is not None:
            valid.append(_candidate(root, manifest_path, manifest))
    if len(valid) != 1:
        _fail("legacy_review_bridge_not_unique")
    return valid[0]


def _validated_postactivation(
    candidates: Sequence[Path],
    *,
    expected_retained_topic: str,
    validator: PostactivationValidator,
) -> tuple[Candidate, ...]:
    expected_topic_sha = _sha_bytes(expected_retained_topic.encode("utf-8"))
    valid: list[Candidate] = []
    for root in candidates:
        try:
            manifest_path, manifest = validator(root)
        except Exception:
            continue
        bindings = manifest.get("bindings")
        if (
            not isinstance(bindings, Mapping)
            or bindings.get("expected_retained_topic_sha256") != expected_topic_sha
        ):
            continue
        valid.append(_candidate(root, manifest_path, manifest))
    return tuple(sorted(valid, key=lambda item: item.name))


def _validated_stages(
    candidates: Sequence[Path],
    *,
    expected_retained_topic: str,
    validator: StageValidator,
) -> tuple[Candidate, ...]:
    valid: list[Candidate] = []
    for root in candidates:
        try:
            manifest = validator(root)
        except Exception:
            continue
        readiness = manifest.get("readiness_binding")
        manifest_path = root / "stage-manifest.json"
        if (
            not isinstance(readiness, Mapping)
            or readiness.get("expected_retained_topic") != expected_retained_topic
            or not _private_file(manifest_path)
        ):
            continue
        valid.append(_candidate(root, manifest_path, manifest))
    return tuple(sorted(valid, key=lambda item: item.name))


def _output_roots(candidates: Sequence[Path]) -> tuple[Path, ...]:
    roots: set[Path] = set()
    for path in candidates:
        manifest = _load_private_json(path / "manifest.json")
        if (
            _private_directory(path)
            and _private_directory(path.parent)
            and manifest is not None
            and manifest.get("schema") == PREPARATION_SCHEMA
        ):
            roots.add(path.parent.resolve())
    return tuple(sorted(roots, key=str))


def validate_repository_binding(
    *,
    expected_repository_sha: str,
    expected_manager_version: str,
    source_root: Path | None = None,
    running_module_path: Path | None = None,
) -> dict[str, str]:
    if _GIT_SHA.fullmatch(expected_repository_sha) is None:
        _fail("expected_repository_sha_invalid")
    if _VERSION.fullmatch(expected_manager_version) is None:
        _fail("expected_manager_version_invalid")
    root = (source_root or Path(__file__).resolve().parents[4]).resolve()
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        _fail("source_repository_unavailable")
    repository_sha = completed.stdout.strip() if completed.returncode == 0 else ""
    if repository_sha != expected_repository_sha:
        _fail("source_repository_sha_mismatch")
    try:
        pyproject = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "show",
                f"{repository_sha}:host/greenhouse-manager/pyproject.toml",
            ],
            check=False,
            capture_output=True,
        )
        committed_module = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "show",
                (
                    f"{repository_sha}:host/greenhouse-manager/src/greenhouse_manager/"
                    "t1_manager_identity_fresh_chain_preparation.py"
                ),
            ],
            check=False,
            capture_output=True,
        )
        if pyproject.returncode != 0 or committed_module.returncode != 0:
            _fail("source_commit_material_unavailable")
        document = tomllib.loads(pyproject.stdout.decode("utf-8"))
        manager_version = str(document["project"]["version"])
        module_path = (running_module_path or Path(__file__)).resolve()
        if module_path.read_bytes() != committed_module.stdout:
            _fail("running_source_module_mismatch")
    except (OSError, UnicodeError, KeyError, TypeError, tomllib.TOMLDecodeError):
        _fail("source_manager_version_unavailable")
    if manager_version != expected_manager_version:
        _fail("source_manager_version_mismatch")
    return {
        "repository_sha": repository_sha,
        "manager_version": manager_version,
    }


def _inventory(
    search_root: Path,
    *,
    bridge_name: str,
    bridge_manifest_sha256: str,
    expected_retained_topic: str,
    bridge_validator: BridgeValidator,
    postactivation_validator: PostactivationValidator,
    stage_validator: StageValidator,
) -> Inventory:
    if not bridge_name.startswith(BRIDGE_PREFIX):
        _fail("legacy_review_bridge_name_invalid")
    if _SHA256.fullmatch(bridge_manifest_sha256) is None:
        _fail("legacy_review_bridge_manifest_sha_invalid")
    if not expected_retained_topic.startswith("gh/"):
        _fail("expected_retained_topic_invalid")
    paths = _walk_candidate_directories(search_root.resolve(), bridge_name)
    bridge = _validated_bridge(
        paths["bridge"],
        expected_manifest_sha256=bridge_manifest_sha256,
        expected_retained_topic=expected_retained_topic,
        validator=bridge_validator,
    )
    postactivation = _validated_postactivation(
        paths["postactivation"],
        expected_retained_topic=expected_retained_topic,
        validator=postactivation_validator,
    )
    stages = _validated_stages(
        paths["stage"],
        expected_retained_topic=expected_retained_topic,
        validator=stage_validator,
    )
    return Inventory(
        bridge=bridge,
        postactivation=postactivation,
        stages=stages,
        output_roots=_output_roots(paths["preparation"]),
    )


def _select(candidates: Sequence[Candidate], requested_name: str | None, code: str) -> Candidate:
    selected = (
        [item for item in candidates if item.name == requested_name]
        if requested_name is not None
        else list(candidates)
    )
    if len(selected) != 1:
        _fail(code)
    return selected[0]


def _select_output_root(candidates: Sequence[Path], requested: Path | None) -> Path:
    if requested is not None:
        root = requested.expanduser().resolve()
        if not _private_directory(root):
            _fail("output_root_invalid")
        return root
    if len(candidates) != 1:
        _fail("output_root_not_unique")
    return candidates[0]


def _contains_protected_path(serialized: str, path: Path) -> bool:
    value = str(path)
    return value != "/" and value in serialized


def _discovery_report(binding: Mapping[str, str], inventory: Inventory) -> dict[str, object]:
    ready = (
        len(inventory.postactivation) == 1 and len(inventory.stages) == 1 and len(inventory.output_roots) == 1
    )
    report = {
        "schema": SCHEMA,
        "status": "fresh_chain_sources_discovered",
        **binding,
        "legacy_review_bridge": inventory.bridge.public(),
        "postactivation_candidates": [item.public() for item in inventory.postactivation],
        "migration_stage_candidates": [item.public() for item in inventory.stages],
        "output_root_candidate_count": len(inventory.output_roots),
        "ready_for_fresh_preparation": ready,
        "ready_for_production_execution": False,
        "read_only_live_services": True,
        "current_services_modified": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    return report


def discover_fresh_chain_sources(
    search_root: str | Path,
    *,
    expected_repository_sha: str,
    expected_manager_version: str,
    expected_retained_topic: str,
    legacy_review_bridge_name: str,
    legacy_review_bridge_manifest_sha256: str,
    source_root: Path | None = None,
    repository_binding_builder: RepositoryBindingBuilder = validate_repository_binding,
    bridge_validator: BridgeValidator = validate_manager_identity_legacy_review_bridge,
    postactivation_validator: PostactivationValidator = _postactivation_handoff,
    stage_validator: StageValidator = verify_migration_stage,
) -> dict[str, object]:
    binding = repository_binding_builder(
        expected_repository_sha=expected_repository_sha,
        expected_manager_version=expected_manager_version,
        source_root=source_root,
    )
    inventory = _inventory(
        Path(search_root),
        bridge_name=legacy_review_bridge_name,
        bridge_manifest_sha256=legacy_review_bridge_manifest_sha256,
        expected_retained_topic=expected_retained_topic,
        bridge_validator=bridge_validator,
        postactivation_validator=postactivation_validator,
        stage_validator=stage_validator,
    )
    report = _discovery_report(binding, inventory)
    serialized = _json(report)
    if (
        _contains_protected_path(serialized, Path(search_root).expanduser().resolve())
        or expected_retained_topic in serialized
    ):
        _fail("discovery_report_contains_protected_value")
    return report


def prepare_fresh_manager_identity_chain(
    search_root: str | Path,
    *,
    expected_repository_sha: str,
    expected_manager_version: str,
    expected_retained_topic: str,
    legacy_review_bridge_name: str,
    legacy_review_bridge_manifest_sha256: str,
    postactivation_handoff_name: str | None = None,
    migration_stage_name: str | None = None,
    output_root: str | Path | None = None,
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    source_root: Path | None = None,
    repository_binding_builder: RepositoryBindingBuilder = validate_repository_binding,
    bridge_validator: BridgeValidator = validate_manager_identity_legacy_review_bridge,
    postactivation_validator: PostactivationValidator = _postactivation_handoff,
    stage_validator: StageValidator = verify_migration_stage,
    preparation_builder: PreparationBuilder = prepare_manager_identity_migration,
) -> dict[str, object]:
    binding = repository_binding_builder(
        expected_repository_sha=expected_repository_sha,
        expected_manager_version=expected_manager_version,
        source_root=source_root,
    )
    inventory = _inventory(
        Path(search_root),
        bridge_name=legacy_review_bridge_name,
        bridge_manifest_sha256=legacy_review_bridge_manifest_sha256,
        expected_retained_topic=expected_retained_topic,
        bridge_validator=bridge_validator,
        postactivation_validator=postactivation_validator,
        stage_validator=stage_validator,
    )
    postactivation = _select(
        inventory.postactivation,
        postactivation_handoff_name,
        "postactivation_handoff_not_unique",
    )
    stage = _select(
        inventory.stages,
        migration_stage_name,
        "migration_stage_not_unique",
    )
    destination_root = _select_output_root(
        inventory.output_roots,
        None if output_root is None else Path(output_root),
    )
    try:
        prepared = preparation_builder(
            postactivation.path,
            stage.path,
            destination_root,
            expected_retained_topic=expected_retained_topic,
            secret_root=secret_root,
            legacy_review_bridge_directory=inventory.bridge.path,
        )
    except Exception as error:
        raise ManagerIdentityFreshChainPreparationError("fresh_preparation_failed") from error
    required = {
        "prepared": True,
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
    if any(prepared.get(field) is not value for field, value in required.items()):
        _fail("fresh_preparation_result_invalid")
    report = {
        "schema": SCHEMA,
        "status": "fresh_chain_preparation_succeeded",
        **binding,
        "preparation_name": prepared.get("preparation_name"),
        "preparation_manifest_sha256": prepared.get("manifest_sha256"),
        "legacy_review_bridge_manifest_sha256": inventory.bridge.manifest_sha256,
        "legacy_review_bridge_bound": True,
        "future_baseline_waiver_enabled": False,
        "postactivation_name_fingerprint": postactivation.name_fingerprint,
        "migration_stage_name_fingerprint": stage.name_fingerprint,
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "ready_for_fresh_evidence_chain": True,
        "ready_for_production_execution": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    if (
        not isinstance(report["preparation_name"], str)
        or not str(report["preparation_name"]).startswith(PREPARATION_PREFIX)
        or not isinstance(report["preparation_manifest_sha256"], str)
        or _SHA256.fullmatch(str(report["preparation_manifest_sha256"])) is None
    ):
        _fail("fresh_preparation_binding_invalid")
    serialized = _json(report)
    protected = (
        Path(search_root).expanduser().resolve(),
        postactivation.path,
        stage.path,
        destination_root,
        inventory.bridge.path,
        Path(secret_root).expanduser().resolve(),
    )
    if any(_contains_protected_path(serialized, path) for path in protected) or (
        expected_retained_topic in serialized
    ):
        _fail("fresh_preparation_report_contains_protected_value")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover or create a fresh manager migration preparation bound to a verified "
            "legacy-review bridge. No authorization or production execution is created."
        )
    )
    parser.add_argument("search_root")
    parser.add_argument("--expected-repository-sha", required=True)
    parser.add_argument("--expected-manager-version", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--legacy-review-bridge-name", required=True)
    parser.add_argument("--legacy-review-bridge-manifest-sha256", required=True)
    parser.add_argument("--discover-only", action="store_true")
    parser.add_argument("--postactivation-handoff-name")
    parser.add_argument("--migration-stage-name")
    parser.add_argument("--output-root")
    parser.add_argument("--secret-root", default="/opt/greenhouse-secrets/mqtt")
    parser.add_argument("--source-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "expected_repository_sha": args.expected_repository_sha,
        "expected_manager_version": args.expected_manager_version,
        "expected_retained_topic": args.expected_retained_topic,
        "legacy_review_bridge_name": args.legacy_review_bridge_name,
        "legacy_review_bridge_manifest_sha256": (args.legacy_review_bridge_manifest_sha256),
        "source_root": args.source_root,
    }
    try:
        if args.discover_only:
            report = discover_fresh_chain_sources(args.search_root, **common)
        else:
            report = prepare_fresh_manager_identity_chain(
                args.search_root,
                postactivation_handoff_name=args.postactivation_handoff_name,
                migration_stage_name=args.migration_stage_name,
                output_root=args.output_root,
                secret_root=args.secret_root,
                **common,
            )
    except ManagerIdentityFreshChainPreparationError as error:
        print(
            _json(
                {
                    "schema": SCHEMA,
                    "status": "fresh_chain_preparation_failed_closed",
                    "error_code": str(error),
                    "authorization_created": False,
                    "authorization_claimed": False,
                    "current_services_modified": False,
                    "manager_identity_migrated": False,
                    "node_credentials_delivered": False,
                    "preserve_anonymous": True,
                    "anonymous_closure_enabled": False,
                    "secret_values_included": False,
                    "source_paths_included": False,
                }
            )
        )
        return 2
    print(_json(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
