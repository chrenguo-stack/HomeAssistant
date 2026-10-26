from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import ipaddress
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
INFRA = ROOT / "infra/n3w-t1"


def _load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_modules():
    broker = _load(
        "n3w_broker_ingress_guard",
        TOOLS / "n3w_broker_ingress_guard.py",
    )
    registration = _load(
        "n3w_registration_ingress_guard",
        TOOLS / "n3w_registration_ingress_guard.py",
    )
    return broker, registration


def _payload(
    broker,
    registration,
    *,
    subnet: ipaddress.IPv4Network | None,
    anchors: bool,
) -> str:
    lines = [
        "*filter",
        ":INPUT ACCEPT [0:0]",
        ":DOCKER-USER - [0:0]",
        f":{broker.CUSTOM_CHAIN} - [0:0]",
        broker._input_anchor_rule(),
    ]
    if anchors:
        lines.extend(
            registration._anchor_rule(protocol, port)
            for protocol, port in registration.PORT_RULES
        )
    lines.append(
        f":{registration.CUSTOM_CHAIN} - [0:0]"
    )
    if subnet is not None:
        lines.append(registration._allow_rule(subnet))
    lines.extend(
        (
            registration._drop_rule(),
            "COMMIT",
            "",
        )
    )
    return "\n".join(lines)


def test_registration_guard_requires_broker_anchor_first() -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    inventory = registration.parse_firewall_inventory(
        _payload(
            broker,
            registration,
            subnet=subnet,
            anchors=False,
        )
    )
    registration._validate_prestate(inventory)
    assert inventory.broker_anchor_position == 1
    assert inventory.registration_anchor_positions == ()


def test_registration_guard_applied_order_is_exact_2_3_4() -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    inventory = registration.parse_firewall_inventory(
        _payload(
            broker,
            registration,
            subnet=subnet,
            anchors=True,
        )
    )
    registration.validate_applied_state(inventory, subnet)
    assert inventory.registration_anchor_positions == (2, 3, 4)


def test_registration_guard_rejects_partial_anchor_state() -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = _payload(
        broker,
        registration,
        subnet=subnet,
        anchors=True,
    )
    payload = payload.replace(
        registration._anchor_rule("udp", 47111) + "\n",
        "",
    )
    inventory = registration.parse_firewall_inventory(payload)
    with pytest.raises(
        registration.RegistrationIngressGuardError,
        match="registration_anchors_not_exact_2_3_4",
    ):
        registration._validate_prestate(inventory)


def test_registration_chain_has_no_loopback_exception() -> None:
    _, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = registration.build_restore_payload(
        subnet,
        create_chain=True,
    )
    assert "-i eth0" in payload
    assert "192.0.2.0/24" in payload
    assert "127.0.0.0/8" not in payload
    assert " lo " not in payload
    assert payload.index("RETURN") < payload.index("DROP")


def test_registration_guard_public_output_hides_raw_subnet(monkeypatch) -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    monkeypatch.setattr(
        broker,
        "read_network_decision",
        lambda: broker.NetworkDecision(
            subnet,
            1,
            "unique_ipv4_subnet",
        ),
    )
    output = io.StringIO()
    status = registration.main(["--dry-run"], stdout=output)
    document = json.loads(output.getvalue())
    assert status == 0
    assert document["status"] == "PASS"
    assert document["raw_customer_subnet_in_public_output"] is False
    assert str(subnet) not in output.getvalue()


def test_systemd_and_dispatcher_order_registration_guard_before_services() -> None:
    unit = (
        INFRA
        / "systemd/n3wfc4-registration-ingress-guard.service"
    ).read_text(encoding="utf-8")
    services = (
        INFRA
        / "systemd/n3wfc4-services-activation.service"
    ).read_text(encoding="utf-8")
    dispatcher = (
        INFRA
        / "NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard"
    ).read_text(encoding="utf-8")

    assert "Requires=n3wfc4-broker-ingress-guard.service" in unit
    assert "ExecStartPre=/usr/local/sbin/n3w-trusted-product-lan-authority --invalidate" in unit
    assert "ExecStart=/usr/local/sbin/n3w-registration-ingress-guard --apply" in unit
    assert "ExecStartPost=/usr/local/sbin/n3w-trusted-product-lan-authority --apply" in unit
    assert "n3wfc4-registration-ingress-guard.service" in services
    assert dispatcher.index(
        "n3wfc4-broker-ingress-guard.service"
    ) < dispatcher.index(
        "n3wfc4-registration-ingress-guard.service"
    )


@pytest.mark.parametrize(
    "compose_name",
    (
        "production/docker-compose.yml",
        "production/docker-compose.fresh.yml",
    ),
)
def test_manager_mounts_trusted_lan_directory_read_only(compose_name: str) -> None:
    compose = (INFRA / compose_name).read_text(encoding="utf-8")
    assert "source: /run/n3wfc4-trusted-lan" in compose
    assert "target: /run/n3w/trusted-product-lan" in compose
    block = compose.split("source: /run/n3wfc4-trusted-lan", 1)[1]
    assert "read_only: true" in block.split("- type: bind", 1)[0]


def test_registration_guard_rejects_duplicate_rule_false_pass() -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    first = registration._anchor_rule("tcp", 47110)
    lines = [
        "*filter",
        ":INPUT ACCEPT [0:0]",
        ":DOCKER-USER - [0:0]",
        f":{broker.CUSTOM_CHAIN} - [0:0]",
        f":{registration.CUSTOM_CHAIN} - [0:0]",
        broker._input_anchor_rule(),
        first,
        first,
        first,
        registration._allow_rule(subnet),
        registration._drop_rule(),
        "COMMIT",
        "",
    ]
    inventory = registration.parse_firewall_inventory("\n".join(lines))
    with pytest.raises(
        registration.RegistrationIngressGuardError,
        match="registration_anchor_order_invalid",
    ):
        registration._validate_prestate(inventory)


def test_installed_registration_guard_loads_extensionless_broker_guard(
    tmp_path: Path,
) -> None:
    installed_broker = tmp_path / "n3w-broker-ingress-guard"
    installed_guard = tmp_path / "n3w-registration-ingress-guard"
    shutil.copy2(
        TOOLS / "n3w_broker_ingress_guard.py",
        installed_broker,
    )
    shutil.copy2(
        TOOLS / "n3w_registration_ingress_guard.py",
        installed_guard,
    )
    sys.modules.pop("n3w_broker_ingress_guard", None)
    module = _load(
        "installed_registration_ingress_guard",
        installed_guard,
    )
    assert module.broker_guard.INTERFACE == "eth0"


@pytest.mark.parametrize("goto_operator", ("-g", "--goto"))
def test_registration_guard_rejects_extra_input_goto(
    goto_operator: str,
) -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = _payload(
        broker,
        registration,
        subnet=subnet,
        anchors=True,
    ).replace(
        "COMMIT\n",
        f"-A INPUT {goto_operator} "
        f"{registration.CUSTOM_CHAIN}\nCOMMIT\n",
    )
    inventory = registration.parse_firewall_inventory(payload)
    assert inventory.foreign_custom_chain_refs
    with pytest.raises(
        registration.RegistrationIngressGuardError,
        match="registration_chain_foreign_reference",
    ):
        registration._validate_prestate(inventory)


@pytest.mark.parametrize("goto_operator", ("-g", "--goto"))
def test_registration_guard_rejects_foreign_chain_goto(
    goto_operator: str,
) -> None:
    broker, registration = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    payload = _payload(
        broker,
        registration,
        subnet=subnet,
        anchors=True,
    ).replace(
        "COMMIT\n",
        ":FOREIGN - [0:0]\n"
        f"-A FOREIGN {goto_operator} "
        f"{registration.CUSTOM_CHAIN}\n"
        "COMMIT\n",
    )
    inventory = registration.parse_firewall_inventory(payload)
    assert inventory.foreign_custom_chain_refs
    with pytest.raises(
        registration.RegistrationIngressGuardError,
        match="registration_chain_foreign_reference",
    ):
        registration._validate_prestate(inventory)
