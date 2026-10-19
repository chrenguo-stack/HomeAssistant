#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

from n3w_t1_production_v2_contract import validate_release

QUALIFICATION_SCHEMA = "gh.n3w-t1-f5-v2-fresh-armbian-qualification/1"
OBSERVATION_SCHEMA = "gh.n3w-t1-f5-v2-fresh-armbian-observation/1"

CHECK_IDS = (
    "HOST.OS_ARCH",
    "HOST.ARMBIAN_IDENTITY",
    "HOST.FIRSTBOOT",
    "HOST.SSH_TRUST",
    "HOST.PRIVILEGE",
    "HOST.NETWORK_TIME",
    "HOST.STORAGE",
    "HOST.APT_SOURCE",
    "HOST.DOCKER_ABSENT",
    "HOST.PRODUCT_ABSENT",
)

PRODUCT_PATHS = (
    "/var/lib/greenhouse-manager",
    "/var/lib/n3wfc4-homeassistant",
    "/var/lib/n3wfc4-broker",
    "/var/lib/n3wfc4-certificate-lifecycle",
    "/opt/greenhouse-secrets",
    "/opt/HomeAssistant",
    "/etc/n3wfc4",
    "/usr/local/sbin/n3w-broker-ingress-guard",
    "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
    "/usr/local/sbin/n3w-broker-certificate-lifecycle",
    "/usr/local/sbin/n3w-t1-provision",
    "/usr/local/sbin/n3w-t1-systemd-staged-install",
    "/usr/local/sbin/n3w-t1-production-activation-enable",
    "/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard",
    "/etc/systemd/system/n3wfc4-broker-ingress-guard.service",
    "/etc/systemd/system/n3wfc4-broker-activation.service",
    "/etc/systemd/system/n3wfc4-services-activation.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer",
    "/etc/systemd/system/n3wfc4-provision-resume.service",
    "/var/lib/n3w-production/run.json",
)

ENGINE_PATHS = (
    "/var/lib/docker",
    "/var/lib/containerd",
    "/var/run/docker.sock",
)

REMOTE_PROBE_SCRIPT = r'''
import json,os,shutil,socket,subprocess
from pathlib import Path

OS_KEYS=("ID","VERSION_ID","VERSION_CODENAME","PRETTY_NAME")
ARMBIAN_KEYS=("BOARD","BOARD_NAME","VERSION","BRANCH","ARCH","IMAGE_TYPE")
PRODUCT_PATHS=%r
ENGINE_PATHS=%r


def run(argv):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,check=False,timeout=20)
        return {"rc":p.returncode,"out":p.stdout.strip(),"err":p.stderr.strip()[:120]}
    except Exception as e:
        return {"rc":127,"out":"","err":type(e).__name__}


def assignments(path,keys):
    result={}
    try:
        text=Path(path).read_text(encoding="utf-8",errors="strict")
    except Exception:
        return None
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key,value=line.split("=",1)
        if key not in keys:
            continue
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'":
            value=value[1:-1]
        result[key]=value
    return result


def service(name):
    fields={}
    for key,argv in {
        "active":["systemctl","is-active",name],
        "load_state":["systemctl","show","-p","LoadState","--value",name],
        "result":["systemctl","show","-p","Result","--value",name],
        "exec_main_status":["systemctl","show","-p","ExecMainStatus","--value",name],
        "unit_file_state":["systemctl","show","-p","UnitFileState","--value",name],
    }.items():
        item=run(argv)
        fields[key]=item["out"] if item["out"] else None
        fields[key+"_rc"]=item["rc"]
    return fields


def installed(name):
    item=run(["dpkg-query","-W","-f=${Status}",name])
    if item["rc"]==0:
        return item["out"]=="install ok installed"
    if item["rc"]==1:
        return False
    return None


def source_summary():
    paths=[Path("/etc/apt/sources.list")]
    root=Path("/etc/apt/sources.list.d")
    if root.is_dir():
        paths.extend(sorted(p for p in root.iterdir() if p.is_file()))
    lines=[]
    unreadable=[]
    for path in paths:
        if not path.exists():
            continue
        try:
            text=path.read_text(encoding="utf-8",errors="ignore")
        except OSError:
            unreadable.append(str(path))
            continue
        for raw in text.splitlines():
            line=raw.split("#",1)[0].strip()
            if line:
                lines.append(line.casefold())
    joined="\n".join(lines)
    return {
        "text_present":bool(lines),
        "hosts":[host for host in ("ports.ubuntu.com",) if host in joined],
        "suites":[suite for suite in ("resolute",) if suite in joined],
        "components":[component for component in ("universe",) if component in joined],
        "unreadable_count":len(unreadable),
    }

unavailable=[]
os_release=assignments("/etc/os-release",OS_KEYS)
armbian_release=assignments("/etc/armbian-release",ARMBIAN_KEYS)
if os_release is None: unavailable.append("os_release")
if armbian_release is None: unavailable.append("armbian_release")
ssh=service("ssh")
networkmanager=service("NetworkManager")
firstboot=service("armbian-firstrun.service")
route=run(["ip","-4","route","show","default"])
if route["rc"]!=0: unavailable.append("default_route")
ntp=run(["timedatectl","show","-p","NTPSynchronized","--value"])
if ntp["rc"]!=0: unavailable.append("ntp")
arch=run(["dpkg","--print-architecture"])
if arch["rc"]!=0: unavailable.append("dpkg_architecture")
try:
    dns=bool(socket.getaddrinfo("github.com",443,type=socket.SOCK_STREAM))
except OSError:
    dns=False
try:
    root_free=shutil.disk_usage("/").free
except OSError:
    root_free=None
    unavailable.append("storage")
source=source_summary()
if source["unreadable_count"]: unavailable.append("apt_source")
docker_installed=installed("docker.io")
compose_installed=installed("docker-compose-v2")
if docker_installed is None: unavailable.append("docker_package")
if compose_installed is None: unavailable.append("compose_package")
try:
    staging_count=len(list(Path("/var/tmp").glob("n3w-fresh-bootstrap*")))
except OSError:
    staging_count=None
    unavailable.append("fresh_staging")
report={
    "schema":"gh.n3w-t1-f5-v2-fresh-armbian-observation/1",
    "os_release":os_release,
    "armbian_release":armbian_release,
    "kernel_architecture":os.uname().machine,
    "package_architecture":arch["out"] if arch["rc"]==0 else None,
    "ssh":ssh,
    "networkmanager":networkmanager,
    "armbian_firstrun":firstboot,
    "default_route_present":bool(route["out"]) if route["rc"]==0 else None,
    "dns_resolution_present":dns,
    "ntp_synchronized":ntp["out"] if ntp["rc"]==0 else None,
    "root_free_bytes":root_free,
    "apt_source":source,
    "docker_package_installed":docker_installed,
    "compose_package_installed":compose_installed,
    "docker_command_present":shutil.which("docker") is not None,
    "engine_paths":{path:(Path(path).exists() or Path(path).is_symlink()) for path in ENGINE_PATHS},
    "product_paths":{path:(Path(path).exists() or Path(path).is_symlink()) for path in PRODUCT_PATHS},
    "fresh_staging_count":staging_count,
    "sudo_noninteractive":True,
    "unavailable":sorted(set(unavailable)),
    "read_only":True,
    "mutation_performed":False,
    "production_service_start":False,
    "board_access":False,
}
print(json.dumps(report,sort_keys=True,separators=(",",":")))
''' % (PRODUCT_PATHS, ENGINE_PATHS)


class FreshQualificationError(RuntimeError):
    pass


def _result(status: str, checks: dict[str, str], reasons: list[str]) -> dict[str, Any]:
    return {
        "schema": QUALIFICATION_SCHEMA,
        "status": status,
        "checks": checks,
        "reasons": sorted(set(reasons)),
        "reflash_required": status == "FAIL_REFLASH_REQUIRED",
        "read_only": True,
        "mutation_performed": False,
        "production_service_start": False,
        "board_access": False,
    }


def stop_unavailable(reason: str) -> dict[str, Any]:
    return _result(
        "STOP_UNAVAILABLE",
        {check_id: "UNAVAILABLE" for check_id in CHECK_IDS},
        [reason],
    )


def _check(condition: bool, check_id: str, checks: dict[str, str], reasons: list[str], reason: str) -> None:
    if condition:
        checks[check_id] = "PASS"
    else:
        checks[check_id] = "FAIL"
        reasons.append(reason)


def evaluate(observation: Any, release_document: Any, *, ssh_trust: bool) -> dict[str, Any]:
    try:
        release = validate_release(release_document)
    except Exception as error:
        raise FreshQualificationError("release_contract_invalid") from error
    if not isinstance(observation, dict) or observation.get("schema") != OBSERVATION_SCHEMA:
        return stop_unavailable("observation_invalid")
    if observation.get("read_only") is not True or observation.get("mutation_performed") is not False:
        return stop_unavailable("observation_safety_boundary_invalid")
    unavailable = observation.get("unavailable")
    if not isinstance(unavailable, list):
        return stop_unavailable("observation_unavailable_invalid")
    if unavailable:
        return stop_unavailable("probe_unavailable:" + ",".join(sorted(str(item) for item in unavailable)))

    checks: dict[str, str] = {}
    reasons: list[str] = []
    os_contract = release["os_contract"]
    os_release = observation.get("os_release") or {}
    armbian = observation.get("armbian_release") or {}

    _check(
        all(os_release.get(key) == os_contract[key] for key in ("ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME"))
        and observation.get("package_architecture") == os_contract["ARCH"]
        and observation.get("kernel_architecture") == os_contract["kernel_arch"],
        "HOST.OS_ARCH",
        checks,
        reasons,
        "os_arch_mismatch",
    )
    _check(
        all(armbian.get(key) == os_contract[key] for key in ("BOARD", "BOARD_NAME", "VERSION", "BRANCH", "ARCH", "IMAGE_TYPE")),
        "HOST.ARMBIAN_IDENTITY",
        checks,
        reasons,
        "armbian_identity_mismatch",
    )
    firstboot = observation.get("armbian_firstrun") or {}
    _check(
        firstboot.get("load_state") == "loaded"
        and firstboot.get("active") == "inactive"
        and firstboot.get("unit_file_state") == "disabled"
        and firstboot.get("result") == "success"
        and firstboot.get("exec_main_status") == "0",
        "HOST.FIRSTBOOT",
        checks,
        reasons,
        "firstboot_incomplete",
    )
    _check(ssh_trust is True, "HOST.SSH_TRUST", checks, reasons, "ssh_trust_unproven")
    _check(observation.get("sudo_noninteractive") is True, "HOST.PRIVILEGE", checks, reasons, "sudo_noninteractive_unavailable")
    _check(
        (observation.get("ssh") or {}).get("active") == "active"
        and (observation.get("networkmanager") or {}).get("active") == "active"
        and observation.get("default_route_present") is True
        and observation.get("dns_resolution_present") is True
        and str(observation.get("ntp_synchronized", "")).casefold() == "yes",
        "HOST.NETWORK_TIME",
        checks,
        reasons,
        "network_time_not_ready",
    )
    minimum_free = release["capacity"]["minimum_post_peak_free_bytes"]
    _check(
        isinstance(observation.get("root_free_bytes"), int)
        and not isinstance(observation.get("root_free_bytes"), bool)
        and observation["root_free_bytes"] >= minimum_free,
        "HOST.STORAGE",
        checks,
        reasons,
        "storage_insufficient",
    )
    apt = observation.get("apt_source") or {}
    policy = release["apt_source_policy"]
    _check(
        apt.get("text_present") is True
        and policy["host"].casefold() in set(apt.get("hosts") or [])
        and policy["suite"].casefold() in set(apt.get("suites") or [])
        and policy["component"].casefold() in set(apt.get("components") or [])
        and observation.get("package_architecture") == policy["architecture"],
        "HOST.APT_SOURCE",
        checks,
        reasons,
        "apt_source_mismatch",
    )
    _check(
        observation.get("docker_package_installed") is False
        and observation.get("compose_package_installed") is False
        and observation.get("docker_command_present") is False
        and not any((observation.get("engine_paths") or {}).values()),
        "HOST.DOCKER_ABSENT",
        checks,
        reasons,
        "docker_present",
    )
    _check(
        not any((observation.get("product_paths") or {}).values())
        and observation.get("fresh_staging_count") == 0,
        "HOST.PRODUCT_ABSENT",
        checks,
        reasons,
        "product_residue_present",
    )
    status = "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL_REFLASH_REQUIRED"
    return _result(status, checks, reasons)


def collect(transport: Any, release_document: Any) -> dict[str, Any]:
    try:
        completed = transport.run_remote(
            ("sudo", "-n", "python3", "-B", "-c", REMOTE_PROBE_SCRIPT),
            timeout=120,
        )
        observation = json.loads(completed.stdout)
    except Exception as error:
        return stop_unavailable(f"remote_probe_failed:{type(error).__name__}")
    return evaluate(observation, release_document, ssh_trust=True)
