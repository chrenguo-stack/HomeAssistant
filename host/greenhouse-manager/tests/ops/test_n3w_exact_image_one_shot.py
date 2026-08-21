from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager.ops import n3w_exact_image_one_shot as one_shot

IMAGE = "local/greenhouse-manager:fc4-3bd3f073"
IMAGE_ID = "sha256:" + "8" * 64
DEFAULT_ENTRYPOINT = object()

SAFE_FAILURE = "\n".join(
    (
        "RECOVERY_EXECUTOR=FAIL:MANAGER_INSPECT_MODE_INVALID",
        "PAIRING_ID_RAW_EXPOSED=false",
        "SECRET_VALUE_EXPOSED=false",
        "",
    )
)


class FakeRunner:
    def __init__(self, responses: list[tuple[int, str]]) -> None:
        self.responses = responses
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(tuple(command))
        return self.responses.pop(0)


def _inspect(
    *,
    image_id: str = IMAGE_ID,
    entrypoint: object = DEFAULT_ENTRYPOINT,
) -> str:
    if entrypoint is DEFAULT_ENTRYPOINT:
        entrypoint = ["greenhouse-manager"]
    return json.dumps(
        [{"Id": image_id, "Config": {"Entrypoint": entrypoint}}]
    )


def _inputs(
    tmp_path: Path,
    *,
    shared_database_parent: bool = False,
) -> tuple[Path, Path, Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()

    private = tmp_path / "fc4-private"
    private.mkdir()

    if shared_database_parent:
        registration_parent = private / "database"
        credential_parent = registration_parent
        registration_parent.mkdir()
    else:
        registration_parent = private / "manager"
        credential_parent = private / "n3w"
        registration_parent.mkdir()
        credential_parent.mkdir()

    registration = registration_parent / "registration.sqlite3"
    credential = credential_parent / "credential-lifecycle.sqlite3"
    inspect = private / "manager.inspect.private.json"

    registration.write_bytes(b"registration")
    credential.write_bytes(b"credential")
    inspect.write_text("[]", encoding="utf-8")

    return source, private, registration, credential, inspect


def _recovery_arguments(
    registration: Path,
    credential: Path,
    inspect: Path,
) -> tuple[str, ...]:
    return (
        "--registration-db",
        str(registration),
        "--credential-db",
        str(credential),
        "--manager-inspect-json",
        str(inspect),
        "--manager-container",
        "fc4-manager",
        "--registration-container-path",
        "/var/lib/greenhouse-manager/manager/registration.sqlite3",
        "--credential-container-path",
        "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3",
        "--hardware-id",
        "ghw-c6-test",
        "--expected-pairing-id-sha256",
        "1" * 64,
        "--expected-registration-sha256",
        "2" * 64,
        "--expected-credential-sha256",
        "3" * 64,
        "--confirm-manager-stopped",
    )


def _binding(source: Path) -> one_shot.ExactImageBinding:
    return one_shot.ExactImageBinding(
        image_id=IMAGE_ID,
        source_root=source,
        product_entrypoint="greenhouse-manager",
    )


def _mounts(command: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        command[index + 1]
        for index, token in enumerate(command[:-1])
        if token == "--mount"
    )


def test_preflight_forces_explicit_python_entrypoint(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [(0, _inspect()), (0, "usage: recovery\n")]
    )

    binding = one_shot.preflight_exact_image(
        runner,
        image=IMAGE,
        expected_image_id=IMAGE_ID,
        source_root=str(source),
    )

    assert binding.image_id == IMAGE_ID
    assert runner.commands[0] == (
        "docker",
        "image",
        "inspect",
        IMAGE,
    )

    command = runner.commands[1]
    assert command[:5] == (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
    )
    assert "--read-only" in command
    assert "--user" not in command
    assert "--privileged" not in command
    assert command[command.index("--entrypoint") + 1] == "python"
    assert command[command.index("--entrypoint") + 2] == IMAGE_ID
    assert command[-3:] == (
        "-m",
        one_shot.RECOVERY_MODULE,
        "--help",
    )


def test_recovery_mounts_only_exact_private_authority(
    tmp_path: Path,
) -> None:
    (
        source,
        private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    arguments = _recovery_arguments(
        registration,
        credential,
        inspect,
    )
    command = one_shot.build_recovery_command(
        _binding(source),
        recovery_arguments=arguments,
    )

    mounts = _mounts(command)

    assert "--read-only" in command
    assert "--user" not in command
    assert "--privileged" not in command

    assert (
        f"type=bind,src={source},"
        f"dst={one_shot.SOURCE_TARGET},readonly"
    ) in mounts

    assert (
        f"type=bind,src={registration.parent},"
        f"dst={registration.parent}"
    ) in mounts
    assert (
        f"type=bind,src={credential.parent},"
        f"dst={credential.parent}"
    ) in mounts
    assert (
        f"type=bind,src={inspect},dst={inspect},readonly"
    ) in mounts

    assert f"type=bind,src={private},dst={private}" not in mounts
    assert len(mounts) == 4

    assert command[-len(arguments) :] == arguments
    assert command[
        command.index("--entrypoint") + 2
    ] == IMAGE_ID


def test_database_parent_mount_is_deduplicated(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(
        tmp_path,
        shared_database_parent=True,
    )

    command = one_shot.build_recovery_command(
        _binding(source),
        recovery_arguments=_recovery_arguments(
            registration,
            credential,
            inspect,
        ),
    )
    mounts = _mounts(command)

    database_mount = (
        f"type=bind,src={registration.parent},"
        f"dst={registration.parent}"
    )
    assert registration.parent == credential.parent
    assert mounts.count(database_mount) == 1
    assert len(mounts) == 3


def test_authority_probe_uses_exact_image_same_user_and_mounts(
    tmp_path: Path,
) -> None:
    (
        source,
        private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    command = one_shot.build_authority_probe_command(
        _binding(source),
        recovery_arguments=_recovery_arguments(
            registration,
            credential,
            inspect,
        ),
    )
    mounts = _mounts(command)

    assert command[0:5] == (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
    )
    assert "--read-only" in command
    assert "--user" not in command
    assert "--privileged" not in command
    assert command[command.index("--entrypoint") + 1] == "python"
    assert command[command.index("--entrypoint") + 2] == IMAGE_ID
    assert f"type=bind,src={private},dst={private}" not in mounts

    script = command[command.index("-c") + 1]

    assert one_shot.EXPECTED_RUNTIME_UID == 999
    assert one_shot.EXPECTED_RUNTIME_GID == 999
    assert "EXPECTED_UID = 999" in script
    assert "EXPECTED_GID = 999" in script
    assert "os.geteuid() != EXPECTED_UID" in script
    assert "os.getegid() != EXPECTED_GID" in script
    assert "stat.S_IMODE(metadata.st_mode) != 0o700" in script
    assert "metadata.st_uid != EXPECTED_UID" in script
    assert "metadata.st_gid != EXPECTED_GID" in script
    assert "os.O_WRONLY | os.O_CREAT | os.O_EXCL" in script
    assert "stat.S_IMODE(inspect_metadata.st_mode) != 0o600" in script
    assert "inspect_metadata.st_uid != EXPECTED_UID" in script
    assert "inspect_metadata.st_gid != EXPECTED_GID" in script
    assert "os.open(inspect_path, os.O_WRONLY)" in script


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            _inspect(image_id="sha256:" + "9" * 64),
            "image ID binding mismatch",
        ),
        (
            _inspect(entrypoint=None),
            "product image entrypoint binding mismatch",
        ),
        (
            _inspect(entrypoint=["python"]),
            "product image entrypoint binding mismatch",
        ),
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

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match=message,
    ):
        one_shot.preflight_exact_image(
            runner,
            image=IMAGE,
            expected_image_id=IMAGE_ID,
            source_root=str(source),
        )

    assert len(runner.commands) == 1


@pytest.mark.parametrize(
    "missing_option",
    (
        "--registration-db",
        "--credential-db",
        "--manager-inspect-json",
    ),
)
def test_recovery_rejects_missing_private_authority_argument(
    tmp_path: Path,
    missing_option: str,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    arguments = list(
        _recovery_arguments(
            registration,
            credential,
            inspect,
        )
    )

    index = arguments.index(missing_option)
    del arguments[index : index + 2]

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="exactly once",
    ):
        one_shot.build_recovery_command(
            _binding(source),
            recovery_arguments=arguments,
        )


def test_recovery_rejects_duplicate_private_authority_argument(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    arguments = (
        *_recovery_arguments(
            registration,
            credential,
            inspect,
        ),
        "--registration-db",
        str(registration),
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="exactly once",
    ):
        one_shot.build_recovery_command(
            _binding(source),
            recovery_arguments=arguments,
        )


def test_recovery_rejects_relative_private_path(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        _registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    arguments = _recovery_arguments(
        Path("registration.sqlite3"),
        credential,
        inspect,
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="must be absolute",
    ):
        one_shot.build_recovery_command(
            _binding(source),
            recovery_arguments=arguments,
        )


def test_recovery_rejects_symlink_private_file(
    tmp_path: Path,
) -> None:
    (
        source,
        private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    registration_link = private / "registration-link.sqlite3"
    registration_link.symlink_to(registration)

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="must not be a symlink",
    ):
        one_shot.build_recovery_command(
            _binding(source),
            recovery_arguments=_recovery_arguments(
                registration_link,
                credential,
                inspect,
            ),
        )


def test_recovery_rejects_parent_symlink_alias(
    tmp_path: Path,
) -> None:
    (
        source,
        private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    alias = tmp_path / "private-alias"
    alias.symlink_to(private, target_is_directory=True)
    aliased_registration = alias / registration.relative_to(
        private
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="invalid",
    ):
        one_shot.build_recovery_command(
            _binding(source),
            recovery_arguments=_recovery_arguments(
                aliased_registration,
                credential,
                inspect,
            ),
        )


def test_authority_preflight_is_fail_closed(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    arguments = _recovery_arguments(
        registration,
        credential,
        inspect,
    )
    runner = FakeRunner(
        [(1, "KF048_AUTHORITY_PROBE=FAIL:RUNTIME_IDENTITY_MISMATCH")]
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="authority preflight failed",
    ) as captured:
        one_shot.preflight_recovery_authority(
            runner,
            _binding(source),
            recovery_arguments=arguments,
        )

    assert captured.value.recovery_started is False
    assert len(runner.commands) == 1


def test_authority_preflight_accepts_only_exact_pass_marker(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    runner = FakeRunner(
        [(0, "KF048_AUTHORITY_PROBE=PASS\n")]
    )

    one_shot.preflight_recovery_authority(
        runner,
        _binding(source),
        recovery_arguments=_recovery_arguments(
            registration,
            credential,
            inspect,
        ),
    )

    assert len(runner.commands) == 1


def test_run_recovery_preserves_sanitized_inner_failure(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    runner = FakeRunner(
        [
            (0, "KF048_AUTHORITY_PROBE=PASS\n"),
            (1, SAFE_FAILURE),
        ]
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="execution failed",
    ) as captured:
        one_shot.run_recovery(
            runner,
            _binding(source),
            recovery_arguments=_recovery_arguments(
                registration,
                credential,
                inspect,
            ),
        )

    error = captured.value
    assert error.recovery_started is True
    assert error.safe_lines == (
        "RECOVERY_EXECUTOR=FAIL:MANAGER_INSPECT_MODE_INVALID",
        "PAIRING_ID_RAW_EXPOSED=false",
        "SECRET_VALUE_EXPOSED=false",
    )
    assert len(runner.commands) == 2


def test_run_recovery_does_not_echo_unclassified_failure(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    unsafe = "unexpected raw diagnostic value=private-data"
    runner = FakeRunner(
        [
            (0, "KF048_AUTHORITY_PROBE=PASS\n"),
            (1, unsafe),
        ]
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
    ) as captured:
        one_shot.run_recovery(
            runner,
            _binding(source),
            recovery_arguments=_recovery_arguments(
                registration,
                credential,
                inspect,
            ),
        )

    error = captured.value
    assert error.recovery_started is True
    assert error.safe_lines == (
        "RECOVERY_EXECUTOR=FAIL:"
        "INNER_RECOVERY_FAILURE_UNCLASSIFIED",
    )
    assert unsafe not in "\n".join(error.safe_lines)


def test_run_recovery_empty_success_is_started_failure(
    tmp_path: Path,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    runner = FakeRunner(
        [
            (0, "KF048_AUTHORITY_PROBE=PASS\n"),
            (0, ""),
        ]
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="EMPTY_RESULT",
    ) as captured:
        one_shot.run_recovery(
            runner,
            _binding(source),
            recovery_arguments=_recovery_arguments(
                registration,
                credential,
                inspect,
            ),
        )

    assert captured.value.recovery_started is True
    assert len(runner.commands) == 2


def test_cli_preflight_reports_explicit_entrypoint_without_recovery(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [(0, _inspect()), (0, "usage: recovery\n")]
    )

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
    assert "RECOVERY_STARTED=true" not in output
    assert len(runner.commands) == 2


def test_cli_authority_failure_reports_not_started(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    runner = FakeRunner(
        [
            (0, _inspect()),
            (0, "usage: recovery\n"),
            (
                1,
                "KF048_AUTHORITY_PROBE=FAIL:"
                "MANAGER_INSPECT_AUTHORITY_INVALID",
            ),
        ]
    )

    result = one_shot.main(
        [
            "--image",
            IMAGE,
            "--expected-image-id",
            IMAGE_ID,
            "--source-root",
            str(source),
            "authority-preflight",
            "--",
            *_recovery_arguments(
                registration,
                credential,
                inspect,
            ),
        ],
        runner=runner,
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "EXACT_IMAGE_ONE_SHOT=FAIL:" in output
    assert "RECOVERY_STARTED=false" in output
    assert len(runner.commands) == 3


def test_cli_inner_failure_reports_started_and_sanitized_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    runner = FakeRunner(
        [
            (0, _inspect()),
            (0, "usage: recovery\n"),
            (0, "KF048_AUTHORITY_PROBE=PASS\n"),
            (1, SAFE_FAILURE),
        ]
    )

    result = one_shot.main(
        [
            "--image",
            IMAGE,
            "--expected-image-id",
            IMAGE_ID,
            "--source-root",
            str(source),
            "run",
            "--",
            *_recovery_arguments(
                registration,
                credential,
                inspect,
            ),
        ],
        runner=runner,
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "RECOVERY_STARTED=true" in output
    assert (
        "RECOVERY_EXECUTOR=FAIL:"
        "MANAGER_INSPECT_MODE_INVALID"
    ) in output
    assert "PAIRING_ID_RAW_EXPOSED=false" in output
    assert "SECRET_VALUE_EXPOSED=false" in output
    assert len(runner.commands) == 4


def test_failed_module_preflight_never_reaches_kf048_authority(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()

    runner = FakeRunner(
        [
            (0, _inspect()),
            (2, "unrecognized arguments"),
        ]
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="preflight failed",
    ):
        one_shot.preflight_exact_image(
            runner,
            image=IMAGE,
            expected_image_id=IMAGE_ID,
            source_root=str(source),
        )

    assert len(runner.commands) == 2
    assert all(
        "--registration-db" not in command
        for command in runner.commands
    )
    assert all(
        "--credential-db" not in command
        for command in runner.commands
    )
    assert all(
        "--manager-inspect-json" not in command
        for command in runner.commands
    )


@pytest.mark.parametrize(
    "probe_failure",
    (
        "RUNTIME_IDENTITY_MISMATCH",
        "REGISTRATION_DATABASE_NOT_READABLE",
        "REGISTRATION_PARENT_AUTHORITY_INVALID",
        "REGISTRATION_PARENT_NOT_WRITABLE",
        "CREDENTIAL_DATABASE_NOT_READABLE",
        "CREDENTIAL_PARENT_AUTHORITY_INVALID",
        "CREDENTIAL_PARENT_NOT_WRITABLE",
        "MANAGER_INSPECT_AUTHORITY_INVALID",
        "MANAGER_INSPECT_NOT_READABLE",
        "MANAGER_INSPECT_NOT_READ_ONLY",
    ),
)
def test_probe_failure_never_starts_recovery(
    tmp_path: Path,
    probe_failure: str,
) -> None:
    (
        source,
        _private,
        registration,
        credential,
        inspect,
    ) = _inputs(tmp_path)

    runner = FakeRunner(
        [
            (
                1,
                f"KF048_AUTHORITY_PROBE=FAIL:{probe_failure}",
            )
        ]
    )

    with pytest.raises(
        one_shot.ExactImageOneShotError,
        match="authority preflight failed",
    ) as captured:
        one_shot.run_recovery(
            runner,
            _binding(source),
            recovery_arguments=_recovery_arguments(
                registration,
                credential,
                inspect,
            ),
        )

    assert captured.value.recovery_started is False
    assert len(runner.commands) == 1
    assert "-m" not in runner.commands[0]
    assert one_shot.RECOVERY_MODULE not in runner.commands[0]
