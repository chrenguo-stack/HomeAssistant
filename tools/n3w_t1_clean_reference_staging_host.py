#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from . import n3w_t1_fresh_product_staging_host as fresh
except ImportError:
    import n3w_t1_fresh_product_staging_host as fresh

SCHEMA = "gh.n3w-t1-clean-reference-r1-host/1"
RUNTIME_BINDING_SCHEMA = "gh.n3w-t1-clean-reference-runtime-binding/1"
S1_SCHEMA = "gh.n3w.t1-fresh-exact-arm64-binding/1"
CONFIRMATION = "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01"
RUNTIME_FILES = frozenset(
    {
        "runtime-payload.tar.gz",
        "runtime-payload.sha256",
        "payload-manifest.sha256",
        "capacity-contract.json",
        "capacity-contract.sha256",
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "host-baseline.py",
        "host-baseline.sha256",
        "runtime-binding.json",
        "build-report.json",
    }
)
IMAGE_CACHE_FILES = frozenset(
    {
        "binding.json",
        "greenhouse-manager-arm64.tar",
        "homeassistant-arm64.tar",
        "broker-arm64.tar",
    }
)


class CleanReferenceHostError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, error_code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CleanReferenceHostError(error_code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanReferenceHostError(error_code) from error
    if not isinstance(value, dict):
        raise CleanReferenceHostError(error_code)
    return value


def _exact_files(root: Path, expected: frozenset[str], error_code: str) -> None:
    if root.is_symlink() or not root.is_dir():
        raise CleanReferenceHostError(error_code)
    actual = {path.name for path in root.iterdir()}
    if actual != expected:
        raise CleanReferenceHostError(error_code)
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise CleanReferenceHostError(error_code)


def _materialize_local_work(
    runtime_root: Path,
    image_root: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    runtime_root = runtime_root.resolve()
    image_root = image_root.resolve()
    _exact_files(runtime_root, RUNTIME_FILES, "runtime_bundle_file_set_invalid")
    _exact_files(image_root, IMAGE_CACHE_FILES, "image_cache_file_set_invalid")

    runtime_binding = _read_json(
        runtime_root / "runtime-binding.json",
        "runtime_binding_invalid",
    )
    s1_binding = _read_json(image_root / "binding.json", "s1_binding_invalid")
    if runtime_binding.get("schema") != RUNTIME_BINDING_SCHEMA:
        raise CleanReferenceHostError("runtime_binding_schema_invalid")
    if s1_binding.get("schema") != S1_SCHEMA:
        raise CleanReferenceHostError("s1_binding_schema_invalid")
    source_head = runtime_binding.get("source_head")
    if (
        source_head != s1_binding.get("source_head")
        or runtime_binding.get("s1_binding_sha256")
        != _sha256_file(image_root / "binding.json")
        or runtime_binding.get("image_rebuild_performed") is not False
        or runtime_binding.get("registry_pull_performed") is not False
        or runtime_binding.get("production_service_start") is not False
    ):
        raise CleanReferenceHostError("runtime_s1_binding_mismatch")

    for label, filename in fresh.IMAGE_ARTIFACT_FILES.items():
        runtime_record = runtime_binding.get("images", {}).get(label)
        s1_record = s1_binding.get(label)
        if not isinstance(runtime_record, dict) or not isinstance(s1_record, dict):
            raise CleanReferenceHostError(f"image_binding_missing:{label}")
        if any(
            runtime_record.get(key) != s1_record.get(key)
            for key in (
                "image",
                "image_id",
                "tar_sha256",
                "tar_size_bytes",
                "platform",
            )
        ):
            raise CleanReferenceHostError(f"image_binding_mismatch:{label}")
        path = image_root / filename
        if (
            path.stat().st_size != runtime_record["tar_size_bytes"]
            or _sha256_file(path) != runtime_record["tar_sha256"]
        ):
            raise CleanReferenceHostError(f"image_cache_sha256_mismatch:{label}")

    work_parent = image_root.parent
    work = Path(
        tempfile.mkdtemp(prefix=".n3w-clean-reference-r1.", dir=str(work_parent))
    )
    try:
        for name in fresh.RELEASE_F3_PAYLOAD_FILES:
            shutil.copy2(runtime_root / name, work / name)
        for filename in fresh.IMAGE_ARTIFACT_FILES.values():
            source = image_root / filename
            target = work / filename
            try:
                os.link(source, target)
            except OSError as error:
                raise CleanReferenceHostError(
                    "image_cache_hardlink_required_same_filesystem"
                ) from error

        archive_sha = (runtime_root / "runtime-payload.sha256").read_text(
            encoding="ascii"
        ).strip()
        manifest_sha = (runtime_root / "payload-manifest.sha256").read_text(
            encoding="ascii"
        ).strip()
        archive = fresh._verify_outer_artifact(
            work,
            archive_sha256=archive_sha,
            manifest_sha256=manifest_sha,
        )
        manifest = fresh._read_payload_manifest(
            archive,
            manifest_sha256=manifest_sha,
        )
        capacity = fresh._capacity_contract(work, manifest)
        fresh._verify_image_artifacts(work, manifest, capacity)
        if manifest.get("source_head") != source_head:
            raise CleanReferenceHostError("payload_source_head_mismatch")
        for label in fresh.IMAGE_LABELS:
            manifest_record = manifest.get("images", {}).get(label)
            runtime_record = runtime_binding["images"][label]
            if not isinstance(manifest_record, dict):
                raise CleanReferenceHostError(f"payload_image_missing:{label}")
            if any(
                manifest_record.get(key) != runtime_record.get(key)
                for key in (
                    "image",
                    "image_id",
                    "tar_sha256",
                    "tar_size_bytes",
                    "platform",
                )
            ):
                raise CleanReferenceHostError(
                    f"payload_image_binding_mismatch:{label}"
                )
        return work, manifest, capacity
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise


def _transfer_executor(t1: str, remote_dir: str) -> str:
    source = Path(__file__).with_name("n3w_t1_clean_reference_executor.py")
    if source.is_symlink() or not source.is_file():
        raise CleanReferenceHostError("clean_reference_executor_missing")
    expected_sha = _sha256_file(source)
    remote = f"{remote_dir}.executor.py"
    fresh._run(("scp", str(source), f"{t1}:{remote}"), timeout=120)
    probe = fresh._run(
        (
            "ssh",
            "-n",
            t1,
            fresh._remote_command(("sha256sum", remote)),
        ),
        timeout=30,
    ).stdout.strip().split()
    if not probe or probe[0] != expected_sha:
        raise CleanReferenceHostError("clean_reference_executor_transfer_mismatch")
    return remote


def _preflight(
    t1: str,
    work: Path,
    manifest: dict[str, Any],
    capacity: dict[str, Any],
) -> dict[str, Any]:
    baseline = fresh._remote_baseline_report(t1, work / "host-baseline.py", "check")
    if baseline.get("status") != "PASS":
        raise CleanReferenceHostError("r0h_host_baseline_not_ready")
    storage = fresh._remote_storage_report(t1)
    archive = work / "runtime-payload.tar.gz"
    plan = fresh._plan_transport(
        manifest,
        archive_size_bytes=archive.stat().st_size,
        remote_free_bytes=min(
            int(storage["staging_free_bytes"]),
            int(storage["docker_free_bytes"]),
            int(storage["image_store_free_bytes"]),
        ),
        capacity=capacity,
    )
    if not plan.capacity_pass:
        raise CleanReferenceHostError("remote_capacity_insufficient")
    return {
        "baseline": baseline,
        "storage": storage,
        "plan": plan,
    }


def _cleanup_remote(t1: str, remote_dir: str) -> bool:
    try:
        completed = fresh._run(
            (
                "ssh",
                "-n",
                t1,
                fresh._remote_command(
                    (
                        "rm",
                        "-rf",
                        "--",
                        remote_dir,
                        f"{remote_dir}.executor.py",
                    )
                ),
            ),
            timeout=120,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def _execute_apply(
    t1: str,
    work: Path,
    manifest: dict[str, Any],
    capacity: dict[str, Any],
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise CleanReferenceHostError("clean_reference_confirmation_mismatch")
    archive_sha = (work / "runtime-payload.sha256").read_text(
        encoding="ascii"
    ).strip()
    manifest_sha = (work / "payload-manifest.sha256").read_text(
        encoding="ascii"
    ).strip()
    remote_dir = fresh._remote_mktemp(t1, "n3w-clean-reference-r1")
    prepared = False
    authorized = False
    final_report: dict[str, Any] | None = None
    try:
        fresh._remote_prepare_payload(
            t1,
            remote_dir,
            work / "runtime-payload.tar.gz",
            archive_sha256=archive_sha,
            manifest_sha256=manifest_sha,
        )
        prepared = True
        executor = _transfer_executor(t1, remote_dir)
        command = fresh._remote_command(
            (
                "python3",
                executor,
                "--payload-root",
                remote_dir,
                "--phase",
                "apply",
                "--confirmation",
                confirmation,
            )
        )
        process = subprocess.Popen(
            ("ssh", "-n", t1, command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        requested: list[str] = []
        loaded: list[str] = []
        assert process.stdout is not None
        try:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event") == "clean_reference_authorized":
                    if event.get("confirmation") != CONFIRMATION:
                        raise CleanReferenceHostError(
                            "clean_reference_authorization_event_invalid"
                        )
                    authorized = True
                    continue
                if event.get("event") == "image_requested":
                    if not authorized:
                        raise CleanReferenceHostError(
                            "image_requested_before_clean_reference_authorization"
                        )
                    label = str(event.get("label"))
                    expected = (
                        fresh.IMAGE_LABELS[len(requested)]
                        if len(requested) < len(fresh.IMAGE_LABELS)
                        else None
                    )
                    if label != expected or label in requested:
                        raise CleanReferenceHostError("image_request_order_invalid")
                    fresh._transfer_requested_image(
                        t1,
                        remote_dir,
                        work,
                        manifest,
                        capacity,
                        label,
                    )
                    requested.append(label)
                    continue
                if event.get("event") == "image_loaded":
                    label = str(event.get("label"))
                    expected = (
                        fresh.IMAGE_LABELS[len(loaded)]
                        if len(loaded) < len(fresh.IMAGE_LABELS)
                        else None
                    )
                    if (
                        label != expected
                        or label not in requested
                        or event.get("staged_tar_deleted") is not True
                    ):
                        raise CleanReferenceHostError("image_load_event_invalid")
                    if fresh._remote_free_bytes(t1) < fresh.MIN_POST_PEAK_FREE_BYTES:
                        raise CleanReferenceHostError("postload_reserve_breached")
                    loaded.append(label)
                    continue
                if (
                    event.get("schema")
                    == "gh.n3w-t1-clean-reference-r1-executor/1"
                    and event.get("phase") == "apply"
                ):
                    final_report = event
            return_code = process.wait()
        except Exception:
            fresh._stop_remote_apply_process(process)
            raise
        if return_code != 0:
            raise CleanReferenceHostError("clean_reference_remote_apply_failed")
        if (
            tuple(requested) != fresh.IMAGE_LABELS
            or tuple(loaded) != fresh.IMAGE_LABELS
            or not authorized
            or not isinstance(final_report, dict)
            or final_report.get("status") != "PASS"
            or final_report.get("fresh_product_staged") is not True
            or final_report.get("node_credential_count") != 0
            or final_report.get("production_v2_authority_used") is not False
            or final_report.get("production_service_start") is not False
            or final_report.get("activation_authorized") is not False
        ):
            raise CleanReferenceHostError("clean_reference_apply_result_invalid")

        removed = _cleanup_remote(t1, remote_dir)
        if not removed:
            raise CleanReferenceHostError(
                "clean_reference_postsuccess_temp_cleanup_failed"
            )
        prepared = False
        return {
            "status": "PASS",
            "fresh_product_staged": True,
            "node_credential_count": 0,
            "image_request_sequence": list(requested),
            "image_load_sequence": list(loaded),
            "production_v2_authority_used": False,
            "production_service_start": False,
            "activation_authorized": False,
            "board_access": False,
        }
    except Exception:
        if prepared:
            print(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "status": "STOP",
                        "remote_payload_preserved": True,
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", required=True)
    parser.add_argument("--runtime-bundle-root", type=Path, required=True)
    parser.add_argument("--image-cache-root", type=Path, required=True)
    parser.add_argument(
        "--phase",
        choices=("preflight", "apply"),
        required=True,
    )
    parser.add_argument("--confirmation")
    return parser


def main() -> int:
    args = _parser().parse_args()
    work: Path | None = None
    try:
        work, manifest, capacity = _materialize_local_work(
            args.runtime_bundle_root,
            args.image_cache_root,
        )
        report = _preflight(args.t1, work, manifest, capacity)
        if args.phase == "preflight":
            result = {
                "schema": SCHEMA,
                "status": "PASS",
                "phase": "preflight",
                "source_head": manifest["source_head"],
                "host_baseline": "PASS",
                "transport": report["plan"].to_dict(),
                "local_exact_image_cache": True,
                "github_large_artifact_download": False,
                "payload_transfer": False,
                "docker_mutation": False,
                "production_v2_authority_used": False,
                "production_service_start": False,
                "activation_authorized": False,
                "board_access": False,
            }
        else:
            if not args.confirmation:
                raise CleanReferenceHostError(
                    "clean_reference_confirmation_required"
                )
            applied = _execute_apply(
                args.t1,
                work,
                manifest,
                capacity,
                args.confirmation,
            )
            result = {
                "schema": SCHEMA,
                "phase": "apply",
                "source_head": manifest["source_head"],
                "local_exact_image_cache": True,
                "github_large_artifact_download": False,
                **applied,
            }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
        return 0
    except (
        CleanReferenceHostError,
        fresh.FreshHostTransportError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
                    "local_exact_image_cache": True,
                    "github_large_artifact_download": False,
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
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
