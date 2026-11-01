#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCHEMA = "gh.n3w-t1-clean-reference-r1-executor/1"
CONFIRMATION = "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01"


class CleanReferenceExecutorError(RuntimeError):
    pass


def _load_module(path: Path, name: str) -> ModuleType:
    if path.is_symlink() or not path.is_file():
        raise CleanReferenceExecutorError("payload_module_missing")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CleanReferenceExecutorError("payload_module_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_payload(payload_root: Path) -> tuple[ModuleType, ModuleType, dict[str, Any], Any]:
    root = payload_root.resolve()
    fresh = _load_module(
        root / "tools/n3w_t1_fresh_product_bootstrap.py",
        "n3w_clean_reference_fresh_transport",
    )
    contract = _load_module(
        root / "contract/fresh_installer.py",
        "n3w_clean_reference_fresh_installer",
    )
    manifest = fresh._load_manifest(root)
    if manifest.get("production_service_start") is not False:
        raise CleanReferenceExecutorError("payload_service_boundary_invalid")
    adapter = fresh.LiveFreshInstallerAdapters(root, manifest, fresh.Runner())
    return fresh, contract, manifest, adapter


def self_check(payload_root: Path) -> dict[str, object]:
    _, contract, manifest, _ = _load_payload(payload_root)
    if not callable(getattr(contract, "run_fresh_staging", None)):
        raise CleanReferenceExecutorError("fresh_staging_contract_missing")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "self-check",
        "source_head": manifest["source_head"],
        "production_v2_authority_used": False,
        "production_service_start": False,
        "activation_authorized": False,
        "board_access": False,
    }


def execute_preflight(payload_root: Path) -> dict[str, object]:
    _, _, manifest, adapter = _load_payload(payload_root)
    report = adapter.preflight()
    if report.get("status") != "PASS":
        raise CleanReferenceExecutorError("clean_reference_preflight_failed")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "preflight",
        "source_head": manifest["source_head"],
        "container_count": report["product_containers"],
        "image_count": report["product_images"],
        "volume_count": report["product_volumes"],
        "product_network_count": report["product_networks"],
        "production_listener_count": report["product_listeners"],
        "production_v2_authority_used": False,
        "production_service_start": False,
        "activation_authorized": False,
        "board_access": False,
    }


def execute_apply(payload_root: Path, confirmation: str) -> dict[str, object]:
    if confirmation != CONFIRMATION:
        raise CleanReferenceExecutorError("clean_reference_confirmation_mismatch")
    if os.geteuid() != 0:
        raise CleanReferenceExecutorError("root_required")
    _, contract, manifest, adapter = _load_payload(payload_root)
    candidate = Path("/var/tmp") / f"n3w-clean-reference-r1-{secrets.token_hex(8)}"

    def authorize() -> None:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "event": "clean_reference_authorized",
                    "confirmation": CONFIRMATION,
                    "production_v2_authority_used": False,
                    "production_service_start": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )

    try:
        report = contract.run_fresh_staging(
            adapter,
            candidate,
            before_mutation=authorize,
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:200],
                    "failed_stage": getattr(error, "failed_stage", "unknown"),
                    "failure_code": getattr(error, "failure_code", "unknown"),
                    "cleanup_result": getattr(error, "cleanup_result", "UNKNOWN"),
                    "production_v2_authority_used": False,
                    "production_service_start": False,
                    "activation_authorized": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )
        raise
    finally:
        if candidate.exists() and not candidate.is_symlink():
            shutil.rmtree(candidate, ignore_errors=True)

    if (
        report.get("status") != "PASS"
        or report.get("fresh_product_staged") is not True
        or report.get("node_credential_count") != 0
        or report.get("production_service_start") is not False
        or report.get("activation_authorized") is not False
    ):
        raise CleanReferenceExecutorError("clean_reference_apply_contract_invalid")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "apply",
        "source_head": manifest["source_head"],
        "fresh_product_staged": True,
        "node_credential_count": 0,
        "production_v2_authority_used": False,
        "production_service_start": False,
        "activation_authorized": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument(
        "--phase",
        choices=("self-check", "preflight", "apply"),
        required=True,
    )
    parser.add_argument("--confirmation")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        root = args.payload_root.resolve()
        if args.phase == "self-check":
            result = self_check(root)
        elif args.phase == "preflight":
            result = execute_preflight(root)
        else:
            if not args.confirmation:
                raise CleanReferenceExecutorError(
                    "clean_reference_confirmation_required"
                )
            result = execute_apply(root, args.confirmation)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
                    "production_v2_authority_used": False,
                    "production_service_start": False,
                    "activation_authorized": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
