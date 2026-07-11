from __future__ import annotations

from datetime import UTC, datetime

from greenhouse_manager.t1_preflight import build_report, parse_safe_directives


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], tuple[int, str]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.calls.append(command)
        if command[:3] == ("docker", "inspect", "-f"):
            name = command[-1]
            return (
                0,
                '{"state":"running","health":"","restarts":"0",'
                f'"image":"test/{name}:latest"' + "}",
            )
        return self.responses.get(command, (1, "redacted failure"))


def test_config_parser_only_returns_whitelisted_directives() -> None:
    config = """
    listener 1883
    allow_anonymous true
    password_file /mosquitto/config/passwords
    plugin_opt_secret should-never-be-returned
    log_dest stdout
    """

    assert parse_safe_directives(config) == (
        {"directive": "listener", "value": "1883"},
        {"directive": "allow_anonymous", "value": "true"},
        {
            "directive": "password_file",
            "value": "/mosquitto/config/passwords",
        },
    )


def test_builds_ready_secret_free_report() -> None:
    config_command = (
        "docker",
        "exec",
        "mosquitto",
        "sh",
        "-c",
        "test -r /mosquitto/config/mosquitto.conf && "
        "cat /mosquitto/config/mosquitto.conf",
    )
    runner = FakeRunner(
        {
            ("docker", "exec", "mosquitto", "mosquitto", "-h"): (
                0,
                "mosquitto version 2.0.22\n",
            ),
            config_command: (
                0,
                "listener 1883\nallow_anonymous true\nplugin_opt_secret hidden\n",
            ),
            (
                "docker",
                "exec",
                "mosquitto",
                "sh",
                "-c",
                "test -f /usr/lib/mosquitto_dynamic_security.so && echo available",
            ): (0, "available\n"),
            (
                "docker",
                "exec",
                "greenhouse-manager",
                "python",
                "-c",
                "import importlib.metadata as m; print(m.version('greenhouse-manager'))",
            ): (0, "0.1.2\n"),
        }
    )

    report = build_report(
        runner, generated_at=datetime(2026, 7, 11, 13, 0, tzinfo=UTC)
    )

    assert report["ready"] is True
    assert report["read_only"] is True
    assert report["broker"]["anonymous_mode"] is True
    assert report["broker"]["dynamic_security_configured"] is False
    assert report["manager"]["version"] == "0.1.2"
    assert "hidden" not in str(report)
    assert all("publish" not in " ".join(call) for call in runner.calls)


def test_blocks_when_dynsec_is_already_configured() -> None:
    config_command = (
        "docker",
        "exec",
        "mosquitto",
        "sh",
        "-c",
        "test -r /mosquitto/config/mosquitto.conf && "
        "cat /mosquitto/config/mosquitto.conf",
    )
    plugin_command = (
        "docker",
        "exec",
        "mosquitto",
        "sh",
        "-c",
        "test -f /usr/lib/mosquitto_dynamic_security.so && echo available",
    )
    runner = FakeRunner(
        {
            config_command: (
                0,
                "allow_anonymous true\n"
                "plugin /usr/lib/mosquitto_dynamic_security.so\n",
            ),
            plugin_command: (0, "available\n"),
        }
    )

    report = build_report(runner)

    assert report["ready"] is False
    assert report["gates"]["shadow_migration_not_active"] is False
