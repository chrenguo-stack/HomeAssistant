"""Run the expired-first recovery module with an explicit exact-image entrypoint."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .t1_migration_readiness import CommandRunner, SubprocessRunner

RECOVERY_MODULE = "greenhouse_manager.ops.n3w_expired_first_recovery_executor"
SOURCE_TARGET = "/workspace"
PYTHONPATH_TARGET = f"{SOURCE_TARGET}/host/greenhouse-manager/src"
EXPECTED_RUNTIME_UID = 999
EXPECTED_RUNTIME_GID = 999
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_SAFE_FAILURE = re.compile(r"RECOVERY_EXECUTOR=FAIL:([A-Z0-9_]+)")

_AUTHORITY_PROBE_SCRIPT = r"""
import os
import stat
import sys
from pathlib import Path

EXPECTED_UID = 999
EXPECTED_GID = 999


def fail(code: str) -> None:
    print(f"KF048_AUTHORITY_PROBE=FAIL:{code}", file=sys.stderr)
    raise SystemExit(1)


if os.geteuid() != EXPECTED_UID or os.getegid() != EXPECTED_GID:
    fail("RUNTIME_IDENTITY_MISMATCH")

registration = Path(sys.argv[1])
credential = Path(sys.argv[2])
inspect_path = Path(sys.argv[3])

for label, database in (
    ("REGISTRATION", registration),
    ("CREDENTIAL", credential),
):
    if not database.is_file():
        fail(f"{label}_DATABASE_NOT_REGULAR")

    try:
        with database.open("rb") as stream:
            stream.read(1)
    except OSError:
        fail(f"{label}_DATABASE_NOT_READABLE")

    parent = database.parent
    try:
        metadata = parent.stat()
    except OSError:
        fail(f"{label}_PARENT_UNAVAILABLE")

    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != EXPECTED_UID
        or metadata.st_gid != EXPECTED_GID
    ):
        fail(f"{label}_PARENT_AUTHORITY_INVALID")

    probe = parent / (
        f".kf048-authority-probe-{os.getpid()}-{label.lower()}"
    )
    try:
        descriptor = os.open(
            probe,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.close(descriptor)
        probe.unlink()
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        fail(f"{label}_PARENT_NOT_WRITABLE")

try:
    inspect_metadata = inspect_path.stat()
except OSError:
    fail("MANAGER_INSPECT_UNAVAILABLE")

if (
    not stat.S_ISREG(inspect_metadata.st_mode)
    or stat.S_IMODE(inspect_metadata.st_mode) != 0o600
    or inspect_metadata.st_uid != EXPECTED_UID
    or inspect_metadata.st_gid != EXPECTED_GID
):
    fail("MANAGER_INSPECT_AUTHORITY_INVALID")

try:
    with inspect_path.open("rb") as stream:
        stream.read(1)
except OSError:
    fail("MANAGER_INSPECT_NOT_READABLE")

try:
    descriptor = os.open(inspect_path, os.O_WRONLY)
except OSError:
    pass
else:
    os.close(descriptor)
    fail("MANAGER_INSPECT_NOT_READ_ONLY")

print("KF048_AUTHORITY_PROBE=PASS")
""".strip()


class ExactImageOneShotError(RuntimeError):
    """A fail-closed exact-image one-shot execution error."""

    def __init__(
        self,
        message: str,
        *,
        recovery_started: bool = False,
        safe_lines: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.recovery_started = recovery_started
        self.safe_lines = tuple(safe_lines)


@dataclass(frozen=True, slots=True)
class ExactImageBinding:
    image_id: str
    source_root: Path
    product_entrypoint: str
    one_shot_entrypoint: str = "python"


@dataclass(frozen=True, slots=True)
class RecoveryPaths:
    registration_db: Path
    credential_db: Path
    manager_inspect_json: Path

    @property
    def database_parents(self) -> tuple[Path, ...]:
        unique: list[Path] = []
        for parent in (
            self.registration_db.parent,
            self.credential_db.parent,
        ):
            if parent not in unique:
                unique.append(parent)
        return tuple(unique)


def _absolute_directory(value: str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ExactImageOneShotError(f"{label} must be absolute")
    if path.is_symlink():
        raise ExactImageOneShotError(f"{label} must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ExactImageOneShotError(f"{label} is unavailable") from error
    if not resolved.is_dir() or path != resolved or "," in str(resolved):
        raise ExactImageOneShotError(f"{label} is invalid")
    return resolved


def _absolute_regular_file(value: str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ExactImageOneShotError(f"{label} must be absolute")
    if path.is_symlink():
        raise ExactImageOneShotError(f"{label} must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ExactImageOneShotError(f"{label} is unavailable") from error
    if (
        not resolved.is_file()
        or path != resolved
        or "," in str(resolved)
        or "," in str(resolved.parent)
    ):
        raise ExactImageOneShotError(f"{label} is invalid")
    return resolved


def _option_value(arguments: Sequence[str], option: str) -> str:
    values: list[str] = []
    index = 0
    prefix = f"{option}="

    while index < len(arguments):
        token = arguments[index]

        if token == option:
            if index + 1 >= len(arguments):
                raise ExactImageOneShotError(
                    f"{option} value is missing"
                )
            values.append(arguments[index + 1])
            index += 2
            continue

        if token.startswith(prefix):
            values.append(token[len(prefix) :])

        index += 1

    if len(values) != 1 or not values[0]:
        raise ExactImageOneShotError(
            f"{option} must be supplied exactly once"
        )

    return values[0]


def _recovery_paths(
    recovery_arguments: Sequence[str],
) -> RecoveryPaths:
    if not recovery_arguments or recovery_arguments[0] == "--":
        raise ExactImageOneShotError("recovery arguments are invalid")

    return RecoveryPaths(
        registration_db=_absolute_regular_file(
            _option_value(
                recovery_arguments,
                "--registration-db",
            ),
            label="registration database",
        ),
        credential_db=_absolute_regular_file(
            _option_value(
                recovery_arguments,
                "--credential-db",
            ),
            label="credential database",
        ),
        manager_inspect_json=_absolute_regular_file(
            _option_value(
                recovery_arguments,
                "--manager-inspect-json",
            ),
            label="manager inspect json",
        ),
    )


def _inspect_binding(
    runner: CommandRunner,
    *,
    image: str,
    expected_image_id: str,
    source_root: str,
    expected_product_entrypoint: str,
) -> ExactImageBinding:
    if _IMAGE_ID.fullmatch(expected_image_id) is None:
        raise ExactImageOneShotError("expected image ID is invalid")

    if expected_product_entrypoint != "greenhouse-manager":
        raise ExactImageOneShotError(
            "expected product entrypoint is invalid"
        )

    code, output = runner.run(
        ("docker", "image", "inspect", image)
    )
    if code != 0:
        raise ExactImageOneShotError(
            "exact image inspection failed"
        )

    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ExactImageOneShotError(
            "exact image inspection returned invalid JSON"
        ) from error

    if not isinstance(documents, list) or len(documents) != 1:
        raise ExactImageOneShotError(
            "exact image inspection is not unique"
        )

    document = documents[0]
    if (
        not isinstance(document, dict)
        or document.get("Id") != expected_image_id
    ):
        raise ExactImageOneShotError(
            "exact image ID binding mismatch"
        )

    config = document.get("Config")
    if not isinstance(config, dict):
        raise ExactImageOneShotError(
            "exact image configuration is incomplete"
        )

    entrypoint = config.get("Entrypoint")
    if entrypoint != [expected_product_entrypoint]:
        raise ExactImageOneShotError(
            "product image entrypoint binding mismatch"
        )

    return ExactImageBinding(
        image_id=expected_image_id,
        source_root=_absolute_directory(
            source_root,
            label="source root",
        ),
        product_entrypoint=expected_product_entrypoint,
    )


def build_preflight_command(
    binding: ExactImageBinding,
) -> tuple[str, ...]:
    return (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "32",
        "--mount",
        (
            "type=bind,"
            f"src={binding.source_root},"
            f"dst={SOURCE_TARGET},readonly"
        ),
        "--env",
        f"PYTHONPATH={PYTHONPATH_TARGET}",
        "--entrypoint",
        binding.one_shot_entrypoint,
        binding.image_id,
        "-m",
        RECOVERY_MODULE,
        "--help",
    )


def _private_mount_arguments(
    paths: RecoveryPaths,
) -> tuple[str, ...]:
    arguments: list[str] = []

    for parent in paths.database_parents:
        arguments.extend(
            (
                "--mount",
                f"type=bind,src={parent},dst={parent}",
            )
        )

    arguments.extend(
        (
            "--mount",
            (
                "type=bind,"
                f"src={paths.manager_inspect_json},"
                f"dst={paths.manager_inspect_json},readonly"
            ),
        )
    )

    return tuple(arguments)


def build_authority_probe_command(
    binding: ExactImageBinding,
    *,
    recovery_arguments: Sequence[str],
) -> tuple[str, ...]:
    paths = _recovery_paths(recovery_arguments)

    return (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "32",
        "--mount",
        (
            "type=bind,"
            f"src={binding.source_root},"
            f"dst={SOURCE_TARGET},readonly"
        ),
        *_private_mount_arguments(paths),
        "--entrypoint",
        binding.one_shot_entrypoint,
        binding.image_id,
        "-c",
        _AUTHORITY_PROBE_SCRIPT,
        str(paths.registration_db),
        str(paths.credential_db),
        str(paths.manager_inspect_json),
    )


def build_recovery_command(
    binding: ExactImageBinding,
    *,
    recovery_arguments: Sequence[str],
) -> tuple[str, ...]:
    paths = _recovery_paths(recovery_arguments)

    return (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "32",
        "--mount",
        (
            "type=bind,"
            f"src={binding.source_root},"
            f"dst={SOURCE_TARGET},readonly"
        ),
        *_private_mount_arguments(paths),
        "--env",
        f"PYTHONPATH={PYTHONPATH_TARGET}",
        "--entrypoint",
        binding.one_shot_entrypoint,
        binding.image_id,
        "-m",
        RECOVERY_MODULE,
        *recovery_arguments,
    )


def preflight_exact_image(
    runner: CommandRunner,
    *,
    image: str,
    expected_image_id: str,
    source_root: str,
    expected_product_entrypoint: str = "greenhouse-manager",
) -> ExactImageBinding:
    binding = _inspect_binding(
        runner,
        image=image,
        expected_image_id=expected_image_id,
        source_root=source_root,
        expected_product_entrypoint=expected_product_entrypoint,
    )

    code, _output = runner.run(
        build_preflight_command(binding)
    )
    if code != 0:
        raise ExactImageOneShotError(
            "isolated recovery module preflight failed"
        )

    return binding


def preflight_recovery_authority(
    runner: CommandRunner,
    binding: ExactImageBinding,
    *,
    recovery_arguments: Sequence[str],
) -> None:
    command = build_authority_probe_command(
        binding,
        recovery_arguments=recovery_arguments,
    )
    code, output = runner.run(command)

    if (
        code != 0
        or output.strip() != "KF048_AUTHORITY_PROBE=PASS"
    ):
        raise ExactImageOneShotError(
            "isolated recovery authority preflight failed"
        )


def _sanitized_inner_failure(
    output: str,
) -> tuple[str, ...]:
    lines = tuple(
        line.strip()
        for line in output.splitlines()
        if line.strip()
    )

    if len(lines) == 3:
        match = _SAFE_FAILURE.fullmatch(lines[0])
        if (
            match is not None
            and lines[1] == "PAIRING_ID_RAW_EXPOSED=false"
            and lines[2] == "SECRET_VALUE_EXPOSED=false"
        ):
            return (
                f"RECOVERY_EXECUTOR=FAIL:{match.group(1)}",
                "PAIRING_ID_RAW_EXPOSED=false",
                "SECRET_VALUE_EXPOSED=false",
            )

    return (
        "RECOVERY_EXECUTOR=FAIL:"
        "INNER_RECOVERY_FAILURE_UNCLASSIFIED",
    )


def run_recovery(
    runner: CommandRunner,
    binding: ExactImageBinding,
    *,
    recovery_arguments: Sequence[str],
) -> str:
    preflight_recovery_authority(
        runner,
        binding,
        recovery_arguments=recovery_arguments,
    )

    command = build_recovery_command(
        binding,
        recovery_arguments=recovery_arguments,
    )
    code, output = runner.run(command)

    if code != 0:
        raise ExactImageOneShotError(
            "isolated recovery module execution failed",
            recovery_started=True,
            safe_lines=_sanitized_inner_failure(output),
        )

    if not output.strip():
        raise ExactImageOneShotError(
            (
                "isolated recovery module execution failed:"
                "EMPTY_RESULT"
            ),
            recovery_started=True,
        )

    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight or run N3-W recovery with an explicit "
            "exact-image entrypoint"
        )
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-image-id", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument(
        "--expected-product-entrypoint",
        default="greenhouse-manager",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )
    subparsers.add_parser("preflight")

    authority = subparsers.add_parser(
        "authority-preflight"
    )
    authority.add_argument(
        "recovery_arguments",
        nargs=argparse.REMAINDER,
    )

    execute = subparsers.add_parser("run")
    execute.add_argument(
        "recovery_arguments",
        nargs=argparse.REMAINDER,
    )

    return parser


def _remainder(
    arguments: Sequence[str],
) -> list[str]:
    result = list(arguments)
    if result and result[0] == "--":
        result.pop(0)
    return result


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    args = _parser().parse_args(argv)
    selected_runner = runner or SubprocessRunner()

    try:
        binding = preflight_exact_image(
            selected_runner,
            image=args.image,
            expected_image_id=args.expected_image_id,
            source_root=args.source_root,
            expected_product_entrypoint=(
                args.expected_product_entrypoint
            ),
        )

        if args.command == "authority-preflight":
            preflight_recovery_authority(
                selected_runner,
                binding,
                recovery_arguments=_remainder(
                    args.recovery_arguments
                ),
            )

        elif args.command == "run":
            output = run_recovery(
                selected_runner,
                binding,
                recovery_arguments=_remainder(
                    args.recovery_arguments
                ),
            )
            print(
                output,
                end="" if output.endswith("\n") else "\n",
            )

    except ExactImageOneShotError as error:
        print(f"EXACT_IMAGE_ONE_SHOT=FAIL:{error}")

        for line in error.safe_lines:
            print(line)

        started = (
            "true"
            if error.recovery_started
            else "false"
        )
        print(f"RECOVERY_STARTED={started}")
        return 1

    print("EXACT_IMAGE_ONE_SHOT=PASS")
    print(f"EXACT_IMAGE_ID={binding.image_id}")
    print(
        f"PRODUCT_ENTRYPOINT={binding.product_entrypoint}"
    )
    print(
        "EXPLICIT_ONE_SHOT_ENTRYPOINT="
        f"{binding.one_shot_entrypoint}"
    )
    print("RECOVERY_MODULE_PREFLIGHT=PASS")

    if args.command == "authority-preflight":
        print("KF048_AUTHORITY_PREFLIGHT=PASS")
    elif args.command == "run":
        print("RECOVERY_STARTED=true")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
