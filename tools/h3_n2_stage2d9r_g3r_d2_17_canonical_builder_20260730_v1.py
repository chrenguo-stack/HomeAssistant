"""Single canonical builder for D2-17 public CI, private delivery, and target-Mac models."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import zipfile
import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
EXECUTION_DIR = 'd2-17-execution-identity-frozen-physical-d2-execution-package'
UPSTREAM_EXECUTION_DIR = 'd2-16-full-inherited-authorization-preflight-repaired-physical-d2-execution-package'
REQUEST_FILE = 'PHYSICAL_D2_REQUEST_17.json'
FAILURE_FILE = 'D2_16_STATIC_CHECK_FAILURE_DISPOSITION.json'
REVIEW_FILE = 'D2_17_EXECUTION_IDENTITY_FREEZE_REVIEW.json'
REVIEW_TAR = 'stage2d9r-g3r-d2-17-execution-identity-freeze-review-v1.tar'
SOURCE_FILES = ('.github/workflows/h3-n2-stage2d9r-g3r-d2-17-execution-identity-freeze-ci-v1.yml', 'docs/decisions/h3-n2-stage2d9r-g3r-d2-17-execution-identity-freeze-20260730-v1.json', 'docs/acceptance/h3-n2-stage2d9r-g3r-d2-16-static-check-failure-disposition-20260730-v1.json', 'docs/development/h3-n2-stage2d9r-g3r-d2-17-execution-chain-stabilization-contract-20260730-v1.md', 'tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_20260730_v1.py', 'tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_shell_20260730_v1.sh', 'tools/h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_base_20260730_v1.py', 'tools/h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1.py', 'tools/h3_n2_stage2d9r_g3r_d2_17_canonical_builder_20260730_v1.py', 'tools/h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1.py', 'tools/run_d2_17_canonical_delivery_outer_20260730_v1.sh', 'tools/run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh')
EXECUTION_SOURCE_NAMES = (contract.SUPPORT_FILE, contract.CONTRACT_FILE, contract.BUILDER_FILE, contract.WRAPPER_FILE, contract.OUTER_FILE, contract.LAUNCHER_FILE)

def write_json(path: Path, value: object, mode: int=384) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=448)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    path.chmod(mode)

def copy_file(source: Path, target: Path, mode: int=384) -> None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=448)
    shutil.copyfile(source, target)
    target.chmod(mode)

def safe_extract_zip(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True, mode=448)
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            name = Path(info.filename)
            if name.is_absolute() or '..' in name.parts or stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError('ARTIFACT_MEMBER_UNSAFE')
        archive.extractall(target)
    for path in target.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('ARTIFACT_SYMLINK_FORBIDDEN')

def verify_recursive_sums(root: Path) -> None:
    sums = root / 'SHA256SUMS'
    if not sums.is_file() or sums.is_symlink():
        raise RuntimeError('ARTIFACT_SUMS_MISSING')
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if name in expected or Path(name).is_absolute() or '..' in Path(name).parts:
            raise RuntimeError('ARTIFACT_SUMS_INVALID')
        expected[name] = digest
    observed = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file() and (not path.is_symlink()) and (path != sums)}
    if set(expected) != observed:
        raise RuntimeError('ARTIFACT_SUMS_COVERAGE_MISMATCH')
    for name, digest in expected.items():
        if contract.sha256_file(root / name) != digest:
            raise RuntimeError('ARTIFACT_MEMBER_DIGEST_MISMATCH')

def extract_upstream(archive: Path, temporary: Path) -> Path:
    if contract.sha256_file(archive) != contract.PR215_ARTIFACT_SHA256:
        raise RuntimeError('PR215_ARTIFACT_DIGEST_MISMATCH')
    outer = temporary / 'pr215'
    safe_extract_zip(archive, outer)
    verify_recursive_sums(outer)
    review_path = outer / 'D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_REPAIR_EXECUTION_BINDING_REVIEW.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    supplied = review.pop('review_binding_sha256', None)
    if supplied != contract.PR215_REVIEW_BINDING_SHA256 or contract.canonical_sha256(review) != supplied:
        raise RuntimeError('PR215_REVIEW_BINDING_MISMATCH')
    if review.get('source_sha') != contract.BASE_HEAD_SHA or review.get('execution_package_sha256') != contract.PR215_EXECUTION_PACKAGE_SHA256:
        raise RuntimeError('PR215_REVIEW_ID_MISMATCH')
    execution = outer / UPSTREAM_EXECUTION_DIR
    if not execution.is_dir() or execution.is_symlink():
        raise RuntimeError('PR215_EXECUTION_PACKAGE_MISSING')
    return execution

def write_recursive_sums(root: Path) -> None:
    sums = root / 'SHA256SUMS'
    lines = [f'{contract.sha256_file(path)}  {path.relative_to(root).as_posix()}' for path in sorted(root.rglob('*'), key=lambda item: item.as_posix()) if path.is_file() and (not path.is_symlink()) and (path != sums)]
    sums.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    sums.chmod(384)

def deterministic_tar(root: Path, target: Path) -> None:
    members = [path for path in sorted(root.rglob('*'), key=lambda item: item.as_posix()) if path.is_file() and (not path.is_symlink()) and (path not in {target, root / 'SHA256SUMS'})]
    with tarfile.open(target, 'w', format=tarfile.PAX_FORMAT) as archive:
        for path in members:
            info = archive.gettarinfo(str(path), arcname=path.relative_to(root).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            info.mode = 448 if path.name.endswith('.sh') else 384
            with path.open('rb') as handle:
                archive.addfile(info, handle)
    target.chmod(384)

def build(args: argparse.Namespace) -> None:
    source = args.source_root.expanduser().resolve(strict=True)
    artifact = args.pr215_artifact.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve(strict=False)
    if output.exists() and (not output.is_dir() or output.is_symlink() or any(output.iterdir())):
        raise RuntimeError('OUTPUT_NOT_EMPTY')
    output.mkdir(parents=True, exist_ok=True, mode=448)
    output.chmod(448)
    contract.validate_decision(source / 'docs/decisions' / contract.DECISION_FILE)
    disposition = contract.validate_failure_disposition(source / 'docs/acceptance' / contract.FAILURE_DISPOSITION_FILE)
    with tempfile.TemporaryDirectory(prefix='d2-17-canonical-builder-') as temporary_name:
        upstream = extract_upstream(artifact, Path(temporary_name))
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=448)
        excluded = {contract.CLOSURE_FILE, contract.PACKAGE_BINDING_FILE, contract.DELIVERY_MANIFEST_FILE, contract.SUMS_FILE}
        for path in sorted(upstream.iterdir(), key=lambda item: item.name):
            if path.is_file() and (not path.is_symlink()) and (path.name not in excluded) and (not path.name.startswith('run_')):
                copy_file(path, execution / path.name)
        copy_file(upstream / contract.SUMS_FILE, execution / 'UPSTREAM_D2_16_EXECUTION_SHA256SUMS')
        for name in EXECUTION_SOURCE_NAMES:
            copy_file(source / 'tools' / name, execution / name, 448 if name.endswith('.sh') else 384)
        source_binding = {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-freeze-source-binding/1', 'decision_id': contract.DECISION_ID, 'd2_request_id': contract.D2_REQUEST_ID, 'source_sha': args.source_sha, 'base_pr': contract.BASE_PR, 'base_head_sha': contract.BASE_HEAD_SHA, 'pr215_artifact_id': contract.PR215_ARTIFACT_ID, 'pr215_artifact_sha256': contract.PR215_ARTIFACT_SHA256, 'pr215_review_binding_sha256': contract.PR215_REVIEW_BINDING_SHA256, 'd2_16_terminal_state': contract.D2_16_TERMINAL_STATE, 'd2_16_outer_failure_code': contract.D2_16_OUTER_FAILURE_CODE, 'd2_16_leaf_failure_code': contract.D2_16_LEAF_FAILURE_CODE, 'complete_chain_bind_before_authorization_required': True, 'execution_identity_freeze_required': True, 'single_canonical_builder_required': True, 'real_shell_full_chain_host_only_required': True, 'physical_request_authorized': False, 'physical_authorization_created': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'flash_operation': False, 'network_operation': False}
        write_json(execution / contract.SOURCE_BINDING_FILE, source_binding)
        delivery = contract.build_delivery_manifest(execution)
        write_json(execution / contract.DELIVERY_MANIFEST_FILE, delivery)
        closure = contract.build_execution_closure_manifest(execution)
        write_json(execution / contract.CLOSURE_FILE, closure)
        binding = {'schema': contract.PACKAGE_BINDING_SCHEMA, 'state': 'FROZEN_UNAUTHORIZED_D2_17_EXECUTION_IDENTITY_STABILIZED_PACKAGE', 'decision_id': contract.DECISION_ID, 'd2_request_id': contract.D2_REQUEST_ID, 'source_sha': args.source_sha, 'base_pr': contract.BASE_PR, 'base_head_sha': contract.BASE_HEAD_SHA, 'pr215_artifact_id': contract.PR215_ARTIFACT_ID, 'pr215_artifact_sha256': contract.PR215_ARTIFACT_SHA256, 'pr215_review_binding_sha256': contract.PR215_REVIEW_BINDING_SHA256, 'execution_closure_sha256': closure['execution_closure_sha256'], 'delivery_equivalence_sha256': delivery['delivery_equivalence_sha256'], 'execution_package_sha256': contract.package_set_digest(execution), 'execution_outer_sha256': contract.sha256_file(execution / contract.OUTER_FILE), 'execution_launcher_sha256': contract.sha256_file(execution / contract.LAUNCHER_FILE), 'execution_wrapper_sha256': contract.sha256_file(execution / contract.WRAPPER_FILE), 'execution_contract_sha256': contract.sha256_file(execution / contract.CONTRACT_FILE), 'execution_support_sha256': contract.sha256_file(execution / contract.SUPPORT_FILE), 'canonical_builder_sha256': contract.sha256_file(execution / contract.BUILDER_FILE), 'immutable_payload_tar_sha256': contract.sha256_file(execution / contract.IMMUTABLE_PAYLOAD_FILE), 'recovery_payload_tar_sha256': contract.sha256_file(execution / contract.RECOVERY_PAYLOAD_FILE), 'complete_chain_bind_before_authorization_required': True, 'execution_identity_freeze_required': True, 'single_canonical_builder_required': True, 'physical_request_authorized': False, 'physical_authorization_created': False}
        write_json(execution / contract.PACKAGE_BINDING_FILE, binding)
        contract.write_flat_sums(execution)
        package = contract.validate_execution_package(execution)
        request = contract.request_template(execution, source_sha=args.source_sha)
        write_json(output / REQUEST_FILE, request)
        write_json(output / FAILURE_FILE, disposition)
        source_root = output / 'source'
        for name in SOURCE_FILES:
            copy_file(source / name, source_root / name, 448 if name.endswith('.sh') else 384)
        review = {'schema': 'gh.h3.n2.stage2d9r-g3r-d2-17-execution-identity-freeze-review/1', 'state': 'FROZEN_UNAUTHORIZED_D2_17_EXECUTION_IDENTITY_STABILIZATION', 'decision_id': contract.DECISION_ID, 'd2_request_id': contract.D2_REQUEST_ID, 'source_sha': args.source_sha, 'base_pr': contract.BASE_PR, 'base_head_sha': contract.BASE_HEAD_SHA, 'pr215_artifact_id': contract.PR215_ARTIFACT_ID, 'pr215_artifact_sha256': contract.PR215_ARTIFACT_SHA256, 'pr215_review_binding_sha256': contract.PR215_REVIEW_BINDING_SHA256, 'd2_16_terminal_state': contract.D2_16_TERMINAL_STATE, 'd2_16_outer_failure_code': contract.D2_16_OUTER_FAILURE_CODE, 'd2_16_leaf_failure_code': contract.D2_16_LEAF_FAILURE_CODE, 'execution_closure_sha256': package['closure']['execution_closure_sha256'], 'delivery_equivalence_sha256': package['delivery']['delivery_equivalence_sha256'], 'delivery_equivalence_fingerprint': contract.delivery_equivalence_fingerprint(execution), 'execution_package_sha256': package['package_sha256'], 'request_binding_sha256': request['request_binding_sha256'], 'immutable_payload_tar_sha256': contract.IMMUTABLE_PAYLOAD_TAR_SHA256, 'recovery_payload_tar_sha256': contract.RECOVERY_PAYLOAD_TAR_SHA256, 'source_files': list(SOURCE_FILES), 'canonical_builder': contract.BUILDER_FILE, 'physical_request_created': True, 'physical_request_authorized': False, 'physical_authorization_created': False, 'authorization_claimed': False, 'authorization_consumed': False, 'board_operation': False, 'usb_enumeration': False, 'serial_operation': False, 'esptool_operation': False, 'flash_operation': False, 'network_operation': False, 'replay_permitted': False, 'automatic_retry_permitted': False}
        review['review_binding_sha256'] = contract.canonical_sha256(review)
        write_json(output / REVIEW_FILE, review)
        deterministic_tar(output, output / REVIEW_TAR)
        write_recursive_sums(output)
        verify_recursive_sums(output)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--pr215-artifact', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if contract.HEX40.fullmatch(args.source_sha) is None:
        raise RuntimeError('SOURCE_SHA_INVALID')
    build(args)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
