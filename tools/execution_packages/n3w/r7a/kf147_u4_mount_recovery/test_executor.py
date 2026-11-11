import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('executor.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
remote = {'__name__': 'tested_remote'}
exec(compile(module.REMOTE, 'remote', 'exec'), remote)
Stop = remote['Stop']

class Guards(unittest.TestCase):
    def test_unmounted(self):
        remote['validate_unmounted']([], {'8:0','8:1'}, '/target')

    def test_other_partition_mounted(self):
        with self.assertRaises(Stop):
            remote['validate_unmounted']([['1','0','8:2','/','/other']], {'8:1','8:2'}, '/target')

    def test_target_occupied(self):
        with self.assertRaises(Stop):
            remote['validate_unmounted']([['1','0','7:0','/','/target']], {'8:1'}, '/target')

    def test_nested_mount(self):
        with self.assertRaises(Stop):
            remote['validate_unmounted']([['1','0','7:0','/','/target/sub']], {'8:1'}, '/target')

    def test_post_mount_pass(self):
        remote['validate_mounted']([['1','0','8:1','/','/target','ro,nodev,nosuid,noexec']], '8:1', '/target')

    def test_wrong_source(self):
        with self.assertRaises(Stop):
            remote['validate_mounted']([['1','0','8:2','/','/target','ro,nodev,nosuid,noexec']], '8:1', '/target')

    def test_writable_mount(self):
        with self.assertRaises(Stop):
            remote['validate_mounted']([['1','0','8:1','/','/target','rw,nodev,nosuid,noexec']], '8:1', '/target')

    def test_missing_serial(self):
        with self.assertRaises(Stop):
            remote['fingerprint']({})

    def test_fingerprint_independent_of_path(self):
        a=dict(serial='test',wwn=None,model='model',size=123,tran='usb',path='/dev/sdb')
        b=dict(a,path='/dev/sda')
        self.assertEqual(remote['fingerprint'](a),remote['fingerprint'](b))

    def test_wrong_device_fingerprint(self):
        a=dict(serial='test',size=123,tran='usb')
        self.assertNotEqual(remote['fingerprint'](a),remote['fingerprint'](dict(a,serial='other')))

    def test_execution_order_and_failure(self):
        import base64, io, contextlib
        plan=module.PLAN
        tx=dict(phase='U4_READY_TO_INSTALL',status='ACTIVE',target_artifact_verified=True,
                usb_capacity_verified=True,authorization_claimed=False,authorization_consumed=False,
                transaction_id_sha256=plan['transaction_id_sha256'],usb_filesystem_uuid=plan['usb_filesystem_uuid'])
        def read_object(path):
            name=path.name
            if name=='authorization_claim.json': return dict(claimed=True,consumed=True,replay_permitted=False)
            if name=='activation.json': return dict(source_activated=True)
            if name=='failure.json': return dict(status='STOP',authorization_consumed=True,replay_permitted=False)
            return tx
        def sha(path):
            return plan['installed_predecessor_sha256'].get(str(path),plan['transaction_sha256'])
        def container(image):
            c=next(v for v in plan['containers'].values() if v['image']==image)
            return dict(container_id=c['container_id'],runtime_image_id=c['runtime_image_id'],restart_count=0,status='running')
        for fault in (None,'identity','mount','target','transaction'):
            calls=[]
            def run(argv,**kwargs):
                calls.append(argv)
                if fault=='mount': raise Stop('mount_failed')
            def resolve(*args):
                if fault=='identity': raise Stop('identity_mismatch')
                return '/dev/sda1','8:1',{'8:0','8:1'}
            def verify(*args):
                if fault=='target': raise Stop('target_sha256_invalid')
            count=[0]
            def digest(path):
                if str(path)==str(remote['TX_PATH']):
                    count[0]+=1
                    if fault=='transaction' and count[0]>=4: return 'changed'
                return sha(path)
            overrides=dict(read_object=read_object,sha_file=digest,run=run,resolve_usb=resolve,
                service_state=lambda:dict(ActiveState='active',SubState='running',MainPID='5'),
                container_view=container,ipc_status=lambda _:dict(accepted=True,phase='READY_TO_INSTALL',error_code=None,installed_version='2026.10.0'),
                safe_mountpoint=lambda *a:None,mount_rows=lambda *a:[],validate_unmounted=lambda *a:None,
                validate_mounted=lambda *a:None,verify_target=verify)
            output=io.StringIO()
            with patch.dict(remote,overrides), patch('os.readlink',return_value='mnt:1'),patch('sys.argv',['remote',base64.b64encode(json.dumps(plan).encode()).decode()]),contextlib.redirect_stdout(output):
                rc=remote['main']()
            result=json.loads(output.getvalue())
            self.assertEqual(rc,0 if fault is None else 2)
            self.assertEqual(len(calls),0 if fault=='identity' else 1)
            if calls: self.assertEqual(calls[0],['mount','-t','ext4','-o','ro,noload,nodev,nosuid,noexec','/dev/sda1',plan['mount_target']])
            self.assertFalse(result['u5_transition'])
            self.assertFalse(result['official_u5_preflight_pass'])

    def test_resolve_usb_requires_tree_output(self):
        import os, stat
        from types import SimpleNamespace
        disk=dict(path='/dev/sda',type='disk',tran='usb',rm=True,ro=False,
                  serial='test',wwn=None,model='test',size=10000,**{'maj:min':'8:0'})
        part=dict(path='/dev/sda1',type='part',fstype='ext4',uuid=module.PLAN['usb_filesystem_uuid'],**{'maj:min':'8:1'})
        seen=[]
        def run(argv,**kwargs):
            seen.append(argv)
            if argv[0]=='blkid': return SimpleNamespace(stdout='/dev/sda1\n')
            inventory=[dict(disk,children=[part])] if '--tree' in argv else [disk,part]
            return SimpleNamespace(stdout=json.dumps(dict(blockdevices=inventory)))
        tx=dict(usb_device_identity_public_fingerprint=remote['fingerprint'](disk))
        with patch.dict(remote,run=run), patch('os.stat',return_value=SimpleNamespace(st_mode=stat.S_IFBLK,st_rdev=os.makedev(8,1))),patch('os.path.realpath',side_effect=lambda p:p):
            self.assertEqual(remote['resolve_usb'](module.PLAN,tx),('/dev/sda1','8:1',{'8:0','8:1'}))
        self.assertIn('--tree',seen[1])
        old=module.REMOTE.replace("'--json', '--tree', '--bytes'", "'--json', '--bytes'")
        old_scope={'__name__':'old_test'}
        exec(compile(old,'old_remote','exec'),old_scope)
        with patch.dict(old_scope,run=run), patch('os.stat',return_value=SimpleNamespace(st_mode=stat.S_IFBLK,st_rdev=os.makedev(8,1))),patch('os.path.realpath',side_effect=lambda p:p):
            with self.assertRaisesRegex(old_scope['Stop'],'usb_parent_ambiguous'):
                old_scope['resolve_usb'](module.PLAN,tx)

    def test_retry_requires_exact_pre_mutation_stop(self):
        previous=dict(status='STOP',stop_code="FileNotFoundError:[Errno 2] No such file or directory: '/run/n3w-t1-ota/media/ca89774eb4254d0f'",mount_attempted=False,
            mount_restored=False,service_restart=False,source_deployment=False,transaction_mutation=False,
            u5_transition=False,u6_plus=False,ssh_master_cleanup=True,rc=2)
        module.validate_retry(previous)
        for key,value in [('mount_attempted',True),('mount_restored',True),('status','PASS'),
                          ('stop_code','unknown'),('rc',0),('ssh_master_cleanup',False)]:
            with self.assertRaises(RuntimeError): module.validate_retry(dict(previous,**{key:value}))
        with self.assertRaises(RuntimeError): module.validate_retry({})

    def test_directory_recovery_filesystem_cases(self):
        import tempfile, stat
        from types import SimpleNamespace
        original=Path.lstat
        for case in ('missing_target','missing_media','symlink','nonempty','unsafe_mode','missing_runtime'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                base=Path(temp)/'runtime'
                if case!='missing_runtime': base.mkdir(mode=0o700)
                media=base/'media'; target=media/'transaction'
                if case not in ('missing_media','missing_runtime'): media.mkdir(mode=0o700)
                if case=='symlink': target.symlink_to(base, target_is_directory=True)
                if case in ('nonempty','unsafe_mode'):
                    target.mkdir(mode=0o700)
                    if case=='nonempty': (target/'keep').write_text('retain')
                    else: target.chmod(0o777)
                def lstat(path,*a,**kw):
                    if path==base or base in path.parents:
                        info=original(path,*a,**kw)
                        return SimpleNamespace(st_mode=info.st_mode,st_uid=0)
                    return SimpleNamespace(st_mode=stat.S_IFDIR|0o755,st_uid=0)
                result=dict(runtime_directory_creation_attempted=False,runtime_directories_created=0)
                with patch.object(Path,'lstat',lstat):
                    if case in ('missing_target','missing_media'):
                        remote['safe_mountpoint'](str(target),result)
                        self.assertEqual(result['runtime_directories_created'],1 if case=='missing_target' else 2)
                        self.assertEqual(target.stat().st_mode & 0o777,0o700)
                    else:
                        with self.assertRaises((Stop,FileNotFoundError)):
                            remote['safe_mountpoint'](str(target),result)
                        self.assertEqual(result['runtime_directories_created'],0)

    def test_mkdir_failure_is_reported_before_mount(self):
        from types import SimpleNamespace
        def check(path):
            if str(path).endswith('/media'): raise FileNotFoundError()
        result=dict(runtime_directory_creation_attempted=False,runtime_directories_created=0)
        with patch.dict(remote,checked_directory=check),patch.object(Path,'mkdir',side_effect=PermissionError()):
            with self.assertRaises(PermissionError): remote['safe_mountpoint']('/run/test/media/tx',result)
        self.assertTrue(result['runtime_directory_creation_attempted'])
        self.assertEqual(result['runtime_directories_created'],0)

if __name__=='__main__': unittest.main()
