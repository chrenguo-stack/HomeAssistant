#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from n3w_t1_golden_master_common import (
    GoldenMasterCommonError,
    claim_authorization,
    load_authorization_record,
    public_tree_sha256,
    sha256_bytes,
    sha256_file,
)

SCHEMA = "gh.n3w.t1-golden-master-build-host/1"
RELEASE_SCHEMA = "gh.n3w.t1-golden-master-release/1"
AUTHORIZATION_ID = "N3W_T1_GOLDEN_MASTER_R2_BUILD_LIVE_APPLY_20261013_01"
AUTHORIZATION_LEDGER_ROOT = Path("/var/lib/n3w-golden-master-authorizations")
RELEASE_RELATIVE_PATH = Path(
    "infra/n3w-t1/production/golden-master-release.json"
)
PUBLIC_EXTERNAL_CANDIDATES = {
    "guard_binary": (
        "stage/n3w-broker-ingress-guard",
        "/usr/local/sbin/n3w-broker-ingress-guard",
    ),
    "guard_unit": (
        "stage/n3wfc4-broker-ingress-guard.service",
        "/etc/systemd/system/n3wfc4-broker-ingress-guard.service",
    ),
}
AUTHORIZATION_LEDGER_POLICY = "retained_nonsecret_no_replay_provenance"
_RELEASE_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


class GoldenMasterBuildError(RuntimeError):
    pass


def _load_module(path: Path, name: str) -> ModuleType:
    if path.is_symlink() or not path.is_file():
        raise GoldenMasterBuildError(f"module_missing:{path.name}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise GoldenMasterBuildError(f"module_invalid:{path.name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _validate_release_id(value: str) -> None:
    if _RELEASE_ID.fullmatch(value) is None:
        raise GoldenMasterBuildError("release_id_invalid")


def _manifest_bytes(document: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode()


def _image_lock_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            manifest["image_lock"],
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode()


def _image_bindings(manifest: Mapping[str, Any]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for label in ("homeassistant", "manager", "broker"):
        record = manifest["images"][label]
        result[label] = {
            key: record[key]
            for key in (
                "image",
                "image_id",
                "platform",
                "tar_sha256",
                "rootfs_layers_sha256",
                "config_contract_sha256",
            )
        }
    return result


def _public_external_bindings(candidate_root: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for label, (relative, destination) in PUBLIC_EXTERNAL_CANDIDATES.items():
        path = candidate_root / relative
        if path.is_symlink() or not path.is_file():
            raise GoldenMasterBuildError(
                f"public_external_candidate_invalid:{label}"
            )
        metadata = path.stat()
        result[label] = {
            "destination": destination,
            "sha256": sha256_file(path),
            "mode": metadata.st_mode & 0o777,
        }
    return result


class GoldenMasterBuildAdapters:
    def __init__(
        self,
        live: object,
        *,
        payload_root: Path,
        manifest: dict[str, Any],
        release_id: str,
    ) -> None:
        _validate_release_id(release_id)
        self.live = live
        self.payload_root = payload_root
        self.manifest = manifest
        self.release_id = release_id
        self.release_document: dict[str, object] | None = None
        self.release_sha256: str | None = None

    def preflight_master(self):
        return self.live.preflight_master()

    def load_images(self):
        return self.live.load_images()

    def stage_public_runtime(self, candidate_root: Path):
        report = self.live.stage_public_runtime(candidate_root)
        product_source = candidate_root / "stage/opt-HomeAssistant"
        release_path = product_source / RELEASE_RELATIVE_PATH
        if release_path.exists() or release_path.is_symlink():
            raise GoldenMasterBuildError("release_manifest_target_exists")

        payload_manifest_sha256 = sha256_file(
            self.payload_root / "payload-manifest.json"
        )
        public_source_tree_sha256 = public_tree_sha256(product_source)
        release_document: dict[str, object] = {
            "schema": RELEASE_SCHEMA,
            "release_id": self.release_id,
            "source_head": self.manifest["source_head"],
            "payload_manifest_sha256": payload_manifest_sha256,
            "image_lock_sha256": sha256_bytes(
                _image_lock_bytes(self.manifest)
            ),
            "public_source_tree_sha256": public_source_tree_sha256,
            "images": _image_bindings(self.manifest),
            "public_external_bindings": _public_external_bindings(candidate_root),
            "architecture": "linux/arm64",
            "instance_material_absent": True,
            "secret_values_included": False,
            "build_authorization_id": AUTHORIZATION_ID,
            "authorization_ledger_policy": AUTHORIZATION_LEDGER_POLICY,
            "seal_state": "UNSEALED",
            "production_service_start": False,
            "board_access": False,
        }
        release_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _manifest_bytes(release_document)
        release_path.write_bytes(payload)
        release_path.chmod(0o644)
        self.release_document = release_document
        self.release_sha256 = sha256_bytes(payload)
        return {
            **report,
            "release_manifest_sha256": self.release_sha256,
        }

    def commit_public_candidate(self, candidate_root: Path):
        return self.live.commit_public_candidate(candidate_root)

    def master_postcheck(self):
        report = self.live.master_postcheck()
        if self.release_document is None or self.release_sha256 is None:
            raise GoldenMasterBuildError("release_manifest_not_staged")
        path = Path("/opt/HomeAssistant") / RELEASE_RELATIVE_PATH
        if path.is_symlink() or not path.is_file():
            raise GoldenMasterBuildError("release_manifest_missing")
        if sha256_file(path) != self.release_sha256:
            raise GoldenMasterBuildError("release_manifest_binding_invalid")
        try:
            observed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise GoldenMasterBuildError("release_manifest_invalid") from error
        if observed != self.release_document:
            raise GoldenMasterBuildError("release_manifest_content_drift")
        return {
            **report,
            "release_manifest_sha256": self.release_sha256,
        }

    def cleanup_master_candidate(self, candidate_root: Path):
        return self.live.cleanup_master_candidate(candidate_root)


def _load_payload(
    payload_root: Path,
    release_id: str,
) -> tuple[ModuleType, ModuleType, dict[str, Any], GoldenMasterBuildAdapters]:
    _validate_release_id(release_id)
    fresh = _load_module(
        payload_root / "tools/n3w_t1_fresh_product_bootstrap.py",
        "n3w_golden_master_fresh_transport",
    )
    contract = _load_module(
        payload_root / "contract/golden_master_installer.py",
        "n3w_golden_master_installer_contract",
    )
    manifest = fresh._load_manifest(payload_root)
    live = fresh.LiveFreshInstallerAdapters(
        payload_root,
        manifest,
        fresh.Runner(),
    )
    adapter = GoldenMasterBuildAdapters(
        live,
        payload_root=payload_root,
        manifest=manifest,
        release_id=release_id,
    )
    return fresh, contract, manifest, adapter


def self_check(payload_root: Path, release_id: str) -> dict[str, object]:
    _, contract, manifest, _ = _load_payload(payload_root, release_id)
    if not callable(getattr(contract, "run_golden_master_build", None)):
        raise GoldenMasterBuildError("golden_master_contract_invalid")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "self-check",
        "release_id": release_id,
        "source_head": manifest["source_head"],
        "authorization_id": AUTHORIZATION_ID,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "live_mutation": False,
        "production_service_start": False,
        "board_access": False,
    }


def execute_preflight(
    payload_root: Path,
    release_id: str,
) -> dict[str, object]:
    _, _, manifest, adapter = _load_payload(payload_root, release_id)
    report = adapter.preflight_master()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "preflight",
        "release_id": release_id,
        "source_head": manifest["source_head"],
        "instance_material_absent": report["instance_material_absent"],
        "authorization_claimed": False,
        "authorization_consumed": False,
        "live_mutation": False,
        "production_service_start": False,
        "board_access": False,
    }


def execute_apply(
    payload_root: Path,
    release_id: str,
    authorization_id: str,
) -> dict[str, object]:
    if authorization_id != AUTHORIZATION_ID:
        raise GoldenMasterBuildError("authorization_id_mismatch")
    if os.geteuid() != 0:
        raise GoldenMasterBuildError("root_required")
    if load_authorization_record(
        AUTHORIZATION_LEDGER_ROOT,
        AUTHORIZATION_ID,
    ) is not None:
        raise GoldenMasterBuildError("authorization_already_consumed")

    _, contract, manifest, adapter = _load_payload(payload_root, release_id)
    payload_manifest_sha256 = sha256_file(
        payload_root / "payload-manifest.json"
    )
    candidate = Path("/var/tmp") / (
        f"n3w-golden-master-build-{secrets.token_hex(8)}"
    )
    claimed = False

    def claim() -> None:
        nonlocal claimed
        claim_authorization(
            AUTHORIZATION_LEDGER_ROOT,
            authorization_id=AUTHORIZATION_ID,
            operation="BUILD",
            source_head=manifest["source_head"],
            payload_manifest_sha256=payload_manifest_sha256,
            release_id=release_id,
        )
        claimed = True

    try:
        report = contract.run_golden_master_build(
            adapter,
            candidate,
            before_mutation=claim,
        )
    finally:
        if candidate.exists() and not candidate.is_symlink():
            shutil.rmtree(candidate)

    if not claimed or adapter.release_sha256 is None:
        raise GoldenMasterBuildError("build_authorization_or_release_missing")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "apply",
        "release_id": release_id,
        "source_head": manifest["source_head"],
        "release_manifest_sha256": adapter.release_sha256,
        "master_ready": report["master_ready"],
        "instance_material_absent": report["instance_material_absent"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "production_service_start": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-golden-master-build")
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument(
        "--phase",
        choices=("self-check", "preflight", "apply"),
        required=True,
    )
    parser.add_argument("--authorization-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.payload_root.resolve()
    try:
        if args.phase == "self-check":
            result = self_check(root, args.release_id)
        elif args.phase == "preflight":
            result = execute_preflight(root, args.release_id)
        else:
            if not args.authorization_id:
                raise GoldenMasterBuildError("authorization_id_required")
            result = execute_apply(
                root,
                args.release_id,
                args.authorization_id,
            )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ImportError,
        subprocess.SubprocessError,
    ) as error:
        try:
            consumed = (
                load_authorization_record(
                    AUTHORIZATION_LEDGER_ROOT,
                    AUTHORIZATION_ID,
                )
                is not None
            )
        except (GoldenMasterCommonError, OSError, ValueError):
            consumed = False
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP_PARTIAL" if consumed else "STOP",
                    "reason": str(error)[:400],
                    "authorization_claimed": consumed,
                    "authorization_consumed": consumed,
                    "replay_allowed": False if consumed else None,
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
