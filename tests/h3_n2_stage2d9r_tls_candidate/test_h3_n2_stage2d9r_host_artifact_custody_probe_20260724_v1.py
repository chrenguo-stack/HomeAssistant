#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, os
from pathlib import Path
import tempfile, unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"tools/h3_n2_stage2d9r_host_artifact_custody_probe_20260724_v1.py"
spec=importlib.util.spec_from_file_location("host_probe",SCRIPT)
assert spec and spec.loader
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class HostProbeContractTest(unittest.TestCase):
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
if __name__=="__main__":unittest.main()
