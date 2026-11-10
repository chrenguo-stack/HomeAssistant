#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-core-stack-current-authority/2"
TARGET_SCHEMA = "gh.n3w-t1-core-updater-target/2"
UPDATER_DELIVERY_SCHEMA = "gh.n3w-t1-core-updater-delivery/1"

PENDING_AUTHORITY_STATE = "SUCCESSOR_READY_NOT_LIVE_APPLIED"
APPLIED_AUTHORITY_STATE = "CURRENT_STACK_LIVE_ACCEPTED"
PENDING_LIVE_STATE = "NOT_YET_APPLIED"
APPLIED_LIVE_STATE = "APPLIED_ACCEPTED"

AUTHORITY = Path("infra/n3w-t1/production/t1-core-stack-current.json")
TARGET = Path("infra/n3w-t1/upgrades/manager-5b32e1ae8210.json")
FRESH_COMPOSE = Path("infra/n3w-t1/production/docker-compose.fresh.yml")
BOOTSTRAP = Path("tools/n3w_t1_fresh_product_bootstrap.py")
CURRENT_STATE = Path("docs/development/N3W_CURRENT_STATE.md")
CURRENT_INDEX = Path("docs/development/N3W_CURRENT_STATE_INDEX.md")
UPDATER_DELIVERY = Path("infra/n3w-t1/updater-releases/delivery-contract.json")
FRESH_PAYLOAD_WORKFLOW = Path(
    ".github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml"
)
UPDATER_PACKAGE_WORKFLOW = Path(
    ".github/workflows/n3w-t1-core-updater-manager-a-to-b-ci.yml"
)
U1_EXECUTOR = Path(
    "tools/execution_packages/n3w/u1/manager_a_to_b_v2_live_apply/executor.py"
)
HISTORICAL_AUTHORITY_FILES = (
    Path("tools/n3w_t1_clean_reference_r2a.py"),
    Path("tools/n3w_t1_clean_reference_r2b.py"),
    Path("tools/n3w_t1_clean_reference_observer.py"),
    Path("tools/n3w_t1_clean_reference_pairing_readiness_bridge.py"),
    Path("tools/n3w_t1_clean_reference_r2a_package_builder.py"),
    Path("tools/n3w_t1_clean_reference_r2b_package_builder.py"),
    Path("tools/n3w_t1_clean_reference_r3_package_builder.py"),
    Path("tools/n3w_t1_clean_reference_pairing_readiness_bridge_package_builder.py"),
)

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


def validate_updater_delivery(
    delivery: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Any]:
    _require(isinstance(delivery, dict), "updater_delivery_invalid")
    expected = {
        "schema": UPDATER_DELIVERY_SCHEMA,
        "mode": "EXACT_PACKAGE_BOUND_EPHEMERAL_PYZ",
        "canonical_package_filename": "t1-core-updater.pyz",
        "permanent_install_required": False,
        "permanent_cli_path": None,
        "allowed_staging_roots": ["/tmp", "/var/tmp"],
        "execution_prefix": ["python3", "-B"],
        "integrity_authority": "package-binding.json:updater_pyz_sha256",
        "accepted_binding_source": (
            "infra/n3w-t1/production/t1-core-stack-current.json:"
            "manager_successor_upgrade"
        ),
        "source_checkout_required_on_t1": False,
        "runtime_health_authority": False,
    }
    _require(delivery == expected, "updater_delivery_contract_invalid")
    upgrade = authority.get("manager_successor_upgrade")
    _require(isinstance(upgrade, dict), "upgrade_authority_invalid")
    pyz = upgrade.get("updater_pyz_sha256")
    _require(
        isinstance(pyz, str) and SHA256.fullmatch(pyz) is not None,
        "updater_pyz_sha256_invalid",
    )
    return delivery


def validate_updater_delivery_sources(
    fresh_payload_workflow: str,
    updater_package_workflow: str,
    u1_executor: str,
) -> dict[str, Any]:
    forbidden_permanent = (
        "runtime-source/opt/HomeAssistant/tools/n3w_t1_core_updater.py",
        "runtime-source/usr/local/sbin/t1-core-updater",
        'cp tools/n3w_t1_core_updater.py "$PAYLOAD/runtime-source',
    )
    for value in forbidden_permanent:
        _require(
            value not in fresh_payload_workflow,
            "updater_permanent_install_reintroduced",
        )

    package_required = (
        'updater_pyz = package / "t1-core-updater.pyz"',
        "zipapp.create_archive(",
        '"updater_pyz_sha256": sha(updater_pyz)',
        'sha(root / "t1-core-updater.pyz") == package["updater_pyz_sha256"]',
    )
    for value in package_required:
        _require(value in updater_package_workflow, "updater_package_binding_missing")

    executor_required = (
        'REMOTE_DIR = "/var/tmp/',
        '"t1-core-updater.pyz"',
        "sha256_file(pyz) != UPDATER_PYZ_SHA256",
        'for item in ["sudo", "-n", "python3", "-B", pyz, *args]',
    )
    for value in executor_required:
        _require(value in u1_executor, "updater_ephemeral_execution_contract_missing")

    _require(
        "/opt/HomeAssistant/tools/n3w_t1_core_updater.py" not in u1_executor,
        "updater_executor_uses_unbound_permanent_source",
    )
    return {
        "updater_delivery_mode": "EXACT_PACKAGE_BOUND_EPHEMERAL_PYZ",
        "updater_permanent_install_required": False,
        "updater_runtime_health_authority": False,
        "updater_exact_digest_required_before_execution": True,
    }


def validate_documents(
    authority: dict[str, Any],
    target: dict[str, Any],
    fresh_compose: str,
    bootstrap_source: str,
    current_state: str,
    current_index: str,
) -> dict[str, Any]:
    _require(authority.get("schema") == SCHEMA, "authority_schema_invalid")
    authority_state = authority.get("authority_state")
    _require(
        authority_state in {PENDING_AUTHORITY_STATE, APPLIED_AUTHORITY_STATE},
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
    _require(
        target.get("mutation_profile") == "IMAGE_ONLY_V1",
        "target_mutation_profile_invalid",
    )
    compatibility = target.get("compatibility_evidence")
    _require(isinstance(compatibility, dict), "target_compatibility_invalid")
    _require(
        compatibility.get("target_source_head") == product_source,
        "target_source_mismatch",
    )
    _require(
        target.get("target_image_ref") == manager.get("image"),
        "target_image_mismatch",
    )
    _require(
        target.get("target_platform") == manager.get("platform"),
        "target_platform_mismatch",
    )
    _require(
        target.get("target_archive_sha256") == manager.get("tar_sha256"),
        "target_tar_sha256_mismatch",
    )
    _require(target.get("rollback_compatible") is True, "target_rollback_invalid")

    _require(
        upgrade.get("target_manifest") == str(TARGET),
        "upgrade_target_manifest_invalid",
    )
    source_repair_pr = upgrade.get("source_repair_pr")
    _require(
        isinstance(source_repair_pr, int)
        and not isinstance(source_repair_pr, bool)
        and source_repair_pr > 0,
        "source_repair_pr_invalid",
    )
    _require(
        upgrade.get("source_repair_head") == product_source,
        "source_repair_head_mismatch",
    )
    manager_build_image_id = upgrade.get("manager_build_image_id")
    _require(
        isinstance(manager_build_image_id, str)
        and IMAGE_ID.fullmatch(manager_build_image_id) is not None
        and manager_build_image_id == manager.get("image_id"),
        "manager_build_image_id_invalid",
    )
    execution_pr = upgrade.get("execution_pr")
    _require(
        isinstance(execution_pr, int)
        and not isinstance(execution_pr, bool)
        and execution_pr > 0,
        "execution_pr_invalid",
    )
    package_control_head = upgrade.get("package_control_head")
    _require(
        isinstance(package_control_head, str)
        and SHA40.fullmatch(package_control_head) is not None,
        "package_control_head_invalid",
    )

    reviewed_head = upgrade.get("updater_reviewed_head")
    _require(
        isinstance(reviewed_head, str) and SHA40.fullmatch(reviewed_head) is not None,
        "updater_reviewed_head_invalid",
    )
    updater_pr = upgrade.get("updater_pr")
    _require(
        isinstance(updater_pr, int)
        and not isinstance(updater_pr, bool)
        and updater_pr > 0,
        "updater_pr_invalid",
    )
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

    live_state = live.get("state")
    _require(
        live_state in {PENDING_LIVE_STATE, APPLIED_LIVE_STATE},
        "live_state_invalid",
    )
    expected_authority_state = (
        PENDING_AUTHORITY_STATE
        if live_state == PENDING_LIVE_STATE
        else APPLIED_AUTHORITY_STATE
    )
    _require(
        authority_state == expected_authority_state,
        "authority_live_state_mismatch",
    )
    immediate_predecessor = live.get("expected_predecessor_manager_image")
    _require(
        isinstance(immediate_predecessor, str)
        and immediate_predecessor.startswith("local/greenhouse-manager:")
        and immediate_predecessor != manager.get("image"),
        "live_predecessor_invalid",
    )
    _require(
        target.get("expected_predecessor_image_ref") == immediate_predecessor,
        "target_predecessor_mismatch",
    )
    _require(
        live.get("expected_target_manager_image") == manager.get("image"),
        "live_target_invalid",
    )

    if live_state == APPLIED_LIVE_STATE:
        _require(
            live.get("current_manager_image") == manager.get("image"),
            "live_current_manager_invalid",
        )
        runtime_image_id = live.get("current_manager_runtime_image_id")
        _require(
            isinstance(runtime_image_id, str)
            and IMAGE_ID.fullmatch(runtime_image_id) is not None,
            "live_runtime_image_id_invalid",
        )
        _require(
            live.get("transaction_status") == "COMMITTED",
            "live_transaction_status_invalid",
        )
        _require(
            live.get("transaction_phase") == "COMMITTED",
            "live_transaction_phase_invalid",
        )
        _require(
            live.get("recovery_required") is False,
            "live_recovery_required_invalid",
        )
        _require(
            live.get("post_upgrade_acceptance") == "PASS",
            "live_post_upgrade_acceptance_invalid",
        )
        _require(
            live.get("runtime_class") == "TARGET_BOUND_RUNNING",
            "live_runtime_class_invalid",
        )
        _require(
            live.get("health_state") == "HEALTHY",
            "live_health_state_invalid",
        )
        _require(
            live.get("kf141_closure") == "CLOSED_PASS",
            "live_kf141_closure_invalid",
        )
        _require(
            live.get("kf139_closure") == "CLOSED_PASS",
            "live_kf139_closure_invalid",
        )
        _require(
            live.get("first_registration_acceptance") == "PASS",
            "live_first_registration_acceptance_invalid",
        )
        _require(
            live.get("credential_lifecycle_private_database_gate") == "PASS",
            "live_private_database_gate_invalid",
        )
        _require(
            live.get("pairing_window_close_reason") == "committed",
            "live_pairing_window_close_reason_invalid",
        )
        _require(
            live.get("homeassistant_continuity") == "PASS",
            "live_homeassistant_continuity_invalid",
        )
        _require(
            live.get("broker_continuity") == "PASS",
            "live_broker_continuity_invalid",
        )
        _require(
            live.get("listener_contract") == "PASS",
            "live_listener_contract_invalid",
        )
        _require(
            live.get("systemd_failed_units") == 0,
            "live_systemd_failed_units_invalid",
        )
        _require(
            live.get("pairing_window_state") == "CLOSED",
            "live_pairing_window_state_invalid",
        )
        _require(
            live.get("board_mutation") is False,
            "live_board_mutation_invalid",
        )

    bindings = {
        "manager": (
            'image: "' + "$" + '{GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}"'
        ),
        "homeassistant": (
            'image: "' + "$"
            + '{GH_HOMEASSISTANT_IMAGE:?GH_HOMEASSISTANT_IMAGE required}"'
        ),
        "broker": (
            'image: "' + "$" + '{GH_BROKER_IMAGE:?GH_BROKER_IMAGE required}"'
        ),
    }
    for component, binding in bindings.items():
        _require(
            binding in fresh_compose,
            f"fresh_compose_{component}_binding_invalid",
        )
    _require(
        "fresh_compose.replace(canonical_compose)" in bootstrap_source,
        "fresh_bootstrap_canonicalization_missing",
    )
    for source, reason in (
        ('f"GH_MANAGER_IMAGE={self.manager_image}\\n"', "manager"),
        (
            'f"GH_HOMEASSISTANT_IMAGE={self.homeassistant_image}\\n"',
            "homeassistant",
        ),
        ('f"GH_BROKER_IMAGE={self.broker_image}\\n"', "broker"),
    ):
        _require(
            source in bootstrap_source,
            f"fresh_bootstrap_{reason}_env_missing",
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

    if live_state == PENDING_LIVE_STATE:
        _require(
            "LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED" in state_top,
            "state_live_deployment_marker_missing",
        )
        _require(
            "live upgrade pending" in index_top.lower(),
            "index_live_deployment_marker_missing",
        )
    else:
        _require(
            "LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED" in state_top,
            "state_live_deployment_marker_missing",
        )
        _require(
            "live upgrade accepted" in index_top.lower(),
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
        "per_module_image_bindings_ready": True,
        "legacy_static_compose_is_current_authority": False,
        "live_deployment_state": live["state"],
    }


def validate_repo(root: Path) -> dict[str, Any]:
    authority = _read_json(root / AUTHORITY)
    result = validate_documents(
        authority,
        _read_json(root / TARGET),
        _read_text(root / FRESH_COMPOSE),
        _read_text(root / BOOTSTRAP),
        _read_text(root / CURRENT_STATE),
        _read_text(root / CURRENT_INDEX),
    )
    delivery = validate_updater_delivery(
        _read_json(root / UPDATER_DELIVERY),
        authority,
    )
    result.update(
        {
            "updater_delivery_mode": delivery["mode"],
            "updater_permanent_install_required": delivery[
                "permanent_install_required"
            ],
            "updater_runtime_health_authority": delivery[
                "runtime_health_authority"
            ],
        }
    )
    result.update(
        validate_updater_delivery_sources(
            _read_text(root / FRESH_PAYLOAD_WORKFLOW),
            _read_text(root / UPDATER_PACKAGE_WORKFLOW),
            _read_text(root / U1_EXECUTOR),
        )
    )
    historical = authority["historical_clean_reference"]
    source_head = historical["source_head"]
    expected = f'PRODUCT_SOURCE_HEAD = "{source_head}"'
    for relative in HISTORICAL_AUTHORITY_FILES:
        _require(
            expected in _read_text(root / relative),
            f"historical_clean_reference_binding_drift:{relative}",
        )
    return result


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
