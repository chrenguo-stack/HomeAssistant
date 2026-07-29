#!/usr/bin/env python3
"""Deterministic review package builder for request -06."""
from h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_packager_support_20260729_v1 import *

def build_execution_package(repository_root: Path, upstream_package: Path,
                            output_root: Path, source_sha: str) -> dict[str, str]:
    output_root.mkdir(parents=True, mode=0o700)
    for path in sorted(upstream_package.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.name == contract.ROOT_SUMS_FILE:
            shutil.copyfile(path, output_root / contract.UPSTREAM_SUMS_FILE)
        else:
            shutil.copyfile(path, output_root / path.name)
        os.chmod(output_root / (contract.UPSTREAM_SUMS_FILE if path.name == contract.ROOT_SUMS_FILE else path.name), 0o600)

    source_map = {
        "h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_base_20260729_v1.py": repository_root / "tools" / "h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_base_20260729_v1.py",
        contract.OVERLAY_HELPER_FILE: repository_root / "tools" / contract.OVERLAY_HELPER_FILE,
        contract.OVERLAY_CONTRACT_FILE: repository_root / "tools" / contract.OVERLAY_CONTRACT_FILE,
        contract.OVERLAY_WRAPPER_FILE: repository_root / "tools" / contract.OVERLAY_WRAPPER_FILE,
        contract.OVERLAY_LAUNCHER_FILE: repository_root / "tools" / contract.OVERLAY_LAUNCHER_FILE,
    }
    for name, source in source_map.items():
        contract.require(source.is_file(), "OVERLAY_SOURCE_FILE_MISSING")
        shutil.copyfile(source, output_root / name)
        os.chmod(output_root / name, 0o600)

    binding = contract.overlay_binding(
        source_sha=source_sha,
        wrapper_sha256=contract.sha256_file(output_root / contract.OVERLAY_WRAPPER_FILE),
        launcher_sha256=contract.sha256_file(output_root / contract.OVERLAY_LAUNCHER_FILE),
    )
    write_json(output_root / contract.OVERLAY_BINDING_FILE, binding)
    manifest = contract.overlay_manifest(
        binding_sha256=contract.sha256_file(output_root / contract.OVERLAY_BINDING_FILE),
        contract_sha256=contract.sha256_file(output_root / contract.OVERLAY_CONTRACT_FILE),
        wrapper_sha256=contract.sha256_file(output_root / contract.OVERLAY_WRAPPER_FILE),
        launcher_sha256=contract.sha256_file(output_root / contract.OVERLAY_LAUNCHER_FILE),
        upstream_sums_sha256=contract.sha256_file(output_root / contract.UPSTREAM_SUMS_FILE),
    )
    write_json(output_root / contract.OVERLAY_MANIFEST_FILE, manifest)
    write_sums(output_root)
    contract.validate_execution_overlay(output_root)
    return {
        "execution_package_sha256": contract.canonical_package_digest(output_root),
        "execution_overlay_sha256": manifest["execution_overlay_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
    }


def add_tar_file(archive: tarfile.TarFile, root: Path, relative: str) -> None:
    data = (root / relative).read_bytes()
    info = tarfile.TarInfo(relative)
    info.size = len(data)
    info.mode = 0o600
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    archive.addfile(info, io.BytesIO(data))


def build(repository_root: Path, upstream_artifact_zip: Path, output_root: Path,
          source_sha: str, repository_head_sha: str) -> dict[str, object]:
    source_sha = contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    repository_head_sha = contract.validate_sha40(repository_head_sha, "REPOSITORY_HEAD_SHA_INVALID")
    contract.require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR198")
    if output_root.exists():
        contract.require(not any(output_root.iterdir()), "OUTPUT_ROOT_MUST_BE_EMPTY")
    else:
        output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)

    with tempfile.TemporaryDirectory(prefix="stage2d9r-overlay-packager-") as directory:
        upstream_package = verify_upstream_artifact(upstream_artifact_zip, Path(directory))
        for relative in SOURCE_FILES:
            source = repository_root / relative
            contract.require(source.is_file(), "SOURCE_FILE_MISSING")
            target = output_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            os.chmod(target, 0o600)
        package_values = build_execution_package(
            repository_root,
            upstream_package,
            output_root / EXECUTION_PACKAGE_DIR,
            source_sha,
        )

    write_json(output_root / REQUEST_05_DISPOSITION_FILE, contract.request_05_invalidation_disposition())
    write_json(output_root / UPSTREAM_REFERENCE_FILE, {
        "artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "embedded": False,
    })

    provisional_review = {
        "schema": contract.REVIEW_SCHEMA,
        "state": "PHYSICAL_EXECUTION_OVERLAY_BINDING_REPAIR_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "decision_id": contract.DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_branch": contract.BASE_BRANCH,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": repository_head_sha,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "request_05_id": contract.REQUEST_05_ID,
        "request_05_state": contract.REQUEST_05_INVALID_STATE,
        "request_06_id": contract.REQUEST_06_ID,
        "corrected_baseline_sha256": contract.CORRECTED_BASELINE_SHA256,
        "invalid_baseline_sha256": contract.INVALID_BASELINE_SHA256,
        "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
        "immutable_payload_changed": False,
        "recovery_payload_changed": False,
        **package_values,
        **contract.FALSE_BOUNDARY,
    }
    review_binding = contract.canonical_json_sha256(provisional_review)
    review = dict(provisional_review)
    review["review_binding_sha256"] = review_binding
    write_json(output_root / REVIEW_FILE, review)

    request = contract.build_physical_request(
        source_sha=source_sha,
        review_binding_sha256=review_binding,
        package_root=output_root / EXECUTION_PACKAGE_DIR,
        execution_package_sha256=package_values["execution_package_sha256"],
    )
    write_json(output_root / REQUEST_06_FILE, request)
    contract.validate_physical_request(request, output_root / EXECUTION_PACKAGE_DIR)

    archive_members = [name for name in recursive_files(output_root) if name not in {ARCHIVE_FILE, contract.ROOT_SUMS_FILE}]
    with tarfile.open(output_root / ARCHIVE_FILE, "w", format=tarfile.PAX_FORMAT) as archive:
        for relative in archive_members:
            add_tar_file(archive, output_root, relative)
    os.chmod(output_root / ARCHIVE_FILE, 0o600)

    checksum_lines = []
    for relative in recursive_files(output_root):
        if relative == contract.ROOT_SUMS_FILE:
            continue
        checksum_lines.append(f"{contract.sha256_file(output_root / relative)}  {relative}")
    (output_root / contract.ROOT_SUMS_FILE).write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    os.chmod(output_root / contract.ROOT_SUMS_FILE, 0o600)

    return {
        "status": "PASS",
        "source_sha": source_sha,
        "review_binding_sha256": review_binding,
        "archive_sha256": contract.sha256_file(output_root / ARCHIVE_FILE),
        "execution_package_sha256": package_values["execution_package_sha256"],
        "execution_overlay_sha256": package_values["execution_overlay_sha256"],
        "request_05_state": contract.REQUEST_05_INVALID_STATE,
        "request_06_created": True,
        "request_06_binding_sha256": request["request_binding_sha256"],
        "request_06_authorized": False,
        "board_operation": False,
        "network_operation": False,
        "file_count": len(recursive_files(output_root)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--upstream-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repository-head-sha", required=True)
    args = parser.parse_args()
    result = build(
        args.repository_root.resolve(),
        args.upstream_artifact_zip.resolve(),
        args.output_root.resolve(),
        args.source_sha,
        args.repository_head_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
