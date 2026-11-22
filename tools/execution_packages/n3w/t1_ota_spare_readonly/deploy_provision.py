import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path("/opt/HomeAssistant/tools")
target = root / "n3w_t1_device_provisioning_host.py"
backup = root / ".n3w_t1_device_provisioning_host.r7-original.py"
unit = "n3wfc4-provision-resume.service"
old_sha = "95c2cdb28b90d032ca1d743aefccb0a7e8319477d814cc1d29e7b33fd4f22ba1"
new_sha = "e1fa28c14fc549e456f6cf6a48a5bcf5ae5bfe29a62f6030f7e04ff07e9ac712"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def checked(path, expected):
    info = path.lstat()
    if (path.resolve(strict=True) != path or not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0 or info.st_mode & 0o022):
        raise RuntimeError("source_metadata_mismatch:" + path.name)
    data = path.read_bytes()
    if digest(data) != expected:
        raise RuntimeError("source_digest_mismatch:" + path.name)
    return data, info

def run(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("command_failed:" + args[0] + ":" + str(result.returncode))
    return result.stdout.strip()

def show():
    props = ("FragmentPath", "DropInPaths", "ActiveState", "SubState",
             "Result", "InvocationID", "ExecStart")
    lines = run("systemctl", "show", *(f"--property={k}" for k in props), unit)
    return dict(line.split("=", 1) for line in lines.splitlines())

def no_legacy_transaction():
    state = Path("/var/lib/n3w-t1-provisioning")
    if state.is_symlink() or any(os.path.lexists(state / name) for name in
                                 ("transaction.json", "FIRSTBOOT_COMPLETE.json")):
        raise RuntimeError("legacy_initialization_record_present")

def snapshot():
    containers = {}
    for name in ("broker", "homeassistant", "manager"):
        identifier = run("docker", "ps", "-q", "--no-trunc",
                         "--filter", "label=com.docker.compose.project=n3wfc4",
                         "--filter", f"label=com.docker.compose.service={name}")
        if len(identifier.splitlines()) != 1:
            raise RuntimeError("running_container_count_mismatch:" + name)
        containers[name] = run("docker", "inspect", "--format",
                               "{{.Id}} {{.Image}} {{.Config.Image}} {{.State.StartedAt}} {{.RestartCount}}",
                               identifier)
    return containers

def sync_directory():
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def write_atomic(data, info, destination, *, keep_existing=False):
    fd, temp = tempfile.mkstemp(prefix=".r7-provision-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fchown(handle.fileno(), info.st_uid, info.st_gid)
            os.fchmod(handle.fileno(), stat.S_IMODE(info.st_mode))
            os.fsync(handle.fileno())
        if keep_existing:
            os.link(temp, destination)
        else:
            os.replace(temp, destination)
        sync_directory()
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)

def verify_noop(invocation_id):
    if len(invocation_id) != 32 or any(ch not in "0123456789abcdef" for ch in invocation_id):
        return False
    journal = run("journalctl", "--no-pager", "-q", "-o", "cat", "-u", unit,
                  "_SYSTEMD_INVOCATION_ID=" + invocation_id)
    for line in journal.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and all(item.get(k) == v for k, v in {
            "status": "PASS", "state": "UNPROVISIONED", "boot_action": "NOOP",
            "production_service_start": False, "board_access": False,
        }.items()):
            return True
    return False

def deploy():
    candidate = base64.b64decode(CANDIDATE, validate=True)
    if digest(candidate) != new_sha:
        raise RuntimeError("candidate_digest_mismatch")
    previous, info = checked(target, old_sha)
    checked(root / "n3w_t1_fresh_product_bootstrap.py", "887ef8db7f17f1be87c10e8b02c17827a79e996a45f12332d958d262c987857b")
    checked(root / "n3w_t1_device_firstboot.py", "5b8cec240ff721e1f6a8284a21d56175e0a101636ac7d02ee0d2b651782a83b8")
    checked(Path("/usr/local/sbin/n3w-t1-provision"), "deb70abb6a040b82a904846c5d5ed92834170c7932d69000bd915be2ae4f0243")
    checked(Path("/etc/systemd/system") / unit, "7040c59da9731b05246595b8b5e5748d4752ce0d93c5f2ddf300facc16e34328")
    before_unit = show()
    if (before_unit.get("FragmentPath") != f"/etc/systemd/system/{unit}"
            or before_unit.get("DropInPaths")
            or "argv[]=/usr/local/sbin/n3w-t1-provision resume-if-needed ;" not in before_unit.get("ExecStart", "")
            or before_unit.get("ActiveState") != "failed"):
        raise RuntimeError("unexpected_provision_unit_state")
    if run("systemctl", "is-active", "docker.service") != "active":
        raise RuntimeError("docker_not_active")
    before = snapshot()
    if before["homeassistant"].split()[2] != "local/n3w-homeassistant:2026.10.4-5881590f":
        raise RuntimeError("homeassistant_baseline_changed")
    no_legacy_transaction()
    write_atomic(previous, info, backup, keep_existing=True)
    try:
        write_atomic(candidate, info, target)
        checked(target, new_sha)
        no_legacy_transaction()
        run("systemctl", "--job-mode=fail", "start", unit, timeout=120)
        state = show()
        if (state.get("ActiveState"), state.get("SubState"), state.get("Result")) != ("active", "exited", "success"):
            raise RuntimeError("provision_unit_not_active_exited")
        if snapshot() != before:
            raise RuntimeError("runtime_changed")
        no_legacy_transaction()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        try:
            if target.is_file() and not target.is_symlink() and digest(target.read_bytes()) == new_sha:
                write_atomic(previous, info, target)
            checked(target, old_sha)
            rollback = "ORIGINAL_BYTES_VERIFIED"
        except (OSError, RuntimeError):
            rollback = "CHECK_ORIGINAL_BACKUP"
        print(json.dumps({"status": "R7_PROVISION_DEPLOY_STOP", "reason": str(error),
                          "script_rollback": rollback}, sort_keys=True))
        return 2
    try:
        noop = verify_noop(state.get("InvocationID", ""))
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        noop = False
    print(json.dumps({"status": "R7_PROVISION_DEPLOY_PASS", "unit": "active/exited",
                      "journal_noop_verified": noop, "runtime_unchanged": True,
                      "candidate_sha256": new_sha}, sort_keys=True))
    return 0

def load_observer():
    observer = base64.b64decode(OBSERVER, validate=True)
    if digest(observer) != "e9f9a5740dd9482a441fc962923ffb24f7eea46072f3daec2357147caaa68110":
        raise RuntimeError("observer_digest_mismatch")
    archive = base64.b64decode(RECOVERY_PACKAGE, validate=True)
    if digest(archive) != "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84":
        raise RuntimeError("observer_package_digest_mismatch")
    return observer

os.environ.pop("DOCKER_CONTEXT", None)
os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
try:
    observer_bytes = load_observer()
    rc = deploy()
except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
    print(json.dumps({"status": "R7_PROVISION_PRECHECK_STOP", "reason": str(error)}, sort_keys=True))
    rc = 2
if rc == 0:
    context = {"__name__": "r7_observer", "PACKAGE_ON_SPARE": RECOVERY_PACKAGE, "USB_MOUNT": ""}
    exec(compile(observer_bytes, "observe.py", "exec"), context)
    rc = context["run_spare"]()
sys.exit(rc)
