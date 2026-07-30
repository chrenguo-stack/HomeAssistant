"""Shared D2-17 package, delivery, request, and execution-identity contract."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable
import h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_contract_20260730_v1 as upstream
DECISION_ID = 'D1-H3N2-STAGE2D9R-G3R-D2-17-EXECUTION-IDENTITY-FREEZE-STABILIZATION-20260730-01'
STAGE = 'H3/N2 Stage 2D-9R G3R D2-17 execution-identity-frozen successor'
D2_REQUEST_ID = 'D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17'
REQUEST_SCHEMA = 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-frozen-physical-request/1'
AUTH_SCHEMA = 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-frozen-physical-authorization/1'
RESULT_SCHEMA = AUTH_SCHEMA.replace('authorization', 'result')
MARKER_SCHEMA = AUTH_SCHEMA.replace('authorization', 'marker')
PRE_RESULT_SCHEMA = AUTH_SCHEMA.replace('authorization', 'preclaim-result')
PRE_MARKER_SCHEMA = AUTH_SCHEMA.replace('authorization', 'preclaim-marker')
IDENTITY_SCHEMA = 'gh.h3.n2.stage2d9r-g3r-d2-17-frozen-execution-identity/1'
PACKAGE_BINDING_SCHEMA = 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-frozen-execution-package/1'
CLOSURE_SCHEMA = 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-frozen-execution-closure-manifest/1'
DELIVERY_SCHEMA = 'gh.h3.n2.stage2d9r-g3r-d2-17-delivery-equivalence-manifest/1'
BASE_PR = 215
BASE_HEAD_SHA = 'bea9a5c2af242f0830163ebdfd49c5023a6e437f'
BASE_BRANCH = 'fix/h3-n2-stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-20260730-v1'
MAIN_SHA_AT_BINDING = '64c6b093c3ba6a8476c9392c8d106394b2542fb5'
PR215_ARTIFACT_ID = 8749684942
PR215_ARTIFACT_SHA256 = '26e0e7ffe9a04f49c402cb06ba171bdab9305a63798342b88d7f94db1e30355b'
PR215_REVIEW_BINDING_SHA256 = 'edba31b546b777903848c01dafad591af2b2b8a13f0de9b8560a800957cb531a'
PR215_EXECUTION_PACKAGE_SHA256 = '8adac28c25a4d3d0e784bf684cca3287dc13e1956e2dffa8ab758666d7871c78'
D2_16_ID = upstream.D2_REQUEST_ID
D2_16_TERMINAL_STATE = 'STATIC_CHECK_FAILED_RETIRED'
D2_16_OUTER_FAILURE_CODE = 'D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_CHECK_FAILED'
D2_16_LEAF_FAILURE_CODE = 'AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH'
D2_16_FAILURE_STAGE = 'FULL_INHERITED_AUTHORIZATION_PREFLIGHT'
D2_16_AUTHORIZATION_CLAIMED = False
D2_16_AUTHORIZATION_CONSUMED = False
D2_16_AUTH_IMMUTABLE_PAYLOAD_TAR_SHA256 = 'e1d10f3fa17c4f543de0e85c7629e761ce82c91fb5deca3348c7188268a67707'
D2_16_ACTUAL_IMMUTABLE_PAYLOAD_TAR_SHA256 = 'ed8e4c673e89107750743702c7e4f4cb9bfada9c53519edcc4ee31719045b2de'
D2_16_AUTH_RECOVERY_PAYLOAD_TAR_SHA256 = '13e59372ed55511c9581b776903a007c8bfa92216b92cc5475b3f1459dcc260f'
D2_16_ACTUAL_RECOVERY_PAYLOAD_TAR_SHA256 = '9a1b75a39edc4b47d7e54417bdb1e6a07671f37a9100e7f4364e63383e11eeb2'
D2_16_PRIVATE_TAR_SHA256 = '96ad639cca21a65f670de5c4ab218a82dce519cf61e885f8dcaf6cfd553ef976'
D2_16_PRIVATE_ZIP_SHA256 = '96b2547816cd40f77d6c9e9713c479683f2c78d46f1deacf0cc05f1f4a63a23a'
D2_16_AUTHORIZATION_RECORD_SHA256 = 'af05d65fe0ca3772ece9533096515e69bf63951a84146b4031b986bb4ac239c6'
CLOSURE_FILE = 'EXECUTION_CLOSURE_MANIFEST.json'
PACKAGE_BINDING_FILE = 'EXECUTION_PACKAGE_BINDING.json'
DELIVERY_MANIFEST_FILE = 'DELIVERY_EQUIVALENCE_MANIFEST.json'
SOURCE_BINDING_FILE = 'D2_17_EXECUTION_IDENTITY_FREEZE_SOURCE_BINDING.json'
SUMS_FILE = 'SHA256SUMS'
CONTROL_FILES = {CLOSURE_FILE, PACKAGE_BINDING_FILE, DELIVERY_MANIFEST_FILE, SUMS_FILE}
OUTER_FILE = 'run_d2_17_canonical_delivery_outer_20260730_v1.sh'
LAUNCHER_FILE = 'run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh'
WRAPPER_FILE = 'h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1.py'
CONTRACT_FILE = 'h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1.py'
SUPPORT_FILE = Path(__file__).name
BUILDER_FILE = 'h3_n2_stage2d9r_g3r_d2_17_canonical_builder_20260730_v1.py'
DECISION_FILE = 'h3-n2-stage2d9r-g3r-d2-17-execution-identity-freeze-20260730-v1.json'
FAILURE_DISPOSITION_FILE = 'h3-n2-stage2d9r-g3r-d2-16-static-check-failure-disposition-20260730-v1.json'
IMMUTABLE_PAYLOAD_FILE = upstream.IMMUTABLE_PAYLOAD_FILE
RECOVERY_PAYLOAD_FILE = upstream.RECOVERY_PAYLOAD_FILE
IMMUTABLE_PAYLOAD_TAR_SHA256 = D2_16_ACTUAL_IMMUTABLE_PAYLOAD_TAR_SHA256
RECOVERY_PAYLOAD_TAR_SHA256 = D2_16_ACTUAL_RECOVERY_PAYLOAD_TAR_SHA256
HEX40 = re.compile('^[0-9a-f]{40}$')
HEX64 = re.compile('^[0-9a-f]{64}$')
DELIVERY_ARGUMENT_ORDER = ('command', '--package-root', '--physical-request', '--authorization-record', '--execution-identity', '--python-executable', '--openssl-executable', '--esptool-executable', '--mosquitto-executable', '--result-output', '--now')
DELIVERY_ENVIRONMENT = ('PYTHONDONTWRITEBYTECODE', 'GH_D2_17_OUTER_PACKAGE_ROOT', 'GH_D2_17_LAUNCHER_PACKAGE_ROOT', 'GH_D2_17_DELIVERY_PROFILE')

class ContractError(RuntimeError):
    """Fail-closed public contract error with a stable leaf code."""

def require(ok: bool, code: str) -> None:
    if not ok:
        raise ContractError(code)

def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def file_mode(path: Path) -> str:
    return f'{stat.S_IMODE(path.stat().st_mode):04o}'

def load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and (not path.is_symlink()), code)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value

def validate_bound_json(path: Path, *, binding_field: str, code: str) -> dict[str, Any]:
    value = load_json(path, code)
    supplied = value.pop(binding_field, None)
    require(isinstance(supplied, str) and HEX64.fullmatch(supplied) is not None, code)
    require(canonical_sha256(value) == supplied, code)
    value[binding_field] = supplied
    return value

def validate_decision(path: Path) -> dict[str, Any]:
    value = validate_bound_json(path, binding_field='decision_binding_sha256', code='DECISION_BINDING_MISMATCH')
    exact = {'decision_id': DECISION_ID, 'base_pr': BASE_PR, 'base_head_sha': BASE_HEAD_SHA, 'd2_request_id': D2_REQUEST_ID, 'state': 'FROZEN_UNAUTHORIZED_D2_17_EXECUTION_IDENTITY_STABILIZATION', 'predecessor_request_id': D2_16_ID, 'predecessor_terminal_state': D2_16_TERMINAL_STATE, 'predecessor_outer_failure_code': D2_16_OUTER_FAILURE_CODE, 'predecessor_leaf_failure_code': D2_16_LEAF_FAILURE_CODE, 'predecessor_authorization_claimed': False, 'predecessor_authorization_consumed': False, 'complete_chain_bind_before_authorization_required': True, 'execution_identity_freeze_required': True, 'single_canonical_builder_required': True, 'real_shell_full_chain_host_only_required': True, 'bind_install_idempotency_required': True, 'hardware_call_sentinels_required': True, 'leaf_error_preservation_required': True, 'delivery_equivalence_required': True, 'target_mac_static_check_required_before_physical_decision': True, 'physical_request_created': True, 'physical_request_authorized': False, 'physical_authorization_created': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'esptool_operation': False, 'flash_operation': False, 'network_operation': False, 'replay_permitted': False, 'automatic_retry_permitted': False}
    for key, expected in exact.items():
        require(value.get(key) == expected, 'DECISION_' + key.upper() + '_MISMATCH')
    return value

def validate_failure_disposition(path: Path) -> dict[str, Any]:
    value = validate_bound_json(path, binding_field='disposition_binding_sha256', code='D2_16_DISPOSITION_BINDING_MISMATCH')
    exact = {'d2_request_id': D2_16_ID, 'terminal_state': D2_16_TERMINAL_STATE, 'outer_failure_code': D2_16_OUTER_FAILURE_CODE, 'leaf_failure_code': D2_16_LEAF_FAILURE_CODE, 'failure_stage': D2_16_FAILURE_STAGE, 'authorization_claimed': False, 'authorization_consumed': False, 'immutable_payload_authorization_sha256': D2_16_AUTH_IMMUTABLE_PAYLOAD_TAR_SHA256, 'immutable_payload_actual_sha256': D2_16_ACTUAL_IMMUTABLE_PAYLOAD_TAR_SHA256, 'recovery_payload_authorization_sha256': D2_16_AUTH_RECOVERY_PAYLOAD_TAR_SHA256, 'recovery_payload_actual_sha256': D2_16_ACTUAL_RECOVERY_PAYLOAD_TAR_SHA256, 'execute_permitted': False, 'static_check_rerun_permitted': False, 'authorization_modification_permitted': False, 'reuse_permitted': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'esptool_operation': False, 'flash_operation': False, 'network_operation': False, 'prepare_executed': False, 'verify_executed': False, 'recovery_executed': False}
    for key, expected in exact.items():
        require(value.get(key) == expected, 'D2_16_DISPOSITION_' + key.upper() + '_MISMATCH')
    return value

def _regular_files(root: Path) -> list[Path]:
    require(root.is_dir() and (not root.is_symlink()), 'PACKAGE_ROOT_INVALID')
    members = list(root.iterdir())
    require(all((path.is_file() and (not path.is_symlink()) for path in members)), 'PACKAGE_MEMBER_INVALID')
    return sorted(members, key=lambda path: path.name)

def write_flat_sums(root: Path) -> None:
    lines = [f'{sha256_file(path)}  {path.name}' for path in _regular_files(root) if path.name != SUMS_FILE]
    target = root / SUMS_FILE
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    target.chmod(384)

def verify_flat_sums(root: Path) -> None:
    sums = root / SUMS_FILE
    require(sums.is_file() and (not sums.is_symlink()), 'PACKAGE_SUMS_INVALID')
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding='utf-8').splitlines():
        parts = line.split('  ', 1)
        require(len(parts) == 2, 'PACKAGE_SUMS_INVALID')
        digest, name = parts
        require(HEX64.fullmatch(digest) is not None and name not in expected and ('/' not in name), 'PACKAGE_SUMS_INVALID')
        expected[name] = digest
    observed = {path.name for path in _regular_files(root) if path.name != SUMS_FILE}
    require(set(expected) == observed, 'PACKAGE_SUMS_COVERAGE_MISMATCH')
    for name, digest in expected.items():
        require(sha256_file(root / name) == digest, 'PACKAGE_DIGEST_MISMATCH')

def package_set_digest(root: Path) -> str:
    files = [{'name': path.name, 'sha256': sha256_file(path)} for path in _regular_files(root) if path.name not in {SUMS_FILE, PACKAGE_BINDING_FILE}]
    require(bool(files), 'PACKAGE_EMPTY')
    return canonical_sha256({'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-package-set/1', 'files': files})

def build_delivery_manifest(root: Path) -> dict[str, Any]:
    files = [{'name': path.name, 'sha256': sha256_file(path), 'mode': file_mode(path)} for path in _regular_files(root) if path.name not in CONTROL_FILES]
    value: dict[str, Any] = {'schema': DELIVERY_SCHEMA, 'decision_id': DECISION_ID, 'd2_request_id': D2_REQUEST_ID, 'canonical_outer': OUTER_FILE, 'launcher': LAUNCHER_FILE, 'wrapper': WRAPPER_FILE, 'contract': CONTRACT_FILE, 'support': SUPPORT_FILE, 'canonical_builder': BUILDER_FILE, 'argument_order': list(DELIVERY_ARGUMENT_ORDER), 'environment_names': list(DELIVERY_ENVIRONMENT), 'path_normalization': 'resolve-strict-pwd-P-macos-private-tmp-compatible', 'files': files}
    value['delivery_equivalence_sha256'] = canonical_sha256(value)
    return value

def build_execution_closure_manifest(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = {'schema': CLOSURE_SCHEMA, 'decision_id': DECISION_ID, 'd2_request_id': D2_REQUEST_ID, 'base_pr': BASE_PR, 'base_head_sha': BASE_HEAD_SHA, 'files': [{'name': path.name, 'sha256': sha256_file(path)} for path in _regular_files(root) if path.name not in {CLOSURE_FILE, PACKAGE_BINDING_FILE, SUMS_FILE}]}
    value['execution_closure_sha256'] = canonical_sha256(value)
    return value

def validate_execution_package(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve(strict=True)
    verify_flat_sums(root)
    closure = validate_bound_json(root / CLOSURE_FILE, binding_field='execution_closure_sha256', code='EXECUTION_CLOSURE_BINDING_MISMATCH')
    delivery = validate_bound_json(root / DELIVERY_MANIFEST_FILE, binding_field='delivery_equivalence_sha256', code='DELIVERY_EQUIVALENCE_BINDING_MISMATCH')
    binding = load_json(root / PACKAGE_BINDING_FILE, 'EXECUTION_PACKAGE_BINDING_INVALID')
    require(binding.get('schema') == PACKAGE_BINDING_SCHEMA, 'EXECUTION_PACKAGE_SCHEMA_MISMATCH')
    require(binding.get('decision_id') == DECISION_ID and binding.get('d2_request_id') == D2_REQUEST_ID, 'EXECUTION_PACKAGE_ID_MISMATCH')
    require(binding.get('base_pr') == BASE_PR and binding.get('base_head_sha') == BASE_HEAD_SHA, 'EXECUTION_PACKAGE_BASE_MISMATCH')
    require(binding.get('pr215_artifact_id') == PR215_ARTIFACT_ID and binding.get('pr215_artifact_sha256') == PR215_ARTIFACT_SHA256, 'PR215_ARTIFACT_MISMATCH')
    require(binding.get('execution_closure_sha256') == closure['execution_closure_sha256'], 'EXECUTION_CLOSURE_DIGEST_MISMATCH')
    require(binding.get('delivery_equivalence_sha256') == delivery['delivery_equivalence_sha256'], 'DELIVERY_EQUIVALENCE_DIGEST_MISMATCH')
    require(binding.get('execution_package_sha256') == package_set_digest(root), 'EXECUTION_PACKAGE_DIGEST_MISMATCH')
    required_files = {'execution_outer_sha256': OUTER_FILE, 'execution_launcher_sha256': LAUNCHER_FILE, 'execution_wrapper_sha256': WRAPPER_FILE, 'execution_contract_sha256': CONTRACT_FILE, 'execution_support_sha256': SUPPORT_FILE, 'canonical_builder_sha256': BUILDER_FILE}
    for field, name in required_files.items():
        require(binding.get(field) == sha256_file(root / name), field.upper() + '_MISMATCH')
    immutable = root / IMMUTABLE_PAYLOAD_FILE
    recovery = root / RECOVERY_PAYLOAD_FILE
    require(immutable.is_file() and recovery.is_file(), 'PAYLOAD_TAR_MISSING')
    require(sha256_file(immutable) == IMMUTABLE_PAYLOAD_TAR_SHA256, 'IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH')
    require(sha256_file(recovery) == RECOVERY_PAYLOAD_TAR_SHA256, 'RECOVERY_PAYLOAD_TAR_SHA256_MISMATCH')
    return {'root': root, 'binding': binding, 'closure': closure, 'delivery': delivery, 'package_sha256': binding['execution_package_sha256']}

def canonical_package_digest(root: Path) -> str:
    return str(validate_execution_package(root)['package_sha256'])

def request_template(root: Path, *, source_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, 'SOURCE_SHA_INVALID')
    package = validate_execution_package(root)
    binding = package['binding']
    value: dict[str, Any] = {'schema': REQUEST_SCHEMA, 'state': 'FROZEN_UNAUTHORIZED_AWAITING_EXACT_D2_17_AUTHORIZATION', 'stage': STAGE, 'decision_id': DECISION_ID, 'd2_request_id': D2_REQUEST_ID, 'source_sha': source_sha, 'base_pr': BASE_PR, 'base_head_sha': BASE_HEAD_SHA, 'execution_closure_sha256': package['closure']['execution_closure_sha256'], 'delivery_equivalence_sha256': package['delivery']['delivery_equivalence_sha256'], 'execution_package_sha256': package['package_sha256'], 'execution_outer_sha256': binding['execution_outer_sha256'], 'execution_launcher_sha256': binding['execution_launcher_sha256'], 'execution_wrapper_sha256': binding['execution_wrapper_sha256'], 'execution_contract_sha256': binding['execution_contract_sha256'], 'canonical_builder_sha256': binding['canonical_builder_sha256'], 'immutable_payload_tar_sha256': IMMUTABLE_PAYLOAD_TAR_SHA256, 'recovery_payload_tar_sha256': RECOVERY_PAYLOAD_TAR_SHA256, 'predecessor_request_id': D2_16_ID, 'predecessor_terminal_state': D2_16_TERMINAL_STATE, 'predecessor_outer_failure_code': D2_16_OUTER_FAILURE_CODE, 'predecessor_leaf_failure_code': D2_16_LEAF_FAILURE_CODE, 'predecessor_authorization_claimed': False, 'predecessor_authorization_consumed': False, 'complete_chain_bind_before_authorization_required': True, 'execution_identity_freeze_required': True, 'single_canonical_builder_required': True, 'real_shell_full_chain_host_only_required': True, 'hardware_call_sentinels_required': True, 'delivery_equivalence_required': True, 'authorized': False, 'authorization_created': False, 'authorization_claimed': False, 'authorization_consumed': False, 'physical_request_authorized': False, 'one_shot': True, 'prepare_max_count': 1, 'verify_max_count': 1, 'locked_recovery_max_count': 1, 'locked_recovery_scope': 'TEST_PARTITION_ONLY', 'replay_permitted': False, 'automatic_retry_permitted': False, 'activate_authorized': False, 'cleanup_authorized': False, 'production_operation_authorized': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'esptool_operation': False, 'flash_operation': False, 'network_operation': False, 'broker_started': False, 'prepare_executed': False, 'verify_executed': False, 'physical_execution_started': False}
    value['request_binding_sha256'] = canonical_sha256(value)
    return value

def validate_physical_request(value: dict[str, Any], root: Path) -> dict[str, Any]:
    require(value == request_template(root, source_sha=str(value.get('source_sha'))), 'REQUEST_MISMATCH')
    return value

def executable_path(path: Path, code: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    require(resolved.is_file() and (not resolved.is_symlink()) and os.access(resolved, os.X_OK), code)
    return resolved

def normalized_delivery_path(path: Path) -> str:
    """Canonicalize symlinks, spaces, and macOS /private/tmp aliases without storing private paths."""
    return path.expanduser().resolve(strict=True).as_posix()

def authorization_field_inventory(extra_names: Iterable[str]=()) -> tuple[str, ...]:
    names = {'schema', 'stage', 'decision_id', 'd2_request_id', 'source_sha', 'request_binding_sha256', 'execution_closure_sha256', 'delivery_equivalence_sha256', 'execution_package_sha256', 'execution_outer_sha256', 'execution_launcher_sha256', 'execution_wrapper_sha256', 'execution_contract_sha256', 'canonical_builder_sha256', 'execution_controller_sha256', 'execution_script_sha256', 'immutable_artifact_id', 'immutable_artifact_archive_sha256', 'immutable_payload_tar_sha256', 'immutable_merged_image_sha256', 'recovery_artifact_id', 'recovery_artifact_archive_sha256', 'recovery_payload_tar_sha256', 'recovery_descriptor_sha256', 'private_package_sha256', 'prepare_command_sha256', 'verify_command_sha256', 'candidate_digest_sha256', 'ca_pem_sha256', 'build_binding', 'python_executable_sha256', 'openssl_executable_sha256', 'esptool_executable_sha256', 'mosquitto_executable_sha256', 'execution_marker_name_sha256', 'board_identity_sha256', 'serial_identity_sha256', 'baseline_state_sha256', 'execution_identity_sha256', 'authorization_field_set_sha256', 'issued_at', 'expires_at', 'authorized', 'authorization_created', 'authorization_claimed', 'authorization_consumed', 'one_shot', 'prepare_max_count', 'verify_max_count', 'locked_recovery_authorized', 'locked_recovery_max_count', 'locked_recovery_scope', 'replay_permitted', 'automatic_retry_permitted', 'activate_authorized', 'cleanup_authorized', 'production_operation_authorized', 'full_inherited_authorization_preflight_required', 'complete_chain_bind_before_authorization_required', 'execution_identity_freeze_required', 'hardware_call_sentinels_required', 'authorization_record_sha256'}
    names.update(extra_names)
    return tuple(sorted(names))

def execution_identity_template(root: Path, *, request: dict[str, Any], controller_path: Path, python_path: Path, openssl_path: Path, esptool_path: Path, mosquitto_path: Path, bind_call_count: int, install_call_count: int) -> dict[str, Any]:
    validate_physical_request(request, root)
    package = validate_execution_package(root)
    paths = [executable_path(python_path, 'PYTHON_EXECUTABLE_INVALID'), executable_path(openssl_path, 'OPENSSL_EXECUTABLE_INVALID'), executable_path(esptool_path, 'ESPTOOL_EXECUTABLE_INVALID'), executable_path(mosquitto_path, 'MOSQUITTO_EXECUTABLE_INVALID')]
    controller = controller_path.expanduser().resolve(strict=True)
    require(controller.is_file() and (not controller.is_symlink()), 'EXECUTION_CONTROLLER_INVALID')
    field_names = authorization_field_inventory()
    value: dict[str, Any] = {'schema': IDENTITY_SCHEMA, 'state': 'COMPLETE_CHAIN_BOUND_EXECUTION_IDENTITY_FROZEN', 'stage': STAGE, 'd2_request_id': D2_REQUEST_ID, 'auth_schema': AUTH_SCHEMA, 'result_schema': RESULT_SCHEMA, 'source_sha': request['source_sha'], 'request_binding_sha256': request['request_binding_sha256'], 'execution_closure_sha256': package['closure']['execution_closure_sha256'], 'delivery_equivalence_sha256': package['delivery']['delivery_equivalence_sha256'], 'execution_package_sha256': package['package_sha256'], 'execution_outer_sha256': package['binding']['execution_outer_sha256'], 'execution_launcher_sha256': package['binding']['execution_launcher_sha256'], 'execution_wrapper_sha256': package['binding']['execution_wrapper_sha256'], 'execution_contract_sha256': package['binding']['execution_contract_sha256'], 'canonical_builder_sha256': package['binding']['canonical_builder_sha256'], 'execution_controller_sha256': sha256_file(controller), 'execution_script_sha256': sha256_file(controller), 'immutable_payload_tar_sha256': sha256_file(package['root'] / IMMUTABLE_PAYLOAD_FILE), 'recovery_payload_tar_sha256': sha256_file(package['root'] / RECOVERY_PAYLOAD_FILE), 'python_executable_sha256': sha256_file(paths[0]), 'openssl_executable_sha256': sha256_file(paths[1]), 'esptool_executable_sha256': sha256_file(paths[2]), 'mosquitto_executable_sha256': sha256_file(paths[3]), 'authorization_field_names': list(field_names), 'authorization_field_set_sha256': hashlib.sha256('\n'.join(field_names).encode('utf-8')).hexdigest(), 'bind_call_count': bind_call_count, 'install_call_count': install_call_count, 'authorization_generated_after_freeze': False, 'authorization_claimed': False, 'authorization_consumed': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'esptool_operation': False, 'flash_operation': False, 'network_operation': False, 'broker_started': False, 'prepare_executed': False, 'verify_executed': False}
    value['execution_identity_sha256'] = canonical_sha256(value)
    return value

def validate_execution_identity(value: dict[str, Any], root: Path, *, request: dict[str, Any], controller_path: Path, python_path: Path, openssl_path: Path, esptool_path: Path, mosquitto_path: Path) -> dict[str, Any]:
    bind_count = int(value.get('bind_call_count', 0))
    install_count = int(value.get('install_call_count', 0))
    expected = execution_identity_template(root, request=request, controller_path=controller_path, python_path=python_path, openssl_path=openssl_path, esptool_path=esptool_path, mosquitto_path=mosquitto_path, bind_call_count=bind_count, install_call_count=install_count)
    require(value == expected, 'EXECUTION_IDENTITY_DRIFT')
    require(bind_count >= 1 and install_count == 1, 'BIND_INSTALL_COUNT_INVALID')
    return value

def leaf_failure_details(code: str, authorization: dict[str, Any] | None, identity: dict[str, Any] | None) -> dict[str, Any]:
    mapping = {'AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH': 'immutable_payload_tar_sha256', 'AUTHORIZATION_RECOVERY_PAYLOAD_TAR_SHA256_MISMATCH': 'recovery_payload_tar_sha256', 'AUTHORIZATION_EXECUTION_PACKAGE_MISMATCH': 'execution_package_sha256', 'AUTHORIZATION_EXECUTION_SCRIPT_SHA256_MISMATCH': 'execution_script_sha256', 'AUTHORIZATION_PYTHON_EXECUTABLE_SHA256_MISMATCH': 'python_executable_sha256', 'AUTHORIZATION_OPENSSL_EXECUTABLE_SHA256_MISMATCH': 'openssl_executable_sha256', 'AUTHORIZATION_ESPTOOL_EXECUTABLE_SHA256_MISMATCH': 'esptool_executable_sha256', 'AUTHORIZATION_MOSQUITTO_EXECUTABLE_SHA256_MISMATCH': 'mosquitto_executable_sha256'}
    field = mapping.get(code)
    if field is None:
        return {'digest_field': None, 'expected_digest': None, 'actual_digest': None}
    return {'digest_field': field, 'expected_digest': None if identity is None else identity.get(field), 'actual_digest': None if authorization is None else authorization.get(field)}

def delivery_equivalence_fingerprint(root: Path) -> str:
    package = validate_execution_package(root)
    return canonical_sha256({'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-delivery-equivalence-fingerprint/1', 'package': package['package_sha256'], 'closure': package['closure']['execution_closure_sha256'], 'delivery': package['delivery']['delivery_equivalence_sha256'], 'outer': package['binding']['execution_outer_sha256'], 'launcher': package['binding']['execution_launcher_sha256'], 'wrapper': package['binding']['execution_wrapper_sha256'], 'argument_order': package['delivery']['argument_order'], 'environment_names': package['delivery']['environment_names']})

def __getattr__(name: str) -> Any:
    return getattr(upstream, name)
