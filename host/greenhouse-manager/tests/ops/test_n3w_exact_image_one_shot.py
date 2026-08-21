from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager.ops import n3w_exact_image_one_shot as one_shot

IMAGE = "local/greenhouse-manager:fc4-3bd3f073"
IMAGE_ID = "sha256:" + "8" * 64
DEFAULT_ENTRYPOINT = object()


class FakeRunner:
    def __init__(self, responses: list[tuple[int, str]]) -> None:
        self.responses = responses
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(tuple(command))
        return self.responses.pop(0)


def _inspect(
    *, image_id: str = IMAGE_ID, entrypoint: object = DEFAULT_ENTRYPOINT
) -> str:
    if entrypoint is DEFAULT_ENTRYPOINT:
        entrypoint = ["greenhouse-manager"]
    return json.dumps([{"Id": image_id, "Config": {"Entrypoint": entrypoint}}])


def test_preflight_forces_explicit_python_entrypoint(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner([ (0, _inspect()), (0, "usage: recovery\n") ])

    binding = one_shot.preflight_exact_image(
        runner,
        image=IMAGE,
        expected_image_id=IMAGE_ID,
        source_root=str(source),
    )

    assert binding.image_id == IMAGE_ID
    assert runner.commands[0] == ("docker", "image", "inspect", IMAGE)
    command = runner.commands[1]
    assert command[:5] == ("docker", "run", "--rm", "--network", "none")
    assert "--read-only" in command
    assert command[command.index("--entrypoint") + 1] == "python"
    assert command[command.index("--entrypoint") + 2] == IMAGE_ID
    assert command[-3:] == ("-m", one_shot.RECOVERY_MODULE, "--help")
    assert "greenhouse-manager" not in command[command.index("--entrypoint") + 1 :]


def test_recovery_command_uses_exact_id_and_same_absolute_state_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    state = tmp_path / "state"
    source.mkdir()
    state.mkdir()
    binding = one_shot.ExactImageBinding(
        image_id=IMAGE_ID,
        source_root=source,
        product_entrypoint="greenhouse-manager",
    )

    command = one_shot.build_recovery_command(
        binding,
        state_root=str(state),
        recovery_arguments=("--registration-db", str(state / "registration.sqlite3")),
    )

    assert "--read-only" not in command
    assert command[command.index("--entrypoint") + 1] == "python"
    assert command[command.index("--entrypoint") + 2] == IMAGE_ID
    assert f"type=bind,src={state},dst={state}" in command
    assert command[-4:] == (
        "-m",
        one_shot.RECOVERY_MODULE,
        "--registration-db",
        str(state / "registration.sqlite3"),
    )


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_inspect(image_id="sha256:" + "9" * 64), "image ID binding mismatch"),
        (_inspect(entrypoint=None), "product image entrypoint binding mismatch"),
        (_inspect(entrypoint=["python"]), "product image entrypoint binding mismatch"),
    ],
)
def test_preflight_rejects_image_or_inherited_entrypoint_drift(
    tmp_path: Path,
    document: str,
    message: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner([(0, document)])

    with pytest.raises(one_shot.ExactImageOneShotError, match=message):
        one_shot.preflight_exact_image(
            runner,
            image=IMAGE,
            expected_image_id=IMAGE_ID,
            source_root=str(source),
        )

    assert len(runner.commands) == 1


def test_failed_module_preflight_never_builds_recovery_command(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner([(0, _inspect()), (2, "unrecognized arguments")])

    with pytest.raises(one_shot.ExactImageOneShotError, match="preflight failed"):
        one_shot.preflight_exact_image(
            runner,
            image=IMAGE,
            expected_image_id=IMAGE_ID,
            source_root=str(source),
        )

    assert len(runner.commands) == 2
    assert all("--registration-db" not in command for command in runner.commands)


def test_run_recovery_rejects_empty_success_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    state = tmp_path / "state"
    source.mkdir()
    state.mkdir()
    binding = one_shot.ExactImageBinding(
        image_id=IMAGE_ID,
        source_root=source,
        product_entrypoint="greenhouse-manager",
    )
    runner = FakeRunner([(0, "")])

    with pytest.raises(one_shot.ExactImageOneShotError, match="execution failed"):
        one_shot.run_recovery(
            runner,
            binding,
            state_root=str(state),
            recovery_arguments=("--confirm-manager-stopped",),
        )


def test_cli_preflight_reports_explicit_entrypoint_without_running_recovery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner([(0, _inspect()), (0, "usage: recovery\n")])

    result = one_shot.main(
        [
            "--image",
            IMAGE,
            "--expected-image-id",
            IMAGE_ID,
            "--source-root",
            str(source),
            "preflight",
        ],
        runner=runner,
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "EXACT_IMAGE_ONE_SHOT=PASS" in output
    assert "EXPLICIT_ONE_SHOT_ENTRYPOINT=python" in output
    assert "RECOVERY_MODULE_PREFLIGHT=PASS" in output
    assert len(runner.commands) == 2
