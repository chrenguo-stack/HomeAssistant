#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
SSH_TRANSPORT_PATH = REPO_ROOT / "tools/n3w_t1_ssh_transport.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "USB_CONFIRMATION_U2_FRESH_READONLY_BASELINE_20261110_01"
)

REMOTE_SCRIPT = r"""
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
PREPARE_SCHEMA = "gh.n3w-t1-ha-usb-prepare-state/1"
IPC_RESPONSE_V3 = "gh.n3w-t1-ha-ota-ipc-response/3"
USB_FLOOR_BYTES = 14 * 1024**3


class Stop(RuntimeError):
    pass


def run(argv, *, check=True, timeout=90):
    result = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise Stop("command_failed:" + Path(argv[0]).name + ":" + str(result.returncode))
    return result


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_private_regular(path, mode=0o600):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise Stop("file_invalid:" + str(p))
    meta = p.stat()
    if meta.st_uid != 0 or stat.S_IMODE(meta.st_mode) != mode:
        raise Stop("file_metadata_invalid:" + str(p))


def read_private_json(path, schema):
    path = Path(path)
    require_private_regular(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("json_invalid:" + path.name) from error
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise Stop("json_schema_invalid:" + path.name)
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def stable_fingerprint(node):
    serial = (
        node["serial"].strip()
        if isinstance(node.get("serial"), str) and node["serial"].strip()
        else None
    )
    wwn = (
        node["wwn"].strip()
        if isinstance(node.get("wwn"), str) and node["wwn"].strip()
        else None
    )
    if serial is None and wwn is None:
        raise Stop("usb_stable_identity_unavailable")
    identity = {
        "serial": serial,
        "wwn": wwn,
        "model": str(node.get("model") or "").strip(),
        "size": node.get("size"),
        "transport": str(node.get("tran") or "").strip().lower(),
    }
    return hashlib.sha256(canonical(identity)).hexdigest()


def boolish(value):
    if value in (1, "1", True):
        return True
    if value in (0, "0", False, None, ""):
        return False
    raise Stop("usb_boolean_invalid")


def mountpoints(node):
    value = node.get("mountpoints")
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str) and item.strip())
    value = node.get("mountpoint")
    if isinstance(value, str) and value.strip():
        return (value,)
    return ()


def flatten(nodes):
    out = []
    stack = list(nodes)
    while stack:
        item = stack.pop()
        if not isinstance(item, dict):
            continue
        out.append(item)
        children = item.get("children")
        if isinstance(children, list):
            stack.extend(children)
    return out


def usb_inventory():
    root_mm = run(
        ["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"],
        timeout=30,
    ).stdout.strip()
    if not root_mm:
        raise Stop("usb_root_device_unresolved")
    raw = run(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--paths",
            "--output",
            "PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,MAJ:MIN",
        ],
        timeout=30,
    ).stdout
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Stop("usb_inventory_invalid") from error
    blocks = document.get("blockdevices")
    if not isinstance(blocks, list):
        raise Stop("usb_inventory_invalid")

    result = []
    for disk in blocks:
        if not isinstance(disk, dict) or disk.get("type") != "disk":
            continue
        path = disk.get("path")
        if not isinstance(path, str) or not path.startswith("/dev/"):
            continue
        descendants = flatten([disk])
        major_minors = {
            str(item.get("maj:min") or "").strip()
            for item in descendants
        }
        transport = str(disk.get("tran") or "").strip().lower()
        removable = boolish(disk.get("rm"))
        if transport != "usb" and not removable:
            continue
        try:
            size = int(disk.get("size"))
        except (TypeError, ValueError):
            size = 0
        result.append(
            {
                "locator": path,
                "public_fingerprint": stable_fingerprint(disk),
                "display_model": str(disk.get("model") or "").strip()
                or "USB Mass Storage",
                "display_capacity_bytes": size,
                "removable": removable,
                "mass_storage": transport == "usb",
                "read_only": boolish(disk.get("ro")),
                "is_root_device": root_mm in major_minors,
                "backs_production_mount": any(
                    mountpoints(item) for item in descendants
                ),
            }
        )
    return result


def docker_one(image):
    ids = [
        line.strip()
        for line in run(
            [
                "docker",
                "ps",
                "--filter",
                "ancestor=" + image,
                "--format",
                "{{.ID}}",
            ],
            timeout=45,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + image + ":" + str(len(ids)))
    try:
        documents = json.loads(
            run(["docker", "inspect", ids[0]], timeout=45).stdout
        )
    except json.JSONDecodeError as error:
        raise Stop("container_inspect_invalid:" + image) from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + image)
    item = documents[0]
    if (
        not isinstance(item, dict)
        or item.get("Config", {}).get("Image") != image
        or item.get("State", {}).get("Status") != "running"
    ):
        raise Stop("container_state_invalid:" + image)
    return item


def env_map(document):
    result = {}
    for item in document.get("Config", {}).get("Env") or []:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def require_manager_ota_wiring(document):
    env = env_map(document)
    expected = {
        "GH_N3W_T1_OTA_ENABLED": "true",
        "GH_N3W_T1_OTA_INSTALLED_VERSION": "2026.10.0",
        "GH_N3W_T1_OTA_MANIFEST_PATH": "/run/n3w/t1-ota/approved-homeassistant.json",
        "GH_N3W_T1_OTA_SOCKET_PATH": "/run/n3w/t1-ota/ha-ota.sock",
    }
    for key, value in expected.items():
        if env.get(key) != value:
            raise Stop("manager_ota_env_drift:" + key)
    matches = [
        item
        for item in document.get("Mounts") or []
        if isinstance(item, dict)
        and item.get("Destination") == "/run/n3w/t1-ota"
    ]
    if (
        len(matches) != 1
        or matches[0].get("Type") != "bind"
        or matches[0].get("Source") != "/run/n3w-t1-ota"
        or matches[0].get("RW") is not False
    ):
        raise Stop("manager_ota_mount_drift")


def manager_ipc_probe(container_id):
    probe = (
        "import json,socket\n"
        "p='/run/n3w/t1-ota/ha-ota.sock'\n"
        "q=(json.dumps({'schema':'gh.n3w-t1-ha-ota-ipc-request/1',"
        "'operation':'status'},sort_keys=True,separators=(',',':')).encode()+b'\\n')\n"
        "s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);"
        "s.settimeout(5);s.connect(p);s.sendall(q);s.shutdown(socket.SHUT_WR)\n"
        "d=bytearray()\n"
        "while len(d)<=8192:\n"
        " b=s.recv(1024)\n"
        " if not b: break\n"
        " d.extend(b)\n"
        " if b'\\n' in d: break\n"
        "s.close();print(bytes(d).split(b'\\n',1)[0].decode())\n"
    )
    raw = run(
        [
            "docker",
            "exec",
            "-u",
            "999:999",
            container_id,
            "python3",
            "-c",
            probe,
        ],
        timeout=30,
    ).stdout.strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Stop("manager_ipc_v3_json_invalid") from error
    if not isinstance(value, dict):
        raise Stop("manager_ipc_v3_shape_invalid")
    return value


def baseline(plan):
    system_state = run(
        ["systemctl", "is-system-running"],
        check=False,
        timeout=30,
    ).stdout.strip()
    if system_state not in {"running", "degraded"}:
        raise Stop("system_state_invalid:" + system_state)

    unit_state = {}
    for unit in (SERVICES_UNIT, HOST_UNIT):
        state = run(
            ["systemctl", "is-active", unit],
            check=False,
            timeout=30,
        ).stdout.strip()
        unit_state[unit] = state
        if state != "active":
            raise Stop("required_unit_inactive:" + unit)

    manager = docker_one(plan["live"]["manager_image"])
    homeassistant = docker_one(plan["live"]["homeassistant_image"])
    broker = docker_one(plan["live"]["broker_image"])
    require_manager_ota_wiring(manager)

    for document, key, label in (
        (manager, "manager_runtime_image_id", "manager"),
        (homeassistant, "homeassistant_runtime_image_id", "homeassistant"),
        (broker, "broker_runtime_image_id", "broker"),
    ):
        if document.get("Image") != plan["live"][key]:
            raise Stop(label + "_runtime_image_drift")

    tx = read_private_json(TX_PATH, TX_SCHEMA)
    tx_sha = sha_file(TX_PATH)
    if tx_sha != plan["live"]["u1_transaction_sha256"]:
        raise Stop("u1_transaction_sha_drift")
    if (
        tx.get("phase") != "U1_PREPARE_REQUESTED"
        or tx.get("status") != "ACTIVE"
        or tx.get("authorization_claimed") is not False
        or tx.get("authorization_consumed") is not False
    ):
        raise Stop("u1_transaction_semantics_drift")
    transaction_id = tx.get("transaction_id_sha256")
    if (
        not isinstance(transaction_id, str)
        or len(transaction_id) != 64
        or any(
            character not in "0123456789abcdef"
            for character in transaction_id
        )
    ):
        raise Stop("u1_transaction_id_invalid")

    target_manifest_identity = tx.get("target_manifest_identity")
    if not isinstance(target_manifest_identity, dict):
        raise Stop("u1_target_manifest_identity_invalid")
    release_identity = target_manifest_identity.get("release_identity")
    if (
        not isinstance(release_identity, str)
        or not 3 <= len(release_identity) <= 128
        or any(character.isspace() for character in release_identity)
    ):
        raise Stop("u1_release_identity_invalid")

    for key in (
        "usb_device_identity_public_fingerprint",
        "usb_filesystem_uuid",
        "usb_mount_authority",
    ):
        if tx.get(key) is not None:
            raise Stop("u2_binding_present_in_u1:" + key)

    prep = read_private_json(PREPARE_PATH, PREPARE_SCHEMA)
    if prep.get("transaction_id_sha256") != transaction_id:
        raise Stop("prepare_transaction_binding_drift")
    if prep.get("release_identity") != release_identity:
        raise Stop("prepare_release_binding_drift")

    baseline_fingerprints = prep.get("baseline_public_fingerprints")
    if (
        not isinstance(baseline_fingerprints, list)
        or len(baseline_fingerprints) > 32
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(
                character not in "0123456789abcdef"
                for character in value
            )
            for value in baseline_fingerprints
        )
        or len(set(baseline_fingerprints)) != len(baseline_fingerprints)
    ):
        raise Stop("prepare_baseline_fingerprints_invalid")
    if (
        plan["live"]["usb_candidate_public_fingerprint"]
        in baseline_fingerprints
    ):
        raise Stop("prepare_candidate_not_fresh")

    candidate = prep.get("candidate")
    if not isinstance(candidate, dict):
        raise Stop("prepare_candidate_missing")
    expected_candidate = {
        "public_fingerprint": plan["live"]["usb_candidate_public_fingerprint"],
        "display_model": plan["live"]["usb_candidate_model"],
        "display_capacity_bytes": plan["live"]["usb_candidate_capacity_bytes"],
    }
    for key, expected in expected_candidate.items():
        if candidate.get(key) != expected:
            raise Stop("prepare_candidate_drift:" + key)
    if (
        prep.get("confirmation_required") is not True
        or prep.get("confirmation_consumed") is not False
    ):
        raise Stop("prepare_confirmation_state_drift")

    snapshot = prep.get("capacity_snapshot")
    if not isinstance(snapshot, dict):
        raise Stop("capacity_snapshot_missing")
    required_bytes = snapshot.get("usb_required_bytes")
    recommended_gb = snapshot.get("recommended_nominal_usb_gb")
    if (
        type(required_bytes) is not int
        or required_bytes <= 0
        or type(recommended_gb) is not int
        or recommended_gb <= 0
    ):
        raise Stop("capacity_snapshot_invalid")
    if plan["live"]["usb_candidate_capacity_bytes"] < max(
        USB_FLOOR_BYTES,
        required_bytes,
    ):
        raise Stop("candidate_capacity_not_plausible")

    inventory = usb_inventory()
    eligible = [
        item
        for item in inventory
        if item["removable"]
        and item["mass_storage"]
        and not item["read_only"]
        and not item["is_root_device"]
        and not item["backs_production_mount"]
    ]
    if len(eligible) != 1:
        raise Stop(
            "usb_eligible_candidate_cardinality:" + str(len(eligible))
        )
    observed = eligible[0]
    for key, expected in expected_candidate.items():
        if observed.get(key) != expected:
            raise Stop("usb_physical_candidate_drift:" + key)

    source_hashes = {}
    for item in plan["remote_authority"]:
        path = Path(item["remote_path"])
        if path.is_symlink() or not path.is_file():
            raise Stop(
                "remote_authority_file_invalid:" + item["repo_path"]
            )
        observed_sha = sha_file(path)
        if observed_sha != item["sha256"]:
            raise Stop("remote_authority_drift:" + item["repo_path"])
        source_hashes[item["repo_path"]] = observed_sha

    ipc = manager_ipc_probe(manager["Id"])
    ipc_candidate = ipc.get("usb_candidate")
    if (
        ipc.get("schema") != IPC_RESPONSE_V3
        or ipc.get("accepted") is not True
        or ipc.get("phase") != "USB_REQUIRED_CONFIRMATION"
        or ipc.get("usb_confirmation_required") is not True
        or not isinstance(ipc_candidate, dict)
        or ipc_candidate.get("public_fingerprint")
        != plan["live"]["usb_candidate_public_fingerprint"]
        or ipc_candidate.get("display_model")
        != plan["live"]["usb_candidate_model"]
        or ipc_candidate.get("display_capacity_bytes")
        != plan["live"]["usb_candidate_capacity_bytes"]
        or ipc.get("usb_capacity_check_state")
        != "CANDIDATE_READY_FOR_CONFIRMATION"
        or ipc.get("user_message_code_or_null") != "USB_CONFIRM_ERASE"
        or ipc.get("usb_required_bytes_or_null") != required_bytes
        or ipc.get("usb_recommended_nominal_gb_or_null") != recommended_gb
    ):
        raise Stop("manager_ipc_v3_validation_failed")

    def container_view(document):
        state = document.get("State") or {}
        return {
            "container_id": document.get("Id"),
            "runtime_image_id": document.get("Image"),
            "restart_count": document.get("RestartCount"),
            "started_at": state.get("StartedAt"),
            "status": state.get("Status"),
        }

    return {
        "schema":
            "gh.n3w-t1-kf147-usb-u2-readonly-baseline-result/1",
        "status": "PASS",
        "read_only": True,
        "mutation": False,
        "system_state": system_state,
        "units": unit_state,
        "manager": container_view(manager),
        "homeassistant": container_view(homeassistant),
        "broker": container_view(broker),
        "u1_transaction_sha256": tx_sha,
        "transaction_id_sha256": transaction_id,
        "transaction_phase": tx.get("phase"),
        "transaction_status": tx.get("status"),
        "release_identity": release_identity,
        "prepare_sha256": sha_file(PREPARE_PATH),
        "prepare_release_identity": prep.get("release_identity"),
        "baseline_public_fingerprints": baseline_fingerprints,
        "candidate_fresh_relative_to_u1_baseline": True,
        "usb_candidate": expected_candidate,
        "usb_confirmation_required": True,
        "usb_confirmation_consumed": False,
        "capacity_snapshot": snapshot,
        "physical_usb_candidate": observed,
        "manager_ipc": ipc,
        "remote_authority_sha256": source_hashes,
        "u2_plus": False,
        "usb_mutation": False,
        "destructive_execution_ready": False,
    }


def main():
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {"status": "STOP", "reason": "arguments_invalid"}
            )
        )
        return 2
    try:
        plan = json.loads(
            __import__("base64").b64decode(sys.argv[1]).decode("utf-8")
        )
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
            "USB_CONFIRMATION_U2_FRESH_READONLY_BASELINE_20261110_01"
        ):
            raise Stop("gate_id_invalid")
        result = baseline(plan)
    except Exception as error:
        result = {
            "schema":
                "gh.n3w-t1-kf147-usb-u2-readonly-baseline-result/1",
            "status": "STOP",
            "read_only": True,
            "mutation": False,
            "reason":
                type(error).__name__ + ":" + str(error)[:240],
            "usb_mutation": False,
            "u2_plus": False,
            "destructive_execution_ready": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


raise SystemExit(main())
"""


class Stop(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop(
            f"local_command_failed:"
            f"{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed


def git_text(*args: str) -> str:
    return run(
        ["git", "-C", str(REPO_ROOT), *args],
        timeout=30,
    ).stdout.strip()


def sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise Stop(f"local_source_invalid:{path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest() -> dict[str, Any]:
    try:
        value = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )
    except Exception as error:
        raise Stop("manifest_invalid") from error
    if not isinstance(value, dict):
        raise Stop("manifest_invalid")
    return value


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if (
            root.is_symlink()
            or not root.is_dir()
            or any(root.iterdir())
        ):
            raise Stop("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    metadata = root.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise Stop("evidence_root_metadata_invalid")
    return root


def write_private(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def validate_local(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text(
        "status",
        "--porcelain",
        "--untracked-files=no",
    ):
        raise Stop("tracked_worktree_dirty")

    manifest = read_manifest()
    if (
        manifest.get("schema")
        != "gh.n3w-t1-kf147-usb-u2-readonly-baseline/1"
        or manifest.get("gate_id") != GATE_ID
        or manifest.get("mode") != "READ_ONLY"
    ):
        raise Stop("manifest_contract_invalid")

    contract = manifest.get("execution_contract")
    if (
        not isinstance(contract, dict)
        or contract.get("read_only") is not True
    ):
        raise Stop("manifest_execution_contract_invalid")
    for key in (
        "remote_write",
        "service_restart",
        "docker_mutation",
        "host_source_mutation",
        "usb_mutation",
        "u2_plus",
        "board_access",
        "merge",
    ):
        if contract.get(key) is not False:
            raise Stop(
                "manifest_mutation_contract_invalid:" + key
            )

    package_authority = manifest.get(
        "package_source_authority"
    )
    if not isinstance(package_authority, dict):
        raise Stop("package_source_authority_invalid")
    for relative, blob in package_authority.items():
        if (
            not isinstance(relative, str)
            or not isinstance(blob, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob) is None
            or git_text("rev-parse", f"HEAD:{relative}")
            != blob
        ):
            raise Stop(
                "package_source_authority_drift:"
                + str(relative)
            )

    remote_authority = manifest.get(
        "remote_source_authority"
    )
    if (
        not isinstance(remote_authority, dict)
        or not remote_authority
    ):
        raise Stop("remote_source_authority_invalid")
    for relative, authority in remote_authority.items():
        if (
            not isinstance(authority, dict)
            or set(authority) != {"blob", "remote_path"}
        ):
            raise Stop(
                "remote_source_authority_invalid:" + relative
            )
        blob = authority.get("blob")
        remote_path = authority.get("remote_path")
        if (
            not isinstance(blob, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob) is None
            or git_text("rev-parse", f"HEAD:{relative}")
            != blob
            or not isinstance(remote_path, str)
            or not remote_path.startswith("/")
        ):
            raise Stop(
                "remote_source_authority_drift:" + relative
            )
    return manifest


def build_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    remote_authority = []
    for relative, authority in (
        manifest["remote_source_authority"].items()
    ):
        remote_authority.append(
            {
                "repo_path": relative,
                "remote_path": authority["remote_path"],
                "sha256": sha_file(REPO_ROOT / relative),
            }
        )
    return {
        "gate_id": GATE_ID,
        "live": manifest["expected_live_entry"],
        "remote_authority": remote_authority,
    }


def load_transport() -> type:
    manifest = read_manifest()
    expected = manifest["package_source_authority"][
        "tools/n3w_t1_ssh_transport.py"
    ]
    if (
        git_text(
            "rev-parse",
            "HEAD:tools/n3w_t1_ssh_transport.py",
        )
        != expected
    ):
        raise Stop("ssh_transport_binding_invalid")
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_ssh_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def run_remote(
    transport: Any,
    plan: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-c", REMOTE_SCRIPT, payload],
        timeout=240,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("remote_result_json_invalid") from error
    if not isinstance(result, dict):
        raise Stop("remote_result_shape_invalid")
    return completed.returncode, result


def execute(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema":
            "gh.n3w-t1-kf147-usb-u2-readonly-local-result/1",
        "status": "STOP",
        "gate_id": GATE_ID,
        "read_only": True,
        "t1_access": False,
        "remote_write": False,
        "service_restart": False,
        "docker_mutation": False,
        "host_source_mutation": False,
        "usb_mutation": False,
        "u2_plus": False,
        "board_access": False,
        "merge": False,
        "destructive_execution_ready": False,
        "first_failed_operation": None,
    }
    transport = None
    try:
        manifest = validate_local(
            args.expected_package_commit
        )
        plan = build_plan(manifest)
        evidence_root = prepare_evidence_root(
            args.evidence_root
        )
        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=(
                args.expected_host_key_sha256
            ),
        )
        transport.start_epoch()
        result["t1_access"] = True

        remote_returncode, baseline = run_remote(
            transport,
            plan,
        )
        write_private(
            evidence_root / "fresh-readonly-baseline.json",
            baseline,
        )
        result["remote_returncode"] = remote_returncode
        if (
            remote_returncode != 0
            or baseline.get("status") != "PASS"
        ):
            result["first_failed_operation"] = (
                baseline.get("reason")
                or "fresh_readonly_baseline_stop"
            )
            return result

        result.update(
            {
                "status": "PASS",
                "fresh_t1_baseline_acquired": True,
                "baseline": baseline,
            }
        )
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__
            + ":"
            + str(error)[:240]
        )
        return result
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception:
                result["ssh_master_cleanup"] = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-package-commit",
        required=True,
    )
    parser.add_argument("--execution-id", required=True)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        required=True,
    )
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument(
        "--known-hosts",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--expected-host-key-sha256",
        required=True,
    )
    args = parser.parse_args()

    if not re.fullmatch(
        r"[A-Za-z0-9._-]{1,160}",
        args.execution_id,
    ):
        print(
            json.dumps(
                {
                    "status": "STOP",
                    "reason": "execution_id_invalid",
                }
            )
        )
        return 2

    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
