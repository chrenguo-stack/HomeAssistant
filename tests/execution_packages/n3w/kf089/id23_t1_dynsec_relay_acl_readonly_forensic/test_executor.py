from __future__ import annotations
import importlib.util
import json
from pathlib import Path

EXECUTOR = Path(__file__).resolve().parents[5] / "tools/execution_packages/n3w/kf089/id23_t1_dynsec_relay_acl_readonly_forensic/executor.py"
spec = importlib.util.spec_from_file_location("id23_executor", EXECUTOR)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def dynsec(manager_gateway: bool = False, node_gateway: bool = True):
    sid = "greenhouse"
    manager_acls = [
        {"acltype":"subscribePattern","topic":f"gh/v1/{sid}/ingress/node/+/telemetry","allow":True,"priority":100},
        {"acltype":"publishClientReceive","topic":f"gh/v1/{sid}/ingress/node/+/telemetry","allow":True,"priority":100},
    ]
    if manager_gateway:
        manager_acls += [
            {"acltype":"subscribePattern","topic":f"gh/v1/{sid}/ingress/gateway/+/+/frame","allow":True,"priority":100},
            {"acltype":"publishClientReceive","topic":f"gh/v1/{sid}/ingress/gateway/+/+/frame","allow":True,"priority":100},
        ]
    node_acls = []
    if node_gateway:
        node_acls.append({"acltype":"publishClientSend","topic":f"gh/v1/{sid}/ingress/gateway/node_a/#","allow":True,"priority":100})
    return {
        "defaultACLAccess":{"publishClientSend":False,"publishClientReceive":False,"subscribe":False,"unsubscribe":True},
        "clients":[
            {"username":"ghs_greenhouse_manager","clientid":"gh-manager-greenhouse","roles":[{"rolename":"manager"}]},
            {"username":"ghn_node_a","clientid":"node_a","roles":[{"rolename":"node_a_role"}]},
        ],
        "roles":[
            {"rolename":"manager","acls":manager_acls},
            {"rolename":"node_a_role","acls":node_acls},
        ],
    }

def test_live_defect_detected():
    result = mod.analyze_dynsec(json.dumps(dynsec()))
    assert result["live_manager_relay_dynsec_source_defect"] is True
    assert result["manager_relay_subscribe_allow_count"] == 0
    assert result["manager_relay_receive_allow_count"] == 0
    assert result["node_client_count"] == 1
    assert result["node_self_gateway_publish_allow_count"] == 1

def test_live_relay_acl_present_not_defect():
    result = mod.analyze_dynsec(json.dumps(dynsec(manager_gateway=True)))
    assert result["live_manager_relay_dynsec_source_defect"] is False
    assert result["manager_relay_subscribe_allow_count"] == 1
    assert result["manager_relay_receive_allow_count"] == 1

def test_node_gateway_acl_missing_is_visible():
    result = mod.analyze_dynsec(json.dumps(dynsec(node_gateway=False)))
    assert result["node_self_gateway_publish_allow_count"] == 0

def test_dynsec_path_derivation():
    conf = """
listener 8883
plugin /usr/lib/mosquitto_dynamic_security.so
plugin_opt_config_file /mosquitto/data/dynamic-security.json
"""
    assert mod.dynsec_path(conf) == "/mosquitto/data/dynamic-security.json"

def test_log_summary():
    summary = mod.log_summary("x ingress/gateway/a/b/frame\nACL denied\n")
    assert summary["gateway_line_count"] == 1
    assert summary["acl_or_denial_line_count"] == 1

def test_placeholder_target_rejected():
    try:
        mod.validate_target("你的T1_SSH_TARGET")
    except mod.StopExecution as exc:
        assert exc.operation == "HOST_PREFLIGHT"
    else:
        raise AssertionError("placeholder target accepted")
