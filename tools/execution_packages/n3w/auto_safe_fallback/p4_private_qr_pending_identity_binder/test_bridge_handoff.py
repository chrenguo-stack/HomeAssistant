import base64
from contextlib import contextmanager
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import bridge_handoff as b

NOW=datetime(2026,10,8,11,0,tzinfo=UTC)
PRE=[f'ghw-c6-{i:012x}' for i in range(1,6)]
HARD='ghw-c6-123456789abc'
PAIR='12345678-1234-4234-8234-123456789abc'
SECRET=base64.urlsafe_b64encode(bytes(range(32))).rstrip(b'=').decode()
QR=f'GHN3W2:{HARD}:{PAIR}:{SECRET}'

@contextmanager
def write_db(path):
    c=sqlite3.connect(path)
    try:
        with c:
            yield c
    finally:
        c.close()

class BridgeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        self.reg=root/'registration.db';self.cred=root/'credential.db'
        self.baseline=frozenset(b.sha(x) for x in PRE)
        with write_db(self.reg) as d:
            d.executescript('''
            CREATE TABLE registrations (hardware_id TEXT,current_pairing_id TEXT,pairing_epoch INT,node_id TEXT,retired_at TEXT);
            CREATE TABLE pairing_sessions (hardware_id TEXT,pairing_id TEXT,pairing_epoch INT,state TEXT,expires_at TEXT);
            CREATE TABLE registration_events (hardware_id TEXT,pairing_id TEXT,node_id TEXT,event TEXT);
            CREATE TABLE registration_node_history (hardware_id TEXT,node_id TEXT);
            CREATE TABLE node_id_leases (hardware_id TEXT,node_id TEXT);
            CREATE TABLE retirement_outbox (hardware_id TEXT,node_id TEXT);
            ''')
            d.executemany('INSERT INTO registrations VALUES (?,\'legacy\',1,\'old-node\',NULL)',[(x,) for x in PRE])
            d.execute('INSERT INTO registrations VALUES (?,?,1,NULL,NULL)',(HARD,PAIR))
            d.execute('INSERT INTO pairing_sessions VALUES (?,?,1,\'pending\',?)',(HARD,PAIR,(NOW+timedelta(seconds=100)).isoformat()))
            d.execute('INSERT INTO registration_events VALUES (?,?,NULL,\'hello_created\')',(HARD,PAIR))
        with write_db(self.cred) as d:
            d.execute('CREATE TABLE credential_assignments (hardware_id TEXT,state TEXT)')

    def update(self, path, sql, args=()):
        with write_db(path) as d:d.execute(sql,args)

    def projection(self):
        return b.project_readonly(self.reg,self.cred,self.baseline)

    def stopped(self, code, fn):
        with self.assertRaises(b.GateStop) as e:fn()
        self.assertEqual(e.exception.code,code)
        self.assertNotIn(HARD,str(e.exception));self.assertNotIn(SECRET,str(e.exception))

    def test_valid_projection_sanitized_and_qr(self):
        projection=self.projection()
        self.assertNotIn(HARD,json.dumps(projection));self.assertNotIn(PAIR,json.dumps(projection));self.assertNotIn(SECRET,json.dumps(projection))
        bound=b.bind_qr(QR,projection,self.baseline,NOW)
        self.assertEqual(bound.pairing_sha256,b.sha(PAIR))

    def test_private_reader_injection(self):
        self.assertEqual(b.capture_private_qr(lambda:QR),QR)

    def test_no_new(self):
        self.update(self.reg,'DELETE FROM registration_events WHERE hardware_id=?',(HARD,))
        self.update(self.reg,'DELETE FROM pairing_sessions WHERE hardware_id=?',(HARD,))
        self.update(self.reg,'DELETE FROM registrations WHERE hardware_id=?',(HARD,))
        self.stopped('NEW_IDENTITY_NOT_UNIQUE',self.projection)

    def test_multiple_new(self):
        self.update(self.reg,"INSERT INTO registrations VALUES ('ghw-c6-444444444444','x',1,NULL,NULL)")
        self.stopped('NEW_IDENTITY_NOT_UNIQUE',self.projection)

    def test_old_missing(self):
        self.update(self.reg,'DELETE FROM registrations WHERE hardware_id=?',(PRE[0],))
        self.stopped('PREBOOT_IDENTITY_DRIFT',self.projection)

    def test_expired_pending(self):
        self.update(self.reg,"UPDATE pairing_sessions SET state='expired'")
        self.stopped('PENDING_BINDING_INVALID',self.projection)

    def test_old_session(self):
        self.update(self.reg,"INSERT INTO pairing_sessions VALUES (?,?,2,'rejected','2026-10-08T00:00:00Z')",(HARD,'prior'))
        self.stopped('PRIOR_IDENTITY_HISTORY',self.projection)

    def test_credential_history(self):
        self.update(self.cred,"INSERT INTO credential_assignments VALUES (?,'revoked')",(HARD,))
        self.stopped('PRIOR_IDENTITY_HISTORY',self.projection)

    def test_prior_node_history(self):
        self.update(self.reg,"INSERT INTO registration_node_history VALUES (?,'old')",(HARD,))
        self.stopped('PRIOR_IDENTITY_HISTORY',self.projection)

    def test_qr_mismatch(self):
        self.stopped('OPTICAL_MANAGER_MISMATCH',lambda:b.bind_qr(QR.replace(HARD,'ghw-c6-ffffffffffff'),self.projection(),self.baseline,NOW))

    def test_short_lifetime(self):
        self.stopped('PENDING_EXPIRED_OR_SHORT',lambda:b.bind_qr(QR,self.projection(),self.baseline,NOW,min_remaining=101))

    def test_invalid_qr(self):
        self.stopped('INVALID_QR',lambda:b.capture_private_qr(lambda:QR+'\n'))

    def test_one_shot_denied(self):
        bound=b.bind_qr(QR,self.projection(),self.baseline,NOW)
        importer=b.OneShotImporter()
        denied=b.ImportPermission(bound.hardware_sha256,bound.pairing_sha256,False,False)
        self.stopped('IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',lambda:importer.import_once(QR,bound,denied,lambda _:b'',NOW))
        self.stopped('IMPORT_ALREADY_CONSUMED',lambda:importer.import_once(QR,bound,denied,lambda _:b'',NOW))

    def live_binding(self):
        projection=self.projection()
        projection.update(container_continuity_pass=True,manager_socket_pass=True,tls_live_reprobe_pass=True,read_at=NOW.isoformat())
        return b.bind_qr(QR,projection,self.baseline,NOW)

    def test_synthetic_binding_cannot_import_even_with_permission(self):
        binding=b.bind_qr(QR,self.projection(),self.baseline,NOW)
        permission=b.ImportPermission(binding.hardware_sha256,binding.pairing_sha256,True,True)
        self.stopped('IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',lambda:b.OneShotImporter().import_once(QR,binding,permission,lambda _:b'',NOW))

    def test_stale_live_projection_rejected(self):
        projection=self.projection()
        projection.update(container_continuity_pass=True,manager_socket_pass=True,tls_live_reprobe_pass=True,read_at=(NOW-timedelta(seconds=15)).isoformat())
        self.stopped('LIVE_PROJECTION_STALE',lambda:b.bind_qr(QR,projection,self.baseline,NOW))

    def test_import_authorized_mock_only(self):
        bound=self.live_binding()
        perm=b.ImportPermission(bound.hardware_sha256,bound.pairing_sha256,True,True)
        consumed=[]
        def fake_pipe(data):
            consumed.append(data)
            return json.dumps({'schema':b.RESULT_SCHEMA,'accepted':True,'code':'accepted'}).encode()
        imp=b.OneShotImporter()
        self.stopped(
            'IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',
            lambda:imp.import_once(QR,bound,perm,fake_pipe,NOW),
        )
        self.assertEqual(consumed,[])
        self.stopped(
            'IMPORT_ALREADY_CONSUMED',
            lambda:imp.import_once(QR,bound,perm,fake_pipe,NOW),
        )

    def test_import_denied_mismatch(self):
        bound=self.live_binding()
        perm=b.ImportPermission('0'*64,bound.pairing_sha256,True,True)
        self.stopped('IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',lambda:b.OneShotImporter().import_once(QR,bound,perm,lambda _:b'',NOW))

    def test_import_expired(self):
        bound=self.live_binding()
        perm=b.ImportPermission(bound.hardware_sha256,bound.pairing_sha256,True,True)
        self.stopped('IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',lambda:b.OneShotImporter().import_once(QR,bound,perm,lambda _:b'',NOW+timedelta(seconds=111)))

    def test_response_invalid(self):
        bound=self.live_binding()
        perm=b.ImportPermission(bound.hardware_sha256,bound.pairing_sha256,True,True)
        self.stopped('IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',lambda:b.OneShotImporter().import_once(QR,bound,perm,lambda _:b'{"raw_secret":"oops"}',NOW))

    def test_ssh_import_source_only_path_disabled(self):
        with patch.object(b.subprocess,'run') as run:
            self.stopped(
                'IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',
                lambda:b.ssh_manager_stdin_transport(
                    'root@192.0.2.10',QR.encode(),
                    expected_target_sha256=b.sha('root@192.0.2.10'),
                ),
            )
            run.assert_not_called()

    def test_forged_binding_and_permission_still_cannot_import(self):
        bound=b.Binding(b.sha(HARD),b.sha(PAIR),NOW+timedelta(seconds=90),True)
        perm=b.ImportPermission(bound.hardware_sha256,bound.pairing_sha256,True,True)
        transport=[]
        self.stopped(
            'IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR',
            lambda:b.OneShotImporter().import_once(
                QR,bound,perm,lambda data:transport.append(data) or b'',NOW,
            ),
        )
        self.assertEqual(transport,[])

    def clean_terminal_document(self):
        return {
            "schema": b.TERMINAL_READONLY_SCHEMA,
            "historical_count": 0,
            "historical_hardware_hashes": [],
            "new_count": 1,
            "hardware_sha256": b.sha(HARD),
            "pairing_sha256": b.sha(PAIR),
            "expires_at": (NOW + timedelta(seconds=100)).isoformat(),
            "pending_state": "pending",
            "first_registration_no_history": True,
            "credential_history_clear": True,
            "replay_linkage_clear": True,
            "read_only": True,
            "read_at": NOW.isoformat(),
        }

    def test_clean_zero_preboot_terminal_binding(self):
        document = self.clean_terminal_document()
        binding = b.bind_clean_terminal_projection(QR, document, frozenset(), NOW)
        self.assertEqual(binding.hardware_sha256, b.sha(HARD))
        self.assertFalse(binding.live_attested)

    def test_clean_binder_refuses_historical_five_baseline(self):
        document = self.clean_terminal_document()
        self.stopped(
            "CLEAN_PREBOOT_NOT_EMPTY",
            lambda: b.bind_clean_terminal_projection(QR, document, self.baseline, NOW),
        )

    def test_clean_binder_refuses_nonzero_claim_with_zero_baseline(self):
        document = self.clean_terminal_document()
        document["historical_count"] = 5
        self.stopped(
            "TERMINAL_PENDING_INVALID",
            lambda: b.bind_clean_terminal_projection(QR, document, frozenset(), NOW),
        )

    def test_snapshot_no_db_write(self):
        import hashlib
        def h():return [hashlib.sha256(x.read_bytes()).hexdigest() for x in (self.reg,self.cred)]
        before=h();self.projection();self.assertEqual(before,h())

if __name__=='__main__':unittest.main(verbosity=2)
