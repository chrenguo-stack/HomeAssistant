#!/usr/bin/env python3
"""Fail-closed validator for Stage 2D-9R command-material descriptors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

PRIVATE_SCHEMA = "gh.h3.n2.stage2d9r-private-command-material-descriptor/1"
PUBLIC_SCHEMA = "gh.h3.n2.stage2d9r-public-command-material-descriptor/1"
STATE = "COMMAND_MATERIAL_FROZEN"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FALSE_PRIVATE = (
    "private_values_included",
    "raw_unlock_token_in_descriptor",
    "board_operation_authorized",
    "network_operation_authorized",
    "broker_operation_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "production_operation_authorized",
)
FALSE_PUBLIC = (
    "private_values_included",
    "private_paths_included",
    "raw_unlock_token_included",
    "execution_authorized",
    "board_operation_authorized",
    "network_operation_authorized",
    "broker_operation_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "production_operation_authorized",
)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def private_path(value: object) -> bool:
    path = PurePosixPath(str(value))
    if not path.is_absolute() or ".." in path.parts:
        return False
    for forbidden in (PurePosixPath("/tmp"), PurePosixPath("/private/tmp"), PurePosixPath("/Users/Shared")):
        try:
            path.relative_to(forbidden)
        except ValueError:
            continue
        return False
    return True


def validate(private: dict[str, Any], public: dict[str, Any]) -> None:
    require(private.get("schema") == PRIVATE_SCHEMA, "private schema mismatch")
    require(public.get("schema") == PUBLIC_SCHEMA, "public schema mismatch")
    require(private.get("state") == STATE and public.get("state") == STATE, "state mismatch")
    for key in ("source_sha", "implementation_binding"):
        require(HEX40.fullmatch(str(private.get(key))) is not None, f"private {key} invalid")
        require(public.get(key) == private.get(key), f"{key} binding mismatch")
    for key in ("generator_sha256", "python_executable_sha256", "public_descriptor_sha256"):
        require(HEX64.fullmatch(str(private.get(key))) is not None, f"{key} invalid")
    require(private.get("test_run_suffix") == "tlsvalid01", "private suffix mismatch")
    require(public.get("test_run_suffix") == "tlsvalid01", "public suffix mismatch")
    require(private_path(private.get("custody_root")), "custody root invalid")
    require(private.get("custody_root_mode") == "0700", "custody mode mismatch")
    token = private.get("unlock_token")
    require(isinstance(token, dict), "unlock token metadata missing")
    require(token.get("relative_path") == "unlock-token.hex", "token relative path mismatch")
    require(token.get("mode") == "0600", "token mode mismatch")
    require(HEX64.fullmatch(str(token.get("file_sha256"))) is not None, "token file sha invalid")
    require(HEX64.fullmatch(str(token.get("unlock_digest_sha256"))) is not None, "unlock digest invalid")
    require(token.get("unlock_digest_sha256") != "0" * 64, "zero unlock digest rejected")
    require(public.get("unlock_digest_sha256") == token.get("unlock_digest_sha256"), "unlock digest binding mismatch")
    require(HEX64.fullmatch(str(public.get("private_material_package_sha256"))) is not None, "private package digest invalid")
    authorization = private.get("authorization")
    require(isinstance(authorization, dict), "authorization missing")
    require(str(authorization.get("authorization_id", "")).startswith("U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-"), "authorization id invalid")
    require(authorization.get("operation") == "GENERATE_PRIVATE_COMMAND_MATERIAL", "authorization operation mismatch")
    require(authorization.get("authorized") is True, "authorization not recorded")
    require(authorization.get("consumed") is True, "authorization not consumed")
    require(authorization.get("one_shot") is True, "authorization not one-shot")
    require(authorization.get("replay_permitted") is False, "authorization replay enabled")
    require(HEX64.fullmatch(str(authorization.get("record_sha256"))) is not None, "authorization digest invalid")
    for key in FALSE_PRIVATE:
        require(private.get(key) is False, f"private {key} must be false")
    for key in FALSE_PUBLIC:
        require(public.get(key) is False, f"public {key} must be false")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-descriptor", type=Path, required=True)
    parser.add_argument("--public-descriptor", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(
            json.loads(args.private_descriptor.read_text()),
            json.loads(args.public_descriptor.read_text()),
        )
    except Exception as exc:
        print("STAGE2D9R_PRIVATE_COMMAND_MATERIAL_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2
    print("STAGE2D9R_PRIVATE_COMMAND_MATERIAL_GATE=PASS")
    print("STATE=COMMAND_MATERIAL_FROZEN")
    print("PRIVATE_VALUES_INCLUDED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    print("BROKER_OPERATION_AUTHORIZED=false")
    print("PREPARE_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
