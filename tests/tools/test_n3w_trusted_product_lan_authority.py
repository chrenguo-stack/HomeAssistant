from __future__ import annotations

import importlib.util
import io
import ipaddress
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_modules():
    broker = _load("n3w_broker_ingress_guard", TOOLS / "n3w_broker_ingress_guard.py")
    authority = _load(
        "n3w_trusted_product_lan_authority",
        TOOLS / "n3w_trusted_product_lan_authority.py",
    )
    return broker, authority


def test_available_publication_uses_exact_broker_guard_decision_contract() -> None:
    broker, authority = load_modules()
    decision = broker.decide_trusted_subnet(
        connected=True,
        raw_addresses=["192.0.2.10/24"],
    )
    document = authority.build_state_document(
        decision,
        now=datetime(2026, 10, 26, 7, 0, tzinfo=UTC),
    )
    assert document["available"] is True
    assert document["interface"] == "eth0"
    assert document["subnet"] == "192.0.2.0/24"
    assert document["reason"] == "unique_ipv4_subnet"


def test_fail_closed_publication_replaces_old_subnet_state(tmp_path: Path) -> None:
    broker, authority = load_modules()
    runtime = tmp_path / "trusted"
    state_file = runtime / "state.json"
    runtime.mkdir()
    state_file.write_text(
        json.dumps(
            {
                "schema": authority.SCHEMA,
                "interface": "eth0",
                "available": True,
                "subnet": "192.0.2.0/24",
                "reason": "unique_ipv4_subnet",
                "published_at": "2026-10-26T06:00:00Z",
                "generation": "old",
            }
        ),
        encoding="utf-8",
    )
    decision = broker.decide_trusted_subnet(
        connected=False,
        raw_addresses=[],
    )
    document = authority.build_state_document(
        decision,
        now=datetime(2026, 10, 26, 7, 0, tzinfo=UTC),
    )
    authority.atomic_publish(
        document,
        runtime_dir=runtime,
        state_file=state_file,
    )
    published = json.loads(state_file.read_text(encoding="utf-8"))
    assert published["available"] is False
    assert "subnet" not in published
    assert published["reason"] == "interface_not_connected"


def test_public_cli_output_never_contains_raw_customer_subnet(monkeypatch) -> None:
    broker, authority = load_modules()
    subnet = ipaddress.ip_network("192.0.2.0/24")
    monkeypatch.setattr(
        broker,
        "read_network_decision",
        lambda: broker.NetworkDecision(subnet, 1, "unique_ipv4_subnet"),
    )
    output = io.StringIO()
    status = authority.main(["--dry-run"], stdout=output)
    result = json.loads(output.getvalue())
    assert status == 0
    assert result["status"] == "PASS"
    assert result["raw_customer_subnet_in_public_output"] is False
    assert str(subnet) not in output.getvalue()


def test_apply_unavailable_is_successful_fail_closed_publication(monkeypatch, tmp_path: Path) -> None:
    broker, authority = load_modules()
    monkeypatch.setattr(
        broker,
        "read_network_decision",
        lambda: broker.NetworkDecision(None, 0, "interface_not_connected"),
    )
    observed = {}
    monkeypatch.setattr(
        authority,
        "atomic_publish",
        lambda document: observed.update(document),
    )
    output = io.StringIO()
    status = authority.main(["--apply"], stdout=output)
    assert status == 0
    assert observed["available"] is False
    result = json.loads(output.getvalue())
    assert result["status"] == "FAIL_CLOSED"
