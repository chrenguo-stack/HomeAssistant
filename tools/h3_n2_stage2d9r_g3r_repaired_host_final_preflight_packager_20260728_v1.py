#!/usr/bin/env python3
"""Build deterministic repaired host-final-preflight review packages."""
from __future__ import annotations

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_execution_20260728_v1 import *

def build(
    repository_root: Path,
    immutable_zip: Path,
    output_root: Path,
    source_sha: str,
) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    immutable_zip = immutable_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_NOT_LAYERED")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)

    baseline_archive, baseline_acceptance = reconstruct_baseline(repository_root)
    immutable_files = validate_immutable_zip(immutable_zip)

    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    write_file(output_root / BASELINE_ARCHIVE_NAME, baseline_archive, 0o600)
    copy_public(immutable_zip, output_root / IMMUTABLE_ZIP_NAME)

    execution = build_execution_package(
        repository_root,
        output_root / EXECUTION_DIR,
        source_sha,
        immutable_files,
    )

    binding: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "state": "HOST_FINAL_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "chain_decision_id": contract.CHAIN_DECISION_ID,
        "main_correction_decision_id": contract.MAIN_CORRECTION_DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_branch": contract.BASE_BRANCH,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "baseline_original_main_sha": contract.BASELINE_ORIGINAL_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "main_tree_zero_net_change": True,
        "accidental_commit_sha": contract.ACCIDENTAL_COMMIT_SHA,
        "correction_commit_sha": contract.CORRECTION_COMMIT_SHA,
        "immutable_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": contract.IMMUTABLE_ARTIFACT_SHA256,
        "final_execution_binding": contract.FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": contract.FINAL_EXECUTION_BINDING_SHA256,
        "baseline_authorization_id": contract.BASELINE_AUTHORIZATION_ID,
        "baseline_public_archive_sha256": contract.BASELINE_PUBLIC_ARCHIVE_SHA256,
        "baseline_public_acceptance_sha256": contract.BASELINE_PUBLIC_ACCEPTANCE_SHA256,
        "baseline_result_sha256": contract.BASELINE_RESULT_SHA256,
        "baseline_status": "CONSUMED_PASS",
        "baseline_replay_permitted": False,
        **execution,
        "future_host_authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
        "future_physical_d2_request_id": contract.PHYSICAL_D2_REQUEST_ID,
        "artifact_purpose": "HOST_ONLY_FINAL_PREFLIGHT_SOURCE_REVIEW",
        "host_preflight_executed": False,
        **contract.FALSE_BOUNDARY,
    }
    binding_without = dict(binding)
    binding["review_binding_sha256"] = canonical_sha256(binding_without)
    write_file(output_root / BINDING_FILE, pretty_bytes(binding), 0o600)

    request = contract.build_request_template(
        source_sha=source_sha,
        review_binding_sha256=binding["review_binding_sha256"],
        execution_package_sha256=execution["execution_package_sha256"],
        execution_wrapper_sha256=execution["execution_wrapper_sha256"],
        execution_launcher_sha256=execution["execution_launcher_sha256"],
        repaired_host_controller_sha256=execution["repaired_host_controller_sha256"],
    )
    write_file(output_root / REQUEST_FILE, pretty_bytes(request), 0o600)

    readme = f"""# Repaired Stage2D9R host-only final preflight review package

This public package is bound to PR #{contract.BASE_PR} HEAD
`{contract.BASE_HEAD_SHA}`, the accepted current main
`{contract.ACCEPTED_CURRENT_MAIN_SHA}`, and the baseline's original main
`{contract.BASELINE_ORIGINAL_MAIN_SHA}`.

It contains a public unauthorized physical-D2 execution package, the canonical
immutable/recovery ZIP, and the redacted consumed baseline evidence. It contains
no authorization record, private key, password preimage, persistence key,
unlock token, private command, private path, or secret value.

Do not connect a board or execute the physical launcher. A separately approved
host-only preflight must complete first and may emit only an authorized=false
physical-D2 request.
"""
    write_file(output_root / "README.md", readme.encode(), 0o600)

    files_before_sums = recursive_files(
        output_root,
        exclude={SUMS_FILE, REVIEW_ARCHIVE_NAME},
    )
    sums = "".join(
        f"{sha256_bytes(files_before_sums[name])}  {name}\n"
        for name in sorted(files_before_sums)
    ).encode()
    write_file(output_root / SUMS_FILE, sums, 0o600)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive, 0o600)

    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-repaired-host-final-preflight-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "archive_name": REVIEW_ARCHIVE_NAME,
        "archive_sha256": sha256_bytes(archive),
        "review_binding_sha256": binding["review_binding_sha256"],
        "execution_package_sha256": execution["execution_package_sha256"],
        "execution_wrapper_sha256": execution["execution_wrapper_sha256"],
        "execution_launcher_sha256": execution["execution_launcher_sha256"],
        "repaired_host_controller_sha256": execution["repaired_host_controller_sha256"],
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--immutable-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        result = build(
            args.repository_root,
            args.immutable_artifact_zip,
            args.output_root,
            args.source_sha,
        )
    except Exception as exc:
        code = (
            exc.args[0]
            if isinstance(exc, (PackageError, contract.ContractError)) and exc.args
            else type(exc).__name__
        )
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
