#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "gh.n3w-t1-minimal-baseline-normalization/1"
MANIFEST_SCHEMA = "gh.n3w-t1-minimal-baseline-normalization-manifest/1"
AUTHORIZATION_ID = "N3W_T1_MINIMAL_BASELINE_NORMALIZATION_LIVE_APPLY_20261012_01"
CUSTOM_CHAIN = "N3WFC4-BROKER-INGRESS"
ANCHOR_COMMENT = "n3wfc4-broker-ingress-v1"
BROKER_TLS_PORT = 8883
DEFAULT_NETWORKS = frozenset(("bridge", "host", "none"))
TARGET_PORTS = frozenset((1883, 8883, 18883, 8123, 47110, 47111, 47112))
MIN_ROOT_FREE_BYTES = 5 * 1024 * 1024 * 1024


class NormalizationError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 60.0,
        allowed: frozenset[int] = frozenset({0}),
    ) -> str:
        completed = subprocess.run(
            tuple(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if completed.returncode not in allowed:
            reason = completed.stderr.strip() or completed.stdout.strip()
            raise NormalizationError(
                f"command_failed:{argv[0]}:{completed.returncode}:{reason[:400]}"
            )
        return completed.stdout


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _volume_set_sha256(names: Sequence[str]) -> str:
    payload = "".join(f"{name}\n" for name in sorted(names))
    return _sha256_text(payload)


def _load_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise NormalizationError("manifest_missing_or_unsafe")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NormalizationError("manifest_invalid") from error
    if not isinstance(document, dict):
        raise NormalizationError("manifest_invalid")
    _validate_manifest(document)
    return document


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise NormalizationError("manifest_schema_invalid")
    if manifest.get("target_baseline") != "ARMBIAN + DOCKER + NETWORK ONLY":
        raise NormalizationError("target_baseline_invalid")
    source = manifest.get("source_inventory")
    if not isinstance(source, dict):
        raise NormalizationError("source_inventory_missing")
    if source.get("volume_count") != 45:
        raise NormalizationError("volume_count_invalid")
    expected_volume_sha = source.get("volume_set_sha256")
    if not isinstance(expected_volume_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_volume_sha
    ):
        raise NormalizationError("volume_set_sha_invalid")

    delete = manifest.get("delete")
    preserve = manifest.get("preserve")
    if not isinstance(delete, dict) or not isinstance(preserve, dict):
        raise NormalizationError("manifest_delete_or_preserve_missing")

    volumes = delete.get("docker_volumes")
    if not isinstance(volumes, list) or len(volumes) != 45:
        raise NormalizationError("docker_volume_list_invalid")
    if len(set(volumes)) != 45:
        raise NormalizationError("docker_volume_list_duplicate")
    if not all(isinstance(name, str) and re.fullmatch(r"[0-9a-f]{64}", name) for name in volumes):
        raise NormalizationError("docker_volume_name_invalid")
    if _volume_set_sha256(volumes) != expected_volume_sha:
        raise NormalizationError("docker_volume_set_binding_invalid")

    networks = delete.get("docker_networks")
    if not isinstance(networks, list) or len(networks) != 5:
        raise NormalizationError("docker_network_list_invalid")
    network_names = []
    for item in networks:
        if not isinstance(item, dict):
            raise NormalizationError("docker_network_record_invalid")
        name = item.get("name")
        prefix = item.get("expected_id_prefix")
        if (
            not isinstance(name, str)
            or not name
            or name in DEFAULT_NETWORKS
            or not isinstance(prefix, str)
            or not re.fullmatch(r"[0-9a-f]{12}", prefix)
        ):
            raise NormalizationError("docker_network_record_invalid")
        network_names.append(name)
    if len(set(network_names)) != 5:
        raise NormalizationError("docker_network_list_duplicate")

    if preserve.get("docker_networks") != ["bridge", "host", "none"]:
        raise NormalizationError("default_network_preserve_invalid")
    framework = preserve.get("docker_firewall_framework")
    if not isinstance(framework, dict) or framework.get("chain") != "DOCKER-USER":
        raise NormalizationError("docker_firewall_preserve_invalid")
    if framework.get("forward_jump_required") is not True:
        raise NormalizationError("docker_forward_preserve_invalid")

    paths = delete.get("product_paths")
    if not isinstance(paths, list) or not paths:
        raise NormalizationError("product_path_list_invalid")
    seen_paths = set()
    for item in paths:
        if not isinstance(item, dict):
            raise NormalizationError("product_path_record_invalid")
        value = item.get("path")
        kind = item.get("kind")
        if (
            not isinstance(value, str)
            or not value.startswith("/")
            or value in {"/", "/var", "/var/lib", "/var/lib/docker", "/etc", "/opt"}
            or any(token in value for token in ("*", "?", "[", "]"))
            or kind not in {"file", "directory"}
        ):
            raise NormalizationError("product_path_record_invalid")
        seen_paths.add(value)
    if len(seen_paths) != len(paths):
        raise NormalizationError("product_path_duplicate")

    firewall = delete.get("firewall")
    if (
        not isinstance(firewall, dict)
        or firewall.get("custom_chain") != CUSTOM_CHAIN
        or firewall.get("anchor_comment") != ANCHOR_COMMENT
        or firewall.get("broker_tls_port") != BROKER_TLS_PORT
        or firewall.get("expected_input_anchor_count") != 1
        or firewall.get("expected_docker_user_anchor_count") != 1
        or firewall.get("expected_custom_rule_count") != 3
        or firewall.get("foreign_custom_chain_references_allowed") is not False
    ):
        raise NormalizationError("firewall_manifest_invalid")

    authorization = manifest.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("id") != AUTHORIZATION_ID:
        raise NormalizationError("authorization_id_invalid")
    if authorization.get("replay_after_mutation") is not False:
        raise NormalizationError("authorization_replay_contract_invalid")


def _systemctl_scalar(
    runner: Runner,
    operation: str,
    unit: str,
) -> str:
    return runner.run(
        ("systemctl", operation, unit),
        allowed=frozenset({0, 1, 3, 4}),
    ).strip()


def _host_report(runner: Runner) -> dict[str, Any]:
    architecture = runner.run(("uname", "-m")).strip()
    ssh = _systemctl_scalar(runner, "is-active", "ssh")
    networkmanager = _systemctl_scalar(runner, "is-active", "NetworkManager")
    docker = _systemctl_scalar(runner, "is-active", "docker")
    compose = runner.run(("docker", "compose", "version", "--short")).strip()
    route = runner.run(("ip", "-4", "route", "show", "default")).strip()
    dns = runner.run(
        ("sh", "-c", "grep -Ev '^[[:space:]]*(#|$)' /etc/resolv.conf | head -n 8")
    ).strip()
    ntp = runner.run(
        ("timedatectl", "show", "-p", "NTPSynchronized", "--value")
    ).strip()
    return {
        "architecture": architecture,
        "ssh_active": ssh,
        "networkmanager_active": networkmanager,
        "docker_active": docker,
        "docker_compose_version": compose,
        "default_route_present": bool(route),
        "dns_config_present": bool(dns),
        "ntp_synchronized": ntp,
        "root_free_bytes": shutil.disk_usage("/").free,
    }


def _docker_report(runner: Runner, manifest: dict[str, Any]) -> dict[str, Any]:
    containers = tuple(
        line.strip()
        for line in runner.run(("docker", "ps", "-aq")).splitlines()
        if line.strip()
    )
    images = tuple(
        line.strip()
        for line in runner.run(("docker", "image", "ls", "-q")).splitlines()
        if line.strip()
    )
    volumes = tuple(
        sorted(
            line.strip()
            for line in runner.run(("docker", "volume", "ls", "-q")).splitlines()
            if line.strip()
        )
    )
    networks = tuple(
        sorted(
            line.strip()
            for line in runner.run(
                ("docker", "network", "ls", "--format", "{{.Name}}")
            ).splitlines()
            if line.strip()
        )
    )
    product_networks = {}
    for record in manifest["delete"]["docker_networks"]:
        name = record["name"]
        raw = runner.run(("docker", "network", "inspect", name))
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise NormalizationError(f"network_inspect_invalid:{name}") from error
        if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
            raise NormalizationError(f"network_inspect_invalid:{name}")
        item = parsed[0]
        containers_map = item.get("Containers")
        product_networks[name] = {
            "id": item.get("Id"),
            "attached_container_count": (
                len(containers_map) if isinstance(containers_map, dict) else -1
            ),
        }
    return {
        "containers": containers,
        "images": images,
        "volumes": volumes,
        "volume_set_sha256": _volume_set_sha256(volumes),
        "networks": networks,
        "product_networks": product_networks,
    }


def _path_kind(path: Path) -> str:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if stat.S_ISDIR(info.st_mode):
        return "directory"
    if stat.S_ISREG(info.st_mode):
        return "file"
    return "other"


def _path_report(manifest: dict[str, Any]) -> dict[str, Any]:
    present = {}
    for record in manifest["delete"]["product_paths"]:
        path = Path(record["path"])
        if not path.exists() and not path.is_symlink():
            present[record["path"]] = {"exists": False}
            continue
        present[record["path"]] = {
            "exists": True,
            "kind": _path_kind(path),
        }
    absent = {}
    for value in manifest.get("expected_absent_before_apply", []):
        path = Path(value)
        absent[value] = not path.exists() and not path.is_symlink()
    return {"delete_paths": present, "expected_absent": absent}


def _systemd_report(runner: Runner, manifest: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for record in manifest["delete"]["systemd_units"]:
        name = record["name"]
        active = _systemctl_scalar(runner, "is-active", name)
        enabled = _systemctl_scalar(runner, "is-enabled", name)
        fragment = runner.run(
            ("systemctl", "show", "-p", "FragmentPath", "--value", name),
            allowed=frozenset({0, 1}),
        ).strip()
        result[name] = {
            "active": active,
            "enabled": enabled,
            "fragment_path": fragment,
        }
    return result


def _listener_report(runner: Runner) -> dict[int, int]:
    output = runner.run(("ss", "-H", "-lntu"))
    counts = {port: 0 for port in TARGET_PORTS}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        local = fields[4]
        try:
            port = int(local.rsplit(":", 1)[1].rstrip("]"))
        except (IndexError, ValueError):
            continue
        if port in counts:
            counts[port] += 1
    return counts


def _rule_semantics(line: str) -> tuple[str, dict[str, list[str]]] | None:
    try:
        tokens = shlex.split(line)
    except ValueError:
        return None
    if len(tokens) < 2 or tokens[0] != "-A":
        return None
    chain = tokens[1]
    values: dict[str, list[str]] = {}
    aliases = {
        "-p": "protocol",
        "-m": "match",
        "--ctdir": "ctdir",
        "--ctorigdstport": "ctorigdstport",
        "--dport": "dport",
        "-i": "interface",
        "-s": "source",
        "--comment": "comment",
        "-j": "jump",
    }
    index = 2
    while index < len(tokens):
        key = aliases.get(tokens[index])
        if key is None or index + 1 >= len(tokens):
            return None
        values.setdefault(key, []).append(tokens[index + 1])
        index += 2
    return chain, values


def _single(values: dict[str, list[str]], key: str) -> str | None:
    found = values.get(key, [])
    return found[0] if len(found) == 1 else None


def _firewall_report(runner: Runner) -> dict[str, Any]:
    payload = runner.run(("iptables-save", "-t", "filter"))
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    docker_user_present = any(line.startswith(":DOCKER-USER ") for line in lines)
    custom_present = any(line.startswith(f":{CUSTOM_CHAIN} ") for line in lines)
    input_present = any(line.startswith(":INPUT ") for line in lines)
    forward_to_docker_user = sum(
        line == "-A FORWARD -j DOCKER-USER" for line in lines
    )

    docker_anchor_count = 0
    input_anchor_count = 0
    custom_rules = []
    foreign_refs = []

    for line in lines:
        parsed = _rule_semantics(line)
        if parsed is None:
            continue
        chain, values = parsed
        jump = _single(values, "jump")
        comment = _single(values, "comment")
        if chain == "DOCKER-USER" and jump == CUSTOM_CHAIN and comment == ANCHOR_COMMENT:
            if (
                _single(values, "protocol") == "tcp"
                and _single(values, "ctdir") == "ORIGINAL"
                and _single(values, "ctorigdstport") == str(BROKER_TLS_PORT)
            ):
                docker_anchor_count += 1
                continue
        if chain == "INPUT" and jump == CUSTOM_CHAIN and comment == ANCHOR_COMMENT:
            if (
                _single(values, "protocol") == "tcp"
                and _single(values, "dport") == str(BROKER_TLS_PORT)
            ):
                input_anchor_count += 1
                continue
        if chain == CUSTOM_CHAIN:
            custom_rules.append((line, values))
            continue
        if jump == CUSTOM_CHAIN:
            foreign_refs.append(line)

    trusted_sha256 = None
    custom_rules_valid = False
    if len(custom_rules) == 3:
        first = custom_rules[0][1]
        second = custom_rules[1][1]
        third = custom_rules[2][1]
        first_source = _single(first, "source")
        second_source = _single(second, "source")
        try:
            first_network = (
                ipaddress.ip_network(first_source, strict=False)
                if first_source is not None
                else None
            )
            second_network = (
                ipaddress.ip_network(second_source, strict=False)
                if second_source is not None
                else None
            )
        except ValueError:
            first_network = None
            second_network = None
        custom_rules_valid = (
            first_network == ipaddress.ip_network("127.0.0.0/8")
            and _single(first, "interface") == "lo"
            and _single(first, "comment") == ANCHOR_COMMENT
            and _single(first, "jump") == "RETURN"
            and isinstance(second_network, ipaddress.IPv4Network)
            and not second_network.is_loopback
            and _single(second, "interface") == "eth0"
            and _single(second, "comment") == ANCHOR_COMMENT
            and _single(second, "jump") == "RETURN"
            and _single(third, "comment") == ANCHOR_COMMENT
            and _single(third, "jump") == "DROP"
        )
        if custom_rules_valid and second_network is not None:
            trusted_sha256 = _sha256_text(str(second_network))

    return {
        "docker_user_present": docker_user_present,
        "custom_chain_present": custom_present,
        "input_present": input_present,
        "forward_to_docker_user_count": forward_to_docker_user,
        "docker_user_anchor_count": docker_anchor_count,
        "input_anchor_count": input_anchor_count,
        "custom_rule_count": len(custom_rules),
        "custom_rules_valid": custom_rules_valid,
        "foreign_custom_chain_references": tuple(foreign_refs),
        "trusted_subnet_sha256": trusted_sha256,
    }


def _collect_preflight(runner: Runner, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": _host_report(runner),
        "docker": _docker_report(runner, manifest),
        "paths": _path_report(manifest),
        "systemd": _systemd_report(runner, manifest),
        "listeners": _listener_report(runner),
        "firewall": _firewall_report(runner),
    }


def _validate_host(host: dict[str, Any]) -> None:
    if host.get("architecture") != "aarch64":
        raise NormalizationError("host_architecture_drift")
    for key in ("ssh_active", "networkmanager_active", "docker_active"):
        if host.get(key) != "active":
            raise NormalizationError(f"host_service_drift:{key}")
    if not host.get("docker_compose_version"):
        raise NormalizationError("docker_compose_missing")
    if host.get("default_route_present") is not True:
        raise NormalizationError("default_route_missing")
    if host.get("dns_config_present") is not True:
        raise NormalizationError("dns_config_missing")
    if host.get("ntp_synchronized") != "yes":
        raise NormalizationError("ntp_not_synchronized")
    if int(host.get("root_free_bytes", 0)) < MIN_ROOT_FREE_BYTES:
        raise NormalizationError("root_capacity_insufficient")


def _validate_preflight(report: dict[str, Any], manifest: dict[str, Any]) -> None:
    _validate_host(report["host"])
    docker = report["docker"]
    if docker["containers"] or docker["images"]:
        raise NormalizationError("docker_runtime_not_empty")
    expected_volumes = tuple(sorted(manifest["delete"]["docker_volumes"]))
    if docker["volumes"] != expected_volumes:
        raise NormalizationError("docker_volume_set_drift")
    if docker["volume_set_sha256"] != manifest["source_inventory"]["volume_set_sha256"]:
        raise NormalizationError("docker_volume_set_sha_drift")
    expected_networks = tuple(
        sorted(
            list(DEFAULT_NETWORKS)
            + [record["name"] for record in manifest["delete"]["docker_networks"]]
        )
    )
    if docker["networks"] != expected_networks:
        raise NormalizationError("docker_network_set_drift")
    expected_prefix = {
        record["name"]: record["expected_id_prefix"]
        for record in manifest["delete"]["docker_networks"]
    }
    for name, item in docker["product_networks"].items():
        image_id = item.get("id")
        if (
            not isinstance(image_id, str)
            or not image_id.startswith(expected_prefix[name])
            or item.get("attached_container_count") != 0
        ):
            raise NormalizationError(f"docker_network_drift:{name}")

    for record in manifest["delete"]["product_paths"]:
        actual = report["paths"]["delete_paths"].get(record["path"])
        if actual != {"exists": True, "kind": record["kind"]}:
            raise NormalizationError(f"product_path_drift:{record['path']}")
    if not all(report["paths"]["expected_absent"].values()):
        raise NormalizationError("expected_absent_path_drift")

    for record in manifest["delete"]["systemd_units"]:
        actual = report["systemd"].get(record["name"])
        if not isinstance(actual, dict):
            raise NormalizationError("systemd_unit_missing")
        if (
            actual.get("active") != record["expected_active"]
            or actual.get("enabled") != record["expected_enabled"]
            or actual.get("fragment_path") != record["fragment_path"]
        ):
            raise NormalizationError("systemd_unit_drift")

    if any(report["listeners"].values()):
        raise NormalizationError("production_listener_present")

    firewall = report["firewall"]
    if (
        firewall.get("docker_user_present") is not True
        or firewall.get("custom_chain_present") is not True
        or firewall.get("input_present") is not True
        or firewall.get("forward_to_docker_user_count", 0) < 1
        or firewall.get("docker_user_anchor_count") != 1
        or firewall.get("input_anchor_count") != 1
        or firewall.get("custom_rule_count") != 3
        or firewall.get("custom_rules_valid") is not True
        or firewall.get("foreign_custom_chain_references")
    ):
        raise NormalizationError("firewall_prestate_drift")


def _delete_exact_path(record: dict[str, str]) -> None:
    path = Path(record["path"])
    if path.is_symlink():
        raise NormalizationError(f"delete_path_symlink:{path}")
    if not path.exists():
        raise NormalizationError(f"delete_path_missing:{path}")
    kind = _path_kind(path)
    if kind != record["kind"]:
        raise NormalizationError(f"delete_path_kind_drift:{path}")
    if kind == "directory":
        shutil.rmtree(path)
    else:
        path.unlink()


def _remove_firewall(runner: Runner) -> None:
    runner.run(
        (
            "iptables",
            "-D",
            "INPUT",
            "-p",
            "tcp",
            "-m",
            "tcp",
            "--dport",
            str(BROKER_TLS_PORT),
            "-m",
            "comment",
            "--comment",
            ANCHOR_COMMENT,
            "-j",
            CUSTOM_CHAIN,
        )
    )
    runner.run(
        (
            "iptables",
            "-D",
            "DOCKER-USER",
            "-p",
            "tcp",
            "-m",
            "conntrack",
            "--ctdir",
            "ORIGINAL",
            "--ctorigdstport",
            str(BROKER_TLS_PORT),
            "-m",
            "comment",
            "--comment",
            ANCHOR_COMMENT,
            "-j",
            CUSTOM_CHAIN,
        )
    )
    runner.run(("iptables", "-F", CUSTOM_CHAIN))
    runner.run(("iptables", "-X", CUSTOM_CHAIN))


def _apply_mutation(runner: Runner, manifest: dict[str, Any]) -> None:
    unit = manifest["delete"]["systemd_units"][0]["name"]
    runner.run(("systemctl", "stop", unit))
    runner.run(("systemctl", "disable", unit))
    _remove_firewall(runner)
    for record in manifest["delete"]["docker_networks"]:
        runner.run(("docker", "network", "rm", record["name"]))
    for name in manifest["delete"]["docker_volumes"]:
        runner.run(("docker", "volume", "rm", name))
    for record in manifest["delete"]["product_paths"]:
        _delete_exact_path(record)
    runner.run(("systemctl", "daemon-reload"))


def _postcheck(runner: Runner, manifest: dict[str, Any]) -> dict[str, Any]:
    host = _host_report(runner)
    _validate_host(host)
    containers = tuple(
        line.strip()
        for line in runner.run(("docker", "ps", "-aq")).splitlines()
        if line.strip()
    )
    images = tuple(
        line.strip()
        for line in runner.run(("docker", "image", "ls", "-q")).splitlines()
        if line.strip()
    )
    volumes = tuple(
        line.strip()
        for line in runner.run(("docker", "volume", "ls", "-q")).splitlines()
        if line.strip()
    )
    networks = tuple(
        sorted(
            line.strip()
            for line in runner.run(
                ("docker", "network", "ls", "--format", "{{.Name}}")
            ).splitlines()
            if line.strip()
        )
    )
    if containers or images or volumes:
        raise NormalizationError("postcheck_docker_not_empty")
    if networks != tuple(sorted(DEFAULT_NETWORKS)):
        raise NormalizationError("postcheck_network_drift")
    for record in manifest["delete"]["product_paths"]:
        path = Path(record["path"])
        if path.exists() or path.is_symlink():
            raise NormalizationError(f"postcheck_product_path_present:{path}")
    for value in manifest.get("expected_absent_before_apply", []):
        path = Path(value)
        if path.exists() or path.is_symlink():
            raise NormalizationError(f"postcheck_expected_absent_path_present:{path}")
    if any(_listener_report(runner).values()):
        raise NormalizationError("postcheck_listener_present")

    firewall = _firewall_report(runner)
    if (
        firewall.get("docker_user_present") is not True
        or firewall.get("custom_chain_present") is not False
        or firewall.get("forward_to_docker_user_count", 0) < 1
        or firewall.get("docker_user_anchor_count") != 0
        or firewall.get("input_anchor_count") != 0
        or firewall.get("foreign_custom_chain_references")
    ):
        raise NormalizationError("postcheck_firewall_drift")

    unit = manifest["delete"]["systemd_units"][0]["name"]
    load_state = runner.run(
        ("systemctl", "show", "-p", "LoadState", "--value", unit),
        allowed=frozenset({0, 1}),
    ).strip()
    if load_state not in {"not-found", ""}:
        raise NormalizationError("postcheck_product_unit_present")

    return {
        "host_baseline": "PASS",
        "containers": 0,
        "images": 0,
        "volumes": 0,
        "docker_networks": list(networks),
        "product_paths_absent": True,
        "product_unit_absent": True,
        "product_firewall_absent": True,
        "production_listeners": 0,
        "docker_user_preserved": True,
        "forward_docker_user_jump_preserved": True,
    }


def _public_preflight_summary(report: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "host_baseline": "PASS",
        "container_count": len(report["docker"]["containers"]),
        "image_count": len(report["docker"]["images"]),
        "volume_count": len(report["docker"]["volumes"]),
        "volume_set_sha256": report["docker"]["volume_set_sha256"],
        "product_network_count": len(manifest["delete"]["docker_networks"]),
        "production_listener_count": sum(report["listeners"].values()),
        "firewall_owned_prestate": True,
        "trusted_subnet_sha256": report["firewall"]["trusted_subnet_sha256"],
        "raw_customer_subnet_in_output": False,
    }


def execute_preflight(manifest: dict[str, Any], runner: Runner | None = None) -> dict[str, Any]:
    active_runner = runner or Runner()
    report = _collect_preflight(active_runner, manifest)
    _validate_preflight(report, manifest)
    return _public_preflight_summary(report, manifest)


def execute_apply(
    manifest: dict[str, Any],
    authorization_id: str,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if authorization_id != AUTHORIZATION_ID:
        raise NormalizationError("authorization_id_mismatch")
    if os.geteuid() != 0:
        raise NormalizationError("root_required")
    active_runner = runner or Runner()
    execute_preflight(manifest, active_runner)
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "event": "authorization_claimed",
                "authorization_id": AUTHORIZATION_ID,
                "authorization_claimed": True,
                "authorization_consumed": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )
    try:
        _apply_mutation(active_runner, manifest)
        postcheck = _postcheck(active_runner, manifest)
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP_PARTIAL",
                    "reason": str(error),
                    "authorization_claimed": True,
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "automatic_rollback": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )
        raise
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "postcheck": postcheck,
        "production_service_start": False,
        "board_access": False,
    }


def self_check(manifest: dict[str, Any]) -> dict[str, Any]:
    _validate_manifest(manifest)
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = (
        "docker system prune",
        "docker volume prune",
        "docker network prune",
        "iptables -F DOCKER-USER",
        "iptables -X DOCKER-USER",
        "shutil.rmtree(Path('/var/lib/docker'))",
    )
    found = [value for value in forbidden if value in source]
    return {
        "schema": SCHEMA,
        "status": "PASS" if not found else "STOP",
        "forbidden_broad_destructive_operations": found,
        "volume_count": len(manifest["delete"]["docker_volumes"]),
        "volume_set_sha256": _volume_set_sha256(
            manifest["delete"]["docker_volumes"]
        ),
        "product_network_count": len(manifest["delete"]["docker_networks"]),
        "authorization_id": AUTHORIZATION_ID,
        "live_mutation_executed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--phase",
        choices=("self-check", "preflight", "apply"),
        required=True,
    )
    parser.add_argument("--authorization-id")
    return parser


def main() -> int:
    args = _parser().parse_args()
    claimed = False
    try:
        manifest = _load_manifest(args.manifest)
        if args.phase == "self-check":
            result = self_check(manifest)
        elif args.phase == "preflight":
            result = {
                "schema": SCHEMA,
                "status": "PASS",
                "phase": "preflight",
                "summary": execute_preflight(manifest),
                "authorization_claimed": False,
                "authorization_consumed": False,
                "live_mutation": False,
                "production_service_start": False,
                "board_access": False,
            }
        else:
            if not args.authorization_id:
                raise NormalizationError("authorization_id_required")
            claimed = args.authorization_id == AUTHORIZATION_ID
            result = execute_apply(manifest, args.authorization_id)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
        return 0 if result.get("status") == "PASS" else 2
    except (NormalizationError, OSError, subprocess.TimeoutExpired) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error),
                    "authorization_claimed": claimed,
                    "authorization_consumed": claimed,
                    "replay_allowed": False if claimed else None,
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
