#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

SCHEMA = "gh.n3w-broker-ingress-guard/1"
INTERFACE = "eth0"
BROKER_TLS_PORT = 8883
CUSTOM_CHAIN = "N3WFC4-BROKER-INGRESS"
ANCHOR_COMMENT = "n3wfc4-broker-ingress-v1"
LOCK_PATH = Path("/run/lock/n3wfc4-broker-ingress-guard.lock")
COMMAND_TIMEOUT_SECONDS = 8


class GuardError(RuntimeError):
    pass


class CommandError(GuardError):
    pass


@dataclass(frozen=True)
class NetworkDecision:
    trusted_subnet: ipaddress.IPv4Network | None
    candidate_network_count: int
    reason: str


@dataclass(frozen=True)
class FirewallInventory:
    docker_user_present: bool
    custom_chain_present: bool
    docker_user_rules: tuple[str, ...]
    custom_chain_rules: tuple[str, ...]
    anchor_positions: tuple[int, ...]
    ambiguous_owned_rules: tuple[str, ...]
    foreign_custom_chain_refs: tuple[str, ...]


def _binary(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise CommandError(f"required_binary_missing:{name}")
    return value


def _run(
    argv: Sequence[str],
    *,
    input_text: str | None = None,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
) -> str:
    try:
        completed = subprocess.run(
            list(argv),
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CommandError(f"command_execution_failed:{Path(argv[0]).name}") from error
    if completed.returncode != 0:
        raise CommandError(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed.stdout


def decide_trusted_subnet(
    *,
    connected: bool,
    raw_addresses: Sequence[str],
) -> NetworkDecision:
    if not connected:
        return NetworkDecision(None, 0, "interface_not_connected")

    networks: set[ipaddress.IPv4Network] = set()
    nonempty = [value.strip() for value in raw_addresses if value.strip()]
    if not nonempty:
        return NetworkDecision(None, 0, "no_ipv4_address")

    for value in nonempty:
        try:
            interface = ipaddress.ip_interface(value)
        except ValueError:
            return NetworkDecision(None, len(networks), "invalid_ipv4_state")
        if not isinstance(interface, ipaddress.IPv4Interface):
            return NetworkDecision(None, len(networks), "invalid_ipv4_state")
        address = interface.ip
        network = interface.network
        if (
            address.is_unspecified
            or address.is_loopback
            or address.is_multicast
            or address.is_link_local
            or network.prefixlen == 0
        ):
            return NetworkDecision(None, len(networks), "invalid_ipv4_state")
        networks.add(network)

    if len(networks) != 1:
        reason = "ambiguous_ipv4_subnet" if networks else "no_ipv4_address"
        return NetworkDecision(None, len(networks), reason)

    return NetworkDecision(next(iter(networks)), 1, "unique_ipv4_subnet")


def read_network_decision() -> NetworkDecision:
    try:
        state_output = _run(
            [
                _binary("nmcli"),
                "-t",
                "-f",
                "GENERAL.STATE",
                "device",
                "show",
                INTERFACE,
            ]
        )
        match = re.search(r"GENERAL\.STATE:(\d+)", state_output)
        connected = match is not None and int(match.group(1)) == 100
        address_output = _run(
            [
                _binary("nmcli"),
                "-g",
                "IP4.ADDRESS",
                "device",
                "show",
                INTERFACE,
            ]
        )
    except CommandError:
        return NetworkDecision(None, 0, "networkmanager_query_failed")

    return decide_trusted_subnet(
        connected=connected,
        raw_addresses=address_output.splitlines(),
    )


def _owned_allow_rule(trusted_subnet: ipaddress.IPv4Network) -> str:
    return (
        f"-A {CUSTOM_CHAIN} -i {INTERFACE} -s {trusted_subnet} "
        f"-m comment --comment {ANCHOR_COMMENT} -j RETURN"
    )


def _owned_drop_rule() -> str:
    return (
        f"-A {CUSTOM_CHAIN} -m comment --comment {ANCHOR_COMMENT} -j DROP"
    )


def build_restore_payload(
    trusted_subnet: ipaddress.IPv4Network | None,
    *,
    create_chain: bool = False,
) -> str:
    lines = ["*filter"]
    if create_chain:
        lines.append(f":{CUSTOM_CHAIN} - [0:0]")
    else:
        lines.append(f"-F {CUSTOM_CHAIN}")
    if trusted_subnet is not None:
        lines.append(_owned_allow_rule(trusted_subnet))
    lines.extend(
        [
            _owned_drop_rule(),
            "COMMIT",
            "",
        ]
    )
    return "\n".join(lines)


def _anchor_rule() -> str:
    return (
        f"-A DOCKER-USER -p tcp -m conntrack --ctdir ORIGINAL "
        f"--ctorigdstport {BROKER_TLS_PORT} -m comment "
        f"--comment {ANCHOR_COMMENT} -j {CUSTOM_CHAIN}"
    )


def _anchor_insert_argv() -> list[str]:
    return [
        _binary("iptables"),
        "-I",
        "DOCKER-USER",
        "1",
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
    ]


def _parse_rule_semantics(
    line: str,
) -> tuple[str, Counter[tuple[str, str]]] | None:
    try:
        tokens = shlex.split(line)
    except ValueError:
        return None
    if len(tokens) < 2 or tokens[0] != "-A":
        return None

    aliases = {
        "-p": "protocol",
        "--protocol": "protocol",
        "-m": "match",
        "--match": "match",
        "--ctdir": "ctdir",
        "--ctorigdstport": "ctorigdstport",
        "-i": "in_interface",
        "--in-interface": "in_interface",
        "-s": "source",
        "--source": "source",
        "--comment": "comment",
        "-j": "jump",
        "--jump": "jump",
    }

    semantics: Counter[tuple[str, str]] = Counter()
    index = 2
    while index < len(tokens):
        token = tokens[index]
        key = aliases.get(token)
        if key is None or index + 1 >= len(tokens):
            return None
        value = tokens[index + 1]
        if key == "source":
            try:
                source = ipaddress.ip_network(value, strict=False)
            except ValueError:
                return None
            if not isinstance(source, ipaddress.IPv4Network):
                return None
            value = str(source)
        semantics[(key, value)] += 1
        index += 2

    return tokens[1], semantics


def _rule_matches(line: str, expected: str) -> bool:
    actual_semantics = _parse_rule_semantics(line)
    expected_semantics = _parse_rule_semantics(expected)
    return (
        actual_semantics is not None
        and expected_semantics is not None
        and actual_semantics == expected_semantics
    )


def _is_exact_anchor(line: str) -> bool:
    return _rule_matches(line, _anchor_rule())


def _owned_custom_chain_rules(
    rules: Sequence[str],
) -> bool:
    if len(rules) == 1:
        return _rule_matches(rules[0], _owned_drop_rule())
    if len(rules) != 2:
        return False

    tokens = shlex.split(rules[0])
    source_indexes = [
        index
        for index, token in enumerate(tokens[:-1])
        if token in {"-s", "--source"}
    ]
    if len(source_indexes) != 1:
        return False

    try:
        source = ipaddress.ip_network(
            tokens[source_indexes[0] + 1],
            strict=False,
        )
    except ValueError:
        return False
    if not isinstance(source, ipaddress.IPv4Network):
        return False

    return (
        _rule_matches(rules[0], _owned_allow_rule(source))
        and _rule_matches(rules[1], _owned_drop_rule())
    )


def parse_firewall_inventory(payload: str) -> FirewallInventory:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    docker_user_present = any(
        line.startswith(":DOCKER-USER ") for line in lines
    )
    custom_chain_present = any(
        line.startswith(f":{CUSTOM_CHAIN} ") for line in lines
    )
    docker_user_rules = tuple(
        line for line in lines if line.startswith("-A DOCKER-USER ")
    )
    custom_chain_rules = tuple(
        line for line in lines if line.startswith(f"-A {CUSTOM_CHAIN} ")
    )

    anchor_positions: list[int] = []
    ambiguous_owned_rules: list[str] = []
    for position, line in enumerate(docker_user_rules, start=1):
        tokens = shlex.split(line)
        if ANCHOR_COMMENT not in tokens:
            continue
        if _is_exact_anchor(line):
            anchor_positions.append(position)
        else:
            ambiguous_owned_rules.append(line)

    foreign_custom_chain_refs: list[str] = []
    for line in lines:
        if not line.startswith("-A "):
            continue
        tokens = shlex.split(line)
        for index, token in enumerate(tokens[:-1]):
            if token in {"-j", "--jump"} and tokens[index + 1] == CUSTOM_CHAIN:
                if not _is_exact_anchor(line):
                    foreign_custom_chain_refs.append(line)

    return FirewallInventory(
        docker_user_present=docker_user_present,
        custom_chain_present=custom_chain_present,
        docker_user_rules=docker_user_rules,
        custom_chain_rules=custom_chain_rules,
        anchor_positions=tuple(anchor_positions),
        ambiguous_owned_rules=tuple(ambiguous_owned_rules),
        foreign_custom_chain_refs=tuple(foreign_custom_chain_refs),
    )


def _save_filter_table() -> str:
    return _run([_binary("iptables-save"), "-t", "filter"])


def _validate_prestate(inventory: FirewallInventory) -> None:
    if not inventory.docker_user_present:
        raise GuardError("docker_user_chain_missing")
    if inventory.custom_chain_present and not _owned_custom_chain_rules(
        inventory.custom_chain_rules
    ):
        raise GuardError("custom_chain_ownership_unproven")
    if inventory.ambiguous_owned_rules:
        raise GuardError("owned_anchor_semantics_ambiguous")
    if inventory.foreign_custom_chain_refs:
        raise GuardError("custom_chain_foreign_reference")


def validate_applied_state(
    inventory: FirewallInventory,
    trusted_subnet: ipaddress.IPv4Network | None,
) -> None:
    if inventory.anchor_positions != (1,):
        raise GuardError("owned_anchor_not_unique_first")
    if not inventory.custom_chain_present:
        raise GuardError("custom_chain_missing")

    expected_drop = _owned_drop_rule()
    if trusted_subnet is None:
        expected_rules = (expected_drop,)
    else:
        expected_rules = (
            _owned_allow_rule(trusted_subnet),
            expected_drop,
        )

    if len(inventory.custom_chain_rules) != len(expected_rules):
        raise GuardError("custom_chain_rule_count_invalid")
    for actual, expected in zip(
        inventory.custom_chain_rules,
        expected_rules,
        strict=True,
    ):
        if not _rule_matches(actual, expected):
            raise GuardError("custom_chain_rule_semantics_invalid")


def _apply_custom_chain_transaction(
    inventory: FirewallInventory,
    trusted_subnet: ipaddress.IPv4Network | None,
) -> None:
    _run(
        [_binary("iptables-restore"), "--noflush"],
        input_text=build_restore_payload(
            trusted_subnet,
            create_chain=not inventory.custom_chain_present,
        ),
    )


def _ensure_single_first_anchor() -> None:
    inventory = parse_firewall_inventory(_save_filter_table())
    _validate_prestate(inventory)
    if inventory.anchor_positions == (1,):
        return
    if inventory.anchor_positions:
        raise GuardError("owned_anchor_not_unique_first")

    _run(_anchor_insert_argv())
    inventory = parse_firewall_inventory(_save_filter_table())
    _validate_prestate(inventory)
    if inventory.anchor_positions != (1,):
        raise GuardError("owned_anchor_insert_verification_failed")


def _network_sha256(network: ipaddress.IPv4Network | None) -> str | None:
    if network is None:
        return None
    return hashlib.sha256(str(network).encode("utf-8")).hexdigest()


def _result(
    decision: NetworkDecision,
    inventory: FirewallInventory | None,
    *,
    applied: bool,
) -> dict[str, object]:
    trusted = decision.trusted_subnet
    status = "PASS" if trusted is not None else "FAIL_CLOSED"
    return {
        "schema": SCHEMA,
        "status": status,
        "applied": applied,
        "interface": INTERFACE,
        "candidate_network_count": decision.candidate_network_count,
        "trusted_network_prefix_length": (
            trusted.prefixlen if trusted is not None else None
        ),
        "trusted_network_sha256": _network_sha256(trusted),
        "anchor_count": (
            len(inventory.anchor_positions) if inventory is not None else None
        ),
        "anchor_position": (
            inventory.anchor_positions[0]
            if inventory is not None and inventory.anchor_positions
            else None
        ),
        "rule_generation": hashlib.sha256(
            build_restore_payload(trusted).encode("utf-8")
        ).hexdigest(),
        "reason": decision.reason,
        "raw_customer_subnet_in_public_output": False,
    }


def apply_guard(decision: NetworkDecision) -> FirewallInventory:
    if os.geteuid() != 0:
        raise GuardError("root_required")

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        inventory = parse_firewall_inventory(_save_filter_table())
        _validate_prestate(inventory)
        _apply_custom_chain_transaction(
            inventory,
            decision.trusted_subnet,
        )
        _ensure_single_first_anchor()

        final_inventory = parse_firewall_inventory(_save_filter_table())
        _validate_prestate(final_inventory)
        validate_applied_state(final_inventory, decision.trusted_subnet)
        return final_inventory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = _parser().parse_args(argv)
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    decision = read_network_decision()

    if args.dry_run:
        json.dump(_result(decision, None, applied=False), output, separators=(",", ":"))
        output.write("\n")
        return 0

    try:
        inventory = apply_guard(decision)
    except GuardError as error:
        json.dump(
            {
                "schema": SCHEMA,
                "status": "ERROR",
                "reason": str(error),
                "raw_customer_subnet_in_public_output": False,
            },
            error_output,
            separators=(",", ":"),
        )
        error_output.write("\n")
        return 3

    json.dump(
        _result(decision, inventory, applied=True),
        output,
        separators=(",", ":"),
    )
    output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
