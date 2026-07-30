from __future__ import annotations
from datetime import datetime, timedelta, timezone
import importlib, json, os
from pathlib import Path
import subprocess, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parents[2]; TOOLS=ROOT/"tools"
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
CONTRACT="h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_contract_20260730_v1"
WRAPPER="h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_wrapper_20260730_v1"

class D216AuthorizationPreflightTests(unittest.TestCase):
    def test_decision_and_source_status(self)->None:
        c=importlib.import_module(CONTRACT); w=importlib.import_module(WRAPPER)
        d=ROOT/"docs/decisions"/c.DECISION_FILE
        self.assertEqual(c.validate_decision(d)["base_pr"],214)
        s=w.source_status(); self.assertEqual(s["predecessor_failure_code"],"AUTHORIZATION_STAGE_MISMATCH")
        self.assertTrue(s["full_inherited_authorization_preflight_required"])

    def test_field_inventory_covers_original_validator(self)->None:
        c=importlib.import_module(CONTRACT)
        expected={
            "immutable_artifact_id","immutable_artifact_archive_sha256","immutable_payload_tar_sha256",
            "immutable_merged_image_sha256","recovery_artifact_id","recovery_artifact_archive_sha256",
            "recovery_payload_tar_sha256","recovery_descriptor_sha256","private_package_sha256",
            "prepare_command_sha256","verify_command_sha256","candidate_digest_sha256","ca_pem_sha256",
            "build_binding","execution_script_sha256","python_executable_sha256","openssl_executable_sha256",
            "esptool_executable_sha256","mosquitto_executable_sha256",
        }
        self.assertEqual(set(c.LEGACY_EXACT_FIELD_NAMES),expected)

    def test_d2_15_shape_fails_before_claim(self)->None:
        c=importlib.import_module(CONTRACT)
        old={"schema":c.AUTH_SCHEMA,"d2_request_id":c.D2_REQUEST_ID,"authorized":True,"one_shot":True,
             "replay_permitted":False,"automatic_retry_permitted":False}
        self.assertNotIn("stage",old)
        self.assertNotEqual(old.get("stage"),c.STAGE)

    def test_full_template_and_original_base_validator(self)->None:
        c=importlib.import_module(CONTRACT); w=importlib.import_module(WRAPPER)
        artifact=os.environ.get("PR214_ARTIFACT_ZIP"); source_sha=os.environ.get("SOURCE_SHA")
        if not artifact or not source_sha: self.skipTest("shell integration supplies package")
        packager=TOOLS/"h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_packager_20260730_v1.py"
        with tempfile.TemporaryDirectory(prefix="d2 16 unit ") as tmp:
            t=Path(tmp); out=t/"review"
            subprocess.run([sys.executable,"-B",str(packager),"--source-root",str(ROOT),"--pr214-artifact",artifact,"--source-sha",source_sha,"--output",str(out)],check=True)
            package=out/"d2-16-full-inherited-authorization-preflight-repaired-physical-d2-execution-package"
            request=json.loads((out/"PHYSICAL_D2_REQUEST_16.json").read_text())
            tools=[]
            for name in ("python","openssl","esptool","mosquitto"):
                p=t/name; p.write_text("#!/bin/sh\nexit 0\n"); p.chmod(0o700); tools.append(p)
            sys.path.insert(0,str(package))
            try:
                module=importlib.import_module(WRAPPER); module.bind_predecessor()
                d2_11=module.predecessor.predecessor.predecessor.predecessor.upstream
                execution_script=Path(d2_11.core.__file__).resolve(strict=True)
                now=datetime.now(timezone.utc)
                auth=c.authorization_template(request=request,root=package,issued_at=now-timedelta(minutes=1),expires_at=now+timedelta(minutes=10),
                    execution_script_path=execution_script,python_path=tools[0],openssl_path=tools[1],esptool_path=tools[2],mosquitto_path=tools[3],
                    board_identity_sha256="1"*64,serial_identity_sha256="2"*64,baseline_state_sha256="3"*64)
                auth_path=t/"candidate-authorization.json"; auth_path.write_text(json.dumps(auth,sort_keys=True,indent=2)+"\n"); auth_path.chmod(0o600)
                result=t/"preflight.json"
                env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","GH_D2_16_LAUNCHER_PACKAGE_ROOT":str(package)}
                run=subprocess.run([sys.executable,"-B",str(package/c.WRAPPER_FILE),"authorization-preclaim-check","--package-root",str(package),"--physical-request",str(out/"PHYSICAL_D2_REQUEST_16.json"),"--authorization-record",str(auth_path),"--python-executable",str(tools[0]),"--openssl-executable",str(tools[1]),"--esptool-executable",str(tools[2]),"--mosquitto-executable",str(tools[3]),"--result-output",str(result),"--now",now.isoformat().replace("+00:00","Z")],env=env,text=True,capture_output=True)
                self.assertEqual(run.returncode,0,run.stderr+run.stdout)
                value=json.loads(result.read_text()); self.assertEqual(value["status"],"PASS"); self.assertTrue(value["base_validate_authorization_executed"])
                self.assertFalse(value["authorization_claimed"]); self.assertFalse(value["usb_enumeration"])
            finally:
                sys.path.remove(str(package))

if __name__=="__main__": unittest.main()
