#!/usr/bin/env python3
"""Assemble the public-only Stage 2D-9R U1-04 preauthorization review package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

REQUEST_ID = "U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-20260724-04"
STAGE = "H3/N2 Stage 2D-9R G3R"
BRANCH = "feature/h3-n2-stage2d9r-g3-tls-valid-candidate-20260723-v1"
U1_03_MARKER_SHA256 = "8aa4a1bcc20f55cf027d1e047286e8289682af7c261d9afb540641427bce15c7"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

FILES = {
    "tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v1.py": "tools",
    "tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v3.py": "tools",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_private_content_binding_probe_20260724_v4.py": "tests",
    "docs/development/h3-n2-stage2d9r-private-content-binding-u1-review-20260724-v2.md": "review",
    "docs/acceptance/h3-n2-stage2d9r-private-content-u1-03-failure-l1-v1.json": "acceptance",
    "tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/public-descriptor.redacted.json": "public",
    "tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/isolated-broker-public-config.redacted.json": "public",
    "tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/root-ca.cert.txt": "public",
    "tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/broker.cert.txt": "public",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_public_inputs(repository: Path) -> None:
    failure = json.loads(
        (repository / "docs/acceptance/h3-n2-stage2d9r-private-content-u1-03-failure-l1-v1.json").read_text()
    )
    public = json.loads(
        (repository / "tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/public-descriptor.redacted.json").read_text()
    )
    require(failure["authorization_id"].endswith("-03"), "U1_03_AUTHORIZATION_ID_MISMATCH")
    require(failure["status"] == "CONSUMED_FAILED", "U1_03_STATUS_MISMATCH")
    require(
        failure["failure_code"] == "BROKER_CERTIFICATE_DIGEST_MISMATCH",
        "U1_03_FAILURE_CODE_MISMATCH",
    )
    require(failure["consumed_marker_sha256"] == U1_03_MARKER_SHA256, "U1_03_MARKER_MISMATCH")
    require(failure["replay_permitted"] is False, "U1_03_REPLAY_MISMATCH")
    require(failure["automatic_retry_permitted"] is False, "U1_03_RETRY_MISMATCH")
    material = public["public_material"]
    require(
        material["broker_certificate_sha256"]
        == "988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7",
        "BROKER_CERTIFICATE_PUBLIC_BINDING_MISMATCH",
    )
    require(
        material["broker_spki_sha256"]
        == "f034dc2a036f709287f0558773418ee1799e75bee50dcf55e09143a3a9052a03",
        "BROKER_SPKI_PUBLIC_BINDING_MISMATCH",
    )
    require(
        material["ca_pem_sha256"]
        == "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963",
        "CA_PEM_PUBLIC_BINDING_MISMATCH",
    )


def build_binding(output: Path, source_sha: str, main_sha: str) -> dict[str, Any]:
    binding: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-private-content-binding-review-package/1",
        "stage": STAGE,
        "state": "PENDING_EXACT_U1_TOOLCHAIN_PROBE_V5",
        "authorization_request_id": REQUEST_ID,
        "repository": "chrenguo-stack/HomeAssistant",
        "pull_request": 176,
        "main_sha": main_sha,
        "source_sha": source_sha,
        "head_branch": BRANCH,
        "probe_sha256": sha256_file(
            output / "tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v3.py"
        ),
        "base_probe_sha256": sha256_file(
            output / "tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v1.py"
        ),
        "contract_test_sha256": sha256_file(
            output / "tests/test_h3_n2_stage2d9r_private_content_binding_probe_20260724_v4.py"
        ),
        "command_group_sha256": sha256_file(output / "COMMAND_GROUP_REVIEW_ONLY.txt"),
        "stop_conditions_sha256": sha256_file(output / "STOP_CONDITIONS.md"),
        "u1_03_failed_marker_sha256": U1_03_MARKER_SHA256,
        "u1_03_failure_acceptance_sha256": sha256_file(
            output / "acceptance/h3-n2-stage2d9r-private-content-u1-03-failure-l1-v1.json"
        ),
        "u1_03_authorization_record_sha256": "38edfa6ba1d42aea5d0d6d57f0a3157209be3afc6873f957d92d0156fceae0a2",
        "u1_03_failure_code": "BROKER_CERTIFICATE_DIGEST_MISMATCH",
        "u1_03_status": "CONSUMED_FAILED",
        "python_executable_sha256_required": "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a",
        "python_version_required": "3.11.9",
        "openssl_executable_sha256_required": "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973",
        "openssl_version_required": "OpenSSL 3.5.0 8 Apr 2025",
        "command_custody": {
            "root_digest_sha256": "ef5f79be168fff686cabcc91fdc4109918d75d3311da1209dd8d0e381804006e",
            "private_descriptor_sha256": "cda5b1604200045fec0db45e46f9c441e1bde10f2e5a57f8c98ee2d14b5f9a75",
            "public_descriptor_sha256": "91c10168174438fc30b3dce087a6b75e24375b87b4262bafddb5b2822ee16d23",
            "package_sha256": "cc9086c20781007655c498b78ff1ce7af3316db0c02edbae2440d177d7fdfbb5",
            "unlock_digest_sha256": "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3",
            "u1_01_marker_sha256": "7461c0396a7be9fc99d1e880fdfc386054f003b4a64f9e758e6b826f93769314",
            "u1_02_marker_sha256": "1fc51b7338adc56b00b38795173b805b7408e7aafa4e0315e7553dc5898779a9",
        },
        "pki_custody": {
            "root_digest_sha256": "4cd43ee4b2df177bd99c32d3904dbe1e1df890aa14c6b6714a6b4f7ae4024868",
            "private_descriptor_sha256": "59814b825cd2df4ac7f0e3eb137798af4efdbbed4da9d627fe8ad98144be8687",
            "public_descriptor_sha256": "93bb071a5bf6f58472ac9e3891c2330dd9de6f05410824ad2fb51829267b4540",
            "package_sha256": "0632b37a70aa2eae416c48ffa9420a8f1e13788c22a7d12e211f77cf6e78a267",
            "ca_pem_sha256": "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963",
            "broker_certificate_sha256": "988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7",
            "broker_spki_sha256": "f034dc2a036f709287f0558773418ee1799e75bee50dcf55e09143a3a9052a03",
            "candidate_digest_sha256": "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5",
            "marker_sha256": "fbe03088de17b8db4d8b048e1985d571ca9f54d3add9b9fc3fce1735c9bec261",
        },
        "immutable_artifact": {
            "artifact_id": 8585140964,
            "run_id": 30062650179,
            "github_digest_sha256": "ecc28451499e0d2d934c7e298037ed5ee156c887bf72a9b258101c4aef7e2808",
            "payload_sha256": "5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3",
            "application_sha256": "7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630",
            "merged_sha256": "ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f",
            "source_sha": "c9e8447c24b0f09f3eac3f56791f2346e8aa5d61",
            "expired": False,
        },
        "recovery_artifact": {
            "artifact_id": 8589561310,
            "run_id": 30075191850,
            "github_digest_sha256": "f1654002f894ec136f4b52248a6b0e26ed9dedc7460e8205ec9f852b161d4a6a",
            "payload_sha256": "c1ed8e5f00b17cbe5bab30aec75d2e8637986b9c19b2389b761bebf3fc0b8d8b",
            "manifest_sha256": "fe82c458533953df4c86966d047d1f66b59da15e5299b3953135702236d68690",
            "erased_sha256": "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063",
            "source_sha": "f312f8580d9f4312f4dd1429b2d7755e1c550636",
            "expired": False,
        },
        "authorization_record_included": False,
        "authorized_execution_launcher_included": False,
        "private_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "network_operation": False,
        "broker_started": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
    }
    binding["review_binding_sha256"] = canonical_json_sha256(binding)
    return binding


def assemble(repository: Path, output: Path, source_sha: str, main_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    require(HEX40.fullmatch(main_sha) is not None, "MAIN_SHA_INVALID")
    verify_public_inputs(repository)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, mode=0o700)
    for relative, destination in FILES.items():
        source = repository / relative
        require(source.is_file(), f"MISSING_SOURCE:{relative}")
        target_dir = output / destination
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = target_dir / source.name
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)

    (output / "COMMAND_GROUP_REVIEW_ONLY.txt").write_text(
        "One future exact U1 may authorize one offline, one-shot, read-only private-content binding verification using the corrected DER certificate digest contract. It may read existing private material only inside the reviewed verifier process and output only booleans and already-public SHA-256 bindings. No secret output, network, Broker, board, serial, Flash/NVS, PREPARE, VERIFY, ACTIVATE, CLEANUP, production, Ready, merge, release, tag or deployment action is permitted.\n"
    )
    (output / "STOP_CONDITIONS.md").write_text(
        "# Fail-closed stop conditions\n\nStop before claim if any PR, main, HEAD, CI, package, toolchain, custody, descriptor, historical marker, candidate, immutable Artifact or recovery Artifact binding differs. U1-03 is permanently CONSUMED_FAILED and cannot be replayed. U1-04 must be one-shot, no longer than two hours, non-replayable and non-retryable; success and failure both permanently consume it.\n"
    )
    (output / "README.md").write_text(
        "# Stage 2D-9R private-content binding preauthorization review V5\n\nReview-only package for request U1-04. It uses the corrected DER certificate digest verifier and binds the retired U1-03 CONSUMED_FAILED marker. It contains no authorization record and no authorized execution launcher.\n"
    )
    for name in ("COMMAND_GROUP_REVIEW_ONLY.txt", "STOP_CONDITIONS.md", "README.md"):
        os.chmod(output / name, 0o600)

    binding = build_binding(output, source_sha, main_sha)
    binding_path = output / "PROBE_PACKAGE_BINDING.json"
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    os.chmod(binding_path, 0o600)

    launcher_name = "run_stage2d9r_private_content_binding_toolchain_probe_20260724_v5_7d31c4a8.sh"
    launcher = output / launcher_name
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "umask 077\n"
        "ROOT=\"$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd -P)\"\n"
        "cd \"$ROOT\"\n"
        "shasum -a 256 -c SHA256SUMS\n"
        "echo PRIVATE_CONTENT_BINDING_TOOLCHAIN_PROBE_V5_BEGIN\n"
        "set +e\n"
        "\"$(command -v python3)\" \"$ROOT/tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v3.py\" --package-root \"$ROOT\" --probe-toolchain\n"
        "rc=$?\n"
        "set -e\n"
        "echo PRIVATE_CONTENT_BINDING_TOOLCHAIN_PROBE_V5_END\n"
        "exit \"$rc\"\n"
    )
    os.chmod(launcher, 0o700)

    sums = output / "SHA256SUMS"
    lines = []
    for path in sorted(item for item in output.rglob("*") if item.is_file() and item != sums):
        lines.append(f"{sha256_file(path)}  {path.relative_to(output).as_posix()}")
    sums.write_text("\n".join(lines) + "\n")
    os.chmod(sums, 0o600)

    payload = b"\n".join(path.read_bytes() for path in output.rglob("*") if path.is_file())
    for forbidden in (b"BEGIN PRIVATE KEY", b"BEGIN RSA PRIVATE KEY", b"BEGIN EC PRIVATE KEY", b"/Users/", b"/private/tmp/"):
        require(forbidden not in payload, "PROHIBITED_PRIVATE_CONTENT")
    require(not (output / "authorization").exists(), "AUTHORIZATION_DIRECTORY_PRESENT")

    return {
        "authorization_request_id": REQUEST_ID,
        "source_sha": source_sha,
        "main_sha": main_sha,
        "probe_sha256": binding["probe_sha256"],
        "review_binding_sha256": binding["review_binding_sha256"],
        "command_group_sha256": binding["command_group_sha256"],
        "stop_conditions_sha256": binding["stop_conditions_sha256"],
        "u1_03_failed_marker_sha256": U1_03_MARKER_SHA256,
        "launcher": launcher_name,
        "authorization_record_included": False,
        "authorized_execution_launcher_included": False,
        "private_content_read": False,
        "network_operation": False,
        "board_operation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    args = parser.parse_args()
    result = assemble(
        args.repository_root.resolve(strict=True),
        args.output.resolve(strict=False),
        args.source_sha,
        args.main_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
