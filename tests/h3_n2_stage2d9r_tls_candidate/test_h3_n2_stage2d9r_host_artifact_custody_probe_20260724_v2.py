#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"tools/h3_n2_stage2d9r_host_artifact_custody_probe_20260724_v2.py"
spec=importlib.util.spec_from_file_location("host_probe_v2",SCRIPT)
assert spec and spec.loader
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class HostProbeV2ContractTest(unittest.TestCase):
    def test_secret_metadata_does_not_read_content(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"secret";f.write_bytes(b"secret");os.chmod(f,0o600)
            original=Path.read_bytes
            def blocked(self):
                if self==f:raise AssertionError("secret read")
                return original(self)
            Path.read_bytes=blocked
            try:p.secret_meta(f,6)
            finally:Path.read_bytes=original

    def test_secret_metadata_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);f=r/"f";f.write_bytes(b"x");os.chmod(f,0o600);l=r/"l";l.symlink_to(f)
            with self.assertRaisesRegex(p.E,"private file invalid"):p.secret_meta(l)

    def test_sums_reject_duplicate(self):
        d="a"*64
        with self.assertRaisesRegex(p.E,"SHA256SUMS invalid"):p.sums(f"{d}  a\n{d}  a\n".encode())

    def test_root_digest_and_mode(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td)/"r";r.mkdir();os.chmod(r,0o700);p.root_meta(r,p.hb(str(r).encode()))

    def test_root_rejects_wrong_mode(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td)/"r";r.mkdir();os.chmod(r,0o755)
            with self.assertRaisesRegex(p.E,"mode"):p.root_meta(r,p.hb(str(r).encode()))

    def _marker(self, root:Path, **changes:object)->tuple[Path,str]:
        data={
            "schema":"gh.test/1",
            "authorization_id":"U1-TEST-01",
            "status":"CONSUMED",
            "record_sha256":"b"*64,
            "one_shot":True,
            "replay_permitted":False,
            "secret_values_included":False,
        }
        data.update(changes)
        path=root/"marker.json"
        raw=(json.dumps(data,indent=2,sort_keys=True)+"\n").encode()
        path.write_bytes(raw);os.chmod(path,0o600)
        return path,hashlib.sha256(raw).hexdigest()

    def test_marker_exact_file_digest_accepts_any_valid_record_digest(self):
        with tempfile.TemporaryDirectory() as td:
            path,digest=self._marker(Path(td),record_sha256="c"*64)
            result=p.marker(path,digest,"U1-TEST-01","CONSUMED")
            self.assertTrue(result["record_sha256_shape_valid"])
            self.assertEqual(result["record_cross_binding"],"DEFERRED_REQUIRES_SEPARATE_EXACT_AUTHORIZATION")
            self.assertNotIn("record_sha256",result)

    def test_marker_rejects_wrong_full_file_digest(self):
        with tempfile.TemporaryDirectory() as td:
            path,_=self._marker(Path(td))
            with self.assertRaisesRegex(p.E,"descriptor digest mismatch"):
                p.marker(path,"0"*64,"U1-TEST-01","CONSUMED")

    def test_marker_rejects_replay_or_invalid_record_shape(self):
        with tempfile.TemporaryDirectory() as td:
            path,digest=self._marker(Path(td),replay_permitted=True)
            with self.assertRaisesRegex(p.E,"marker binding mismatch"):
                p.marker(path,digest,"U1-TEST-01","CONSUMED")
        with tempfile.TemporaryDirectory() as td:
            path,digest=self._marker(Path(td),record_sha256="invalid")
            with self.assertRaisesRegex(p.E,"marker record shape mismatch"):
                p.marker(path,digest,"U1-TEST-01","CONSUMED")

if __name__=="__main__":unittest.main()
