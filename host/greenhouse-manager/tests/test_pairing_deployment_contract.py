from __future__ import annotations

from pathlib import Path

from greenhouse_manager.pairing_runtime_config import (
    FROZEN_PAIRING_HTTP_PORT,
    FROZEN_PAIRING_UDP_PORT,
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_pairing_lab_dockerfile_installs_only_explicit_pairing_image() -> None:
    dockerfile = (
        repository_root()
        / "host"
        / "greenhouse-manager"
        / "Dockerfile.pairing-lab"
    ).read_text(encoding="utf-8")
    assert "pip install '.[pairing]'" in dockerfile
    assert 'ENTRYPOINT ["greenhouse-manager-pairing-lab"]' in dockerfile
    assert 'CMD ["--check-config"]' in dockerfile


def test_pairing_lab_compose_has_no_host_publication() -> None:
    compose = (
        repository_root()
        / "infra"
        / "compose"
        / "h3-pairing-lab"
        / "compose.yaml"
    ).read_text(encoding="utf-8")

    assert "\n    ports:" not in compose
    assert f'- "{FROZEN_PAIRING_HTTP_PORT}/tcp"' in compose
    assert f'- "{FROZEN_PAIRING_UDP_PORT}/udp"' in compose
    assert 'GH_PAIRING_SERVICE_ENABLED: "false"' in compose
    assert 'GH_PAIRING_DEPLOYMENT_MODE: "isolated-lab"' in compose
    assert "internal: true" in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "\n      - ALL\n" in compose
    assert "/var/run/docker.sock" not in compose
    assert "homeassistant" not in compose.lower()
    assert "mosquitto" not in compose.lower()
