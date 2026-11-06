from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_ha_template_convergence as tool


HA = "local/n3w-homeassistant:2026.10.0-0c73235a"


def compose() -> bytes:
    return (
        "name: n3wfc4\n"
        "services:\n"
        "  broker:\n"
        "    image: local/n3w-mosquitto:2.1.2-3184566d\n"
        "  manager:\n"
        "    image: \"${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}\"\n"
        "  homeassistant:\n"
        f"    image: {HA}\n"
        "    network_mode: host\n"
        "networks:\n"
        "  n3wfc4-private: {}\n"
    ).encode()


def env() -> bytes:
    return (
        "GH_MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210\n"
        "GH_SYSTEM_ID=gh-test\n"
    ).encode()


def test_candidate_adds_only_ha_dynamic_binding():
    updated_compose = tool.candidate_compose(compose(), HA)
    updated_env = tool.candidate_env(env(), HA)

    assert b'    image: "${GH_HOMEASSISTANT_IMAGE:?GH_HOMEASSISTANT_IMAGE required}"\n' in updated_compose
    assert f"GH_HOMEASSISTANT_IMAGE={HA}\n".encode() in updated_env
    assert b"local/n3w-mosquitto:2.1.2-3184566d" in updated_compose
    assert b"GH_MANAGER_IMAGE" in updated_compose


def test_candidate_rejects_wrong_live_ha_image():
    with pytest.raises(
        tool.ConvergenceError,
        match="homeassistant_compose_predecessor_drift",
    ):
        tool.candidate_compose(
            compose(),
            "local/n3w-homeassistant:2026.10.4-deadbeef",
        )


def test_candidate_rejects_duplicate_ha_env_binding():
    payload = (
        env()
        + f"GH_HOMEASSISTANT_IMAGE={HA}\n".encode()
        + f"GH_HOMEASSISTANT_IMAGE={HA}\n".encode()
    )
    with pytest.raises(
        tool.ConvergenceError,
        match="homeassistant_env_line_count_invalid",
    ):
        tool.candidate_env(payload, HA)


def test_inspect_requires_semantic_render_equality(tmp_path: Path, monkeypatch):
    compose_path = tmp_path / "docker-compose.yml"
    env_path = tmp_path / "docker-compose.env"
    compose_path.write_bytes(compose())
    env_path.write_bytes(env())

    renders = [
        {"services": {"homeassistant": {"image": HA}}},
        {"services": {"homeassistant": {"image": HA}}},
    ]
    monkeypatch.setattr(tool, "_render", lambda *args: renders.pop(0))

    result = tool.inspect(
        compose=compose_path,
        env=env_path,
        expected_image=HA,
    )

    assert result["status"] == "PASS"
    assert result["mutation"] is False
    assert result["current_binding_mode"] == "legacy_static"
    assert result["candidate_binding_mode"] == "dynamic"
    assert result["render_semantically_equal"] is True


def test_inspect_stops_on_candidate_semantic_drift(tmp_path: Path, monkeypatch):
    compose_path = tmp_path / "docker-compose.yml"
    env_path = tmp_path / "docker-compose.env"
    compose_path.write_bytes(compose())
    env_path.write_bytes(env())

    renders = [
        {"services": {"homeassistant": {"image": HA}}},
        {
            "services": {
                "homeassistant": {
                    "image": HA,
                    "unexpected": True,
                }
            }
        },
    ]
    monkeypatch.setattr(tool, "_render", lambda *args: renders.pop(0))

    with pytest.raises(
        tool.ConvergenceError,
        match="candidate_render_semantic_drift",
    ):
        tool.inspect(
            compose=compose_path,
            env=env_path,
            expected_image=HA,
        )
