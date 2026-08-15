#!/usr/bin/env python3
"""Synthetic-only initializer for an S5 dedicated two-node Manager state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
from pathlib import Path

AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-DEDICATED-TWO-NODE-STATE-"
    "INITIALIZER-HOSTONLY-CONTRACT-AND-SYNTHETIC-VALIDATION-20260815-01"
)
INPUT_SCHEMA = "gh.n3w-product-s5-dedicated-two-node-state-synthetic/1"
SYNTHETIC_MARKER = "S5-SYNTHETIC-ONLY-NOT-REAL-CREDENTIALS"
RELAY_CAPABILITY = "n3w-product-relay"
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_HW = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")
_PAIR = re.compile(r"^[A-Za-z0-9_-]{3,96}$")
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class SyntheticStateError(RuntimeError):
    pass


def private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, exist_ok=False)
    os.chmod(path, 0o700)


def write_json(path: Path, value: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True, indent=2)
        out.write("\n")


def validate_node(raw: object, role: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise SyntheticStateError(f"{role}_object_required")
    fields = {
        "role", "hardware_id", "pairing_id", "pairing_epoch", "node_id",
        "credential_generation", "key_epoch", "application_key_hex",
        "local_mac", "capabilities",
    }
    if set(raw) != fields or raw.get("role") != role:
        raise SyntheticStateError(f"{role}_fields_invalid")
    if not isinstance(raw["hardware_id"], str) or not _HW.fullmatch(raw["hardware_id"]):
        raise SyntheticStateError(f"{role}_hardware_id_invalid")
    if not isinstance(raw["pairing_id"], str) or not _PAIR.fullmatch(raw["pairing_id"]):
        raise SyntheticStateError(f"{role}_pairing_id_invalid")
    if not isinstance(raw["node_id"], str) or not _ID.fullmatch(raw["node_id"]):
        raise SyntheticStateError(f"{role}_node_id_invalid")
    for field in ("pairing_epoch", "credential_generation", "key_epoch"):
        value = raw[field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise SyntheticStateError(f"{role}_{field}_invalid")
    if raw["credential_generation"] != raw["pairing_epoch"]:
        raise SyntheticStateError(f"{role}_credential_generation_pairing_epoch_mismatch")
    caps = raw["capabilities"]
    if not isinstance(caps, list) or not caps or any(not isinstance(x, str) or not x for x in caps):
        raise SyntheticStateError(f"{role}_capabilities_invalid")
    if len(set(caps)) != len(caps) or RELAY_CAPABILITY not in caps:
        raise SyntheticStateError(f"{role}_relay_capability_missing")
    mac = raw["local_mac"]
    if not isinstance(mac, str) or not _MAC.fullmatch(mac):
        raise SyntheticStateError(f"{role}_local_mac_invalid")
    mac = mac.lower()
    if int(mac.split(":")[0], 16) & 1 or int(mac.replace(":", ""), 16) == 0:
        raise SyntheticStateError(f"{role}_local_mac_invalid")
    key_hex = raw["application_key_hex"]
    if not isinstance(key_hex, str) or len(key_hex) != 64:
        raise SyntheticStateError(f"{role}_application_key_invalid")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise SyntheticStateError(f"{role}_application_key_invalid") from exc
    if not any(key):
        raise SyntheticStateError(f"{role}_application_key_zero")
    value = dict(raw)
    value["local_mac"] = mac
    value["application_key_hex"] = key.hex()
    return value


def load_fixture(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise SyntheticStateError("fixture_unavailable")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SyntheticStateError("fixture_json_invalid") from exc
    expected = {"schema", "synthetic_only", "synthetic_marker", "system_id", "child", "relay"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise SyntheticStateError("fixture_fields_invalid")
    if raw["schema"] != INPUT_SCHEMA:
        raise SyntheticStateError("fixture_schema_invalid")
    if raw["synthetic_only"] is not True or raw["synthetic_marker"] != SYNTHETIC_MARKER:
        raise SyntheticStateError("real_materialization_rejected")
    if not isinstance(raw["system_id"], str) or not _ID.fullmatch(raw["system_id"]):
        raise SyntheticStateError("system_id_invalid")
    child, relay = validate_node(raw["child"], "child"), validate_node(raw["relay"], "relay")
    for field in ("hardware_id", "pairing_id", "node_id", "local_mac", "application_key_hex"):
        if child[field] == relay[field]:
            raise SyntheticStateError(f"child_relay_{field}_collision")
    return {**raw, "child": child, "relay": relay}


REGISTRATION_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE pairing_sessions(
 pairing_id TEXT PRIMARY KEY, hardware_id TEXT NOT NULL,
 pairing_epoch INTEGER NOT NULL CHECK(pairing_epoch>=1), model TEXT NOT NULL,
 fw_version TEXT NOT NULL, node_nonce TEXT NOT NULL, capabilities_json TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN('pending','approved','rejected','expired')),
 first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,expires_at TEXT NOT NULL,reason TEXT);
CREATE INDEX pairing_sessions_hardware_epoch ON pairing_sessions(hardware_id,pairing_epoch);
CREATE TABLE registrations(
 hardware_id TEXT PRIMARY KEY,current_pairing_id TEXT NOT NULL UNIQUE,
 pairing_epoch INTEGER NOT NULL CHECK(pairing_epoch>=1),node_id TEXT UNIQUE,
 logical_location_id TEXT,repair_authorized INTEGER NOT NULL DEFAULT 0 CHECK(repair_authorized IN(0,1)),
 retired_at TEXT,retirement_reason TEXT,
 FOREIGN KEY(current_pairing_id) REFERENCES pairing_sessions(pairing_id));
CREATE TABLE credential_assignments(
 assignment_id INTEGER PRIMARY KEY,hardware_id TEXT NOT NULL,pairing_id TEXT,
 node_id TEXT UNIQUE,last_node_id TEXT NOT NULL UNIQUE,
 active_generation INTEGER NOT NULL CHECK(active_generation>=1),pending_generation INTEGER,
 state TEXT NOT NULL CHECK(state IN('active','rotating','revoked','recovery_required')),
 reason TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revoked_at TEXT,
 CHECK(pending_generation IS NULL OR pending_generation>active_generation),
 CHECK(state='revoked' OR node_id IS NOT NULL));
CREATE UNIQUE INDEX credential_assignments_current_hardware ON credential_assignments(hardware_id) WHERE state!='revoked';
CREATE INDEX credential_assignments_hardware_history ON credential_assignments(hardware_id,assignment_id);
"""
REPLAY_SCHEMA = """
CREATE TABLE n3w_replay_meta(schema_version INTEGER NOT NULL);
INSERT INTO n3w_replay_meta VALUES(1);
CREATE TABLE n3w_replay_state(node_id TEXT PRIMARY KEY,highest_session_hex TEXT NOT NULL);
CREATE TABLE n3w_replay_seen(node_id TEXT NOT NULL,boot_id TEXT NOT NULL,seq INTEGER NOT NULL,committed_at TEXT NOT NULL,PRIMARY KEY(node_id,boot_id,seq));
"""
RELAY_SCHEMA = """
CREATE TABLE n3w_relay_meta(schema_version INTEGER NOT NULL);INSERT INTO n3w_relay_meta VALUES(2);
CREATE TABLE n3w_relay_nodes(node_id TEXT PRIMARY KEY,active INTEGER NOT NULL);
CREATE TABLE n3w_relay_gateway_nodes(gateway_id TEXT NOT NULL,node_id TEXT NOT NULL,enabled INTEGER NOT NULL);
CREATE TABLE n3w_relay_key_epochs(node_id TEXT NOT NULL,key_epoch INTEGER NOT NULL,key_file TEXT NOT NULL,enabled INTEGER NOT NULL,state TEXT NOT NULL,key_sha256 TEXT);
CREATE TABLE n3w_relay_operations(operation_key TEXT PRIMARY KEY,kind TEXT NOT NULL,node_id TEXT NOT NULL,gateway_id TEXT,key_epoch INTEGER,status TEXT NOT NULL);
"""


def create_registration(path: Path, fixture: dict[str, object]) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(REGISTRATION_SCHEMA)
        for assignment_id, role in enumerate(("child", "relay"), 1):
            node = fixture[role]
            now = "2026-08-15T00:00:00.000Z"
            db.execute(
                "INSERT INTO pairing_sessions VALUES(?,?,?,?,?,?,?,'approved',?,?,?,NULL)",
                (node["pairing_id"], node["hardware_id"], node["pairing_epoch"],
                 "ESP32-C6-WROOM-1", "s5-synthetic", ("A" if role == "child" else "B")*43,
                 json.dumps(node["capabilities"], separators=(",", ":")), now, now, "2099-01-01T00:00:00.000Z"),
            )
            db.execute(
                "INSERT INTO registrations VALUES(?,?,?,?,NULL,0,NULL,NULL)",
                (node["hardware_id"], node["pairing_id"], node["pairing_epoch"], node["node_id"]),
            )
            db.execute(
                "INSERT INTO credential_assignments VALUES(?,?,?,?,?,?,NULL,'active',NULL,?,?,NULL)",
                (assignment_id, node["hardware_id"], node["pairing_id"], node["node_id"],
                 node["node_id"], node["credential_generation"], now, now),
            )
        db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)


def create_simple_db(path: Path, schema: str) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(schema); db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)


def create_relay_auth(path: Path, keys: Path, fixture: dict[str, object]) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(RELAY_SCHEMA)
        for role in ("child", "relay"):
            node = fixture[role]; raw = bytes.fromhex(node["application_key_hex"]); name = f"{role}.key"
            fd = os.open(keys/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out: out.write(raw)
            db.execute("INSERT INTO n3w_relay_nodes VALUES(?,1)", (node["node_id"],))
            db.execute("INSERT INTO n3w_relay_key_epochs VALUES(?,?,?,1,'ACTIVE',?)",
                       (node["node_id"],node["key_epoch"],name,hashlib.sha256(raw).hexdigest()))
        db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)


def credential(system_id: str, node: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in {
        "system_id": system_id,"node_id": node["node_id"],
        "credential_generation": node["credential_generation"],"key_epoch": node["key_epoch"],
        "application_key_hex": node["application_key_hex"],"local_mac": node["local_mac"],
    }.items()}


def assert_output(root: Path, fixture: dict[str, object]) -> dict[str, object]:
    state, creds = root/"manager_state", root/"credentials"
    if {p.name for p in root.iterdir()} != {"manager_state","credentials","synthetic_manifest.json"}:
        raise SyntheticStateError("output_root_not_minimal")
    if {p.name for p in state.iterdir()} != {"registration.sqlite3","replay.sqlite3","relay-authorization.sqlite3","relay-keys"}:
        raise SyntheticStateError("manager_state_not_minimal")
    if {p.name for p in (state/"relay-keys").iterdir()} != {"child.key","relay.key"}:
        raise SyntheticStateError("relay_key_closure_not_exact")
    if {p.name for p in creds.iterdir()} != {"child.json","relay.json"}:
        raise SyntheticStateError("credential_closure_not_exact")
    reg = sqlite3.connect(state/"registration.sqlite3")
    try:
        tables={r[0] for r in reg.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith('sqlite_')}
        if tables != {"pairing_sessions","registrations","credential_assignments"}: raise SyntheticStateError("registration_tables_not_minimal")
        if reg.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] != 2: raise SyntheticStateError("registration_membership_invalid")
        if reg.execute("SELECT COUNT(*) FROM credential_assignments WHERE state='active' AND pending_generation IS NULL").fetchone()[0] != 2: raise SyntheticStateError("credential_lifecycle_invalid")
    finally: reg.close()
    replay=sqlite3.connect(state/"replay.sqlite3")
    try:
        if replay.execute("SELECT COUNT(*) FROM n3w_replay_state").fetchone()[0] or replay.execute("SELECT COUNT(*) FROM n3w_replay_seen").fetchone()[0]: raise SyntheticStateError("replay_not_blank")
    finally: replay.close()
    auth=sqlite3.connect(state/"relay-authorization.sqlite3")
    try:
        counts=[auth.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("n3w_relay_nodes","n3w_relay_key_epochs","n3w_relay_gateway_nodes","n3w_relay_operations")]
        if counts != [2,2,0,0]: raise SyntheticStateError("relay_authorization_not_minimal")
    finally: auth.close()
    for p in root.rglob("*"):
        if stat.S_IMODE(p.stat().st_mode) != (0o700 if p.is_dir() else 0o600): raise SyntheticStateError("output_permissions_invalid")
    return {"synthetic_only":True,"target_node_count":2,"gateway_relation_row_count":0,"relay_operation_row_count":0,"replay_state_row_count":0,"replay_seen_row_count":0,"credential_generation_equals_pairing_epoch":True,"pair_lmk_present":False,"pmk_present":False,"output_contract_verified":True,"authorization":AUTHORIZATION}


def initialize(fixture_path: Path, output: Path) -> dict[str, object]:
    os.umask(0o077); fixture=load_fixture(fixture_path)
    if output.exists(): raise SyntheticStateError("output_already_exists")
    private_dir(output); private_dir(output/"manager_state"); private_dir(output/"credentials"); private_dir(output/"manager_state"/"relay-keys")
    state=output/"manager_state"
    create_registration(state/"registration.sqlite3", fixture)
    create_simple_db(state/"replay.sqlite3", REPLAY_SCHEMA)
    create_relay_auth(state/"relay-authorization.sqlite3", state/"relay-keys", fixture)
    for role in ("child","relay"): write_json(output/"credentials"/f"{role}.json", credential(fixture["system_id"], fixture[role]))
    write_json(output/"synthetic_manifest.json", {
        "schema":"gh.n3w-product-s5-dedicated-two-node-state-synthetic-result/1","authorization":AUTHORIZATION,
        "synthetic_only":True,"real_private_state_materialized":False,"static_gateway_relation_present":False,
        "pair_lmk_present":False,"pmk_present":False,
        "system_id_sha256":hashlib.sha256(fixture["system_id"].encode()).hexdigest(),
        "child_node_id_sha256":hashlib.sha256(fixture["child"]["node_id"].encode()).hexdigest(),
        "relay_node_id_sha256":hashlib.sha256(fixture["relay"]["node_id"].encode()).hexdigest(),
    })
    return assert_output(output, fixture)


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--fixture",required=True); parser.add_argument("--output",required=True); args=parser.parse_args()
    try: result=initialize(Path(args.fixture).resolve(),Path(args.output).resolve())
    except (OSError,sqlite3.Error,SyntheticStateError) as exc:
        print(f"S5_SYNTHETIC_TWO_NODE_STATE_INITIALIZER=FAIL reason={exc}"); return 2
    print("S5_SYNTHETIC_TWO_NODE_STATE_INITIALIZER=PASS"); print(json.dumps(result,sort_keys=True,separators=(",",":"))); return 0


if __name__ == "__main__": raise SystemExit(main())
