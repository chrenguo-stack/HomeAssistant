#!/usr/bin/env python3
"""R7 successor wrapper for the private S5 two-board package builder.

This wrapper preserves the historical base builder and adds only the private-lab
R7 Child telemetry stimulus binding. It remains host/compile-only. It reads the
bound Manager replay snapshot without mutation, chooses one boot session strictly
above the Child high-water, enables exactly one application telemetry record at
seq=0 in the rendered Child configuration, and leaves Relay stimulus disabled.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from typing import Any

AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-R7-PRIVATE-TELEMETRY-STIMULUS-"
    "PACKAGE-BUILDER-CONTRACT-REPAIR-20260816-01"
)
STARTING_HEAD = "9862d7ecbe95439fd36ceb91854505a923cbfea2"
WRAPPER_RELATIVE_PATH = "tools/n3w_product_s5_build_private_package_r7.py"
MAX_BOOT_SESSION = (1 << 64) - 1
_BOOT_HEX = re.compile(r"^[0-9a-f]{16}$")


class R7PrivatePackageBuildError(RuntimeError):
    """R7 package stimulus binding cannot be proven safely."""


def _load_base_builder():
    path = Path(__file__).with_name("n3w_product_s5_build_private_package.py")
    spec = importlib.util.spec_from_file_location("n3w_product_s5_base_builder", path)
    if spec is None or spec.loader is None:
        raise R7PrivatePackageBuildError("base_builder_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_private_regular_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise R7PrivatePackageBuildError(f"{label}_symlink_rejected")
    try:
        info = path.stat()
    except OSError as exc:
        raise R7PrivatePackageBuildError(f"{label}_unavailable") from exc
    if not stat.S_ISREG(info.st_mode):
        raise R7PrivatePackageBuildError(f"{label}_not_regular_file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise R7PrivatePackageBuildError(f"{label}_permissions_invalid")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise R7PrivatePackageBuildError(f"{label}_owner_invalid")


def _select_replay_safe_stimulus(replay_path: Path, child_node_id: str) -> dict[str, object]:
    """Select the next Child boot session using a read-only replay snapshot."""
    replay_path = replay_path.resolve()
    _require_private_regular_file(replay_path, "manager_replay")
    try:
        connection = sqlite3.connect(
            f"{replay_path.as_uri()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick is None or quick[0] != "ok":
            raise R7PrivatePackageBuildError("manager_replay_corrupt")
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'n3w_replay_%'"
            ).fetchall()
        }
        if names != {"n3w_replay_meta", "n3w_replay_state", "n3w_replay_seen"}:
            raise R7PrivatePackageBuildError("manager_replay_schema_mismatch")
        versions = connection.execute("SELECT schema_version FROM n3w_replay_meta").fetchall()
        if len(versions) != 1 or versions[0][0] != 1:
            raise R7PrivatePackageBuildError("manager_replay_schema_mismatch")

        row = connection.execute(
            "SELECT highest_session_hex FROM n3w_replay_state WHERE node_id = ?",
            (child_node_id,),
        ).fetchone()
        if row is None:
            highest_session = None
            highest_session_hex = None
            candidate = 1
        else:
            highest_session_hex = row["highest_session_hex"]
            if not isinstance(highest_session_hex, str) or _BOOT_HEX.fullmatch(highest_session_hex) is None:
                raise R7PrivatePackageBuildError("child_replay_high_water_invalid")
            highest_session = int(highest_session_hex, 16)
            if highest_session == 0:
                raise R7PrivatePackageBuildError("child_replay_high_water_invalid")
            if highest_session >= MAX_BOOT_SESSION:
                raise R7PrivatePackageBuildError("child_replay_boot_session_exhausted")
            candidate = highest_session + 1

        boot_id = f"boot_{candidate:016x}"
        seen = connection.execute(
            "SELECT 1 FROM n3w_replay_seen WHERE node_id = ? AND boot_id = ? AND seq = 0",
            (child_node_id, boot_id),
        ).fetchone()
        if seen is not None:
            raise R7PrivatePackageBuildError("child_replay_candidate_already_seen")
        return {
            "enabled": True,
            "node_id": child_node_id,
            "source_highest_session_hex": highest_session_hex,
            "source_highest_session": highest_session,
            "boot_session": candidate,
            "boot_id": boot_id,
            "seq": 0,
            "replay_snapshot_read_only": True,
        }
    except sqlite3.Error as exc:
        raise R7PrivatePackageBuildError("manager_replay_unavailable") from exc
    finally:
        connection = locals().get("connection")
        if connection is not None:
            connection.close()


def _render_r7_child(base, stimulus: dict[str, object], **kwargs: Any) -> str:
    rendered = base._render_child(**kwargs)
    if "telemetry_stimulus_" in rendered:
        raise R7PrivatePackageBuildError("base_child_stimulus_already_present")
    if not rendered.endswith("\n"):
        raise R7PrivatePackageBuildError("base_child_render_termination_invalid")
    return (
        rendered
        + "  telemetry_stimulus_enabled: true\n"
        + f"  telemetry_stimulus_boot_session: {int(stimulus['boot_session'])}\n"
        + f"  telemetry_stimulus_seq: {int(stimulus['seq'])}\n"
    )


def _verify_successor_source_binding(base, source_root: Path, source_head: str) -> None:
    lineage = base._run_git(
        source_root,
        "merge-base",
        "--is-ancestor",
        STARTING_HEAD,
        source_head,
        check=False,
    )
    if lineage.returncode != 0:
        raise R7PrivatePackageBuildError("r7_successor_source_lineage_mismatch")
    committed = base._run_git(
        source_root,
        "cat-file",
        "-e",
        f"{source_head}:{WRAPPER_RELATIVE_PATH}",
        check=False,
    )
    if committed.returncode != 0:
        raise R7PrivatePackageBuildError("r7_successor_builder_not_committed")
    status = base._run_git(
        source_root,
        "status",
        "--porcelain",
        "--",
        WRAPPER_RELATIVE_PATH,
    ).stdout
    if status.strip():
        raise R7PrivatePackageBuildError("r7_successor_builder_dirty")


def _replace_private_json(base, path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".r7-tmp")
    base._write_private_json(temporary, value)
    os.replace(temporary, path)


def build(args) -> dict[str, object]:
    base = _load_base_builder()
    source_root = Path(args.source_root).resolve()
    _verify_successor_source_binding(base, source_root, args.source_head)

    child = base._load_credentials(Path(args.child_credentials).resolve(), "child_credentials")
    manager_state = Path(args.manager_state_root).resolve()
    stimulus = _select_replay_safe_stimulus(
        manager_state / "replay.sqlite3",
        str(child["node_id"]),
    )

    original_render_child = base._render_child

    def render_child_with_r7_stimulus(**kwargs: Any) -> str:
        return _render_r7_child(base, stimulus, **kwargs)

    base._render_child = render_child_with_r7_stimulus
    try:
        result = base.build(args)
    finally:
        base._render_child = original_render_child

    output = Path(args.output).resolve()
    child_yaml = (output / "rendered" / "child.yml").read_text(encoding="utf-8")
    relay_yaml = (output / "rendered" / "relay.yml").read_text(encoding="utf-8")
    expected = (
        "  telemetry_stimulus_enabled: true\n"
        f"  telemetry_stimulus_boot_session: {int(stimulus['boot_session'])}\n"
        "  telemetry_stimulus_seq: 0\n"
    )
    if child_yaml.count(expected) != 1:
        raise R7PrivatePackageBuildError("r7_child_stimulus_render_binding_failed")
    if "telemetry_stimulus_" in relay_yaml:
        raise R7PrivatePackageBuildError("r7_relay_stimulus_must_remain_disabled")

    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    implementation = manifest.setdefault("implementation_provenance", {})
    implementation["r7_package_stimulus_repair_authorization"] = AUTHORIZATION
    implementation["r7_package_stimulus_repair_starting_head"] = STARTING_HEAD
    implementation["r7_successor_builder_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    manifest["telemetry_stimulus_binding"] = {
        "schema": "gh.n3w-product-s5-r7-private-telemetry-stimulus-binding/1",
        "role": "child",
        "enabled": True,
        "node_id": stimulus["node_id"],
        "source_highest_session_hex": stimulus["source_highest_session_hex"],
        "boot_session": stimulus["boot_session"],
        "boot_id": stimulus["boot_id"],
        "seq": 0,
        "selection": "highest_plus_one_or_one_when_absent",
        "manager_replay_snapshot_sha256": base._sha256_file(output / "manager_state" / "replay.sqlite3"),
        "manager_replay_snapshot_mutated": False,
        "relay_stimulus_enabled": False,
    }
    composition = manifest.setdefault("composition_contract", {})
    composition["r7_private_child_telemetry_stimulus_enabled"] = True
    composition["r7_private_relay_telemetry_stimulus_enabled"] = False
    composition["r7_private_telemetry_stimulus_exactly_once_application_record"] = True
    _replace_private_json(base, manifest_path, manifest)

    result["r7_telemetry_stimulus_enabled"] = True
    result["r7_telemetry_stimulus_boot_session"] = stimulus["boot_session"]
    result["r7_telemetry_stimulus_seq"] = 0
    return result


def main() -> int:
    base = _load_base_builder()
    try:
        result = build(base.parser().parse_args())
    except (OSError, R7PrivatePackageBuildError, base.PrivatePackageBuildError) as exc:
        print(f"R7_PRIVATE_PACKAGE_BUILD=FAIL reason={exc}")
        return 2
    print("R7_PRIVATE_PACKAGE_BUILD=PASS")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
