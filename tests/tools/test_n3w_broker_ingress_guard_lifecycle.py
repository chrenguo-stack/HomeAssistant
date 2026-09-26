from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra/n3w-t1"
GUARD_UNIT = INFRA / "systemd/n3wfc4-broker-ingress-guard.service"
ACTIVATION_UNIT = INFRA / "systemd/n3wfc4-broker-activation.service"
DISPATCHER = (
    INFRA
    / "NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_guard_unit_orders_after_docker_before_broker_activation() -> None:
    unit = read(GUARD_UNIT)

    assert "Requires=docker.service" in unit
    assert "After=docker.service" in unit
    assert "Before=n3wfc4-broker-activation.service" in unit
    assert "PartOf=docker.service" in unit
    assert "WantedBy=docker.service" in unit
    assert (
        "ExecStart=/usr/local/sbin/n3w-broker-ingress-guard --apply"
        in unit
    )
    assert (
        "ExecReload=/usr/local/sbin/n3w-broker-ingress-guard --apply"
        in unit
    )
    assert "network-online.target" not in unit


def test_broker_activation_is_runtime_supervisor() -> None:
    unit = read(ACTIVATION_UNIT)

    assert "Type=simple" in unit
    assert (
        "Requires=docker.service n3wfc4-broker-ingress-guard.service"
        in unit
    )
    assert (
        "After=docker.service n3wfc4-broker-ingress-guard.service"
        in unit
    )
    assert "PartOf=docker.service" in unit
    assert "WantedBy=docker.service" in unit
    assert "EnvironmentFile=/etc/n3wfc4/broker-activation.env" in unit
    assert (
        "ExecStartPre=/usr/bin/systemctl reload "
        "n3wfc4-broker-ingress-guard.service"
        in unit
    )
    assert unit.count("--project-name ${N3WFC4_COMPOSE_PROJECT_NAME}") == 2
    assert "up --no-deps --no-log-prefix --exit-code-from broker broker" in unit
    assert "up -d" not in unit
    assert "stop broker" in unit
    assert "Restart=always" in unit
    assert "RestartSec=5" in unit
    assert "RemainAfterExit=yes" not in unit


def test_dispatcher_only_handles_eth0_and_bounded_network_events() -> None:
    script = read(DISPATCHER)

    assert '[ "$interface" = "eth0" ] || exit 0' in script
    for action in (
        "pre-up",
        "up",
        "dhcp4-change",
        "reapply",
        "pre-down",
        "down",
    ):
        assert action in script
    assert "is-active docker.service || exit 0" in script
    assert "/usr/bin/timeout 20s" in script
    assert (
        "reload-or-restart n3wfc4-broker-ingress-guard.service"
        in script
    )
    assert "systemctl reload n3wfc4-broker-ingress-guard.service" not in script
    assert "systemctl restart n3wfc4-broker-ingress-guard.service" not in script


def test_dispatcher_recovers_broker_after_guard_recovers() -> None:
    script = read(DISPATCHER)
    guard = (
        "/usr/bin/timeout 20s /usr/bin/systemctl reload-or-restart "
        "n3wfc4-broker-ingress-guard.service"
    )
    start = (
        "/usr/bin/timeout 30s /usr/bin/systemctl start "
        "n3wfc4-broker-activation.service"
    )
    stop = (
        "/usr/bin/timeout 30s /usr/bin/systemctl stop "
        "n3wfc4-broker-activation.service"
    )

    assert guard in script
    assert start in script
    assert stop in script
    assert script.index(guard) < script.index(start) < script.index(stop)


def test_dispatcher_guard_or_broker_start_failure_stops_activation_owner() -> None:
    script = read(DISPATCHER)

    assert (
        "/usr/bin/timeout 30s /usr/bin/systemctl stop "
        "n3wfc4-broker-activation.service"
        in script
    )
    assert script.rstrip().endswith("exit 1")


def test_dispatcher_does_not_accept_event_subnet_as_authority() -> None:
    script = read(DISPATCHER)

    forbidden = (
        "IP4_ADDRESS",
        "DHCP4_",
        "CONNECTION_IP4",
        "192.168.",
        "10.0.",
        "172.16.",
    )
    for value in forbidden:
        assert value not in script
