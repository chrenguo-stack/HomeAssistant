"""D2-17 canonical outer target: bind, freeze, authorize, and static-check host-only."""
from __future__ import annotations
import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any, Iterator
from unittest import mock
import h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_wrapper_20260730_v1 as predecessor
import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
OUTER_ROOT_ENV = 'GH_D2_17_OUTER_PACKAGE_ROOT'
LAUNCHER_ROOT_ENV = 'GH_D2_17_LAUNCHER_PACKAGE_ROOT'
DELIVERY_PROFILE_ENV = 'GH_D2_17_DELIVERY_PROFILE'
_BOUND = False
_BIND_CALL_COUNT = 0
_INSTALL_CALL_COUNT = 0
_BIND_SIGNATURE: str | None = None
_BOUND_D2_11: Any | None = None

def _error_code(exc: BaseException) -> str:
    if exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return type(exc).__name__

def _atomic_json(path: Path, value: object) -> None:
    path = path.expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True, mode=448)
    os.chmod(path.parent, 448)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 384)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', closefd=False) as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)

def _utc(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception as exc:
        raise contract.ContractError('TIME_INVALID') from exc

def _package_from_environment(value: Path) -> Path:
    package = value.expanduser().resolve(strict=True)
    outer = os.environ.get(OUTER_ROOT_ENV)
    launcher = os.environ.get(LAUNCHER_ROOT_ENV)
    profile = os.environ.get(DELIVERY_PROFILE_ENV)
    contract.require(outer is not None and Path(outer).resolve(strict=True) == package, 'OUTER_PACKAGE_ROOT_MISMATCH')
    contract.require(launcher is not None and Path(launcher).resolve(strict=True) == package, 'LAUNCHER_PACKAGE_ROOT_MISMATCH')
    contract.require(profile in {'public-ci', 'private-package', 'target-mac-static-check'}, 'DELIVERY_PROFILE_INVALID')
    return package

def _binding_signature(d2_11: Any) -> str:
    core = d2_11.core
    value = {'contract_module': contract.__name__, 'stage': getattr(core, 'STAGE', None), 'd2_request_id': getattr(core, 'D2_REQUEST_ID', None), 'auth_schema': getattr(core, 'AUTH_SCHEMA', None), 'result_schema': getattr(core, 'RESULT_SCHEMA', None), 'core_file': Path(core.__file__).resolve(strict=True).name, 'validator_module': getattr(d2_11._BASE_VALIDATE_AUTHORIZATION, '__module__', None), 'validator_name': getattr(d2_11._BASE_VALIDATE_AUTHORIZATION, '__name__', None), 'immutable_payload_tar_sha256': contract.IMMUTABLE_PAYLOAD_TAR_SHA256, 'recovery_payload_tar_sha256': contract.RECOVERY_PAYLOAD_TAR_SHA256}
    return contract.canonical_sha256(value)

def bind_complete_chain() -> dict[str, Any]:
    """Bind the full successor chain exactly once; repeat calls only verify the frozen binding."""
    global _BOUND, _BIND_CALL_COUNT, _INSTALL_CALL_COUNT, _BIND_SIGNATURE, _BOUND_D2_11
    contract.require(sys.dont_write_bytecode, 'PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START')
    _BIND_CALL_COUNT += 1
    if not _BOUND:
        predecessor.contract = contract
        d2_11 = predecessor.bind_predecessor()
        _INSTALL_CALL_COUNT += 1
        _BOUND_D2_11 = d2_11
        _BIND_SIGNATURE = _binding_signature(d2_11)
        _BOUND = True
    else:
        contract.require(_BOUND_D2_11 is not None and _BIND_SIGNATURE is not None, 'BIND_STATE_INVALID')
        contract.require(_binding_signature(_BOUND_D2_11) == _BIND_SIGNATURE, 'COMPLETE_CHAIN_BINDING_DRIFT')
    return {'complete_chain_bound': True, 'bind_call_count': _BIND_CALL_COUNT, 'install_call_count': _INSTALL_CALL_COUNT, 'bind_signature_sha256': _BIND_SIGNATURE}

def _bound_d2_11() -> Any:
    contract.require(_BOUND_D2_11 is not None, 'COMPLETE_CHAIN_NOT_BOUND')
    return _BOUND_D2_11

class HardwareBoundaryReached(RuntimeError):
    pass

@contextmanager
def hardware_sentinels() -> Iterator[dict[str, int]]:
    """Replace concrete inherited physical boundaries and generic external calls with fail-closed sentinels."""
    counts = {'board_operation': 0, 'usb_enumeration': 0, 'serial_operation': 0, 'esptool_operation': 0, 'flash_operation': 0, 'physical_nvs_operation': 0, 'network_operation': 0, 'broker_started': 0, 'prepare_executed': 0, 'verify_executed': 0, 'recovery_executed': 0, 'external_process_operation': 0}
    def blocker(field: str):
        def blocked(*_args: Any, **_kwargs: Any) -> Any:
            counts[field] += 1
            raise HardwareBoundaryReached('UNEXPECTED_PHYSICAL_BOUNDARY_REACHED')
        return blocked
    with ExitStack() as stack:
        core = _bound_d2_11().core
        concrete = {'enumerate_serial': 'usb_enumeration', 'select_serial': 'serial_operation', 'run_process': 'esptool_operation', 'baseline': 'physical_nvs_operation', 'flash_firmware': 'flash_operation', 'wait_serial_line': 'serial_operation', 'start_broker': 'broker_started', 'locked_recovery': 'recovery_executed'}
        for name, field in concrete.items():
            contract.require(hasattr(core, name), 'HARDWARE_SENTINEL_TARGET_MISSING_' + name.upper())
            stack.enter_context(mock.patch.object(core, name, blocker(field)))
        serial_module = getattr(_bound_d2_11(), 'serial', None)
        if serial_module is not None and hasattr(serial_module, 'Serial'):
            stack.enter_context(mock.patch.object(serial_module, 'Serial', blocker('serial_operation')))
        for target in ('subprocess.run', 'subprocess.Popen', 'subprocess.call', 'subprocess.check_call', 'subprocess.check_output', 'os.system'):
            stack.enter_context(mock.patch(target, blocker('external_process_operation')))
        stack.enter_context(mock.patch('socket.create_connection', blocker('network_operation')))
        stack.enter_context(mock.patch.object(socket.socket, 'connect', blocker('network_operation')))
        yield counts

def _common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--package-root', type=Path, required=True)
    parser.add_argument('--physical-request', type=Path, required=True)
    parser.add_argument('--python-executable', type=Path, required=True)
    parser.add_argument('--openssl-executable', type=Path, required=True)
    parser.add_argument('--esptool-executable', type=Path, required=True)
    parser.add_argument('--mosquitto-executable', type=Path, required=True)
    return parser

def _load_request(path: Path, package: Path) -> dict[str, Any]:
    value = contract.load_json(path.expanduser().resolve(strict=True), 'PHYSICAL_REQUEST_INVALID')
    return contract.validate_physical_request(value, package)

def freeze_execution_identity(argv: list[str]) -> int:
    parser = _common_parser('Freeze the complete D2-17 execution identity before authorization creation')
    parser.add_argument('--identity-output', type=Path, required=True)
    args = parser.parse_args(argv)
    package = _package_from_environment(args.package_root)
    request = _load_request(args.physical_request, package)
    first = bind_complete_chain()
    second = bind_complete_chain()
    contract.require(first['install_call_count'] == second['install_call_count'] == 1, 'INSTALL_NOT_IDEMPOTENT')
    contract.require(second['bind_call_count'] == 2, 'BIND_CALL_COUNT_UNEXPECTED')
    d2_11 = _bound_d2_11()
    identity = contract.execution_identity_template(package, request=request, controller_path=Path(d2_11.core.__file__), python_path=args.python_executable, openssl_path=args.openssl_executable, esptool_path=args.esptool_executable, mosquitto_path=args.mosquitto_executable, bind_call_count=second['bind_call_count'], install_call_count=second['install_call_count'])
    _atomic_json(args.identity_output, identity)
    print(json.dumps({'status': 'PASS', 'execution_identity_sha256': identity['execution_identity_sha256'], 'bind_call_count': identity['bind_call_count'], 'install_call_count': identity['install_call_count'], 'authorization_claimed': False, 'authorization_consumed': False, 'board_operation': False}, sort_keys=True))
    return 0

def create_authorization(argv: list[str]) -> int:
    parser = _common_parser('Create authorization only from an already frozen, reverified identity')
    parser.add_argument('--execution-identity', type=Path, required=True)
    parser.add_argument('--authorization-output', type=Path, required=True)
    parser.add_argument('--issued-at', required=True)
    parser.add_argument('--expires-at', required=True)
    parser.add_argument('--board-identity-sha256', required=True)
    parser.add_argument('--serial-identity-sha256', required=True)
    parser.add_argument('--baseline-state-sha256', required=True)
    args = parser.parse_args(argv)
    package = _package_from_environment(args.package_root)
    request = _load_request(args.physical_request, package)
    bind_complete_chain()
    report = bind_complete_chain()
    d2_11 = _bound_d2_11()
    identity = contract.load_json(args.execution_identity.resolve(strict=True), 'EXECUTION_IDENTITY_INVALID')
    contract.validate_execution_identity(identity, package, request=request, controller_path=Path(d2_11.core.__file__), python_path=args.python_executable, openssl_path=args.openssl_executable, esptool_path=args.esptool_executable, mosquitto_path=args.mosquitto_executable)
    contract.require(report['install_call_count'] == 1, 'INSTALL_NOT_IDEMPOTENT')
    authorization = contract.authorization_template(request=request, identity=identity, issued_at=_utc(args.issued_at), expires_at=_utc(args.expires_at), board_identity_sha256=args.board_identity_sha256, serial_identity_sha256=args.serial_identity_sha256, baseline_state_sha256=args.baseline_state_sha256)
    _atomic_json(args.authorization_output, authorization)
    print(json.dumps({'status': 'PASS', 'authorization_record_sha256': authorization['authorization_record_sha256'], 'execution_identity_sha256': identity['execution_identity_sha256'], 'authorization_claimed': False, 'authorization_consumed': False, 'board_operation': False}, sort_keys=True))
    return 0

def full_chain_host_only_check(argv: list[str]) -> int:
    parser = _common_parser('Run outer -> launcher -> wrapper -> original inherited validator and stop before claim')
    parser.add_argument('--authorization-record', type=Path, required=True)
    parser.add_argument('--execution-identity', type=Path, required=True)
    parser.add_argument('--result-output', type=Path, required=True)
    parser.add_argument('--now')
    args = parser.parse_args(argv)
    authorization: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    validator_executed = False
    identity_verified = False
    sentinels: dict[str, int] = {}
    try:
        package = _package_from_environment(args.package_root)
        request = _load_request(args.physical_request, package)
        first = bind_complete_chain()
        second = bind_complete_chain()
        contract.require(first['install_call_count'] == second['install_call_count'] == 1, 'INSTALL_NOT_IDEMPOTENT')
        contract.require(second['bind_call_count'] == 2, 'BIND_CALL_COUNT_UNEXPECTED')
        d2_11 = _bound_d2_11()
        identity = contract.load_json(args.execution_identity.resolve(strict=True), 'EXECUTION_IDENTITY_INVALID')
        authorization = contract.load_json(args.authorization_record.resolve(strict=True), 'AUTHORIZATION_RECORD_INVALID')
        now = _utc(args.now) if args.now else None
        with hardware_sentinels() as sentinels:
            contract.validate_execution_identity(identity, package, request=request, controller_path=Path(d2_11.core.__file__), python_path=args.python_executable, openssl_path=args.openssl_executable, esptool_path=args.esptool_executable, mosquitto_path=args.mosquitto_executable)
            identity_verified = True
            validator_executed = True
            d2_11._BASE_VALIDATE_AUTHORIZATION(args.authorization_record.resolve(strict=True), package_root=package, python_path=contract.executable_path(args.python_executable, 'PYTHON_EXECUTABLE_INVALID'), openssl_path=contract.executable_path(args.openssl_executable, 'OPENSSL_EXECUTABLE_INVALID'), esptool_path=contract.executable_path(args.esptool_executable, 'ESPTOOL_EXECUTABLE_INVALID'), mosquitto_path=contract.executable_path(args.mosquitto_executable, 'MOSQUITTO_EXECUTABLE_INVALID'), now=now)
            contract.validate_authorization_contract(authorization, request, identity, now=now)
        value: dict[str, Any] = {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-full-chain-host-only-static-check/1', 'status': 'PASS', 'failure_code': None, 'failure_stage': None, 'd2_request_id': contract.D2_REQUEST_ID, 'full_inherited_validator_executed': True, 'full_inherited_validator_status': 'PASS', 'complete_chain_bound': True, 'execution_identity_verified': True, 'payload_digests_verified': True, 'tool_executable_digests_verified': True, 'request_closure_package_binding_verified': True, 'delivery_equivalence_verified': True, 'bind_call_count': second['bind_call_count'], 'install_call_count': second['install_call_count'], 'hardware_sentinels_untouched': all((count == 0 for count in sentinels.values())), 'hardware_sentinel_counts': sentinels, 'authorization_claimed': False, 'authorization_consumed': False, 'one_shot': True, 'replay_permitted': False, 'automatic_retry_permitted': False, 'board_operation': bool(sentinels.get('board_operation', 0)), 'usb_enumeration': bool(sentinels.get('usb_enumeration', 0)), 'serial_operation': bool(sentinels.get('serial_operation', 0)), 'esptool_operation': bool(sentinels.get('esptool_operation', 0)), 'flash_operation': bool(sentinels.get('flash_operation', 0)), 'physical_nvs_operation': bool(sentinels.get('physical_nvs_operation', 0)), 'network_operation': bool(sentinels.get('network_operation', 0)), 'broker_started': bool(sentinels.get('broker_started', 0)), 'prepare_executed': bool(sentinels.get('prepare_executed', 0)), 'verify_executed': bool(sentinels.get('verify_executed', 0)), 'recovery_executed': bool(sentinels.get('recovery_executed', 0)), 'activate_executed': False, 'cleanup_executed': False, 'expected_digest': None, 'actual_digest': None, 'digest_field': None}
        return_code = 0
    except Exception as exc:
        code = _error_code(exc)
        detail = contract.leaf_failure_details(code, authorization, identity)
        value = {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-full-chain-host-only-static-check/1', 'status': 'FAIL', 'failure_code': code, 'failure_stage': 'FULL_INHERITED_AUTHORIZATION_PREFLIGHT', 'd2_request_id': contract.D2_REQUEST_ID, 'full_inherited_validator_executed': validator_executed, 'full_inherited_validator_status': 'FAIL' if validator_executed else 'NOT_REACHED', 'complete_chain_bound': _BOUND, 'execution_identity_verified': identity_verified, 'hardware_sentinels_untouched': code != 'UNEXPECTED_PHYSICAL_BOUNDARY_REACHED', 'hardware_sentinel_counts': sentinels, 'authorization_claimed': False, 'authorization_consumed': False, 'one_shot': True, 'replay_permitted': False, 'automatic_retry_permitted': False, 'board_operation': bool(sentinels.get('board_operation', 0)), 'usb_enumeration': bool(sentinels.get('usb_enumeration', 0)), 'serial_operation': bool(sentinels.get('serial_operation', 0)), 'esptool_operation': bool(sentinels.get('esptool_operation', 0)), 'flash_operation': bool(sentinels.get('flash_operation', 0)), 'physical_nvs_operation': bool(sentinels.get('physical_nvs_operation', 0)), 'network_operation': bool(sentinels.get('network_operation', 0)), 'broker_started': bool(sentinels.get('broker_started', 0)), 'prepare_executed': bool(sentinels.get('prepare_executed', 0)), 'verify_executed': bool(sentinels.get('verify_executed', 0)), 'recovery_executed': bool(sentinels.get('recovery_executed', 0)), 'activate_executed': False, 'cleanup_executed': False, **detail}
        return_code = 2
    value['static_check_result_sha256'] = contract.canonical_sha256(value)
    _atomic_json(args.result_output, value)
    print(json.dumps(value, sort_keys=True))
    return return_code

def idempotency_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--result-output', type=Path, required=True)
    args = parser.parse_args(argv)
    first = bind_complete_chain()
    second = bind_complete_chain()
    third = bind_complete_chain()
    contract.require(first['install_call_count'] == second['install_call_count'] == third['install_call_count'] == 1, 'INSTALL_NOT_IDEMPOTENT')
    contract.require(third['bind_call_count'] == 3, 'BIND_CALL_COUNT_UNEXPECTED')
    value = {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-bind-install-idempotency-check/1', 'status': 'PASS', 'bind_call_count': 3, 'install_call_count': 1, 'bind_signature_sha256': third['bind_signature_sha256'], 'board_operation': False, 'authorization_claimed': False, 'authorization_consumed': False}
    _atomic_json(args.result_output, value)
    print(json.dumps(value, sort_keys=True))
    return 0

def hardware_sentinel_self_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--result-output', type=Path, required=True)
    args = parser.parse_args(argv)
    bind_complete_chain()
    observed: list[str] = []
    with hardware_sentinels() as counts:
        probes = (('usb_enumeration', lambda: _bound_d2_11().core.enumerate_serial()), ('serial_operation', lambda: _bound_d2_11().core.wait_serial_line('/dev/null', b'x', 0.0, Path('/tmp/nope'))), ('esptool_operation', lambda: _bound_d2_11().core.run_process([])), ('flash_operation', lambda: _bound_d2_11().core.flash_firmware(None, Path('/tmp/nope'), Path('/tmp/nope'), Path('/tmp/nope'))), ('broker_started', lambda: _bound_d2_11().core.start_broker(Path('/tmp/nope'), Path('/tmp/nope'), Path('/tmp/nope'))), ('recovery_executed', lambda: _bound_d2_11().core.locked_recovery(None, Path('/tmp/nope'), Path('/tmp/nope'), Path('/tmp/nope'), {})), ('network_operation', lambda: socket.create_connection(('127.0.0.1', 1))), ('external_process_operation', lambda: subprocess.run(['false'])))
        for field, probe in probes:
            try:
                probe()
            except HardwareBoundaryReached as exc:
                contract.require(_error_code(exc) == 'UNEXPECTED_PHYSICAL_BOUNDARY_REACHED', 'HARDWARE_SENTINEL_CODE_MISMATCH')
                observed.append(field)
            else:
                raise contract.ContractError('HARDWARE_SENTINEL_NOT_TRIGGERED_' + field.upper())
        for field in observed:
            contract.require(counts[field] >= 1, 'HARDWARE_SENTINEL_COUNT_MISSING_' + field.upper())
    value = {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-hardware-sentinel-self-check/1', 'status': 'PASS', 'failure_code': None, 'observed_sentinels': observed, 'sentinel_counts': counts, 'authorization_claimed': False, 'authorization_consumed': False, 'physical_operation_completed': False}
    _atomic_json(args.result_output, value)
    print(json.dumps(value, sort_keys=True))
    return 0

def source_status() -> dict[str, Any]:
    return {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-freeze-source/1', 'status': 'SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_17_PRIVATE_PACKAGE_GATE', 'decision_id': contract.DECISION_ID, 'd2_request_id': contract.D2_REQUEST_ID, 'predecessor_request_id': contract.D2_16_ID, 'predecessor_terminal_state': contract.D2_16_TERMINAL_STATE, 'predecessor_outer_failure_code': contract.D2_16_OUTER_FAILURE_CODE, 'predecessor_leaf_failure_code': contract.D2_16_LEAF_FAILURE_CODE, 'complete_chain_bind_before_authorization_required': True, 'execution_identity_freeze_required': True, 'single_canonical_builder_required': True, 'full_chain_host_only_static_check_required': True, 'target_mac_static_check_required_before_physical_decision': True, 'physical_request_created': False, 'physical_authorization_created': False, 'authorization_claimed': False, 'authorization_consumed': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'esptool_operation': False, 'flash_operation': False, 'network_operation': False, 'replay_permitted': False, 'automatic_retry_permitted': False}

def main() -> int:
    if not sys.dont_write_bytecode:
        print(json.dumps({**source_status(), 'status': 'FAIL', 'failure_code': 'PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START'}, sort_keys=True))
        return 2
    if len(sys.argv) == 1:
        print(json.dumps(source_status(), sort_keys=True))
        return 0
    command = sys.argv[1]
    argv = sys.argv[2:]
    if command == 'freeze-execution-identity':
        return freeze_execution_identity(argv)
    if command == 'create-authorization-from-frozen-identity':
        return create_authorization(argv)
    if command in {'full-chain-host-only-check', 'static-check'}:
        return full_chain_host_only_check(argv)
    if command == 'bind-install-idempotency-check':
        return idempotency_check(argv)
    if command == 'hardware-sentinel-self-check':
        return hardware_sentinel_self_check(argv)
    if command == 'execute':
        predecessor.contract = contract
        bind_complete_chain()
        sys.argv = [sys.argv[0], 'execute', *argv]
        return predecessor.main()
    print('unsupported D2-17 command', file=sys.stderr)
    return 2
if __name__ == '__main__':
    raise SystemExit(main())
