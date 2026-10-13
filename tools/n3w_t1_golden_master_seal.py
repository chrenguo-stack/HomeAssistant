#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from n3w_t1_golden_master_common import (
    GoldenMasterCommonError,
    authorization_record_path,
    canonical_sha256,
    load_authorization_record,
    public_tree_sha256,
    sha256_file,
)

SCHEMA = "gh.n3w.t1-golden-master-seal-host/1"
RELEASE_SCHEMA = "gh.n3w.t1-golden-master-release/1"
AUTHORIZATION_ID = "N3W_T1_GOLDEN_MASTER_R2_FINAL_SEAL_LIVE_APPLY_20261013_01"
BUILD_AUTHORIZATION_ID = "N3W_T1_GOLDEN_MASTER_R2_BUILD_LIVE_APPLY_20261013_01"
AUTHORIZATION_LEDGER_ROOT = Path("/var/lib/n3w-golden-master-authorizations")
AUTHORIZATION_LEDGER_POLICY = "retained_nonsecret_no_replay_provenance"
RELEASE_RELATIVE_PATH = Path(
    "infra/n3w-t1/production/golden-master-release.json"
)
IMAGE_LOCK_RELATIVE_PATH = Path("infra/n3w-t1/production/image-lock.json")
PUBLIC_EXTERNAL_FILES = {
    "guard_binary": Path("/usr/local/sbin/n3w-broker-ingress-guard"),
    "guard_unit": Path(
        "/etc/systemd/system/n3wfc4-broker-ingress-guard.service"
    ),
}
DEFAULT_NETWORKS = frozenset(("bridge", "host", "none"))
TARGET_PORTS = frozenset((1883, 8883, 18883, 8123, 47110, 47111, 47112))
INSTANCE_PATHS = (
    "/var/lib/greenhouse-manager",
    "/var/lib/n3wfc4-broker",
    "/var/lib/n3wfc4-homeassistant",
    "/opt/greenhouse-secrets",
    "/etc/n3wfc4",
)
EXTRA_ABSENT = (
    "/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard",
    "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
    "/usr/local/sbin/n3w-broker-certificate-lifecycle",
    "/etc/systemd/system/n3wfc4-broker-activation.service",
    "/etc/systemd/system/n3wfc4-services-activation.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer",
    "/etc/systemd/system/n3wfc4-provision-resume.service",
)
GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
ABSENT_UNITS = (
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
    "n3wfc4-broker-certificate-lifecycle.service",
    "n3wfc4-broker-certificate-lifecycle.timer",
    "n3wfc4-provision-resume.service",
)
STAGING_GLOBS = (
    "/var/tmp/n3w-golden-master-build-*",
    "/var/tmp/n3w-fresh-bootstrap-*",
)
PRODUCT_NAMESPACE_RULES = (
    (
        Path("/opt"),
        ("HomeAssistant", "greenhouse-"),
        frozenset({"HomeAssistant"}),
    ),
    (
        Path("/var/lib"),
        ("greenhouse-manager", "n3w"),
        frozenset({"n3w-golden-master-authorizations"}),
    ),
    (
        Path("/usr/local/sbin"),
        ("n3w-",),
        frozenset({"n3w-broker-ingress-guard"}),
    ),
    (
        Path("/etc/systemd/system"),
        ("n3wfc4-",),
        frozenset({"n3wfc4-broker-ingress-guard.service"}),
    ),
    (
        Path("/etc/NetworkManager/dispatcher.d"),
        ("90-n3wfc4-",),
        frozenset(),
    ),
)
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")


class GoldenMasterSealHostError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        argv: Sequence[str],
        *,
        allowed: frozenset[int] = frozenset({0}),
    ) -> str:
        completed = subprocess.run(
            tuple(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if completed.returncode not in allowed:
            raise GoldenMasterSealHostError(
                f"command_failed:{Path(argv[0]).name}:{completed.returncode}"
            )
        return completed.stdout


def _source_root(path: Path) -> Path:
    root = path.expanduser()
    if not root.is_absolute():
        raise GoldenMasterSealHostError("source_root_not_absolute")
    if root.is_symlink() or not root.is_dir():
        raise GoldenMasterSealHostError("source_root_invalid")
    try:
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise GoldenMasterSealHostError("source_root_invalid") from error
    if resolved != root:
        raise GoldenMasterSealHostError("source_root_alias_forbidden")
    return root


def _load_release(source_root: Path) -> dict[str, Any]:
    path = source_root / RELEASE_RELATIVE_PATH
    if path.is_symlink() or not path.is_file():
        raise GoldenMasterSealHostError("release_manifest_missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GoldenMasterSealHostError("release_manifest_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != RELEASE_SCHEMA
        or not isinstance(document.get("release_id"), str)
        or not document["release_id"]
        or _SHA40.fullmatch(str(document.get("source_head"))) is None
        or _SHA64.fullmatch(str(document.get("payload_manifest_sha256"))) is None
        or _SHA64.fullmatch(str(document.get("image_lock_sha256"))) is None
        or _SHA64.fullmatch(str(document.get("public_source_tree_sha256"))) is None
        or document.get("architecture") != "linux/arm64"
        or document.get("instance_material_absent") is not True
        or document.get("secret_values_included") is not False
        or document.get("build_authorization_id") != BUILD_AUTHORIZATION_ID
        or document.get("authorization_ledger_policy")
        != AUTHORIZATION_LEDGER_POLICY
        or document.get("seal_state") != "UNSEALED"
        or document.get("production_service_start") is not False
    ):
        raise GoldenMasterSealHostError("release_manifest_contract_invalid")

    images = document.get("images")
    if not isinstance(images, dict) or set(images) != {
        "homeassistant",
        "manager",
        "broker",
    }:
        raise GoldenMasterSealHostError("release_manifest_images_invalid")
    for label, record in images.items():
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("image"), str)
            or not record["image"]
            or _IMAGE_ID.fullmatch(str(record.get("image_id"))) is None
            or record.get("platform") != "linux/arm64"
            or _SHA64.fullmatch(str(record.get("tar_sha256"))) is None
            or _SHA64.fullmatch(str(record.get("rootfs_layers_sha256"))) is None
            or _SHA64.fullmatch(str(record.get("config_contract_sha256"))) is None
        ):
            raise GoldenMasterSealHostError(
                f"release_manifest_image_record_invalid:{label}"
            )

    external = document.get("public_external_bindings")
    if not isinstance(external, dict) or set(external) != set(PUBLIC_EXTERNAL_FILES):
        raise GoldenMasterSealHostError(
            "release_manifest_public_external_bindings_invalid"
        )
    for label, expected_path in PUBLIC_EXTERNAL_FILES.items():
        record = external[label]
        if (
            not isinstance(record, dict)
            or record.get("destination") != str(expected_path)
            or _SHA64.fullmatch(str(record.get("sha256"))) is None
            or not isinstance(record.get("mode"), int)
            or isinstance(record.get("mode"), bool)
        ):
            raise GoldenMasterSealHostError(
                f"release_manifest_public_external_invalid:{label}"
            )
    return document


def _normalized_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _image_config_contract(config: object) -> dict[str, object]:
    value = config if isinstance(config, dict) else {}
    result: dict[str, object] = {}
    sequence_fields = {"Entrypoint", "Cmd", "Env"}
    string_fields = {"User", "WorkingDir", "StopSignal"}
    mapping_fields = {
        "Labels",
        "Healthcheck",
        "Volumes",
        "ExposedPorts",
    }
    for key in (
        "Entrypoint",
        "Cmd",
        "User",
        "Env",
        "WorkingDir",
        "Labels",
        "Healthcheck",
        "StopSignal",
        "Volumes",
        "ExposedPorts",
    ):
        observed = value.get(key)
        if key in sequence_fields and observed is None:
            observed = []
        elif key in string_fields and observed is None:
            observed = ""
        elif key in mapping_fields and observed is None:
            observed = {}
        result[key] = observed
    return result


def _verify_images(
    runner: Runner,
    release: dict[str, Any],
) -> None:
    for label, record in release["images"].items():
        raw = runner.run(("docker", "image", "inspect", str(record["image"])))
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as error:
            raise GoldenMasterSealHostError(
                f"image_inspect_invalid:{label}"
            ) from error
        if (
            not isinstance(values, list)
            or len(values) != 1
            or not isinstance(values[0], dict)
        ):
            raise GoldenMasterSealHostError(
                f"image_inspect_invalid:{label}"
            )
        item = values[0]
        if (
            item.get("Id") != record["image_id"]
            or item.get("Architecture") != "arm64"
            or item.get("Os") != "linux"
            or record["platform"] != "linux/arm64"
        ):
            raise GoldenMasterSealHostError(
                f"image_exact_binding_invalid:{label}"
            )
        rootfs = item.get("RootFS")
        layers = rootfs.get("Layers") if isinstance(rootfs, dict) else None
        if (
            not isinstance(layers, list)
            or _normalized_hash(layers) != record["rootfs_layers_sha256"]
        ):
            raise GoldenMasterSealHostError(
                f"image_rootfs_binding_invalid:{label}"
            )
        if (
            _normalized_hash(_image_config_contract(item.get("Config")))
            != record["config_contract_sha256"]
        ):
            raise GoldenMasterSealHostError(
                f"image_config_binding_invalid:{label}"
            )


def _verify_public_external_files(release: dict[str, Any]) -> None:
    bindings = release["public_external_bindings"]
    for label, path in PUBLIC_EXTERNAL_FILES.items():
        if path.is_symlink() or not path.is_file():
            raise GoldenMasterSealHostError(
                f"public_external_file_missing:{label}"
            )
        metadata = path.stat()
        record = bindings[label]
        if (
            sha256_file(path) != record["sha256"]
            or stat.S_IMODE(metadata.st_mode) != record["mode"]
        ):
            raise GoldenMasterSealHostError(
                f"public_external_file_binding_invalid:{label}"
            )


def _listener_count(runner: Runner) -> int:
    output = runner.run(("ss", "-H", "-lntu"))
    count = 0
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            port = int(fields[4].rsplit(":", 1)[1].rstrip("]"))
        except (IndexError, ValueError):
            continue
        if port in TARGET_PORTS:
            count += 1
    return count


def _unit_load_state(runner: Runner, unit: str) -> str:
    return runner.run(
        ("systemctl", "show", "-p", "LoadState", "--value", unit),
        allowed=frozenset({0, 1}),
    ).strip()


def _systemctl(runner: Runner, operation: str, unit: str) -> str:
    return runner.run(
        ("systemctl", operation, unit),
        allowed=frozenset({0, 1, 3, 4}),
    ).strip()


def _require_absent_paths(paths: Sequence[str]) -> None:
    for value in paths:
        path = Path(value)
        if path.exists() or path.is_symlink():
            raise GoldenMasterSealHostError(
                f"instance_or_activation_path_present:{value}"
            )


def _require_no_staging_residue() -> None:
    for pattern in STAGING_GLOBS:
        parent = Path(pattern).parent
        name = Path(pattern).name
        if any(parent.glob(name)):
            raise GoldenMasterSealHostError(
                f"staging_residue_present:{name}"
            )


def _audit_product_namespace_whitelist() -> None:
    for parent, prefixes, allowed in PRODUCT_NAMESPACE_RULES:
        if not parent.is_dir() or parent.is_symlink():
            raise GoldenMasterSealHostError(
                f"product_namespace_parent_invalid:{parent}"
            )
        for path in parent.iterdir():
            if not any(path.name.startswith(prefix) for prefix in prefixes):
                continue
            if path.name not in allowed:
                raise GoldenMasterSealHostError(
                    f"product_namespace_not_whitelisted:{path}"
                )


def _audit_authorization_ledger(
    release: dict[str, Any],
) -> dict[str, object]:
    try:
        build = load_authorization_record(
            AUTHORIZATION_LEDGER_ROOT,
            BUILD_AUTHORIZATION_ID,
        )
        seal = load_authorization_record(
            AUTHORIZATION_LEDGER_ROOT,
            AUTHORIZATION_ID,
        )
    except (GoldenMasterCommonError, OSError, ValueError) as error:
        raise GoldenMasterSealHostError(
            "authorization_ledger_invalid"
        ) from error

    if build is None:
        raise GoldenMasterSealHostError(
            "build_authorization_record_missing"
        )
    expected = {
        "source_head": release["source_head"],
        "payload_manifest_sha256": release["payload_manifest_sha256"],
        "release_id": release["release_id"],
    }
    if build.get("operation") != "BUILD" or any(
        build.get(key) != value for key, value in expected.items()
    ):
        raise GoldenMasterSealHostError(
            "build_authorization_record_binding_invalid"
        )
    if seal is not None and (
        seal.get("operation") != "SEAL"
        or any(seal.get(key) != value for key, value in expected.items())
    ):
        raise GoldenMasterSealHostError(
            "seal_authorization_record_binding_invalid"
        )

    expected_paths = {
        authorization_record_path(
            AUTHORIZATION_LEDGER_ROOT,
            BUILD_AUTHORIZATION_ID,
        )
    }
    if seal is not None:
        expected_paths.add(
            authorization_record_path(
                AUTHORIZATION_LEDGER_ROOT,
                AUTHORIZATION_ID,
            )
        )
    try:
        observed_paths = {
            path
            for path in AUTHORIZATION_LEDGER_ROOT.iterdir()
            if path.exists() or path.is_symlink()
        }
    except OSError as error:
        raise GoldenMasterSealHostError(
            "authorization_ledger_invalid"
        ) from error
    if observed_paths != expected_paths:
        raise GoldenMasterSealHostError(
            "authorization_ledger_unknown_residue"
        )

    return {
        "authorization_ledger_classified": True,
        "authorization_ledger_policy": AUTHORIZATION_LEDGER_POLICY,
        "build_authorization_proven": True,
        "seal_authorization_claimed": seal is not None,
    }


def _audit_quiescence(runner: Runner) -> dict[str, object]:
    containers = tuple(
        value
        for value in runner.run(("docker", "ps", "-aq")).splitlines()
        if value
    )
    if containers:
        raise GoldenMasterSealHostError("product_container_present")

    volumes = tuple(
        value
        for value in runner.run(("docker", "volume", "ls", "-q")).splitlines()
        if value
    )
    if volumes:
        raise GoldenMasterSealHostError("product_volume_present")

    networks = frozenset(
        value
        for value in runner.run(
            ("docker", "network", "ls", "--format", "{{.Name}}")
        ).splitlines()
        if value
    )
    if networks != DEFAULT_NETWORKS:
        raise GoldenMasterSealHostError("product_network_set_invalid")

    listeners = _listener_count(runner)
    if listeners:
        raise GoldenMasterSealHostError("product_listener_present")

    firewall = runner.run(("iptables-save", "-t", "filter"))
    if (
        "N3WFC4-BROKER-INGRESS" in firewall
        or "n3wfc4-broker-ingress-v1" in firewall
    ):
        raise GoldenMasterSealHostError("product_firewall_active")

    if _unit_load_state(runner, GUARD_UNIT) != "loaded":
        raise GoldenMasterSealHostError("guard_unit_missing")
    if _systemctl(runner, "is-active", GUARD_UNIT) not in {
        "inactive",
        "unknown",
    }:
        raise GoldenMasterSealHostError("guard_unit_active")
    if _systemctl(runner, "is-enabled", GUARD_UNIT) not in {
        "disabled",
        "static",
        "indirect",
    }:
        raise GoldenMasterSealHostError("guard_unit_enabled")

    for unit in ABSENT_UNITS:
        if _unit_load_state(runner, unit) not in {"", "not-found"}:
            raise GoldenMasterSealHostError(
                f"activation_unit_present:{unit}"
            )

    _require_absent_paths((*INSTANCE_PATHS, *EXTRA_ABSENT))
    _require_no_staging_residue()
    _audit_product_namespace_whitelist()

    return {
        "product_container_count": 0,
        "product_volume_count": 0,
        "product_network_count": 0,
        "product_listener_count": 0,
        "product_firewall_active": False,
        "instance_material_absent": True,
        "activation_units_absent": True,
        "staging_residue_absent": True,
        "product_namespace_whitelist_exact": True,
        "forbidden_instance_inventory_absent": True,
    }


def audit_public_master(
    source_root: Path,
    *,
    runner: Runner | None = None,
) -> dict[str, object]:
    root = _source_root(source_root)
    release = _load_release(root)
    release_path = root / RELEASE_RELATIVE_PATH
    release_manifest_sha256 = sha256_file(release_path)
    excluded = frozenset({RELEASE_RELATIVE_PATH.as_posix()})
    try:
        observed_tree = public_tree_sha256(root, excluded=excluded)
    except GoldenMasterCommonError as error:
        raise GoldenMasterSealHostError(
            "public_source_tree_invalid"
        ) from error
    if observed_tree != release["public_source_tree_sha256"]:
        raise GoldenMasterSealHostError("public_source_tree_binding_invalid")

    image_lock = root / IMAGE_LOCK_RELATIVE_PATH
    if image_lock.is_symlink() or not image_lock.is_file():
        raise GoldenMasterSealHostError("image_lock_missing")
    if sha256_file(image_lock) != release["image_lock_sha256"]:
        raise GoldenMasterSealHostError("image_lock_binding_invalid")

    _verify_public_external_files(release)
    ledger = _audit_authorization_ledger(release)
    active = runner or Runner()
    _verify_images(active, release)
    quiescence = _audit_quiescence(active)
    public_audit = {
        "release_id": release["release_id"],
        "source_head": release["source_head"],
        "release_manifest_sha256": release_manifest_sha256,
        "image_lock_sha256": release["image_lock_sha256"],
        "public_source_tree_sha256": release["public_source_tree_sha256"],
        "public_external_bindings": release["public_external_bindings"],
        **ledger,
        **quiescence,
    }

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "public-audit",
        "release_id": release["release_id"],
        "source_head": release["source_head"],
        "release_manifest_sha256": release_manifest_sha256,
        "image_lock_sha256": release["image_lock_sha256"],
        "public_audit_sha256": canonical_sha256(public_audit),
        "exact_release_binding": True,
        "instance_material_absent": True,
        "public_source_tree_exact": True,
        "public_external_files_exact": True,
        "image_lock_exact": True,
        "image_binding_exact": True,
        **ledger,
        **quiescence,
        "target_identity_adapter_ready": False,
        "disk_capture_ready": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }


def execute_seal(_source_root: Path, authorization_id: str) -> dict[str, object]:
    if authorization_id != AUTHORIZATION_ID:
        raise GoldenMasterSealHostError("authorization_id_mismatch")
    raise GoldenMasterSealHostError("target_identity_adapter_required")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-golden-master-seal")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("/opt/HomeAssistant"),
    )
    parser.add_argument(
        "--phase",
        choices=("public-audit", "seal"),
        required=True,
    )
    parser.add_argument("--authorization-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.phase == "public-audit":
            result = audit_public_master(args.source_root)
        else:
            if not args.authorization_id:
                raise GoldenMasterSealHostError("authorization_id_required")
            result = execute_seal(args.source_root, args.authorization_id)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (
        GoldenMasterSealHostError,
        GoldenMasterCommonError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "replay_allowed": None,
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
