#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-core-stack-current-authority/1"
TARGET_SCHEMA = "gh.n3w-t1-core-updater-manager-target/1"

AUTHORITY = Path("infra/n3w-t1/production/t1-core-stack-current.json")
TARGET = Path("infra/n3w-t1/upgrades/manager-3539c8f871e2.json")
FRESH_COMPOSE = Path("infra/n3w-t1/production/docker-compose.fresh.yml")
BOOTSTRAP = Path("tools/n3w_t1_fresh_product_bootstrap.py")
CURRENT_STATE = Path("docs/development/N3W_CURRENT_STATE.md")
CURRENT_INDEX = Path("docs/development/N3W_CURRENT_STATE_INDEX.md")

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


class AuthorityError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AuthorityError(f"file_invalid:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AuthorityError(f"json_invalid:{path}") from error
    if not isinstance(value, dict):
        raise AuthorityError(f"json_shape_invalid:{path}")
    return value


def _read_text(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise AuthorityError(f"file_invalid:{path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise AuthorityError(f"text_invalid:{path}") from error


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise AuthorityError(reason)


def _first_section(text: str) -> str:
    if not text.startswith("## "):
        raise AuthorityError("current_state_heading_invalid")
    marker = text.find("\n## ", 3)
    return text if marker < 0 else text[:marker]


def validate_documents(
    authority: dict[str, Any],
    target: dict[str, Any],
    fresh_compose: str,
    bootstrap_source: str,
    current_state: str,
    current_index: str,
) -> dict[str, Any]:
    _require(authority.get("schema") == SCHEMA, "authority_schema_invalid")
    _require(
        authority.get("authority_state") == "SUCCESSOR_READY_NOT_LIVE_APPLIED",
        "authority_state_invalid",
    )

    historical = authority.get("historical_clean_reference")
    current = authority.get("current_repository_stack")
    upgrade = authority.get("manager_successor_upgrade")
    mutation = authority.get("mutation_scope")
    live = authority.get("live_deployment")

    _require(isinstance(historical, dict), "historical_authority_invalid")
    _require(isinstance(current, dict), "current_stack_invalid")
    _require(isinstance(upgrade, dict), "upgrade_authority_invalid")
    _require(isinstance(mutation, dict), "mutation_scope_invalid")
    _require(isinstance(live, dict), "live_deployment_invalid")

    old_source = historical.get("source_head")
    old_manager = historical.get("manager_image")
    _require(
        isinstance(old_source, str) and SHA40.fullmatch(old_source) is not None,
        "historical_source_invalid",
    )
    _require(
        isinstance(old_manager, str) and old_manager.startswith("local/greenhouse-manager:"),
        "historical_manager_invalid",
    )
    _require(
        historical.get("immutable_history") is True,
        "historical_immutability_invalid",
    )

    product_source = current.get("product_source_head")
    manager = current.get("manager")
    homeassistant = current.get("homeassistant")
    broker = current.get("broker")
    runtime_template = current.get("runtime_template")
    legacy_compose = current.get("legacy_static_compose")

    _require(
        isinstance(product_source, str)
        and SHA40.fullmatch(product_source) is not None,
        "current_product_source_invalid",
    )
    _require(product_source != old_source, "successor_source_not_advanced")

    for name, record in (
        ("manager", manager),
        ("homeassistant", homeassistant),
        ("broker", broker),
    ):
        _require(isinstance(record, dict), f"{name}_record_invalid")
        image_id = record.get("image_id")
        _require(
            isinstance(image_id, str) and IMAGE_ID.fullmatch(image_id) is not None,
            f"{name}_image_id_invalid",
        )
        _require(record.get("platform") == "linux/arm64", f"{name}_platform_invalid")

    _require(manager.get("image") != old_manager, "successor_manager_not_advanced")
    _require(
        isinstance(manager.get("tar_sha256"), str)
        and SHA256.fullmatch(manager["tar_sha256"]) is not None,
        "manager_tar_sha256_invalid",
    )

    for name, record in (("homeassistant", homeassistant), ("broker", broker)):
        digest = record.get("manifest_digest")
        _require(
            isinstance(digest, str)
            and digest.startswith("sha256:")
            and SHA256.fullmatch(digest[7:]) is not None,
            f"{name}_manifest_digest_invalid",
        )

    _require(
        isinstance(runtime_template, dict)
        and runtime_template.get("source")
        == "infra/n3w-t1/production/docker-compose.fresh.yml"
        and runtime_template.get("live_canonical_destination")
        == "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml"
        and runtime_template.get("manager_image_binding") == "GH_MANAGER_IMAGE"
        and runtime_template.get("staging_rule")
        == "fresh_compose_replaces_canonical_compose",
        "runtime_template_authority_invalid",
    )
    _require(
        isinstance(legacy_compose, dict)
        and legacy_compose.get("source")
        == "infra/n3w-t1/production/docker-compose.yml"
        and legacy_compose.get("current_successor_authority") is False
        and legacy_compose.get("retained_for_historical_compatibility") is True,
        "legacy_compose_boundary_invalid",
    )

    _require(target.get("schema") == TARGET_SCHEMA, "target_schema_invalid")
    _require(target.get("component") == "manager", "target_component_invalid")
    _require(target.get("source_head") == product_source, "target_source_mismatch")
    _require(target.get("image") == manager.get("image"), "target_image_mismatch")
    _require(target.get("image_id") == manager.get("image_id"), "target_image_id_mismatch")
    _require(
        target.get("tar_sha256") == manager.get("tar_sha256"),
        "target_tar_sha256_mismatch",
    )
    _require(
        target.get("expected_predecessor_image") == old_manager,
        "target_predecessor_mismatch",
    )
    _require(target.get("rollback_compatible") is True, "target_rollback_invalid")

    _require(
        upgrade.get("target_manifest") == str(TARGET),
        "upgrade_target_manifest_invalid",
    )
    reviewed_head = upgrade.get("updater_reviewed_head")
    _require(
        isinstance(reviewed_head, str) and SHA40.fullmatch(reviewed_head) is not None,
        "updater_reviewed_head_invalid",
    )
    _require(upgrade.get("updater_pr") == 748, "updater_pr_invalid")
    merge_commit = upgrade.get("updater_merge_commit")
    _require(
        isinstance(merge_commit, str) and SHA40.fullmatch(merge_commit) is not None,
        "updater_merge_commit_invalid",
    )
    _require(
        isinstance(upgrade.get("package_run_id"), int)
        and upgrade["package_run_id"] > 0,
        "package_run_id_invalid",
    )
    _require(
        isinstance(upgrade.get("package_artifact_id"), int)
        and upgrade["package_artifact_id"] > 0,
        "package_artifact_id_invalid",
    )
    package_digest = upgrade.get("package_artifact_digest")
    _require(
        isinstance(package_digest, str)
        and package_digest.startswith("sha256:")
        and SHA256.fullmatch(package_digest[7:]) is not None,
        "package_artifact_digest_invalid",
    )
    pyz = upgrade.get("updater_pyz_sha256")
    _require(
        isinstance(pyz, str) and SHA256.fullmatch(pyz) is not None,
        "updater_pyz_sha256_invalid",
    )
    _require(upgrade.get("manager_rebuilt") is False, "manager_rebuilt_invalid")
    _require(upgrade.get("rollback_compatible") is True, "upgrade_rollback_invalid")

    _require(
        mutation
        == {
            "manager": True,
            "homeassistant_image": False,
            "broker_image": False,
            "host_platform": False,
            "board": False,
        },
        "mutation_scope_not_manager_only",
    )

    _require(live.get("state") == "NOT_YET_APPLIED", "live_state_invalid")
    _require(
        live.get("expected_predecessor_manager_image") == old_manager,
        "live_predecessor_invalid",
    )
    _require(
        live.get("expected_target_manager_image") == manager.get("image"),
        "live_target_invalid",
    )

    _require(
        'image: "\${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}"' in fresh_compose,
        "fresh_compose_manager_binding_invalid",
    )
    _require(
        f'image: {homeassistant["image"]}' in fresh_compose,
        "fresh_compose_homeassistant_invalid",
    )
    _require(
        f'image: {broker["image"]}' in fresh_compose,
        "fresh_compose_broker_invalid",
    )
    _require(
        "fresh_compose.replace(canonical_compose)" in bootstrap_source,
        "fresh_bootstrap_canonicalization_missing",
    )
    _require(
        'f"GH_MANAGER_IMAGE={self.manager_image}\\n"' in bootstrap_source,
        "fresh_bootstrap_manager_env_missing",
    )

    state_top = _first_section(current_state)
    index_top = _first_section(current_index)
    for label, text in (("state", state_top), ("index", index_top)):
        _require(str(AUTHORITY) in text, f"{label}_authority_link_missing")
        _require(product_source in text, f"{label}_product_source_missing")
        _require(str(manager["image"]) in text, f"{label}_manager_missing")
        _require(str(homeassistant["image"]) in text, f"{label}_homeassistant_missing")
        _require(str(broker["image"]) in text, f"{label}_broker_missing")
        _require(old_source in text, f"{label}_historical_source_missing")
        _require(old_manager in text, f"{label}_historical_manager_missing")

    _require(
        "LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED" in state_top,
        "state_live_deployment_marker_missing",
    )
    _require(
        "live upgrade pending" in index_top.lower(),
        "index_live_deployment_marker_missing",
    )

    return {
        "schema": "gh.n3w-t1-core-stack-current-authority-check/1",
        "status": "PASS",
        "historical_clean_reference_source_head": old_source,
        "current_repository_product_source_head": product_source,
        "current_repository_manager": manager["image"],
        "homeassistant_unchanged": True,
        "broker_unchanged": True,
        "manager_only_upgrade": True,
        "legacy_static_compose_is_current_authority": False,
        "live_deployment_state": live["state"],
    }


def validate_repo(root: Path) -> dict[str, Any]:
    return validate_documents(
        _read_json(root / AUTHORITY),
        _read_json(root / TARGET),
        _read_text(root / FRESH_COMPOSE),
        _read_text(root / BOOTSTRAP),
        _read_text(root / CURRENT_STATE),
        _read_text(root / CURRENT_INDEX),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    try:
        result = validate_repo(Path(args.repo_root).resolve())
    except (AuthorityError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema": "gh.n3w-t1-core-stack-current-authority-check/1",
                    "status": "STOP",
                    "reason": str(error)[:300],
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
