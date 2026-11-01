#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "gh.n3w-t1-minimal-baseline-readonly-inventory/1"
PRODUCT_TOKENS = (
    "n3w",
    "greenhouse",
    "homeassistant",
    "home-assistant",
    "mosquitto",
)
DEFAULT_DOCKER_NETWORKS = frozenset(("bridge", "host", "none"))
KNOWN_HISTORICAL_PRODUCT_NETWORKS = frozenset(
    ("corrected-successor-mqtt-runtime-20260827-01_default",)
)
HISTORICAL_VOLUME_COUNT = 45
HISTORICAL_VOLUME_SET_SHA256 = (
    "20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b"
)
FORBIDDEN_MUTATION_MARKERS = (
    "docker rm",
    "docker rmi",
    "docker volume rm",
    "docker network rm",
    "systemctl stop",
    "systemctl start",
    "systemctl restart",
    "systemctl enable",
    "systemctl disable",
    "iptables -d",
    "iptables -f",
    "nft delete",
    "nft flush",
    " rm ",
    " unlink ",
    " chmod ",
    " chown ",
)

REMOTE_SCRIPT = r"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
from pathlib import Path

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
    "/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard",
    "/etc/systemd/system/n3wfc4-broker-ingress-guard.service",
    "/etc/systemd/system/n3wfc4-broker-activation.service",
    "/etc/systemd/system/n3wfc4-services-activation.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer",
)
TARGET_PORTS = {1883, 8883, 18883, 8123, 47110, 47111, 47112}
PRODUCT_TOKENS = ("n3w", "greenhouse", "homeassistant", "home-assistant", "mosquitto")


def run(argv, timeout=20):
    try:
        completed = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return {
            "rc": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"rc": 127, "stdout": "", "stderr": type(error).__name__}


def scalar(argv, timeout=20):
    result = run(argv, timeout=timeout)
    return {
        "rc": result["rc"],
        "value": result["stdout"].strip(),
        "error": result["stderr"].strip()[:200],
    }


def productish(value):
    lowered = value.lower()
    return any(token in lowered for token in PRODUCT_TOKENS)


def file_meta(path_text):
    path = Path(path_text)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"path": path_text, "exists": False}
    kind = (
        "symlink"
        if stat.S_ISLNK(info.st_mode)
        else "directory"
        if stat.S_ISDIR(info.st_mode)
        else "file"
        if stat.S_ISREG(info.st_mode)
        else "other"
    )
    result = {
        "path": path_text,
        "exists": True,
        "kind": kind,
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "size": info.st_size,
    }
    if kind == "directory":
        try:
            children = []
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                child_info = child.lstat()
                child_kind = (
                    "symlink"
                    if child.is_symlink()
                    else "directory"
                    if child.is_dir()
                    else "file"
                    if child.is_file()
                    else "other"
                )
                children.append(
                    {
                        "name": child.name,
                        "kind": child_kind,
                        "mode": oct(stat.S_IMODE(child_info.st_mode)),
                        "uid": child_info.st_uid,
                        "gid": child_info.st_gid,
                        "size": child_info.st_size,
                    }
                )
            result["children"] = children
        except OSError as error:
            result["children_error"] = type(error).__name__
    return result


def json_lines(text):
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {"raw": line}
        records.append(value)
    return records


def docker_inventory():
    info = scalar(["docker", "info", "--format", "{{json .}}"], timeout=30)
    containers = scalar(["docker", "ps", "-a", "--format", "{{json .}}"], timeout=30)
    images = scalar(["docker", "image", "ls", "--no-trunc", "--format", "{{json .}}"], timeout=30)
    volumes = scalar(["docker", "volume", "ls", "--format", "{{json .}}"], timeout=30)
    networks = scalar(["docker", "network", "ls", "--format", "{{json .}}"], timeout=30)
    volume_records = json_lines(volumes["value"]) if volumes["rc"] == 0 else []
    volume_names = [
        str(record.get("Name", ""))
        for record in volume_records
        if isinstance(record, dict) and record.get("Name")
    ]
    volume_inspect = []
    if volume_names:
        inspected = run(["docker", "volume", "inspect", *volume_names], timeout=30)
        if inspected["rc"] == 0:
            try:
                parsed = json.loads(inspected["stdout"])
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            volume_inspect.append(
                                {
                                    "Name": item.get("Name"),
                                    "Driver": item.get("Driver"),
                                    "Labels": item.get("Labels"),
                                    "Mountpoint": item.get("Mountpoint"),
                                    "Scope": item.get("Scope"),
                                }
                            )
            except json.JSONDecodeError:
                pass
    docker_info = {}
    if info["rc"] == 0 and info["value"]:
        try:
            parsed_info = json.loads(info["value"])
            if isinstance(parsed_info, dict):
                docker_info = {
                    "ServerVersion": parsed_info.get("ServerVersion"),
                    "DockerRootDir": parsed_info.get("DockerRootDir"),
                    "Driver": parsed_info.get("Driver"),
                    "Architecture": parsed_info.get("Architecture"),
                    "OperatingSystem": parsed_info.get("OperatingSystem"),
                    "Containers": parsed_info.get("Containers"),
                    "Images": parsed_info.get("Images"),
                }
        except json.JSONDecodeError:
            pass
    return {
        "info": docker_info,
        "containers": json_lines(containers["value"]) if containers["rc"] == 0 else [],
        "images": json_lines(images["value"]) if images["rc"] == 0 else [],
        "volumes": volume_records,
        "volume_inspect": volume_inspect,
        "networks": json_lines(networks["value"]) if networks["rc"] == 0 else [],
        "errors": {
            "info": info["error"] if info["rc"] else "",
            "containers": containers["error"] if containers["rc"] else "",
            "images": images["error"] if images["rc"] else "",
            "volumes": volumes["error"] if volumes["rc"] else "",
            "networks": networks["error"] if networks["rc"] else "",
        },
    }


def systemd_inventory():
    listing = run(
        [
            "systemctl",
            "list-unit-files",
            "--type=service",
            "--type=timer",
            "--no-legend",
            "--no-pager",
        ],
        timeout=30,
    )
    names = []
    if listing["rc"] == 0:
        for line in listing["stdout"].splitlines():
            fields = line.split()
            if fields and productish(fields[0]):
                names.append(fields[0])
    records = []
    for name in sorted(set(names)):
        active = scalar(["systemctl", "is-active", name])
        enabled = scalar(["systemctl", "is-enabled", name])
        fragment = scalar(["systemctl", "show", "-p", "FragmentPath", "--value", name])
        records.append(
            {
                "name": name,
                "active": active["value"] if active["value"] else f"rc={active['rc']}",
                "enabled": enabled["value"] if enabled["value"] else f"rc={enabled['rc']}",
                "fragment_path": fragment["value"],
            }
        )
    return {
        "units": records,
        "list_error": listing["stderr"].strip()[:200] if listing["rc"] else "",
    }


def listeners():
    result = run(["ss", "-H", "-lntu"], timeout=20)
    records = []
    if result["rc"] != 0:
        return {"records": [], "error": result["stderr"].strip()[:200]}
    for line in result["stdout"].splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        local = fields[4]
        try:
            port = int(local.rsplit(":", 1)[1].rstrip("]"))
        except (IndexError, ValueError):
            continue
        if port in TARGET_PORTS:
            records.append({"protocol": fields[0], "local": local, "port": port})
    return {"records": records, "error": ""}


def firewall():
    commands = (
        ["sudo", "-n", "iptables", "-S"],
        ["sudo", "-n", "iptables", "-t", "nat", "-S"],
        ["sudo", "-n", "nft", "list", "ruleset"],
    )
    records = []
    for command in commands:
        result = run(command, timeout=20)
        relevant = []
        if result["rc"] == 0:
            for line in result["stdout"].splitlines():
                if productish(line) or "8883" in line or "DOCKER-USER" in line:
                    relevant.append(line)
        records.append(
            {
                "command": " ".join(command[2:] if command[:2] == ["sudo", "-n"] else command),
                "rc": result["rc"],
                "relevant_lines": relevant,
                "error": result["stderr"].strip()[:200] if result["rc"] else "",
            }
        )
    return records


def host_baseline():
    os_release = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                if key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
                    os_release[key] = value.strip().strip('"')
    except OSError:
        pass
    route = scalar(["ip", "-4", "route", "show", "default"])
    dns = scalar(["sh", "-c", "grep -Ev '^[[:space:]]*(#|$)' /etc/resolv.conf | head -n 8"])
    ntp = scalar(["timedatectl", "show", "-p", "NTPSynchronized", "--value"])
    root_usage = shutil.disk_usage("/")
    return {
        "architecture": os.uname().machine,
        "hostname_sha256": hashlib.sha256(socket.gethostname().encode()).hexdigest(),
        "os_release": os_release,
        "ssh_active": scalar(["systemctl", "is-active", "ssh"])["value"],
        "networkmanager_active": scalar(["systemctl", "is-active", "NetworkManager"])["value"],
        "docker_active": scalar(["systemctl", "is-active", "docker"])["value"],
        "docker_compose_version": scalar(["docker", "compose", "version", "--short"])["value"],
        "default_route_present": route["rc"] == 0 and bool(route["value"]),
        "dns_config_present": dns["rc"] == 0 and bool(dns["value"]),
        "ntp_synchronized": ntp["value"],
        "root_free_bytes": root_usage.free,
    }


def canonical_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


report = {
    "schema": "gh.n3w-t1-minimal-baseline-remote-inventory/1",
    "host_baseline": host_baseline(),
    "docker": docker_inventory(),
    "systemd": systemd_inventory(),
    "product_paths": [file_meta(path) for path in PRODUCT_PATHS],
    "listeners": listeners(),
    "firewall": firewall(),
    "mutation_performed": False,
    "production_service_start": False,
    "board_access": False,
}
report["inventory_sha256"] = canonical_sha256(report)
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
"""


class ReadOnlyInventoryError(RuntimeError):
    pass


def _run(
    command: Sequence[str],
    *,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        tuple(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise ReadOnlyInventoryError(
            f"command_failed:{command[0]}:{completed.returncode}:{reason[:500]}"
        )
    return completed


def _remote_command() -> str:
    encoded = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    expression = (
        "import base64;"
        f"exec(compile(base64.b64decode({encoded!r}),'<n3w-readonly>','exec'))"
    )
    return " ".join(shlex.quote(part) for part in ("python3", "-c", expression))


def _productish(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in PRODUCT_TOKENS)


def _volume_set_sha256(names: Sequence[str]) -> str:
    payload = "".join(f"{name}\n" for name in sorted(name for name in names if name)).encode()
    return hashlib.sha256(payload).hexdigest()


def _classify(report: dict[str, Any]) -> dict[str, Any]:
    preserve = []
    delete_candidates = []
    unknown = []

    host = report.get("host_baseline")
    if isinstance(host, dict):
        for key in (
            "architecture",
            "os_release",
            "ssh_active",
            "networkmanager_active",
            "docker_active",
            "docker_compose_version",
            "default_route_present",
            "dns_config_present",
            "ntp_synchronized",
            "root_free_bytes",
        ):
            preserve.append({"type": "host_baseline", "name": key, "observed": host.get(key)})

    for item in report.get("product_paths", []):
        if isinstance(item, dict) and item.get("exists") is True:
            delete_candidates.append(
                {
                    "type": "product_path",
                    "name": item.get("path"),
                    "reason": "known_repository_product_path",
                }
            )

    systemd = report.get("systemd")
    if isinstance(systemd, dict):
        for item in systemd.get("units", []):
            if isinstance(item, dict):
                delete_candidates.append(
                    {
                        "type": "systemd_unit",
                        "name": item.get("name"),
                        "reason": "product_named_unit",
                    }
                )

    docker = report.get("docker")
    if isinstance(docker, dict):
        for collection, object_type in (
            ("containers", "docker_container"),
            ("images", "docker_image"),
        ):
            for item in docker.get(collection, []):
                if not isinstance(item, dict):
                    continue
                rendered = json.dumps(item, sort_keys=True)
                target = delete_candidates if _productish(rendered) else unknown
                target.append(
                    {
                        "type": object_type,
                        "name": item.get("Names")
                        or item.get("Name")
                        or item.get("Repository")
                        or rendered,
                        "reason": (
                            "product_token_match"
                            if target is delete_candidates
                            else "ownership_unproven"
                        ),
                    }
                )

        for item in docker.get("networks", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name", ""))
            rendered = json.dumps(item, sort_keys=True)
            if name in DEFAULT_DOCKER_NETWORKS:
                preserve.append(
                    {
                        "type": "docker_network",
                        "name": name,
                        "reason": "docker_engine_default_network",
                    }
                )
            elif (
                name in KNOWN_HISTORICAL_PRODUCT_NETWORKS
                or _productish(rendered)
            ):
                delete_candidates.append(
                    {
                        "type": "docker_network",
                        "name": name,
                        "reason": "historical_or_current_product_network",
                    }
                )
            else:
                unknown.append(
                    {
                        "type": "docker_network",
                        "name": name,
                        "reason": "ownership_unproven",
                    }
                )

        volume_records = [
            item for item in docker.get("volumes", []) if isinstance(item, dict)
        ]
        volume_names = [str(item.get("Name", "")) for item in volume_records]
        historical_volume_set = (
            len(volume_names) == HISTORICAL_VOLUME_COUNT
            and _volume_set_sha256(volume_names) == HISTORICAL_VOLUME_SET_SHA256
        )
        inspected = {
            str(item.get("Name")): item
            for item in docker.get("volume_inspect", [])
            if isinstance(item, dict) and item.get("Name")
        }
        for item in volume_records:
            name = str(item.get("Name", ""))
            detail = inspected.get(name, {})
            rendered = json.dumps(detail or item, sort_keys=True)
            labels = detail.get("Labels") if isinstance(detail, dict) else None
            compose_project = (
                labels.get("com.docker.compose.project")
                if isinstance(labels, dict)
                else None
            )
            proven = (
                historical_volume_set
                or compose_project == "n3wfc4"
                or _productish(name)
                or _productish(rendered)
            )
            target = delete_candidates if proven else unknown
            target.append(
                {
                    "type": "docker_volume",
                    "name": name,
                    "reason": (
                        "historical_frozen_volume_set_exact_match"
                        if historical_volume_set
                        else "product_label_or_token_match"
                        if proven
                        else "ownership_unproven"
                    ),
                }
            )

    firewall = report.get("firewall")
    if isinstance(firewall, list):
        firewall_by_command = {
            str(item.get("command")): item
            for item in firewall
            if isinstance(item, dict)
        }
        iptables_views_complete = all(
            isinstance(firewall_by_command.get(command), dict)
            and firewall_by_command[command].get("rc") == 0
            for command in ("iptables -S", "iptables -t nat -S")
        )
        for item in firewall:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command"))
            error = str(item.get("error") or "")
            optional_nft_absent = (
                command == "nft list ruleset"
                and item.get("rc") != 0
                and "command not found" in error.lower()
                and iptables_views_complete
            )
            if item.get("rc") != 0 and not optional_nft_absent:
                unknown.append(
                    {
                        "type": "firewall_visibility",
                        "name": item.get("command"),
                        "reason": "read_failed",
                    }
                )
            elif optional_nft_absent:
                preserve.append(
                    {
                        "type": "firewall_visibility",
                        "name": command,
                        "reason": "optional_backend_absent_iptables_views_complete",
                    }
                )
            for line in item.get("relevant_lines", []):
                if not isinstance(line, str):
                    continue
                if (
                    "N3WFC4-BROKER-INGRESS" in line
                    or "n3wfc4-broker-ingress-v1" in line
                ):
                    delete_candidates.append(
                        {
                            "type": "firewall_rule",
                            "name": line,
                            "reason": "n3w_product_firewall_rule",
                        }
                    )
                elif "DOCKER-USER" in line:
                    preserve.append(
                        {
                            "type": "firewall_rule",
                            "name": line,
                            "reason": "docker_engine_firewall_framework",
                        }
                    )

    return {
        "PRESERVE_HOST_BASELINE": preserve,
        "DELETE_PRODUCT_STATE_CANDIDATE": delete_candidates,
        "UNKNOWN_STOP": unknown,
    }


def _validate_remote_report(report: dict[str, Any]) -> None:
    if report.get("schema") != "gh.n3w-t1-minimal-baseline-remote-inventory/1":
        raise ReadOnlyInventoryError("remote_schema_invalid")
    if report.get("mutation_performed") is not False:
        raise ReadOnlyInventoryError("remote_mutation_flag_invalid")
    if report.get("production_service_start") is not False:
        raise ReadOnlyInventoryError("remote_service_start_flag_invalid")
    digest = report.get("inventory_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ReadOnlyInventoryError("inventory_sha256_invalid")


def collect(t1: str) -> dict[str, Any]:
    if not t1.strip():
        raise ReadOnlyInventoryError("t1_target_empty")
    completed = _run(("ssh", "-n", t1, _remote_command()), timeout=180)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ReadOnlyInventoryError("remote_inventory_json_invalid") from error
    if not isinstance(report, dict):
        raise ReadOnlyInventoryError("remote_inventory_json_invalid")
    _validate_remote_report(report)
    classifications = _classify(report)
    return {
        "schema": SCHEMA,
        "status": "STOP" if classifications["UNKNOWN_STOP"] else "PASS",
        "target_sha256": hashlib.sha256(t1.encode()).hexdigest(),
        "inventory_sha256": report["inventory_sha256"],
        "remote": report,
        "classifications": classifications,
        "read_only": True,
        "mutation_performed": False,
        "destructive_authorization_claimed": False,
        "production_service_start": False,
        "board_access": False,
    }


def self_check() -> dict[str, object]:
    lowered = f" {REMOTE_SCRIPT.lower()} "
    found = [marker for marker in FORBIDDEN_MUTATION_MARKERS if marker in lowered]
    return {
        "schema": SCHEMA,
        "status": "PASS" if not found else "STOP",
        "forbidden_mutation_markers": found,
        "ssh_stdin_disabled": '"ssh", "-n"' in Path(__file__).read_text(encoding="utf-8"),
        "read_only": True,
        "mutation_performed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1")
    parser.add_argument("--self-check", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.self_check:
            result = self_check()
        else:
            if not args.t1:
                raise ReadOnlyInventoryError("t1_target_required")
            result = collect(args.t1)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
        return 0 if result.get("status") == "PASS" else 2
    except (ReadOnlyInventoryError, OSError, subprocess.TimeoutExpired) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error),
                    "read_only": True,
                    "mutation_performed": False,
                    "destructive_authorization_claimed": False,
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
