from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[5]
    / "tools/execution_packages/n3w/kf089/"
    "id24r1_t1_dynsec_state_readonly_recovery/executor.py"
)
SPEC = importlib.util.spec_from_file_location("id24r1_executor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
executor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(executor)


def runtime_env() -> dict[str, str]:
    return {
        "GH_MQTT_USERNAME": "ghs_greenhouse_manager",
        "GH_MQTT_CLIENT_ID": "gh-manager-greenhouse",
    }


def dynsec_document(*, repaired: bool = False, broad: bool = False) -> str:
    relay = "gh/v1/greenhouse/ingress/gateway/+/+/frame"
    direct = "gh/v1/greenhouse/ingress/node/+/telemetry"
    acls = [
        {
            "acltype": acl_type,
            "topic": direct,
            "allow": True,
            "priority": 100,
        }
        for acl_type in executor.id24.TARGET_ACL_TYPES
    ]
    if repaired:
        acls.extend(
            {
                "acltype": acl_type,
                "topic": relay,
                "allow": True,
                "priority": 100,
            }
            for acl_type in executor.id24.TARGET_ACL_TYPES
        )
    if broad:
        acls.append(
            {
                "acltype": "subscribePattern",
                "topic": "gh/v1/greenhouse/ingress/gateway/#",
                "allow": True,
                "priority": 100,
            }
        )
    return json.dumps(
        {
            "defaultACLAccess": {
                "publishClientSend": False,
                "publishClientReceive": False,
                "subscribe": False,
                "unsubscribe": True,
            },
            "clients": [
                {
                    "username": "ghs_greenhouse_manager",
                    "clientid": "gh-manager-greenhouse",
                    "roles": [{"rolename": "gh-service-greenhouse-manager"}],
                }
            ],
            "roles": [
                {
                    "rolename": "gh-service-greenhouse-manager",
                    "acls": acls,
                }
            ],
        }
    )


def test_classifies_pre_repair_defect() -> None:
    analysis = executor.id24.analyze_dynsec(
        dynsec_document(),
        runtime_env(),
        require_defect=False,
    )
    assert executor.classify(analysis) == "PRE_REPAIR_DEFECT"
    assert analysis["relay_exact_count"] == 0


def test_classifies_exact_repaired_state() -> None:
    analysis = executor.id24.analyze_dynsec(
        dynsec_document(repaired=True),
        runtime_env(),
        require_defect=False,
    )
    assert executor.classify(analysis) == "EXACT_REPAIRED"
    assert analysis["relay_exact_count"] == 3


def test_classifies_broader_grant_as_partial_or_drift() -> None:
    analysis = executor.id24.analyze_dynsec(
        dynsec_document(repaired=True, broad=True),
        runtime_env(),
        require_defect=False,
    )
    assert executor.classify(analysis) == "PARTIAL_OR_DRIFT"


def test_sanitized_analysis_excludes_private_identity_fields() -> None:
    analysis = executor.id24.analyze_dynsec(
        dynsec_document(),
        runtime_env(),
        require_defect=False,
    )
    public = executor.sanitized_analysis(analysis)
    assert "system_id" not in public
    assert "role_name" not in public
    assert "relay_topic" not in public


def test_executor_source_contains_no_live_mutation_callsite() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "mutation_started" not in source
    assert "mutate_add_" not in source
    assert "rollback_target_acls(" not in source
