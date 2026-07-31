#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g14_execution_package_mode_normalized_view_repair_20260731_v1.py"
DISPOSITION = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g13-consumed-package-file-invalid-disposition-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g14-private-package-static-check-authorization-pending-20260731-v1.json"
BUILDER = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_canonical_builder_20260730_v1.py"
SUCCESSOR = ROOT / "tools/h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"


def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def load_bound(path: Path, field: str, expected: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value[field] == expected
    core = dict(value)
    core.pop(field)
    assert canonical(core) == expected
    return value


def write_fixture(root: Path) -> None:
    values = {
        "run_d2_17_canonical_delivery_outer_20260730_v1.sh": b"#!/bin/sh\nexit 0\n",
        "run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh": b"#!/bin/sh\nexit 0\n",
        "contract.py": b"VALUE = 1\n",
    }
    for name, payload in values.items():
        path = root / name
        path.write_bytes(payload)
        os.chmod(path, 0o700 if name.endswith(".sh") else 0o600)
    lines = [f"{hashlib.sha256(payload).hexdigest()}  {name}" for name, payload in sorted(values.items())]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(root / "SHA256SUMS", 0o600)


def main() -> int:
    disposition = load_bound(
        DISPOSITION,
        "disposition_binding_sha256",
        "2c37dcd807731d47c25f7a5b6a2ec0a03add0efc01ee461526cd95f86868915c",
    )
    pending = load_bound(
        PENDING,
        "g14_pending_binding_sha256",
        "a91a3b699122ee83af663ef2c014115d1db02b28b9aa8890876a810462023d92",
    )
    assert disposition["terminal_record_sha256"] == "93c3ccb94adf3c185e1da6e535c93e9e9fc32edaf1121f00c8da63ccdb4cca2d"
    assert disposition["authorization_claimed"] is True
    assert disposition["authorization_consumed"] is True
    assert disposition["failure_code"] == "PACKAGE_FILE_INVALID"
    assert disposition["failure_stage"] == "PRECLAIM"
    assert disposition["g13_retired"] is True
    assert disposition["flash_operation"] is False
    assert disposition["prepare_executed"] is False
    assert pending["g13_disposition_binding_sha256"] == disposition["disposition_binding_sha256"]
    assert pending["g14_private_package_created"] is False
    assert pending["physical_execution_authorized"] is False

    spec = importlib.util.spec_from_file_location("g14_repair", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    audit = module.inspect_exact_mode_contract(
        BUILDER.read_text(encoding="utf-8"), SUCCESSOR.read_text(encoding="utf-8")
    )
    assert audit["conflict_confirmed"] is True
    assert audit["canonical_builder_shell_mode"] == "0700"
    assert audit["inherited_preclaim_required_mode"] == "0600"
    assert audit["failure_code"] == "PACKAGE_FILE_INVALID"

    with tempfile.TemporaryDirectory(prefix="g14-mode-view-test-") as name:
        base = Path(name)
        source = base / "source"
        source.mkdir(mode=0o700)
        write_fixture(source)
        source_modes = {path.name: stat.S_IMODE(path.stat().st_mode) for path in source.iterdir()}
        view = base / "view"
        report = module.create_mode_normalized_execution_view(source, view)
        assert report["ready_for_inherited_preclaim"] is True
        assert report["content_equivalent"] is True
        assert report["canonical_source_mutated"] is False
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in view.iterdir())
        assert source_modes == {path.name: stat.S_IMODE(path.stat().st_mode) for path in source.iterdir()}

        try:
            module.create_mode_normalized_execution_view(source, view)
        except module.RepairError as exc:
            assert str(exc) == "G14_TARGET_ROOT_ALREADY_EXISTS"
        else:
            raise AssertionError("existing target accepted")

        bad = base / "bad"
        bad.mkdir(mode=0o700)
        write_fixture(bad)
        (bad / "contract.py").unlink()
        (bad / "contract.py").symlink_to(bad / "run_d2_17_canonical_delivery_outer_20260730_v1.sh")
        try:
            module.create_mode_normalized_execution_view(bad, base / "bad-view")
        except module.RepairError as exc:
            assert str(exc) == "G14_SOURCE_MEMBER_INVALID"
        else:
            raise AssertionError("symlink source accepted")

    print(json.dumps({
        "status": "PASS",
        "g13_disposition_binding_sha256": disposition["disposition_binding_sha256"],
        "g14_pending_binding_sha256": pending["g14_pending_binding_sha256"],
        "root_cause": disposition["root_cause"],
        "mode_normalized_execution_view_validated": True,
        "physical_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
