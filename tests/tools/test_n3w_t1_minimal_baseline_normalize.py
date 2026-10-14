from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_minimal_baseline_normalize.py"
MANIFEST = (
    ROOT
    / "infra/n3w-t1/production/minimal-baseline-normalization-manifest.json"
)


def load_tool():
    name = "n3w_t1_minimal_baseline_normalize"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_is_exact_and_binds_frozen_volume_set() -> None:
    tool = load_tool()
    document = manifest()
    tool._validate_manifest(document)

    volumes = document["delete"]["docker_volumes"]
    assert len(volumes) == 45
    assert len(set(volumes)) == 45
    assert (
        tool._volume_set_sha256(volumes)
        == "20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b"
    )
    assert document["source_inventory"]["sha256"] == (
        "0ad246ee33dcddf70555fcf23551c7b106f8b0edad8eb0523a24421d674f4814"
    )


def test_manifest_preserves_host_docker_framework() -> None:
    document = manifest()

    assert document["preserve"]["docker_networks"] == ["bridge", "host", "none"]
    assert document["preserve"]["docker_firewall_framework"] == {
        "chain": "DOCKER-USER",
        "forward_jump_required": True,
    }
    deleted_networks = {
        item["name"] for item in document["delete"]["docker_networks"]
    }
    assert deleted_networks.isdisjoint({"bridge", "host", "none"})


def test_manifest_paths_are_exact_without_globs() -> None:
    document = manifest()

    for item in document["delete"]["product_paths"]:
        path = item["path"]
        assert path.startswith("/")
        assert not any(token in path for token in ("*", "?", "[", "]"))
        assert path not in {"/", "/var", "/var/lib", "/var/lib/docker", "/etc", "/opt"}


def test_self_check_forbids_broad_destructive_operations() -> None:
    tool = load_tool()
    result = tool.self_check(manifest())

    assert result["status"] == "PASS"
    assert result["forbidden_broad_destructive_operations"] == []
    assert result["live_mutation_executed"] is False


def test_apply_rejects_wrong_authorization_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    mutated = False

    def fake_mutate(_runner, _manifest):
        nonlocal mutated
        mutated = True

    monkeypatch.setattr(tool, "_apply_mutation", fake_mutate)

    with pytest.raises(tool.NormalizationError, match="authorization_id_mismatch"):
        tool.execute_apply(manifest(), "WRONG", runner=object())

    assert mutated is False


def test_firewall_parser_accepts_owned_r5_shape() -> None:
    tool = load_tool()

    payload = """
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:DOCKER-USER - [0:0]
:N3WFC4-BROKER-INGRESS - [0:0]
-A INPUT -p tcp -m tcp --dport 8883 -m comment --comment n3wfc4-broker-ingress-v1 -j N3WFC4-BROKER-INGRESS
-A FORWARD -j DOCKER-USER
-A DOCKER-USER -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 8883 -m comment --comment n3wfc4-broker-ingress-v1 -j N3WFC4-BROKER-INGRESS
-A N3WFC4-BROKER-INGRESS -s 127.0.0.0/8 -i lo -m comment --comment n3wfc4-broker-ingress-v1 -j RETURN
-A N3WFC4-BROKER-INGRESS -s 203.0.113.0/24 -i eth0 -m comment --comment n3wfc4-broker-ingress-v1 -j RETURN
-A N3WFC4-BROKER-INGRESS -m comment --comment n3wfc4-broker-ingress-v1 -j DROP
COMMIT
"""

    class FakeRunner:
        def run(self, argv, **_kwargs):
            assert tuple(argv) == ("iptables-save", "-t", "filter")
            return payload

    result = tool._firewall_report(FakeRunner())

    assert result["docker_user_present"] is True
    assert result["custom_chain_present"] is True
    assert result["input_anchor_count"] == 1
    assert result["docker_user_anchor_count"] == 1
    assert result["custom_rule_count"] == 3
    assert result["custom_rules_valid"] is True
    assert result["foreign_custom_chain_references"] == ()
    assert result["trusted_subnet_sha256"] == tool._sha256_text("203.0.113.0/24")


def test_firewall_parser_detects_foreign_reference() -> None:
    tool = load_tool()

    payload = """
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:DOCKER-USER - [0:0]
:N3WFC4-BROKER-INGRESS - [0:0]
:OTHER - [0:0]
-A INPUT -p tcp -m tcp --dport 8883 -m comment --comment n3wfc4-broker-ingress-v1 -j N3WFC4-BROKER-INGRESS
-A FORWARD -j DOCKER-USER
-A DOCKER-USER -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 8883 -m comment --comment n3wfc4-broker-ingress-v1 -j N3WFC4-BROKER-INGRESS
-A OTHER -j N3WFC4-BROKER-INGRESS
-A N3WFC4-BROKER-INGRESS -s 127.0.0.0/8 -i lo -m comment --comment n3wfc4-broker-ingress-v1 -j RETURN
-A N3WFC4-BROKER-INGRESS -s 203.0.113.0/24 -i eth0 -m comment --comment n3wfc4-broker-ingress-v1 -j RETURN
-A N3WFC4-BROKER-INGRESS -m comment --comment n3wfc4-broker-ingress-v1 -j DROP
COMMIT
"""

    class FakeRunner:
        def run(self, argv, **_kwargs):
            return payload

    result = tool._firewall_report(FakeRunner())
    assert result["foreign_custom_chain_references"] == (
        "-A OTHER -j N3WFC4-BROKER-INGRESS",
    )
