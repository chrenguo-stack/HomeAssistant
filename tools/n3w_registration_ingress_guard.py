#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import ipaddress
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


def _load_broker_guard():
    try:
        import n3w_broker_ingress_guard as module
        return module
    except ModuleNotFoundError:
        path = Path(__file__).with_name("n3w-broker-ingress-guard")
        loader = importlib.machinery.SourceFileLoader(
            "n3w_broker_ingress_guard",
            str(path),
        )
        spec = importlib.util.spec_from_loader(
            "n3w_broker_ingress_guard",
            loader,
        )
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules["n3w_broker_ingress_guard"] = module
        spec.loader.exec_module(module)
        return module


broker_guard = _load_broker_guard()

SCHEMA = "gh.n3w-registration-ingress-guard/1"
INTERFACE = broker_guard.INTERFACE
CUSTOM_CHAIN = "N3WFC4-REGISTRATION-INGRESS"
ANCHOR_COMMENT = "n3wfc4-registration-ingress-v1"
LOCK_PATH = Path("/run/lock/n3wfc4-registration-ingress-guard.lock")
COMMAND_TIMEOUT_SECONDS = 8
PORT_RULES = (
    ("tcp", 47110),
    ("udp", 47111),
    ("tcp", 47112),
)


class RegistrationIngressGuardError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FirewallInventory:
    input_present: bool
    custom_chain_present: bool
    input_rules: tuple[str, ...]
    custom_chain_rules: tuple[str, ...]
    registration_anchor_positions: tuple[int, ...]
    ambiguous_owned_rules: tuple[str, ...]
    foreign_custom_chain_refs: tuple[str, ...]
    broker_anchor_position: int | None


def _binary(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise RegistrationIngressGuardError(f"required_binary_missing:{name}")
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
        raise RegistrationIngressGuardError(
            f"command_execution_failed:{Path(argv[0]).name}"
        ) from error
    if completed.returncode != 0:
        raise RegistrationIngressGuardError(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed.stdout


def _allow_rule(subnet: ipaddress.IPv4Network) -> str:
    return (
        f"-A {CUSTOM_CHAIN} -i {INTERFACE} -s {subnet} "
        f"-m comment --comment {ANCHOR_COMMENT} -j RETURN"
    )


def _drop_rule() -> str:
    return (
        f"-A {CUSTOM_CHAIN} -m comment --comment {ANCHOR_COMMENT} -j DROP"
    )


def _anchor_rule(protocol: str, port: int) -> str:
    return (
        f"-A INPUT -p {protocol} -m {protocol} --dport {port} "
        f"-m comment --comment {ANCHOR_COMMENT} -j {CUSTOM_CHAIN}"
    )


def _anchor_insert_argv(protocol: str, port: int, position: int) -> list[str]:
    return [
        _binary("iptables"),
        "-I",
        "INPUT",
        str(position),
        "-p",
        protocol,
        "-m",
        protocol,
        "--dport",
        str(port),
        "-m",
        "comment",
        "--comment",
        ANCHOR_COMMENT,
        "-j",
        CUSTOM_CHAIN,
    ]


def build_restore_payload(
    trusted_subnet: ipaddress.IPv4Network | None,
    *,
    create_chain: bool,
) -> str:
    lines = ["*filter"]
    if create_chain:
        lines.append(f":{CUSTOM_CHAIN} - [0:0]")
    else:
        lines.append(f"-F {CUSTOM_CHAIN}")
    if trusted_subnet is not None:
        lines.append(_allow_rule(trusted_subnet))
    lines.extend((_drop_rule(), "COMMIT", ""))
    return "\n".join(lines)


def _extract_allow_source(rule: str) -> ipaddress.IPv4Network | None:
    try:
        tokens = shlex.split(rule)
    except ValueError:
        return None
    positions = [
        index
        for index, token in enumerate(tokens[:-1])
        if token in {"-s", "--source"}
    ]
    if len(positions) != 1:
        return None
    try:
        parsed = ipaddress.ip_network(tokens[positions[0] + 1], strict=False)
    except ValueError:
        return None
    return parsed if isinstance(parsed, ipaddress.IPv4Network) else None


def _owned_chain_rules(rules: Sequence[str]) -> bool:
    if len(rules) == 1:
        return broker_guard._rule_matches(rules[0], _drop_rule())
    if len(rules) != 2:
        return False
    subnet = _extract_allow_source(rules[0])
    return (
        subnet is not None
        and broker_guard._rule_matches(rules[0], _allow_rule(subnet))
        and broker_guard._rule_matches(rules[1], _drop_rule())
    )


def parse_firewall_inventory(payload: str) -> FirewallInventory:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    input_present = any(line.startswith(":INPUT ") for line in lines)
    custom_chain_present = any(
        line.startswith(f":{CUSTOM_CHAIN} ") for line in lines
    )
    input_rules = tuple(
        line for line in lines if line.startswith("-A INPUT ")
    )
    custom_chain_rules = tuple(
        line for line in lines if line.startswith(f"-A {CUSTOM_CHAIN} ")
    )

    broker_positions = tuple(
        position
        for position, line in enumerate(input_rules, start=1)
        if broker_guard._rule_matches(
            line,
            broker_guard._input_anchor_rule(),
        )
    )
    broker_anchor_position = (
        broker_positions[0] if len(broker_positions) == 1 else None
    )

    expected_anchors = tuple(
        _anchor_rule(protocol, port)
        for protocol, port in PORT_RULES
    )
    positions: list[int] = []
    ambiguous: list[str] = []
    for position, line in enumerate(input_rules, start=1):
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = []
        if ANCHOR_COMMENT not in tokens:
            continue
        matches = [
            broker_guard._rule_matches(line, expected)
            for expected in expected_anchors
        ]
        if sum(matches) == 1:
            positions.append(position)
        else:
            ambiguous.append(line)

    foreign_refs: list[str] = []
    for line in lines:
        if not line.startswith("-A "):
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        for index, token in enumerate(tokens[:-1]):
            if token in {"-j", "--jump"} and tokens[index + 1] == CUSTOM_CHAIN:
                if not any(
                    broker_guard._rule_matches(line, expected)
                    for expected in expected_anchors
                ):
                    foreign_refs.append(line)

    return FirewallInventory(
        input_present=input_present,
        custom_chain_present=custom_chain_present,
        input_rules=input_rules,
        custom_chain_rules=custom_chain_rules,
        registration_anchor_positions=tuple(positions),
        ambiguous_owned_rules=tuple(ambiguous),
        foreign_custom_chain_refs=tuple(foreign_refs),
        broker_anchor_position=broker_anchor_position,
    )


def _validate_prestate(inventory: FirewallInventory) -> None:
    if not inventory.input_present:
        raise RegistrationIngressGuardError("input_chain_missing")
    if inventory.broker_anchor_position != 1:
        raise RegistrationIngressGuardError("broker_guard_must_be_input_rule_1")
    if inventory.custom_chain_present and not _owned_chain_rules(
        inventory.custom_chain_rules
    ):
        raise RegistrationIngressGuardError(
            "registration_chain_ownership_unproven"
        )
    if inventory.ambiguous_owned_rules:
        raise RegistrationIngressGuardError(
            "registration_anchor_semantics_ambiguous"
        )
    if inventory.foreign_custom_chain_refs:
        raise RegistrationIngressGuardError(
            "registration_chain_foreign_reference"
        )
    if inventory.registration_anchor_positions not in ((), (2, 3, 4)):
        raise RegistrationIngressGuardError(
            "registration_anchors_not_exact_2_3_4"
        )
    if inventory.registration_anchor_positions == (2, 3, 4):
        expected = tuple(
            _anchor_rule(protocol, port)
            for protocol, port in PORT_RULES
        )
        actual = inventory.input_rules[1:4]
        if len(actual) != len(expected):
            raise RegistrationIngressGuardError(
                "registration_anchor_order_invalid"
            )
        for observed, wanted in zip(actual, expected, strict=True):
            if not broker_guard._rule_matches(observed, wanted):
                raise RegistrationIngressGuardError(
                    "registration_anchor_order_invalid"
                )


def validate_applied_state(
    inventory: FirewallInventory,
    trusted_subnet: ipaddress.IPv4Network | None,
) -> None:
    _validate_prestate(inventory)
    if inventory.registration_anchor_positions != (2, 3, 4):
        raise RegistrationIngressGuardError(
            "registration_anchors_not_exact_2_3_4"
        )
    expected = (
        (_allow_rule(trusted_subnet), _drop_rule())
        if trusted_subnet is not None
        else (_drop_rule(),)
    )
    if len(inventory.custom_chain_rules) != len(expected):
        raise RegistrationIngressGuardError(
            "registration_chain_rule_count_invalid"
        )
    for actual, wanted in zip(
        inventory.custom_chain_rules,
        expected,
        strict=True,
    ):
        if not broker_guard._rule_matches(actual, wanted):
            raise RegistrationIngressGuardError(
                "registration_chain_rule_semantics_invalid"
            )


def _save_filter_table() -> str:
    return _run([_binary("iptables-save"), "-t", "filter"])


def apply_guard(
    decision: broker_guard.NetworkDecision,
) -> FirewallInventory:
    if os.geteuid() != 0:
        raise RegistrationIngressGuardError("root_required")
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        inventory = parse_firewall_inventory(_save_filter_table())
        _validate_prestate(inventory)
        _run(
            [_binary("iptables-restore"), "--noflush"],
            input_text=build_restore_payload(
                decision.trusted_subnet,
                create_chain=not inventory.custom_chain_present,
            ),
        )

        inventory = parse_firewall_inventory(_save_filter_table())
        _validate_prestate(inventory)
        if not inventory.registration_anchor_positions:
            for position, (protocol, port) in enumerate(
                PORT_RULES,
                start=2,
            ):
                _run(_anchor_insert_argv(protocol, port, position))

        final = parse_firewall_inventory(_save_filter_table())
        validate_applied_state(final, decision.trusted_subnet)
        return final


def _network_sha256(
    network: ipaddress.IPv4Network | None,
) -> str | None:
    if network is None:
        return None
    return hashlib.sha256(str(network).encode("utf-8")).hexdigest()


def _result(
    decision: broker_guard.NetworkDecision,
    *,
    applied: bool,
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": (
            "PASS"
            if decision.trusted_subnet is not None
            else "FAIL_CLOSED"
        ),
        "applied": applied,
        "interface": INTERFACE,
        "trusted_network_sha256": _network_sha256(
            decision.trusted_subnet
        ),
        "reason": decision.reason,
        "raw_customer_subnet_in_public_output": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    decision = broker_guard.read_network_decision()

    if args.dry_run:
        output.write(
            json.dumps(
                _result(decision, applied=False),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 0

    try:
        apply_guard(decision)
    except RegistrationIngressGuardError as error:
        error_output.write(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "ERROR",
                    "reason": str(error),
                    "raw_customer_subnet_in_public_output": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 3

    output.write(
        json.dumps(
            _result(decision, applied=True),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
