import hashlib
import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import host_readonly as h
import remote_projection as rp

ROOT=pathlib.Path(__file__).parent
BASE=frozenset(f'{i:064x}' for i in range(1,6))
GOOD={"schema":"n3w.p4.pending-identity-projection/1","hardware_sha256":"a"*64,"pairing_sha256":"b"*64,
      "expires_at":"2026-10-08T13:00:00+00:00","preboot_count":5,"preboot_hashes":sorted(BASE),"new_count":1,
      "read_at":"2026-10-08T12:00:00+00:00","container_continuity_pass":True,"manager_socket_pass":True,"tls_live_reprobe_pass":True}

class HostTests(unittest.TestCase):
    def script(self):
        with patch.object(h, 'private_preboot_baseline', return_value=BASE):
            return h.build_remote_program((ROOT/'bridge_handoff.py').read_text(),(ROOT/'remote_projection.py').read_text())

    def test_combined_script_syntax(self):
        import ast
        ast.parse(self.script())
        self.assertIn('BASELINE_HASHES',self.script())
        self.assertNotIn('GHN3W2:ghw-c6-',self.script())

    def test_wrong_baseline(self):
        with self.assertRaises(ValueError):
            h.private_preboot_baseline(ROOT / 'not-the-frozen-private-snapshot.json')

    def test_missing_readonly_functions_rejected(self):
        with patch.object(h, 'private_preboot_baseline', return_value=BASE):
            with self.assertRaisesRegex(ValueError, 'READONLY_CORE_MISSING'):
                h.build_remote_program('print(1)', (ROOT/'remote_projection.py').read_text())

    def test_remote_code_excludes_importer_even_if_bridge_contains_it(self):
        script=self.script()
        self.assertNotIn('OneShotImporter', script)
        self.assertNotIn('ssh_manager_stdin_transport', script)
        self.assertNotIn('import-payload', script)
        self.assertNotIn('capture_private_qr', script)
        self.assertNotIn('setup_secret', script)

    def test_mutating_sql_in_readonly_extract_stops(self):
        bridge=(ROOT/'bridge_handoff.py').read_text()
        mutated=bridge.replace('PRAGMA query_only=ON','DELETE FROM registrations')
        with patch.object(h,'private_preboot_baseline',return_value=BASE):
            with self.assertRaisesRegex(ValueError,'REMOTE_SQL_MUTATION'):
                h.build_remote_program(mutated,(ROOT/'remote_projection.py').read_text())

    def test_happy_remote_readonly_pipe_with_mock(self):
        args=[]
        def runner(cmd,**kw):
            args.append((cmd,kw))
            return SimpleNamespace(returncode=0,stdout=json.dumps(GOOD).encode())
        result=h.remote_snapshot_once('root@10.0.0.2',hashlib.sha256(b'root@10.0.0.2').hexdigest(),self.script(),runner=runner)
        self.assertEqual(result,GOOD)
        self.assertNotIn('GHN3W2:',str(args))
        self.assertIn('python3',args[0][0])
        self.assertEqual(args[0][1]['input'],self.script().encode())

    def test_target_mismatch_does_not_call_ssh(self):
        with patch.object(h.subprocess,'run') as runner:
            with self.assertRaises(ValueError):
                h.remote_snapshot_once('root@10.0.0.2','0'*64,self.script(),runner=runner)
            runner.assert_not_called()

    def test_tls_reprobe_missing_fails_closed(self):
        wrong=dict(GOOD,tls_live_reprobe_pass=False)
        r=lambda *_args,**_kw:SimpleNamespace(returncode=0,stdout=json.dumps(wrong).encode())
        with self.assertRaises(ValueError):
            h.remote_snapshot_once('root@10.0.0.2',hashlib.sha256(b'root@10.0.0.2').hexdigest(),self.script(),runner=r)

    def test_container_continuity_false_fails(self):
        wrong=dict(GOOD,container_continuity_pass=False)
        r=lambda *_args,**_kw:SimpleNamespace(returncode=0,stdout=json.dumps(wrong).encode())
        with self.assertRaises(ValueError):
            h.remote_snapshot_once('root@10.0.0.2',hashlib.sha256(b'root@10.0.0.2').hexdigest(),self.script(),runner=r)

    def test_t1_remote_entry_with_simulated_source(self):
        with patch.object(rp,'_assert_runtime') as attest, patch.object(rp,'project_readonly',create=True) as project:
            attest.return_value=(pathlib.Path('/synth/reg.db'),pathlib.Path('/synth/cred.db'))
            project.return_value=dict(GOOD)
            result=rp.main_remote(sorted(BASE))
            self.assertTrue(result['tls_live_reprobe_pass'])
            self.assertNotIn('setup_secret',result)

    def test_bad_preboot_blocked_before_probe(self):
        with patch.object(rp,'_assert_runtime') as attest:
            with self.assertRaises(Exception):rp.main_remote(['a'*64])
            attest.assert_not_called()

    def test_remote_stop_on_nonzero_exit(self):
        r=lambda *_a,**_kw:SimpleNamespace(returncode=2,stdout=b'{}')
        with self.assertRaises(ValueError):h.remote_snapshot_once('root@10.0.0.2',hashlib.sha256(b'root@10.0.0.2').hexdigest(),self.script(),runner=r)

    def test_runtime_contract_has_broker_ca_and_leaf(self):
        txt=(ROOT/'remote_projection.py').read_text()
        self.assertIn('EXPECTED_TLS_CA',txt)
        self.assertIn('EXPECTED_TLS_LEAF',txt)
        self.assertIn('ssl.create_default_context',txt)
        self.assertIn('tls.getpeercert',txt)
        self.assertNotIn('shell=True',txt)

if __name__=='__main__':unittest.main(verbosity=2)
