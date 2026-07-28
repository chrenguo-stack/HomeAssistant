#!/usr/bin/env python3
"""One-shot host-only final preflight for repaired Stage2D9R."""
from __future__ import annotations

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_validation_20260728_v1 import *

def claim(marker: Path, authorization: Mapping[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json_exclusive(
        marker,
        {
            "schema": MARKER_SCHEMA,
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "status": "CLAIMED",
            "authorization_record_sha256": authorization["authorization_record_sha256"],
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "secret_values_included": False,
            "private_paths_included": False,
        },
    )


def finish_marker(marker: Path, status: str, result_sha256: str, failure_code: str | None) -> None:
    replace_json(
        marker,
        {
            "schema": MARKER_SCHEMA,
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "status": status,
            "terminal_result_sha256": result_sha256,
            "failure_code": failure_code,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "secret_values_included": False,
            "private_paths_included": False,
        },
    )


def execute(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    package_root = args.package_root.expanduser().resolve(strict=True)
    binding, request_template, package_digests = validate_package(package_root)
    toolchain = probe_toolchain(args)
    home = args.home.expanduser().resolve(strict=True)
    custody = (home / CUSTODY_RELATIVE).resolve(strict=True)
    authorization = validate_authorization(
        args.authorization.expanduser().resolve(strict=True),
        package_root=package_root,
        binding=binding,
        package_digests=package_digests,
        toolchain=toolchain,
        custody_root=custody,
    )
    marker = (
        home / AUTH_STATE_RELATIVE
        / (sha256_bytes(contract.FUTURE_HOST_AUTHORIZATION_ID.encode("utf-8")) + ".json")
    ).resolve(strict=False)
    claim(marker, authorization)
    try:
        custody_result = validate_private_custody(custody, toolchain["openssl_path"])
        result: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "state": "HOST_FINAL_PREFLIGHT_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION",
            "status": "CONSUMED_PASS",
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "source_sha": binding["source_sha"],
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "baseline_original_main_sha": contract.BASELINE_ORIGINAL_MAIN_SHA,
            "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
            "main_tree_zero_net_change": True,
            "review_binding_sha256": binding["review_binding_sha256"],
            **package_digests,
            **custody_result,
            "immutable_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
            "immutable_artifact_sha256": contract.IMMUTABLE_ARTIFACT_SHA256,
            "final_execution_binding": contract.FINAL_EXECUTION_BINDING,
            "final_execution_binding_sha256": contract.FINAL_EXECUTION_BINDING_SHA256,
            "baseline_result_sha256": contract.BASELINE_RESULT_SHA256,
            "board_identity_sha256": contract.BOARD_IDENTITY_SHA256,
            "serial_identity_sha256": contract.SERIAL_IDENTITY_SHA256,
            "baseline_state_sha256": contract.BASELINE_STATE_SHA256,
            "python_executable_sha256": toolchain["python_executable_sha256"],
            "openssl_executable_sha256": toolchain["openssl_executable_sha256"],
            "esptool_executable_sha256": toolchain["esptool_executable_sha256"],
            "esptool_module_sha256": toolchain["esptool_module_sha256"],
            "pyserial_module_sha256": toolchain["pyserial_module_sha256"],
            "mosquitto_executable_sha256": toolchain["mosquitto_executable_sha256"],
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
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
            "activate_executed": False,
            "cleanup_executed": False,
            "ready": False,
            "merge": False,
            "release": False,
            "tag": False,
            "deployment": False,
            "private_values_included": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        result["preflight_result_sha256"] = canonical_sha256(result)
        issued = datetime.now(timezone.utc).replace(microsecond=0)
        expires = issued + timedelta(hours=2)
        request = contract.finalize_request(
            request_template,
            host_preflight_result_sha256=result["preflight_result_sha256"],
            toolchain={
                key: toolchain[key]
                for key in (
                    "python_executable_sha256",
                    "openssl_executable_sha256",
                    "esptool_executable_sha256",
                    "esptool_module_sha256",
                    "pyserial_module_sha256",
                    "mosquitto_executable_sha256",
                )
            },
            issued_at=issued.isoformat().replace("+00:00", "Z"),
            expires_at=expires.isoformat().replace("+00:00", "Z"),
        )
        write_json_exclusive(args.preflight_output, result)
        write_json_exclusive(args.request_output, request)
        finish_marker(marker, "CONSUMED_PASS", result["preflight_result_sha256"], None)
        return result, request
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (ProbeError, private_contract.ContractError, protocol.CommandError)) and exc.args else type(exc).__name__
        failure = {
            "schema": RESULT_SCHEMA,
            "status": "CONSUMED_FAILED",
            "failure_code": str(code),
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
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
        failure["preflight_result_sha256"] = canonical_sha256(failure)
        if not args.preflight_output.exists():
            write_json_exclusive(args.preflight_output, failure)
        finish_marker(marker, "CONSUMED_FAILED", failure["preflight_result_sha256"], str(code))
        raise ProbeError(str(code)) from exc


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--probe-host", action="store_true")
    value.add_argument("--package-root", type=Path)
    value.add_argument("--authorization", type=Path)
    value.add_argument("--preflight-output", type=Path)
    value.add_argument("--request-output", type=Path)
    value.add_argument("--home", type=Path, default=Path.home())
    value.add_argument("--openssl")
    value.add_argument("--esptool")
    value.add_argument("--mosquitto")
    return value


def main() -> int:
    args = parser().parse_args()
    if not args.probe_host:
        print(
            json.dumps(
                {
                    "status": "SOURCE_ONLY_AWAITING_EXACT_HOST_PREFLIGHT_AUTHORIZATION",
                    "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
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
                },
                sort_keys=True,
            )
        )
        return 0
    for name in ("package_root", "authorization", "preflight_output", "request_output"):
        require(getattr(args, name) is not None, "ARGUMENT_REQUIRED_" + name.upper())
    try:
        result, request = execute(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ProbeError) and exc.args else type(exc).__name__
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "failure_code": str(code),
                    "authorization_created": False,
                    "board_operation": False,
                    "usb_enumeration": False,
                    "serial_operation": False,
                    "flash_operation": False,
                    "network_operation": False,
                    "prepare_executed": False,
                    "verify_executed": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "preflight_result_sha256": result["preflight_result_sha256"],
                "request_binding_sha256": request["request_binding_sha256"],
                "authorized": False,
                "authorization_created": False,
                "authorization_claimed": False,
                "authorization_consumed": False,
                "host_authorization_consumed": True,
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
