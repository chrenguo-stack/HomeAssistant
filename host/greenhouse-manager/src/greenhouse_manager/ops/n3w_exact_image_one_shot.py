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
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")


class ExactImageOneShotError(RuntimeError):
    """A fail-closed exact-image one-shot execution error."""


@dataclass(frozen=True, slots=True)
class ExactImageBinding:
    image_id: str
    source_root: Path
    product_entrypoint: str
    one_shot_entrypoint: str = "python"


def _absolute_directory(value: str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ExactImageOneShotError(f"{label} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ExactImageOneShotError(f"{label} is unavailable") from error
    if not resolved.is_dir() or "," in str(resolved):
        raise ExactImageOneShotError(f"{label} is invalid")
    return resolved


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
        raise ExactImageOneShotError("expected product entrypoint is invalid")
    code, output = runner.run(("docker", "image", "inspect", image))
    if code != 0:
        raise ExactImageOneShotError("exact image inspection failed")
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ExactImageOneShotError("exact image inspection returned invalid JSON") from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise ExactImageOneShotError("exact image inspection is not unique")
    document = documents[0]
    if not isinstance(document, dict) or document.get("Id") != expected_image_id:
        raise ExactImageOneShotError("exact image ID binding mismatch")
    config = document.get("Config")
    if not isinstance(config, dict):
        raise ExactImageOneShotError("exact image configuration is incomplete")
    entrypoint = config.get("Entrypoint")
    if entrypoint != [expected_product_entrypoint]:
        raise ExactImageOneShotError("product image entrypoint binding mismatch")
    return ExactImageBinding(
        image_id=expected_image_id,
        source_root=_absolute_directory(source_root, label="source root"),
        product_entrypoint=expected_product_entrypoint,
    )


def build_preflight_command(binding: ExactImageBinding) -> tuple[str, ...]:
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
        f"type=bind,src={binding.source_root},dst={SOURCE_TARGET},readonly",
        "--env",
        f"PYTHONPATH={PYTHONPATH_TARGET}",
        "--entrypoint",
        binding.one_shot_entrypoint,
        binding.image_id,
        "-m",
        RECOVERY_MODULE,
        "--help",
    )


def build_recovery_command(
    binding: ExactImageBinding,
    *,
    state_root: str,
    recovery_arguments: Sequence[str],
) -> tuple[str, ...]:
    state = _absolute_directory(state_root, label="state root")
    if not recovery_arguments or recovery_arguments[0] == "--":
        raise ExactImageOneShotError("recovery arguments are invalid")
    return (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "32",
        "--mount",
        f"type=bind,src={binding.source_root},dst={SOURCE_TARGET},readonly",
        "--mount",
        f"type=bind,src={state},dst={state}",
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
    code, _output = runner.run(build_preflight_command(binding))
    if code != 0:
        raise ExactImageOneShotError("isolated recovery module preflight failed")
    return binding


def run_recovery(
    runner: CommandRunner,
    binding: ExactImageBinding,
    *,
    state_root: str,
    recovery_arguments: Sequence[str],
) -> str:
    command = build_recovery_command(
        binding,
        state_root=state_root,
        recovery_arguments=recovery_arguments,
    )
    code, output = runner.run(command)
    if code != 0 or not output.strip():
        raise ExactImageOneShotError("isolated recovery module execution failed")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preflight or run N3-W recovery with an explicit exact-image entrypoint"
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-image-id", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument(
        "--expected-product-entrypoint", default="greenhouse-manager"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    execute = subparsers.add_parser("run")
    execute.add_argument("--state-root", required=True)
    execute.add_argument("recovery_arguments", nargs=argparse.REMAINDER)
    return parser


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
            expected_product_entrypoint=args.expected_product_entrypoint,
        )
        if args.command == "run":
            recovery_arguments = list(args.recovery_arguments)
            if recovery_arguments and recovery_arguments[0] == "--":
                recovery_arguments.pop(0)
            output = run_recovery(
                selected_runner,
                binding,
                state_root=args.state_root,
                recovery_arguments=recovery_arguments,
            )
            print(output, end="" if output.endswith("\n") else "\n")
    except ExactImageOneShotError as error:
        print(f"EXACT_IMAGE_ONE_SHOT=FAIL:{error}")
        print("RECOVERY_STARTED=false")
        return 1

    print("EXACT_IMAGE_ONE_SHOT=PASS")
    print(f"EXACT_IMAGE_ID={binding.image_id}")
    print(f"PRODUCT_ENTRYPOINT={binding.product_entrypoint}")
    print(f"EXPLICIT_ONE_SHOT_ENTRYPOINT={binding.one_shot_entrypoint}")
    print("RECOVERY_MODULE_PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
