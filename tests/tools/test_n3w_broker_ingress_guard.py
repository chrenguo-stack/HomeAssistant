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


def test_drop_only_restore_payload_does_not_flush_global_chains() -> None:
    tool = load_tool()

    payload = tool.build_restore_payload(None)

    assert f"-F {tool.CUSTOM_CHAIN}" in payload
    assert (
        f"-A {tool.CUSTOM_CHAIN} -m comment --comment "
        f"{tool.ANCHOR_COMMENT} -j DROP"
    ) in payload
    assert "ACCEPT" not in payload
    assert "-F DOCKER-USER" not in payload
    assert "-F FORWARD" not in payload


def test_trusted_restore_payload_returns_before_terminal_drop() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")

    payload = tool.build_restore_payload(subnet)
    allow = tool._owned_allow_rule(subnet)
    drop = tool._owned_drop_rule()

    assert payload.index(allow) < payload.index(drop)
    assert "ACCEPT" not in payload


def test_inventory_recognizes_exact_anchor_and_preserves_foreign_rule() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            tool._anchor_rule(),
            "-A DOCKER-USER -s 203.0.113.0/24 -j DROP",
            tool._owned_drop_rule(),
            "COMMIT",
        ]
    )

    inventory = tool.parse_firewall_inventory(payload)

    assert inventory.anchor_positions == (1,)
    assert inventory.ambiguous_owned_rules == ()
    assert inventory.foreign_custom_chain_refs == ()
    assert inventory.docker_user_rules[1].endswith("-j DROP")


def test_inventory_rejects_same_comment_with_different_semantics() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            (
                f"-A DOCKER-USER -i eth0 -p tcp -m conntrack "
                f"--ctdir ORIGINAL --ctorigdstport 8883 -m comment "
                f"--comment {tool.ANCHOR_COMMENT} -j {tool.CUSTOM_CHAIN}"
            ),
            tool._owned_drop_rule(),
            "COMMIT",
        ]
    )

    inventory = tool.parse_firewall_inventory(payload)

    assert inventory.anchor_positions == ()
    assert len(inventory.ambiguous_owned_rules) == 1


def test_inventory_detects_foreign_custom_chain_reference() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
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


def test_validate_applied_state_accepts_trusted_chain() -> None:
    tool = load_tool()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = "\n".join(
        [
            "*filter",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            tool._anchor_rule(),
            (
                f"-A {tool.CUSTOM_CHAIN} -s {subnet} "
                f"-i {tool.INTERFACE} -m comment "
                f"--comment {tool.ANCHOR_COMMENT} -j RETURN"
            ),
            tool._owned_drop_rule(),
            "COMMIT",
        ]
    )

    inventory = tool.parse_firewall_inventory(payload)

    tool.validate_applied_state(inventory, subnet)


def test_validate_applied_state_accepts_drop_only_chain() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            tool._anchor_rule(),
            tool._owned_drop_rule(),
            "COMMIT",
        ]
    )

    inventory = tool.parse_firewall_inventory(payload)

    tool.validate_applied_state(inventory, None)


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


def test_existing_unknown_same_name_chain_is_not_owned() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            f"-A {tool.CUSTOM_CHAIN} -j DROP",
            "COMMIT",
        ]
    )
    inventory = tool.parse_firewall_inventory(payload)

    with pytest.raises(
        tool.GuardError,
        match="custom_chain_ownership_unproven",
    ):
        tool._validate_prestate(inventory)


def test_existing_owned_drop_only_chain_is_accepted() -> None:
    tool = load_tool()
    payload = "\n".join(
        [
            "*filter",
            ":DOCKER-USER - [0:0]",
            f":{tool.CUSTOM_CHAIN} - [0:0]",
            tool._owned_drop_rule(),
            "COMMIT",
        ]
    )
    inventory = tool.parse_firewall_inventory(payload)

    tool._validate_prestate(inventory)


@pytest.mark.parametrize(
    "positions",
    [(2,), (1, 3), (2, 4)],
)
def test_anchor_repair_never_deletes_by_numeric_position(
    monkeypatch,
    positions: tuple[int, ...],
) -> None:
    tool = load_tool()
    inventory = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(),
        custom_chain_rules=(tool._owned_drop_rule(),),
        anchor_positions=positions,
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
    )
    monkeypatch.setattr(
        tool,
        "_save_filter_table",
        lambda: "unused",
    )
    monkeypatch.setattr(
        tool,
        "parse_firewall_inventory",
        lambda _payload: inventory,
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        tool,
        "_run",
        lambda argv, **_kwargs: calls.append(list(argv)) or "",
    )

    with pytest.raises(
        tool.GuardError,
        match="owned_anchor_not_unique_first",
    ):
        tool._ensure_single_first_anchor()

    assert calls == []


def test_missing_anchor_is_inserted_once_and_verified(monkeypatch) -> None:
    tool = load_tool()
    before = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(),
        custom_chain_rules=(tool._owned_drop_rule(),),
        anchor_positions=(),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
    )
    after = tool.FirewallInventory(
        docker_user_present=True,
        custom_chain_present=True,
        docker_user_rules=(tool._anchor_rule(),),
        custom_chain_rules=(tool._owned_drop_rule(),),
        anchor_positions=(1,),
        ambiguous_owned_rules=(),
        foreign_custom_chain_refs=(),
    )
    inventories = iter((before, after))
    monkeypatch.setattr(
        tool,
        "_save_filter_table",
        lambda: "unused",
    )
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
