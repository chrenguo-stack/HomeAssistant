#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

STACK_RELEASE_SCHEMA = "gh.n3w-t1-core-stack-release/1"
STACK_UPGRADE_PLAN_SCHEMA = "gh.n3w-t1-core-stack-upgrade-plan/1"
SUPPORTED_PLATFORM = "linux/arm64"
COMPONENTS = ("manager", "homeassistant", "broker")
IMAGE_PREFIXES = {
    "manager": "local/greenhouse-manager:",
    "homeassistant": "local/n3w-homeassistant:",
    "broker": "local/n3w-mosquitto:",
}
BINDING_MODES = frozenset({"dynamic", "legacy_static"})
IDENTITY_KINDS = frozenset({"tar_sha256", "manifest_digest_sha256"})
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class StackReleaseError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _mapping(value: Any, reason: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StackReleaseError(reason)
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], reason: str) -> None:
    if set(value) != expected:
        raise StackReleaseError(reason)


def _nonempty(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise StackReleaseError(reason)
    return value


def _sha256(value: Any, reason: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise StackReleaseError(reason)
    return value


def _git_sha(value: Any, reason: str) -> str:
    if not isinstance(value, str) or GIT_SHA.fullmatch(value) is None:
        raise StackReleaseError(reason)
    return value


def parse_semver(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise StackReleaseError("stack_version_invalid")
    match = SEMVER.fullmatch(value)
    if match is None:
        raise StackReleaseError("stack_version_invalid")
    return tuple(int(part) for part in match.groups())


def _validate_component(name: str, raw: Any) -> dict[str, Any]:
    record = copy.deepcopy(_mapping(raw, f"{name}_record_invalid"))
    _exact_keys(record, {"image", "platform", "identity"}, f"{name}_record_keys_invalid")
    image = _nonempty(record["image"], f"{name}_image_invalid")
    if not image.startswith(IMAGE_PREFIXES[name]):
        raise StackReleaseError(f"{name}_image_namespace_invalid")
    if record["platform"] != SUPPORTED_PLATFORM:
        raise StackReleaseError(f"{name}_platform_invalid")
    identity = _mapping(record["identity"], f"{name}_identity_invalid")
    _exact_keys(identity, {"kind", "sha256"}, f"{name}_identity_keys_invalid")
    if identity["kind"] not in IDENTITY_KINDS:
        raise StackReleaseError(f"{name}_identity_kind_invalid")
    _sha256(identity["sha256"], f"{name}_identity_sha256_invalid")
    return record


def _validate_runtime_contract(raw: Any) -> dict[str, Any]:
    contract = copy.deepcopy(_mapping(raw, "runtime_contract_invalid"))
    _exact_keys(
        contract,
        {"live_compose_path", "image_binding_modes", "service_owners"},
        "runtime_contract_keys_invalid",
    )
    _nonempty(contract["live_compose_path"], "live_compose_path_invalid")
    modes = _mapping(contract["image_binding_modes"], "image_binding_modes_invalid")
    owners = _mapping(contract["service_owners"], "service_owners_invalid")
    if set(modes) != set(COMPONENTS):
        raise StackReleaseError("image_binding_modes_keys_invalid")
    if set(owners) != set(COMPONENTS):
        raise StackReleaseError("service_owners_keys_invalid")
    for component in COMPONENTS:
        if modes[component] not in BINDING_MODES:
            raise StackReleaseError(f"{component}_binding_mode_invalid")
        _nonempty(owners[component], f"{component}_service_owner_invalid")
    if owners["manager"] != owners["homeassistant"]:
        raise StackReleaseError("manager_homeassistant_service_owner_mismatch")
    if owners["broker"] == owners["manager"]:
        raise StackReleaseError("broker_service_owner_not_independent")
    return contract


def release_material(document: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(document)
    material.pop("release_id", None)
    return material


def validate_release(document: Any) -> dict[str, Any]:
    value = copy.deepcopy(_mapping(document, "release_invalid"))
    _exact_keys(
        value,
        {
            "schema",
            "stack_version",
            "release_id",
            "product_source_head",
            "components",
            "runtime_contract",
        },
        "release_keys_invalid",
    )
    if value["schema"] != STACK_RELEASE_SCHEMA:
        raise StackReleaseError("release_schema_invalid")
    parse_semver(value["stack_version"])
    release_id = _sha256(value["release_id"], "release_id_invalid")
    _git_sha(value["product_source_head"], "product_source_head_invalid")
    components = _mapping(value["components"], "components_invalid")
    if set(components) != set(COMPONENTS):
        raise StackReleaseError("components_keys_invalid")
    for component in COMPONENTS:
        components[component] = _validate_component(component, components[component])
    value["runtime_contract"] = _validate_runtime_contract(value["runtime_contract"])
    if canonical_sha256(release_material(value)) != release_id:
        raise StackReleaseError("release_id_mismatch")
    return value


def make_release(material: Any) -> dict[str, Any]:
    value = copy.deepcopy(_mapping(material, "release_material_invalid"))
    if "release_id" in value:
        raise StackReleaseError("release_material_contains_release_id")
    value["release_id"] = canonical_sha256(value)
    return validate_release(value)


def build_upgrade_plan(current: Any, target: Any) -> dict[str, Any]:
    before = validate_release(current)
    after = validate_release(target)
    if parse_semver(after["stack_version"]) <= parse_semver(before["stack_version"]):
        raise StackReleaseError("target_stack_version_not_greater")

    component_actions: dict[str, str] = {}
    for component in COMPONENTS:
        component_actions[component] = (
            "KEEP"
            if before["components"][component] == after["components"][component]
            else "UPGRADE"
        )
    runtime_contract_action = (
        "KEEP"
        if before["runtime_contract"] == after["runtime_contract"]
        else "UPDATE"
    )
    if (
        all(action == "KEEP" for action in component_actions.values())
        and runtime_contract_action == "KEEP"
    ):
        raise StackReleaseError("empty_stack_upgrade")

    material = {
        "schema": STACK_UPGRADE_PLAN_SCHEMA,
        "from_stack_version": before["stack_version"],
        "from_release_id": before["release_id"],
        "to_stack_version": after["stack_version"],
        "to_release_id": after["release_id"],
        "component_actions": component_actions,
        "runtime_contract_action": runtime_contract_action,
        "rollback_authority_release_id": before["release_id"],
        "commit_rule": "TARGET_STACK_ACCEPTANCE_REQUIRED",
    }
    return {"plan_id": canonical_sha256(material), **material}
