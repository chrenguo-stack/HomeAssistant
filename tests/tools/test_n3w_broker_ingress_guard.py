from __future__ import annotations

import importlib.util
import io
import ipaddress
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_ingress_guard.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_ingress_guard",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def firewall_payload(
    tool,
    *,
    trusted_subnet: ipaddress.IPv4Network | None,
    r5: bool,
    docker_anchor: bool = True,
    input_anchor: bool = True,
    foreign_input_rule: str | None = None,
    foreign_docker_rule: str | None = None,
) -> str:
    lines = [
        "*filter",
        ":INPUT ACCEPT [0:0]",
        ":DOCKER-USER - [0:0]",
        f":{tool.CUSTOM_CHAIN} - [0:0]",
    ]
    if input_anchor:
        lines.append(tool._input_anchor_rule())
    if foreign_input_rule is not None:
        lines.append(foreign_input_rule)
    if docker_anchor:
        lines.append(tool._anchor_rule())
    if foreign_docker_rule is not None:
        lines.append(foreign_docker_rule)
    if r5:
        lines.append(tool._owned_loopback_rule())
    if trusted_subnet is not None:
        lines.append(tool._owned_allow_rule(trusted_subnet))
    lines.extend([tool._owned_drop_rule(), "COMMIT"])
    return "\n".join(lines)


def test_unique_ipv4_subnet_is_trusted() -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=True,
        raw_addresses=["192.0.2.23/24"],
    )
    assert decision.trusted_subnet == ipaddress.ip_network("192.0.2.0/24")
    assert decision.candidate_network_count == 1
    assert decision.reason == "unique_ipv4_subnet"


def test_multiple_addresses_in_same_subnet_are_trusted() -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=True,
        raw_addresses=["192.0.2.23/24", "192.0.2.24/24"],
    )
    assert decision.trusted_subnet == ipaddress.ip_network("192.0.2.0/24")
    assert decision.candidate_network_count == 1


def test_disconnected_interface_fails_closed() -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=False,
        raw_addresses=["192.0.2.23/24"],
    )
    assert decision.trusted_subnet is None
    assert decision.reason == "interface_not_connected"


def test_no_ipv4_address_fails_closed() -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=True,
        raw_addresses=[],
    )
    assert decision.trusted_subnet is None
    assert decision.reason == "no_ipv4_address"


def test_two_different_subnets_fail_closed() -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=True,
        raw_addresses=["192.0.2.23/24", "198.51.100.23/24"],
    )
    assert decision.trusted_subnet is None
    assert decision.candidate_network_count == 2
    assert decision.reason == "ambiguous_ipv4_subnet"


@pytest.mark.parametrize(
    "address",
    [
        "not-an-address",
        "169.254.10.2/16",
        "127.0.0.1/8",
        "0.0.0.0/24",
        "224.0.0.1/24",
        "192.0.2.23/0",
        "2001:db8::10/64",
    ],
)
def test_invalid_ipv4_state_fails_closed(address: str) -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=True,
        raw_addresses=[address],
    )
    assert decision.trusted_subnet is None
    assert decision.reason == "invalid_ipv4_state"


def test_global_ipv4_subnet_is_not_hardcoded_out() -> None:
    tool = load_tool()
    decision = tool.decide_trusted_subnet(
        connected=True,
        raw_addresses=["8.8.8.8/24"],
    )
    assert decision.trusted_subnet == ipaddress.ip_network("8.8.8.0/24")


def test_fail_closed_payload_keeps_loopback_then_drop() -> None:
    tool = load_tool()
    payload = tool.build_restore_payload(None)
    loopback = tool._owned_loopback_rule()
    drop = tool._owned_drop_rule()
    assert payload.index(loopback) < payload.index(drop)
    assert "ACCEPT" not in payload
    assert "-F INPUT" not in payload
    assert "-F DOCKER-USER" not in payload
    assert "-F FORWARD" not in payload


def test_trusted_payload_order_is_loopback_trusted_drop() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = tool.build_restore_payload(subnet)
    loopback = tool._owned_loopback_rule()
    allow = tool._owned_allow_rule(subnet)
    drop = tool._owned_drop_rule()
    assert payload.index(loopback) < payload.index(allow) < payload.index(drop)


def test_first_install_restore_payload_creates_owned_chain_only() -> None:
    tool = load_tool()
    payload = tool.build_restore_payload(None, create_chain=True)
    assert f":{tool.CUSTOM_CHAIN} - [0:0]" in payload
    assert f"-F {tool.CUSTOM_CHAIN}" not in payload
    assert "-F INPUT" not in payload
    assert "-F DOCKER-USER" not in payload
    assert tool._owned_loopback_rule() in payload
    assert tool._owned_drop_rule() in payload


def test_existing_chain_refresh_only_flushes_owned_chain() -> None:
    tool = load_tool()
    payload = tool.build_restore_payload(None)
    assert f"-F {tool.CUSTOM_CHAIN}" in payload
    assert "-F INPUT" not in payload
    assert "-F DOCKER-USER" not in payload
    assert "-F FORWARD" not in payload


def test_first_install_uses_one_restore_transaction(monkeypatch) -> None:
    tool = load_tool()
    inventory = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=False,
        docker_user_rules=(),
        custom_chain_rules=(),
        anchor_positions=(),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
        input_present=True,
    )
    calls: list[tuple[list[str], str | None]] = []
    monkeypatch.setattr(tool, "_binary", lambda name: name)
    monkeypatch.setattr(
        tool,
        "_run",
        lambda argv, **kwargs: calls.append(
            (list(argv), kwargs.get("input_text"))
        ) or "",
    )
    tool._apply_custom_chain_transaction(inventory, None)
    assert len(calls) == 1
    argv, payload = calls[0]
    assert argv == ["iptables-restore", "--noflush"]
    assert payload is not None
    assert f":{tool.CUSTOM_CHAIN} - [0:0]" in payload


def test_inventory_recognizes_both_exact_anchors_and_preserves_foreign_rules() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=True,
        foreign_input_rule="-A INPUT -p icmp -j ACCEPT",
        foreign_docker_rule="-A DOCKER-USER -s 203.0.113.0/24 -j DROP",
    )
    inventory = tool.parse_firewall_inventory(payload)
    assert inventory.anchor_positions == (1,)
    assert inventory.input_anchor_positions == (1,)
    assert inventory.ambiguous_owned_rules == ()
    assert inventory.ambiguous_owned_input_rules == ()
    assert inventory.foreign_custom_chain_refs == ()
    assert inventory.input_rules[1] == "-A INPUT -p icmp -j ACCEPT"
    assert inventory.docker_user_rules[1].endswith("-j DROP")


def test_input_anchor_requires_exact_tcp_8883_semantics() -> None:
    tool = load_tool()
    assert tool._is_exact_input_anchor(tool._input_anchor_rule())
    wrong = tool._input_anchor_rule().replace("--dport 8883", "--dport 1883")
    assert not tool._is_exact_input_anchor(wrong)


def test_docker_anchor_rejects_swapped_option_values() -> None:
    tool = load_tool()
    swapped = (
        "-A DOCKER-USER -p tcp -m conntrack "
        "--ctdir ORIGINAL --ctorigdstport 8883 -m comment "
        f"--comment {tool.CUSTOM_CHAIN} "
        f"-j {tool.ANCHOR_COMMENT}"
    )
    assert tool._is_exact_anchor(swapped) is False


def test_rule_match_accepts_option_reordering_but_preserves_pairs() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    reordered = (
        f"-A {tool.CUSTOM_CHAIN} -s {subnet} "
        f"-i {tool.INTERFACE} -m comment "
        f"--comment {tool.ANCHOR_COMMENT} -j RETURN"
    )
    assert tool._rule_matches(reordered, tool._owned_allow_rule(subnet))


def test_inventory_rejects_same_comment_wrong_input_semantics() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    wrong_input = (
        f"-A INPUT -p tcp -m tcp --dport 1883 -m comment "
        f"--comment {tool.ANCHOR_COMMENT} -j {tool.CUSTOM_CHAIN}"
    )
    payload = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=True,
        input_anchor=False,
        foreign_input_rule=wrong_input,
    )
    inventory = tool.parse_firewall_inventory(payload)
    assert inventory.input_anchor_positions == ()
    assert len(inventory.ambiguous_owned_input_rules) == 1
    with pytest.raises(
        tool.GuardError,
        match="owned_input_anchor_semantics_ambiguous",
    ):
        tool._validate_prestate(inventory)


def test_inventory_detects_foreign_custom_chain_reference() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
            ":INPUT ACCEPT [0:0]",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            f"-A FORWARD -j {tool.CUSTOM_CHAIN}",
            tool._owned_drop_rule(),
            "COMMIT",
        ]
    )
    inventory = tool.parse_firewall_inventory(payload)
    assert inventory.foreign_custom_chain_refs == (
        f"-A FORWARD -j {tool.CUSTOM_CHAIN}",
    )


def test_r4_trusted_prestate_is_accepted_for_migration() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=False,
        input_anchor=False,
    )
    inventory = tool.parse_firewall_inventory(payload)
    tool._validate_prestate(inventory)
    assert tool._r4_owned_custom_chain_rules(inventory.custom_chain_rules)
    assert not tool._r5_owned_custom_chain_rules(inventory.custom_chain_rules)


def test_r4_drop_only_prestate_is_accepted_for_migration() -> None:
    tool = load_tool()
    payload = firewall_payload(
        tool,
        trusted_subnet=None,
        r5=False,
        input_anchor=False,
    )
    inventory = tool.parse_firewall_inventory(payload)
    tool._validate_prestate(inventory)
    assert tool._r4_owned_custom_chain_rules(inventory.custom_chain_rules)


def test_r5_trusted_prestate_is_accepted() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=True,
    )
    inventory = tool.parse_firewall_inventory(payload)
    tool._validate_prestate(inventory)
    assert tool._r5_owned_custom_chain_rules(inventory.custom_chain_rules)


def test_validate_applied_state_accepts_r5_trusted_chain() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    inventory = tool.parse_firewall_inventory(
        firewall_payload(tool, trusted_subnet=subnet, r5=True)
    )
    tool.validate_applied_state(inventory, subnet)


def test_validate_applied_state_accepts_loopback_only_fail_closed_chain() -> None:
    tool = load_tool()
    inventory = tool.parse_firewall_inventory(
        firewall_payload(tool, trusted_subnet=None, r5=True)
    )
    tool.validate_applied_state(inventory, None)


def test_validate_applied_state_rejects_r4_chain() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    inventory = tool.parse_firewall_inventory(
        firewall_payload(
            tool,
            trusted_subnet=subnet,
            r5=False,
            input_anchor=False,
        )
    )
    with pytest.raises(tool.GuardError):
        tool.validate_applied_state(inventory, subnet)


@pytest.mark.parametrize(
    ("docker_positions", "input_positions", "reason"),
    [
        ((2,), (), "owned_anchor_not_unique_first"),
        ((1, 3), (), "owned_anchor_not_unique_first"),
        ((1,), (2,), "owned_input_anchor_not_unique_first"),
        ((1,), (1, 3), "owned_input_anchor_not_unique_first"),
    ],
)
def test_wrong_or_duplicate_anchor_position_fails_closed(
    docker_positions: tuple[int, ...],
    input_positions: tuple[int, ...],
    reason: str,
) -> None:
    tool = load_tool()
    inventory = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(),
        custom_chain_rules=(
            tool._owned_loopback_rule(),
            tool._owned_drop_rule(),
        ),
        anchor_positions=docker_positions,
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
        input_present=True,
        input_anchor_positions=input_positions,
    )
    with pytest.raises(tool.GuardError, match=reason):
        tool._validate_prestate(inventory)


def test_missing_docker_anchor_is_inserted_once_and_verified(monkeypatch) -> None:
    tool = load_tool()
    before = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(),
        custom_chain_rules=(
            tool._owned_loopback_rule(),
            tool._owned_drop_rule(),
        ),
        anchor_positions=(),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
        input_present=True,
    )
    after = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(tool._anchor_rule(),),
        custom_chain_rules=(
            tool._owned_loopback_rule(),
            tool._owned_drop_rule(),
        ),
        anchor_positions=(1,),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
        input_present=True,
    )
    inventories = iter((before, after))
    monkeypatch.setattr(tool, "_save_filter_table", lambda: "unused")
    monkeypatch.setattr(
        tool,
        "parse_firewall_inventory",
        lambda _payload: next(inventories),
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        tool,
        "_anchor_insert_argv",
        lambda: ["iptables", "-I", "DOCKER-USER", "1"],
    )
    monkeypatch.setattr(
        tool,
        "_run",
        lambda argv, **_kwargs: calls.append(list(argv)) or "",
    )
    tool._ensure_single_first_anchor()
    assert calls == [["iptables", "-I", "DOCKER-USER", "1"]]


def test_missing_input_anchor_is_inserted_once_and_verified(monkeypatch) -> None:
    tool = load_tool()
    before = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(tool._anchor_rule(),),
        custom_chain_rules=(
            tool._owned_loopback_rule(),
            tool._owned_drop_rule(),
        ),
        anchor_positions=(1,),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
        input_present=True,
        input_anchor_positions=(),
    )
    after = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(tool._anchor_rule(),),
        custom_chain_rules=(
            tool._owned_loopback_rule(),
            tool._owned_drop_rule(),
        ),
        anchor_positions=(1,),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
        input_present=True,
        input_rules=(tool._input_anchor_rule(),),
        input_anchor_positions=(1,),
    )
    inventories = iter((before, after))
    monkeypatch.setattr(tool, "_save_filter_table", lambda: "unused")
    monkeypatch.setattr(
        tool,
        "parse_firewall_inventory",
        lambda _payload: next(inventories),
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        tool,
        "_input_anchor_insert_argv",
        lambda: ["iptables", "-I", "INPUT", "1"],
    )
    monkeypatch.setattr(
        tool,
        "_run",
        lambda argv, **_kwargs: calls.append(list(argv)) or "",
    )
    tool._ensure_single_first_input_anchor()
    assert calls == [["iptables", "-I", "INPUT", "1"]]


def test_apply_migrates_chain_before_input_anchor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    r4 = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=False,
        input_anchor=False,
    )
    r5_without_input = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=True,
        input_anchor=False,
    )
    r5_final = firewall_payload(
        tool,
        trusted_subnet=subnet,
        r5=True,
    )
    payloads = iter((r4, r5_without_input, r5_final))
    events: list[str] = []

    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(tool, "LOCK_PATH", tmp_path / "guard.lock")
    monkeypatch.setattr(tool, "_save_filter_table", lambda: next(payloads))
    monkeypatch.setattr(
        tool,
        "_apply_custom_chain_transaction",
        lambda _inventory, _subnet: events.append("chain"),
    )
    monkeypatch.setattr(
        tool,
        "_ensure_single_first_anchor",
        lambda: events.append("docker"),
    )
    monkeypatch.setattr(
        tool,
        "_ensure_single_first_input_anchor",
        lambda: events.append("input"),
    )

    inventory = tool.apply_guard(
        tool.NetworkDecision(subnet, 1, "unique_ipv4_subnet")
    )

    assert events == ["chain", "docker", "input"]
    assert inventory.input_anchor_positions == (1,)


def test_dry_run_output_does_not_expose_raw_subnet(monkeypatch) -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    monkeypatch.setattr(
        tool,
        "read_network_decision",
        lambda: tool.NetworkDecision(subnet, 1, "unique_ipv4_subnet"),
    )
    output = io.StringIO()
    status = tool.main(["--dry-run"], stdout=output)
    result = json.loads(output.getvalue())
    assert status == 0
    assert result["status"] == "PASS"
    assert result["applied"] is False
    assert result["raw_customer_subnet_in_public_output"] is False
    assert str(subnet) not in output.getvalue()


def test_apply_failure_is_structured_and_secret_free(monkeypatch) -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    monkeypatch.setattr(
        tool,
        "read_network_decision",
        lambda: tool.NetworkDecision(subnet, 1, "unique_ipv4_subnet"),
    )

    def fail(_decision):
        raise tool.GuardError("synthetic_failure")

    monkeypatch.setattr(tool, "apply_guard", fail)
    error = io.StringIO()
    status = tool.main(["--apply"], stderr=error)
    result = json.loads(error.getvalue())
    assert status == 3
    assert result["status"] == "ERROR"
    assert result["reason"] == "synthetic_failure"
    assert result["raw_customer_subnet_in_public_output"] is False
    assert str(subnet) not in error.getvalue()
