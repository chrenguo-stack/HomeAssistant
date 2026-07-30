#!/usr/bin/env python3
"""Build deterministic public D2-16 unauthorized review package."""
from __future__ import annotations
import argparse, json, shutil, stat, tarfile, tempfile, zipfile
from pathlib import Path, PurePosixPath
import h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_contract_20260730_v1 as contract

EXECUTION_DIR = "d2-16-full-inherited-authorization-preflight-repaired-physical-d2-execution-package"
UPSTREAM_DIR = "d2-15-contract-compatibility-install-preflight-repaired-physical-d2-execution-package"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_16.json"
REVIEW_FILE = "D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_REPAIR_EXECUTION_BINDING_REVIEW.json"
FAILURE_FILE = "D2_15_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_FAILURE_DISPOSITION.json"
SOURCE_BINDING_FILE = "D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_REPAIR_EXECUTION_BINDING.json"
REVIEW_TAR = "stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-execution-binding-review-v1.tar"
SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-20260730-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-contract-20260730-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_20260730_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_shell_20260730_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_d2_16_contract_base_20260730_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_contract_20260730_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_packager_20260730_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_wrapper_20260730_v1.py",
    "tools/run_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_20260730_v1.sh",
)

def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, sort_keys=True, indent=2)+"\n", encoding="utf-8"); path.chmod(0o600)

def copy(source: Path, target: Path, mode: int=0o600) -> None:
    if not source.is_file() or source.is_symlink(): raise RuntimeError("SOURCE_FILE_INVALID")
    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes()); target.chmod(mode)

def safe_extract_zip(source: Path, target: Path) -> None:
    target.mkdir(mode=0o700)
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            pure=PurePosixPath(info.filename)
            if not info.filename or pure.is_absolute() or ".." in pure.parts or info.is_dir(): raise RuntimeError("ARTIFACT_MEMBER_INVALID")
            mode=(info.external_attr>>16)&0o170000
            if mode and mode != stat.S_IFREG: raise RuntimeError("ARTIFACT_MEMBER_INVALID")
            dest=target.joinpath(*pure.parts); dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700); dest.write_bytes(archive.read(info)); dest.chmod(0o600)

def verify_recursive_sums(root: Path) -> None:
    sums=root/"SHA256SUMS"; expected={}
    for line in sums.read_text(encoding="utf-8").splitlines(): digest,name=line.split("  ",1); expected[name]=digest
    observed={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.is_symlink() and p!=sums}
    if set(expected)!=observed: raise RuntimeError("ARTIFACT_SUMS_COVERAGE_MISMATCH")
    for name,digest in expected.items():
        if contract.sha256_file(root/name)!=digest: raise RuntimeError("ARTIFACT_MEMBER_DIGEST_MISMATCH")

def extract_upstream(archive: Path, temporary: Path) -> Path:
    if contract.sha256_file(archive)!=contract.PR214_ARTIFACT_SHA256: raise RuntimeError("PR214_ARTIFACT_DIGEST_MISMATCH")
    outer=temporary/"pr214"; safe_extract_zip(archive,outer); verify_recursive_sums(outer)
    review=json.loads((outer/"D2_15_CONTRACT_COMPATIBILITY_INSTALL_PREFLIGHT_REPAIR_EXECUTION_BINDING_REVIEW.json").read_text(encoding="utf-8"))
    supplied=review.pop("review_binding_sha256",None)
    if supplied!=contract.PR214_REVIEW_BINDING_SHA256 or contract.canonical_sha256(review)!=supplied: raise RuntimeError("PR214_REVIEW_BINDING_MISMATCH")
    if review.get("source_sha")!=contract.BASE_HEAD_SHA or review.get("d2_request_id")!=contract.D2_15_ID: raise RuntimeError("PR214_REVIEW_ID_MISMATCH")
    return outer/UPSTREAM_DIR

def write_flat_sums(root: Path) -> None:
    lines=[f"{contract.sha256_file(p)}  {p.name}" for p in sorted(root.iterdir(),key=lambda x:x.name) if p.is_file() and p.name!="SHA256SUMS"]
    (root/"SHA256SUMS").write_text("\n".join(lines)+"\n",encoding="utf-8"); (root/"SHA256SUMS").chmod(0o600)

def write_recursive_sums(root: Path) -> None:
    sums=root/"SHA256SUMS"; lines=[f"{contract.sha256_file(p)}  {p.relative_to(root).as_posix()}" for p in sorted(root.rglob("*"),key=lambda x:x.as_posix()) if p.is_file() and not p.is_symlink() and p!=sums]
    sums.write_text("\n".join(lines)+"\n",encoding="utf-8"); sums.chmod(0o600)

def deterministic_tar(root: Path, target: Path) -> None:
    members=[p for p in sorted(root.rglob("*"),key=lambda x:x.as_posix()) if p.is_file() and not p.is_symlink() and p!=target and p!=root/"SHA256SUMS"]
    with tarfile.open(target,"w",format=tarfile.PAX_FORMAT) as archive:
        for path in members:
            info=archive.gettarinfo(str(path),arcname=path.relative_to(root).as_posix()); info.uid=info.gid=0; info.uname=info.gname=""; info.mtime=0; info.mode=0o700 if path.name.endswith(".sh") else 0o600
            with path.open("rb") as handle: archive.addfile(info,handle)
    target.chmod(0o600)

def build(args: argparse.Namespace) -> None:
    source=args.source_root.resolve(strict=True); output=args.output.resolve(strict=False)
    if output.exists() and (not output.is_dir() or output.is_symlink() or any(output.iterdir())): raise RuntimeError("OUTPUT_NOT_EMPTY")
    output.mkdir(parents=True,exist_ok=True,mode=0o700); output.chmod(0o700)
    contract.validate_decision(source/"docs/decisions"/contract.DECISION_FILE)
    with tempfile.TemporaryDirectory(prefix="d2-16-auth-preflight-") as temp:
        upstream=extract_upstream(args.pr214_artifact.resolve(strict=True),Path(temp)); execution=output/EXECUTION_DIR; execution.mkdir(mode=0o700)
        excluded={"EXECUTION_CLOSURE_MANIFEST.json","EXECUTION_PACKAGE_BINDING.json","SHA256SUMS"}
        for path in sorted(upstream.iterdir(),key=lambda x:x.name):
            if path.is_file() and not path.is_symlink() and path.name not in excluded and not path.name.startswith("run_"): copy(path,execution/path.name)
        copy(upstream/"SHA256SUMS",execution/"UPSTREAM_D2_15_EXECUTION_SHA256SUMS")
        for name in (contract.SUPPORT_FILE,contract.CONTRACT_FILE,contract.WRAPPER_FILE,contract.LAUNCHER_FILE): copy(source/"tools"/name,execution/name)
        source_binding={
            "schema":"gh.h3.n2.stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-execution-binding/1",
            "decision_id":contract.DECISION_ID,"d2_request_id":contract.D2_REQUEST_ID,"source_sha":args.source_sha,
            "base_pr":contract.BASE_PR,"base_head_sha":contract.BASE_HEAD_SHA,"pr214_artifact_id":contract.PR214_ARTIFACT_ID,
            "pr214_artifact_sha256":contract.PR214_ARTIFACT_SHA256,"d2_15_terminal_state":contract.D2_15_TERMINAL_STATE,
            "d2_15_failure_code":contract.D2_15_FAILURE_CODE,"full_inherited_authorization_preflight_required":True,
            "legacy_authorization_field_set_sha256":contract.LEGACY_FIELD_SET_SHA256,"physical_request_authorized":False,
            "physical_authorization_created":False,"board_operation":False,"serial_operation":False,"flash_operation":False,"network_operation":False,
        }; write_json(execution/SOURCE_BINDING_FILE,source_binding)
        closure=contract.build_execution_closure_manifest(execution); write_json(execution/contract.CLOSURE_FILE,closure)
        binding={
            "schema":contract.PACKAGE_BINDING_SCHEMA,"state":"FROZEN_UNAUTHORIZED_D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_REPAIRED_PACKAGE",
            "decision_id":contract.DECISION_ID,"d2_request_id":contract.D2_REQUEST_ID,"source_sha":args.source_sha,
            "base_pr":contract.BASE_PR,"base_head_sha":contract.BASE_HEAD_SHA,"execution_closure_sha256":closure["execution_closure_sha256"],
            "execution_package_sha256":contract.package_set_digest(execution),"execution_wrapper_sha256":contract.sha256_file(execution/contract.WRAPPER_FILE),
            "execution_launcher_sha256":contract.sha256_file(execution/contract.LAUNCHER_FILE),"execution_contract_sha256":contract.sha256_file(execution/contract.CONTRACT_FILE),"execution_support_sha256":contract.sha256_file(execution/contract.SUPPORT_FILE),
            "pr214_artifact_id":contract.PR214_ARTIFACT_ID,"pr214_artifact_sha256":contract.PR214_ARTIFACT_SHA256,
            "pr214_review_binding_sha256":contract.PR214_REVIEW_BINDING_SHA256,"full_inherited_authorization_preflight_required":True,
            "legacy_authorization_field_set_sha256":contract.LEGACY_FIELD_SET_SHA256,"physical_request_authorized":False,"physical_authorization_created":False,
        }; write_json(execution/contract.PACKAGE_BINDING_FILE,binding); write_flat_sums(execution); contract.validate_execution_package(execution)
        request=contract.request_template(execution,source_sha=args.source_sha); write_json(output/REQUEST_FILE,request)
        failure={
            "schema":"gh.h3.n2.stage2d9r-g3r-d2-15-full-inherited-authorization-preflight-failure-disposition/1",
            "d2_request_id":contract.D2_15_ID,"terminal_state":contract.D2_15_TERMINAL_STATE,"failure_code":contract.D2_15_FAILURE_CODE,
            "failure_stage":contract.D2_15_FAILURE_STAGE,"returncode":contract.D2_15_RETURN_CODE,"terminal_result_sha256":contract.D2_15_TERMINAL_RESULT_SHA256,
            "stdout_sha256":contract.D2_15_STDOUT_SHA256,"stderr_sha256":contract.D2_15_STDERR_SHA256,
            "authorization_claimed":False,"authorization_consumed":True,"board_operation":False,"usb_enumeration":False,
            "serial_operation":False,"esptool_operation":False,"flash_operation":False,"network_operation":False,
            "replay_permitted":False,"automatic_retry_permitted":False,
        }; write_json(output/FAILURE_FILE,failure)
        source_root=output/"source"
        for name in SOURCE_FILES: copy(source/name,source_root/name,0o700 if name.endswith(".sh") else 0o600)
        review={
            "schema":"gh.h3.n2.stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-execution-binding-review/1",
            "state":"FROZEN_UNAUTHORIZED_D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_REPAIR",
            "decision_id":contract.DECISION_ID,"d2_request_id":contract.D2_REQUEST_ID,"source_sha":args.source_sha,
            "base_pr":contract.BASE_PR,"base_head_sha":contract.BASE_HEAD_SHA,"pr214_artifact_id":contract.PR214_ARTIFACT_ID,
            "pr214_artifact_sha256":contract.PR214_ARTIFACT_SHA256,"pr214_review_binding_sha256":contract.PR214_REVIEW_BINDING_SHA256,
            "d2_15_terminal_state":contract.D2_15_TERMINAL_STATE,"d2_15_failure_code":contract.D2_15_FAILURE_CODE,
            "d2_15_authorization_claimed":False,"d2_15_authorization_consumed":True,"d2_15_board_operation":False,
            "full_inherited_authorization_preflight_required":True,"legacy_authorization_field_set_sha256":contract.LEGACY_FIELD_SET_SHA256,
            "execution_closure_sha256":closure["execution_closure_sha256"],"execution_package_sha256":binding["execution_package_sha256"],
            "request_binding_sha256":request["request_binding_sha256"],"source_files":list(SOURCE_FILES),"physical_request_created":True,
            "physical_request_authorized":False,"physical_authorization_created":False,"authorization_claimed":False,"authorization_consumed":False,
            "board_operation":False,"usb_enumeration":False,"serial_operation":False,"esptool_operation":False,"flash_operation":False,"network_operation":False,
            "replay_permitted":False,"automatic_retry_permitted":False,
        }; review["review_binding_sha256"]=contract.canonical_sha256(review); write_json(output/REVIEW_FILE,review)
        deterministic_tar(output,output/REVIEW_TAR); write_recursive_sums(output); verify_recursive_sums(output)

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--source-root",type=Path,required=True); parser.add_argument("--pr214-artifact",type=Path,required=True); parser.add_argument("--source-sha",required=True); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args(); build(args); return 0
if __name__=="__main__": raise SystemExit(main())
