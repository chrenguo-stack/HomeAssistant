from __future__ import annotations
import argparse,ast,hashlib,io,json,os,subprocess,sys,tarfile,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[2]; T=R/"tools"; sys.path.insert(0,str(T))
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_packager_20260728_v1 as p
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as w

class Tests(unittest.TestCase):
 def root(self,r,n):
  x=r/n;x.mkdir(mode=0o700);os.chmod(x,0o700);return x
 def tar(self,path,files,sums=None,special=()):
  m=dict(files); sums=sums if sums is not None else [f"{hashlib.sha256(v).hexdigest()}  {k}" for k,v in sorted(files.items())]
  m["SHA256SUMS"]=("\n".join(sums)+"\n").encode()
  with tarfile.open(path,"w",format=tarfile.USTAR_FORMAT) as a:
   for n,d in sorted(m.items()):
    i=tarfile.TarInfo(n);i.size=len(d);i.mode=0o600;a.addfile(i,io.BytesIO(d))
   for i in special:a.addfile(i)
  os.chmod(path,0o600);return hashlib.sha256(path.read_bytes()).hexdigest()
 def reject(self,files,expected,sums=None,special=()):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);t=r/"p.tar";h=self.tar(t,files,sums,special)
   with self.assertRaises(w.core.ExecutionError):w.safe_extract_payload(t,self.root(r,"o"),expected_tar_sha256=h,expected_members=expected,code="BAD")
 def artifact(self):
  x=os.environ.get("STAGE2D9R_REPAIRED_IMMUTABLE_ZIP")
  if not x:self.skipTest("canonical Artifact not supplied")
  return Path(x).resolve(strict=True)
 def test_boundary(self):
  self.assertEqual((p.BASE_PR,p.BASE_HEAD_SHA),(189,"45c80baf43ccc3f917ae5964ee92a202a74cc2ba"));self.assertIn("SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION",(T/p.WRAPPER_NAME).read_text())
 def test_paths_and_roles(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);real=r/"private/var";real.mkdir(parents=True);alias=r/"var";alias.symlink_to(real,target_is_directory=True);t=real/"p.tar";h=self.tar(t,{"a":b"x"});o=self.root(r,"o")
   self.assertEqual(w.normalized_path(alias/"p.tar",strict=True),t.resolve());w.safe_extract_payload(t,o,expected_tar_sha256=h,expected_members={"SHA256SUMS","a"},code="BAD");self.assertTrue(t.is_file());self.assertFalse((o/t.name).exists())
 def test_archive_fail_closed_matrix(self):
  link=tarfile.TarInfo("link");link.type=tarfile.SYMTYPE;link.linkname="x";line=f"{hashlib.sha256(b'a').hexdigest()}  a"
  cases=[({},{"SHA256SUMS","link"},None,[link]),({"a":b"a"},{"SHA256SUMS","a"},[],()),({"a":b"a"},{"SHA256SUMS","a"},[line,line],()),({"a":b"a","x":b"x"},{"SHA256SUMS","a"},None,()),({"a":b"a"},{"SHA256SUMS","a"},[f"{'0'*64}  a"],())]
  for c in cases:
   with self.subTest(c=c[1:3]):self.reject(*c)
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);t=r/"p.tar"
   with tarfile.open(t,"w") as a:i=tarfile.TarInfo("../x");i.size=1;a.addfile(i,io.BytesIO(b"x"))
   os.chmod(t,0o600)
   with self.assertRaises(w.core.ExecutionError):w.safe_extract_payload(t,self.root(r,"o"),expected_tar_sha256=hashlib.sha256(t.read_bytes()).hexdigest(),expected_members={"../x"},code="BAD")
 def test_preclaim_consumed_no_replay(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);a=r/"a.json";a.write_text("{}\n");os.chmod(a,0o600);n=argparse.Namespace(authorization_record=a,state_root=r/"s",result_output=r/"r1")
   v=w.write_preclaim_evidence(n,"IMMUTABLE_PAYLOAD_INVALID");self.assertEqual(v["terminal_state"],"CONSUMED_FAILED_PRECLAIM");self.assertTrue(v["authorization_consumed"]);self.assertFalse(v["authorization_claimed"] or v["replay_permitted"])
   n.result_output=r/"r2";v=w.write_preclaim_evidence(n,"AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED",replay_attempted=True);self.assertTrue(v["replay_attempted"]);self.assertFalse(v["authorization_claimed"] or v["replay_permitted"])
 def test_locked_recovery_boundary(self):
  q=ast.parse((T/p.FROZEN_WRAPPER_NAME).read_text());f=next(x for x in q.body if isinstance(x,ast.FunctionDef) and x.name=="locked_recovery");s=[x.value for x in ast.walk(f) if isinstance(x,ast.Constant) and isinstance(x.value,str)];self.assertEqual((s.count("read_flash"),s.count("erase_region")),(2,1));self.assertNotIn("write_flash",s);self.assertNotIn("erase_flash",s)
 def test_real_shell_integration_and_replay(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);review=r/"review";p.build(R,self.artifact(),review,"1"*40);launch=review/p.EXECUTION_DIR/p.LAUNCHER_NAME;private=r/"private/var";private.mkdir(parents=True);alias=r/"var";alias.symlink_to(private,target_is_directory=True);a=private/"a.json";a.write_text("{}\n");os.chmod(a,0o600);c=private/"home"/w.frozen.CUSTODY_RELATIVE;c.mkdir(parents=True,mode=0o755);os.chmod(c,0o755);b=r/"bin";b.mkdir()
   for n in("openssl","esptool","mosquitto"):x=b/n;x.write_text("#!/bin/sh\nexit 0\n");os.chmod(x,0o700)
   st=r/"st";st.mkdir();(st/"serial.py").write_text("class Serial:\n pass\n");e={**os.environ,"HOME":str(alias/"home"),"TMPDIR":str(alias),"PATH":f"{b}{os.pathsep}{os.environ.get('PATH','')}","PYTHONPATH":str(st)}
   for i,code in((1,"PRIVATE_CUSTODY_ROOT_INVALID"),(2,"AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")):
    z=alias/f"r{i}.json";run=subprocess.run(["sh",str(launch),str(alias/"a.json"),str(z)],capture_output=True,text=True,env=e,timeout=30);self.assertEqual(run.returncode,2,run.stdout+run.stderr);v=json.loads((private/f"r{i}.json").read_text());self.assertEqual(v["failure_code"],code);self.assertFalse(v["authorization_claimed"] or v["board_operation"] or v["replay_permitted"])
 def test_deterministic_all_authorities_false(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=Path(d)/"a",Path(d)/"b";x=self.artifact();self.assertEqual(p.build(R,x,a,"1"*40),p.build(R,x,b,"1"*40));self.assertEqual((a/p.REVIEW_ARCHIVE_NAME).read_bytes(),(b/p.REVIEW_ARCHIVE_NAME).read_bytes());v=json.loads((a/p.BINDING_FILE).read_text());self.assertEqual(v["payload_handoff_contract"],"ORIGINAL_TAR_AND_EMPTY_EXTRACTION_ROOTS_SEPARATE");self.assertFalse(v["immutable_payload_content_changed"] or v["recovery_payload_content_changed"])
   for k in "authorized authorization_created authorization_claimed authorization_consumed board_operation usb_enumeration serial_operation esptool_operation flash_operation physical_nvs_operation network_operation broker_started prepare_executed verify_executed activate_executed cleanup_executed production_operation ready merge release tag deployment".split():self.assertFalse(v[k],k)
if __name__=="__main__":unittest.main()
