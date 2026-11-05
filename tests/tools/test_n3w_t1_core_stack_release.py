from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_stack_release import (
    STACK_RELEASE_SCHEMA,
    StackReleaseError,
    build_upgrade_plan,
    make_release,
    validate_release,
)


def material(version: str = "1.0.0") -> dict:
    return {
        "schema": STACK_RELEASE_SCHEMA,
        "stack_version": version,
        "product_source_head": "5b32e1ae82104a42f9e4e6907fe44d9172e87615",
        "components": {
            "manager": {
                "image": "local/greenhouse-manager:fresh-5b32e1ae8210",
                "platform": "linux/arm64",
                "identity": {
                    "kind": "tar_sha256",
                    "sha256": "2" * 64,
                },
            },
            "homeassistant": {
                "image": "local/n3w-homeassistant:2026.10.0-0c73235a",
                "platform": "linux/arm64",
                "identity": {
                    "kind": "manifest_digest_sha256",
                    "sha256": "3" * 64,
                },
            },
            "broker": {
                "image": "local/n3w-mosquitto:2.1.2-3184566d",
                "platform": "linux/arm64",
                "identity": {
                    "kind": "manifest_digest_sha256",
                    "sha256": "4" * 64,
                },
            },
        },
        "runtime_contract": {
            "live_compose_path": "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml",
            "image_binding_modes": {
                "manager": "dynamic",
                "homeassistant": "legacy_static",
                "broker": "legacy_static",
            },
            "service_owners": {
                "manager": "n3wfc4-services-activation.service",
                "homeassistant": "n3wfc4-services-activation.service",
                "broker": "n3wfc4-broker-activation.service",
            },
        },
    }


def test_release_round_trip() -> None:
    release = make_release(material())
    assert validate_release(release) == release
    assert release["stack_version"] == "1.0.0"
    assert len(release["release_id"]) == 64


def test_release_id_detects_component_identity_drift() -> None:
    first = make_release(material())
    changed = material()
    changed["components"]["homeassistant"]["identity"]["sha256"] = "5" * 64
    second = make_release(changed)
    assert first["release_id"] != second["release_id"]


def test_release_rejects_release_id_mismatch() -> None:
    release = make_release(material())
    release["release_id"] = "0" * 64
    with pytest.raises(StackReleaseError, match="release_id_mismatch"):
        validate_release(release)


def test_stack_1_0_to_1_1_ha_only_upgrade_plan() -> None:
    current = make_release(material("1.0.0"))
    target_material = copy.deepcopy(material("1.1.0"))
    target_material["components"]["homeassistant"] = {
        "image": "local/n3w-homeassistant:2026.10.4-bbbbbbbb",
        "platform": "linux/arm64",
        "identity": {
            "kind": "manifest_digest_sha256",
            "sha256": "5" * 64,
        },
    }
    target_material["runtime_contract"]["image_binding_modes"]["homeassistant"] = "dynamic"
    target = make_release(target_material)

    plan = build_upgrade_plan(current, target)

    assert plan["from_stack_version"] == "1.0.0"
    assert plan["to_stack_version"] == "1.1.0"
    assert plan["component_actions"] == {
        "manager": "KEEP",
        "homeassistant": "UPGRADE",
        "broker": "KEEP",
    }
    assert plan["runtime_contract_action"] == "UPDATE"
    assert plan["rollback_authority_release_id"] == current["release_id"]
    assert plan["commit_rule"] == "TARGET_STACK_ACCEPTANCE_REQUIRED"


def test_runtime_contract_only_change_is_visible() -> None:
    current = make_release(material("1.0.0"))
    target_material = material("1.0.1")
    target_material["runtime_contract"]["image_binding_modes"]["homeassistant"] = "dynamic"
    target = make_release(target_material)

    plan = build_upgrade_plan(current, target)

    assert plan["component_actions"] == {
        "manager": "KEEP",
        "homeassistant": "KEEP",
        "broker": "KEEP",
    }
    assert plan["runtime_contract_action"] == "UPDATE"


def test_target_version_must_advance() -> None:
    current = make_release(material("1.0.0"))
    target_material = copy.deepcopy(material("1.0.0"))
    target_material["components"]["homeassistant"]["identity"]["sha256"] = "6" * 64
    target = make_release(target_material)

    with pytest.raises(StackReleaseError, match="target_stack_version_not_greater"):
        build_upgrade_plan(current, target)


def test_empty_version_bump_is_rejected() -> None:
    current = make_release(material("1.0.0"))
    target = make_release(material("1.0.1"))

    with pytest.raises(StackReleaseError, match="empty_stack_upgrade"):
        build_upgrade_plan(current, target)


@pytest.mark.parametrize("version", ["1.0", "01.0.0", "1.0.0-rc1", "v1.0.0"])
def test_stack_version_is_strict_semver(version: str) -> None:
    with pytest.raises(StackReleaseError, match="stack_version_invalid"):
        make_release(material(version))
