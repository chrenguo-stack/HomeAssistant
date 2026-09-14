#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shlex, subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"

DEPLOYED_MANAGER_SOURCE = "8fbedc7e0778ce91d146cd5f0772bebdd20ad13a"
ID22_PACKAGE_COMMIT = "23b3dc63dc112979a8e94928185daf8af2da6640"
ID22R2_AUTHORIZATION = "N3W_KF089_ID22_T1_RELAY_INGRESS_CONFIRMATION_20260913_22R2"
MANAGER_NAME = "greenhouse-manager"
MANAGER_IMAGE_PREFIX = "greenhouse-manager:"
BROKER_SERVICE = "broker"
BROKER_PROJECT = "n3wfc4"
ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
PLACEHOLDERS = ("你的", "t1_ssh_target", "placeholder", "example", "<", ">")

class StopExecution(RuntimeError):
    def __init__(self, operation: str, reason: str):
        super().__init__(reason); self.operation = operation; self.reason = reason

def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="backslashreplace")

def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def git_text(args: list[str]) -> str:
    p = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, check=False)
    if p.returncode:
        raise StopExecution("HOST_PREFLIGHT", decode(p.stderr).strip() or f"git {' '.join(args)} failed")
    return decode(p.stdout).strip()

def run_op(root: Path, index: int, name: str, argv: list[str]) -> tuple[int, str, str]:
    d = root / f"op_{index:02d}_{name}"
    d.mkdir(parents=True, exist_ok=False)
    dump(d / "command.json", {"argv": argv})
    p = subprocess.run(argv, capture_output=True, check=False)
    out, err = decode(p.stdout), decode(p.stderr)
    (d / "stdout.txt").write_text(out, encoding="utf-8")
    (d / "stderr.txt").write_text(err, encoding="utf-8")
    dump(d / "result.json", {"returncode": p.returncode, "stdout_bytes": len(p.stdout), "stderr_bytes": len(p.stderr)})
    return p.returncode, out, err

def ssh_op(root: Path, index: int, name: str, target: str, command: str) -> tuple[int, str, str]:
    return run_op(root, index, name, [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1", target, command
    ])

def require_ok(result: tuple[int, str, str], op: str, message: str) -> str:
    rc, out, err = result
    if rc:
        raise StopExecution(op, f"{message}: {(err.strip() or out.strip() or 'rc='+str(rc))[:800]}")
    return out

def validate_target(target: str) -> None:
    if not target or target.strip() != target or any(c.isspace() for c in target):
        raise StopExecution("HOST_PREFLIGHT", "T1 SSH target is empty or contains whitespace")
    folded = target.casefold()
    if any(marker.casefold() in folded for marker in PLACEHOLDERS):
        raise StopExecution("HOST_PREFLIGHT", "T1 SSH target looks like documentation placeholder")
    try: target.encode("ascii")
    except UnicodeEncodeError as exc:
        raise StopExecution("HOST_PREFLIGHT", "T1 SSH target must be ASCII") from exc

def validate_output_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise StopExecution("HOST_PREFLIGHT", "evidence root exists and is non-empty")
    root.mkdir(parents=True, exist_ok=True)

def source_contract_check() -> dict[str, str]:
    refs = {
        "service_identity_plan": ("host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py",
                                  "8d90ed70b5598db475b4b40f7243c2186b742e68"),
        "node_dynsec_plan": ("host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_plan.py",
                             "380516ec03c68e055ef06375c36c11686f24a1bb"),
        "simplified_service": ("host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_isolated_mqtt_service.py",
                               "2a478300e66bed341f55b44e629c24847128f413"),
    }
    observed = {}
    for key, (path, expected) in refs.items():
        blob = git_text(["rev-parse", f"{DEPLOYED_MANAGER_SOURCE}:{path}"])
        if blob != expected: raise StopExecution("HOST_PREFLIGHT", f"{key} blob drift")
        observed[key] = blob
    manager_plan = git_text(["show", f"{DEPLOYED_MANAGER_SOURCE}:{refs['service_identity_plan'][0]}"])
    node_plan = git_text(["show", f"{DEPLOYED_MANAGER_SOURCE}:{refs['node_dynsec_plan'][0]}"])
    service = git_text(["show", f"{DEPLOYED_MANAGER_SOURCE}:{refs['simplified_service'][0]}"])
    if "ingress/gateway/+/+/frame" not in service:
        raise StopExecution("HOST_PREFLIGHT", "deployed Manager source lacks Relay subscription")
    if "ingress/gateway/" in manager_plan:
        raise StopExecution("HOST_PREFLIGHT", "deployed Manager identity plan unexpectedly grants gateway ingress")
    if 'relay_ingress = f"gh/v1/{system_id}/ingress/gateway/{node_id}/#"' not in node_plan:
        raise StopExecution("HOST_PREFLIGHT", "deployed node plan lacks self gateway publish ACL")
    return observed

def bind_id22(root: Path) -> tuple[str, str]:
    p = root / "closure.json"
    if not p.is_file(): raise StopExecution("ID22R2_EVIDENCE_BINDING", "closure.json missing")
    try: c = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc: raise StopExecution("ID22R2_EVIDENCE_BINDING", f"closure parse failed: {exc}") from exc
    expected = {
        "authorization": ID22R2_AUTHORIZATION,
        "execution_package_commit": ID22_PACKAGE_COMMIT,
        "first_failed_operation": "T1_MANAGER_RELAY_ACCEPTANCE",
        "replay_permitted": False,
        "board_side_relay_chain_proven_in_id22_session": True,
    }
    for k, v in expected.items():
        if c.get(k) != v: raise StopExecution("ID22R2_EVIDENCE_BINDING", f"closure mismatch: {k}")
    a = (((c.get("board_relay_phase") or {}).get("board_a") or {}).get("compact_counters") or {})
    if int(a.get("compact_forward_submit_success", 0)) < 1:
        raise StopExecution("ID22R2_EVIDENCE_BINDING", "Board A forward submit success not proven")
    w = c.get("t1_window") or {}
    if w.get("manager_accepted_relay_count") != 0 or w.get("manager_rejected_relay_count") != 0:
        raise StopExecution("ID22R2_EVIDENCE_BINDING", "unexpected ID22R2 Manager window counts")
    def timestamp(pattern: str) -> str:
        files = list(root.glob(pattern))
        if len(files) != 1: raise StopExecution("ID22R2_EVIDENCE_BINDING", f"timestamp evidence count !=1 for {pattern}")
        found = ISO_RE.findall(files[0].read_text(encoding="utf-8", errors="backslashreplace"))
        if len(found) != 1: raise StopExecution("ID22R2_EVIDENCE_BINDING", f"UTC timestamp count !=1 in {files[0].name}")
        return found[0]
    start = timestamp("op_*_t1_relay_window_start_utc/stdout.txt")
    end = timestamp("op_*_t1_relay_window_end_utc/stdout.txt")
    if start >= end: raise StopExecution("ID22R2_EVIDENCE_BINDING", "window start >= end")
    return start, end

def parse_inventory(raw: str) -> list[dict[str, Any]]:
    try: value = json.loads(raw)
    except Exception as exc: raise StopExecution("T1_RUNTIME_PRECLAIM", f"inspect JSON invalid: {exc}") from exc
    if not isinstance(value, list): raise StopExecution("T1_RUNTIME_PRECLAIM", "inspect root is not list")
    return [x for x in value if isinstance(x, dict)]

def bind_runtime(items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    managers, brokers = [], []
    for x in items:
        config = x.get("Config") if isinstance(x.get("Config"), dict) else {}
        labels = config.get("Labels") if isinstance(config.get("Labels"), dict) else {}
        host = x.get("HostConfig") if isinstance(x.get("HostConfig"), dict) else {}
        state = x.get("State") if isinstance(x.get("State"), dict) else {}
        if (str(x.get("Name") or "").lstrip("/") == MANAGER_NAME
            and str(config.get("Image") or "").startswith(MANAGER_IMAGE_PREFIX)
            and labels.get("org.opencontainers.image.revision") == DEPLOYED_MANAGER_SOURCE
            and host.get("NetworkMode") == "host" and state.get("Running") is True):
            managers.append(x)
        if (labels.get("com.docker.compose.service") == BROKER_SERVICE
            and labels.get("com.docker.compose.project") == BROKER_PROJECT
            and state.get("Running") is True):
            brokers.append(x)
    if len(managers) != 1: raise StopExecution("T1_RUNTIME_PRECLAIM", f"Manager count={len(managers)}, expected 1")
    if len(brokers) != 1: raise StopExecution("T1_RUNTIME_PRECLAIM", f"Broker count={len(brokers)}, expected 1")
    return managers[0], brokers[0]

def dynsec_path(conf: str) -> str:
    plugin = False; paths = []
    for raw in conf.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        if line.startswith(("plugin ", "global_plugin ")) and "dynamic_security" in line: plugin = True
        if line.startswith("plugin_opt_config_file "): paths.append(line.split(None, 1)[1].strip())
    unique = sorted(set(paths))
    if not plugin or len(unique) != 1 or not unique[0].startswith("/"):
        raise StopExecution("T1_DYNSEC_CONFIG", f"cannot derive active DynSec path: plugin={plugin} paths={unique}")
    return unique[0]

def role_names(client: dict[str, Any]) -> list[str]:
    out = []
    for x in client.get("roles") or []:
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict) and isinstance(x.get("rolename"), str): out.append(x["rolename"])
    return out

def analyze_dynsec(raw: str) -> dict[str, Any]:
    try: value = json.loads(raw)
    except Exception as exc: raise StopExecution("T1_DYNSEC_STATE", f"DynSec JSON invalid: {exc}") from exc
    if not isinstance(value, dict): raise StopExecution("T1_DYNSEC_STATE", "DynSec root not object")
    clients = [x for x in (value.get("clients") or []) if isinstance(x, dict)]
    roles_list = [x for x in (value.get("roles") or []) if isinstance(x, dict)]
    roles = {x.get("rolename"): x for x in roles_list if isinstance(x.get("rolename"), str)}
    managers = []
    for client in clients:
        cid, user = client.get("clientid"), client.get("username")
        sid = None
        if isinstance(cid, str) and cid.startswith("gh-manager-"): sid = cid[len("gh-manager-"):]
        elif isinstance(user, str) and user.startswith("ghs_") and user.endswith("_manager"): sid = user[4:-8]
        if sid: managers.append((client, sid))
    if len(managers) != 1: raise StopExecution("T1_DYNSEC_STATE", f"Manager DynSec client count={len(managers)}")
    manager, sid = managers[0]
    def acls(client: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        for name in role_names(client):
            r = roles.get(name)
            if isinstance(r, dict):
                result.extend(x for x in (r.get("acls") or []) if isinstance(x, dict))
        return result
    def allows(items: list[dict[str, Any]], acltype: str, candidates: set[str]) -> list[str]:
        return [str(x["topic"]) for x in items if x.get("acltype") == acltype and x.get("allow") is True and x.get("topic") in candidates]
    prefix = f"gh/v1/{sid}/ingress/gateway/"
    expected = f"{prefix}+/+/frame"
    broad = {expected, f"{prefix}#", f"gh/v1/{sid}/ingress/#", f"gh/v1/{sid}/#", "gh/#", "#"}
    manager_acls = acls(manager)
    sub = allows(manager_acls, "subscribePattern", broad)
    recv = allows(manager_acls, "publishClientReceive", broad)
    defaults = value.get("defaultACLAccess")
    if not isinstance(defaults, dict): raise StopExecution("T1_DYNSEC_STATE", "defaultACLAccess missing")
    default_sub_deny = defaults.get("subscribe") is False
    default_recv_deny = defaults.get("publishClientReceive") is False
    nodes = [x for x in clients if isinstance(x.get("username"), str) and str(x["username"]).startswith("ghn_")
             and isinstance(x.get("clientid"), str) and x.get("clientid")]
    node_ok = 0
    for client in nodes:
        nid = str(client["clientid"])
        allowed = allows(acls(client), "publishClientSend", {
            f"gh/v1/{sid}/ingress/gateway/{nid}/#", f"{prefix}#",
            f"gh/v1/{sid}/ingress/#", f"gh/v1/{sid}/#", "gh/#", "#"})
        node_ok += bool(allowed)
    defect = default_sub_deny and default_recv_deny and not sub and not recv
    return {
        "manager_client_id": manager.get("clientid"),
        "manager_role_names": role_names(manager),
        "default_subscribe_deny": default_sub_deny,
        "default_publish_client_receive_deny": default_recv_deny,
        "manager_relay_subscribe_allow_count": len(sub),
        "manager_relay_receive_allow_count": len(recv),
        "manager_relay_subscribe_allow_topics": sub,
        "manager_relay_receive_allow_topics": recv,
        "node_client_count": len(nodes),
        "node_self_gateway_publish_allow_count": node_ok,
        "live_manager_relay_dynsec_source_defect": defect,
    }

def log_summary(text: str) -> dict[str, int]:
    lines = text.splitlines()
    gateway = sum("ingress/gateway/" in x for x in lines)
    denial = sum(any(k in x.casefold() for k in ("not authorized", "not authorised", "acl", "denied", "permission")) for x in lines)
    return {"line_count": len(lines), "gateway_line_count": gateway, "acl_or_denial_line_count": denial}

def self_check() -> None:
    m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if m.get("gate_id") != "id23_t1_dynsec_relay_acl_readonly_forensic": raise SystemExit("manifest gate mismatch")
    if m.get("authority_references", {}).get("deployed_manager_source") != DEPLOYED_MANAGER_SOURCE: raise SystemExit("source mismatch")
    source_contract_check()
    print(json.dumps({"self_check": "PASS"}, sort_keys=True))

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-check", action="store_true")
    for name in ("expected-package-commit", "authorization-id", "execution-id", "evidence-root", "t1-ssh-target", "id22r2-evidence-root"):
        p.add_argument(f"--{name}")
    a = p.parse_args()
    if a.self_check: self_check(); return 0
    if any(not getattr(a, name.replace("-", "_")) for name in ("expected-package-commit","authorization-id","execution-id","evidence-root","t1-ssh-target","id22r2-evidence-root")):
        p.error("all execution arguments are required")
    root = Path(a.evidence_root).expanduser().resolve()
    closure: dict[str, Any] = {
        "authorization": a.authorization_id, "authorization_claimed": False, "authorization_consumed": False,
        "execution_id": a.execution_id, "execution_package_commit": a.expected_package_commit, "replay_permitted": False,
        "t1_access_occurred": False, "board_a_physical_access": False, "board_b_physical_access": False,
        "controlled_rf_experiment": False, "t1_file_write": False, "t1_docker_mutation": False,
        "t1_network_mutation": False, "mqtt_test_publish": False, "mqtt_extra_subscriber": False,
        "forensic_result": "STOP", "first_failed_operation": None, "stop_reason": None,
        "live_t1_manager_dynsec_role_matches_source_defect": "NOT_PROVEN",
        "live_t1_node_gateway_publish_acl": "NOT_PROVEN", "broker_window_acl_evidence": "NOT_PROVEN",
        "kf089_end_to_end_relay_telemetry": "NOT_PROVEN", "next_route": "STOP_RETURN_TO_HIGH_LEVEL_MODEL",
    }
    try:
        validate_target(a.t1_ssh_target); validate_output_root(root)
        head = git_text(["rev-parse", "HEAD"])
        if head != a.expected_package_commit: raise StopExecution("HOST_PREFLIGHT", f"HEAD {head} != expected")
        if git_text(["status", "--porcelain", "--untracked-files=no"]): raise StopExecution("HOST_PREFLIGHT", "tracked worktree dirty")
        blobs = source_contract_check()
        start, end = bind_id22(Path(a.id22r2_evidence_root).expanduser().resolve())
        dump(root / "host_preflight_private.json", {"head": head, "source_blobs": blobs, "id22r2_window_start": start, "id22r2_window_end": end})
        dump(root / "authorization.json", {"authorization": a.authorization_id, "claimed": False, "consumed": False, "replay_permitted": False})
        closure["authorization_claimed"] = closure["authorization_consumed"] = True
        dump(root / "authorization.json", {"authorization": a.authorization_id, "claimed": True, "consumed": True, "replay_permitted": False})
        closure["t1_access_occurred"] = True

        ids = require_ok(ssh_op(root,1,"t1_container_ids",a.t1_ssh_target,"docker ps -aq --no-trunc"),
                         "T1_RUNTIME_PRECLAIM","cannot enumerate containers")
        ids = [x.strip() for x in ids.splitlines() if x.strip()]
        if not ids: raise StopExecution("T1_RUNTIME_PRECLAIM","container inventory empty")
        inspect = require_ok(ssh_op(root,2,"t1_container_inspect",a.t1_ssh_target,
                                    "docker inspect " + " ".join(shlex.quote(x) for x in ids)),
                             "T1_RUNTIME_PRECLAIM","cannot inspect containers")
        manager, broker = bind_runtime(parse_inventory(inspect))
        broker_id = str(broker.get("Id") or "")
        if not broker_id: raise StopExecution("T1_RUNTIME_PRECLAIM","Broker ID missing")

        conf = require_ok(ssh_op(root,3,"broker_mosquitto_conf",a.t1_ssh_target,
                                 f"docker exec {shlex.quote(broker_id)} sh -c 'cat /mosquitto/config/mosquitto.conf'"),
                          "T1_DYNSEC_CONFIG","cannot read mosquitto.conf")
        path = dynsec_path(conf)
        raw = require_ok(ssh_op(root,4,"broker_dynamic_security_json",a.t1_ssh_target,
                                f"docker exec {shlex.quote(broker_id)} cat {shlex.quote(path)}"),
                         "T1_DYNSEC_STATE","cannot read Dynamic Security JSON")
        analysis = analyze_dynsec(raw); dump(root / "dynsec_analysis_private.json", analysis)

        logs = require_ok(ssh_op(root,5,"broker_id22r2_window_logs",a.t1_ssh_target,
                                 "docker logs --timestamps --since " + shlex.quote(start) + " --until " + shlex.quote(end) + " " + shlex.quote(broker_id)),
                          "T1_BROKER_WINDOW_LOGS","cannot read bounded Broker logs")
        summary = log_summary(logs); dump(root / "broker_window_summary_private.json", summary)

        defect = bool(analysis["live_manager_relay_dynsec_source_defect"])
        n = int(analysis["node_client_count"]); n_ok = int(analysis["node_self_gateway_publish_allow_count"])
        closure.update({
            "live_t1_manager_dynsec_role_matches_source_defect": "PROVEN" if defect else "NOT_PROVEN",
            "live_t1_node_gateway_publish_acl": "PROVEN_FOR_ALL_NODE_CLIENTS" if n and n == n_ok else "PARTIAL_OR_NOT_PROVEN",
            "manager_relay_subscribe_allow_count": analysis["manager_relay_subscribe_allow_count"],
            "manager_relay_receive_allow_count": analysis["manager_relay_receive_allow_count"],
            "dynsec_default_subscribe_deny": analysis["default_subscribe_deny"],
            "dynsec_default_publish_client_receive_deny": analysis["default_publish_client_receive_deny"],
            "node_client_count": n, "node_self_gateway_publish_allow_count": n_ok,
            "broker_window_gateway_log_count": summary["gateway_line_count"],
            "broker_window_acl_or_denial_log_count": summary["acl_or_denial_line_count"],
            "broker_window_acl_evidence": "OBSERVED" if summary["gateway_line_count"] or summary["acl_or_denial_line_count"] else "NO_RELEVANT_LINE_OBSERVED",
            "forensic_result": "PASS",
            "root_cause": "MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING" if defect else "NOT_PROVEN_BY_ID23",
            "next_route": "PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE" if defect else "PREPARE_KF089_BROKER_RELAY_INGRESS_DEEPER_FORENSIC_PACKAGE",
        })
    except StopExecution as exc:
        closure["first_failed_operation"], closure["stop_reason"] = exc.operation, exc.reason
    except Exception as exc:
        closure["first_failed_operation"], closure["stop_reason"] = "UNEXPECTED_EXCEPTION", f"{type(exc).__name__}: {exc}"
    if root.exists(): dump(root / "closure.json", closure)
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["forensic_result"] == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
