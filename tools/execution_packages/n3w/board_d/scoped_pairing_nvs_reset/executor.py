from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pwd
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.execution_packages.n3w.board_d.post_r4_write_target_preflight import executor as base

SCHEMA = "n3w.board-d.scoped-pairing-nvs-reset/1"
CLAIM_SCHEMA = "n3w.board-d.scoped-pairing-nvs-reset-claim/1"
PREFLIGHT_SCHEMA = "n3w.board-d.post-r4-write-target-preflight/1"

EXPECTED_HARDWARE_ID_SHA256 = "3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5"
EXPECTED_BOOTLOADER_SHA256 = "ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46"
EXPECTED_PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
NVS_OFFSET = 0x790000
NVS_SIZE = 0x70000
ERASED_SHA256 = hashlib.sha256(b"\xff" * NVS_SIZE).hexdigest()
AUTHORIZATION_ID = "N3W_T1_BOARD_D_SCOPED_PAIRING_NVS_RESET_20261025_01"
CONFIRMATION = "ERASE BOARD D SCOPED PAIRING NVS: YES"
PREFLIGHT_MAX_AGE_SECONDS = 900
AUTHORIZATION_STATE_RELATIVE = Path(".local/state/n3w/board-d-scoped-pairing-nvs-reset")


class StopExecution(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_private_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.exists() or path.is_symlink():
        raise StopExecution("private evidence path collision")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if path.exists():
            path.chmod(0o600)


def read_json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("preflight record missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("preflight record invalid") from error
    if not isinstance(value, dict):
        raise StopExecution("preflight record invalid")
    return value


def require_preflight(path: Path, port: str) -> dict[str, object]:
    value = read_json(path)
    if value.get("schema") != PREFLIGHT_SCHEMA or value.get("status") != "PASS":
        raise StopExecution("preflight status invalid")
    for key in ("persistent_mutation", "flash_write", "nvs_write", "write_command_present", "write_authorization_granted"):
        if value.get(key) is not False:
            raise StopExecution("preflight mutation boundary invalid")
    if value.get("replay_permitted") is not False:
        raise StopExecution("preflight replay boundary invalid")
    if value.get("artifact") != base.artifact_binding_payload():
        raise StopExecution("preflight artifact binding drifted")
    created = value.get("created_at")
    if not isinstance(created, str):
        raise StopExecution("preflight timestamp missing")
    try:
        created_at = dt.datetime.fromisoformat(created)
    except ValueError as error:
        raise StopExecution("preflight timestamp invalid") from error
    if created_at.tzinfo is None:
        raise StopExecution("preflight timestamp invalid")
    age = (utc_now() - created_at.astimezone(dt.timezone.utc)).total_seconds()
    if age < -30 or age > PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("preflight expired")
    board = value.get("board")
    if not isinstance(board, dict):
        raise StopExecution("preflight board missing")
    if board.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("preflight Board D identity mismatch")
    if board.get("bootloader_sha256") != EXPECTED_BOOTLOADER_SHA256:
        raise StopExecution("preflight bootloader mismatch")
    if board.get("partition_table_sha256") != EXPECTED_PARTITION_TABLE_SHA256:
        raise StopExecution("preflight partition table mismatch")
    if board.get("bootloader_matches_release") is not True or board.get("partition_table_matches_release") is not True:
        raise StopExecution("preflight release binding mismatch")
    expected_port_sha = hashlib.sha256(port.encode("utf-8")).hexdigest()
    if board.get("port_sha256") != expected_port_sha:
        raise StopExecution("preflight serial port binding mismatch")
    return value


def fresh_board_preclaim(port: str, release_bundle: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="n3w-board-d-scoped-nvs-preclaim-") as raw:
        files = base.validate_release_bundle(release_bundle, Path(raw))
        base.verify_esptool_version()
        base.verify_image(files["firmware.bin"])
        board = base.probe_board(port)
    if board["hardware_id_sha256"] != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("Board D identity mismatch")
    if board["bootloader_sha256"] != EXPECTED_BOOTLOADER_SHA256:
        raise StopExecution("bootloader drift")
    if board["partition_table_sha256"] != EXPECTED_PARTITION_TABLE_SHA256:
        raise StopExecution("partition table drift")
    if board["chip"] != "ESP32-C6" or board["flash_size"] != "8MB":
        raise StopExecution("Board D chip or flash mismatch")
    if board["secure_boot"] is not False or board["flash_encryption"] is not False:
        raise StopExecution("Board D security state blocks erase")
    return board


def noreset_read(port: str, offset: int, size: int, destination: Path, *, before_no_reset: bool) -> str:
    args = base.esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub"]
    if before_no_reset:
        args += ["--before", "no-reset"]
    args += ["--after", "no-reset", "read-flash", hex(offset), hex(size), str(destination)]
    base.run_capture(args, port=port)
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("no-reset flash readback size mismatch")
    return sha256_file(destination)


def erase_nvs_noreset(port: str) -> None:
    args = base.esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--no-stub",
        "--after",
        "no-reset",
        "erase-region",
        hex(NVS_OFFSET),
        hex(NVS_SIZE),
    ]
    base.run_capture(args, port=port)


def non_ff_count(path: Path) -> int:
    total = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            total += sum(value != 0xFF for value in block)
    return total


def authorization_state_root() -> Path:
    account = pwd.getpwuid(os.getuid())
    home = Path(account.pw_dir)
    if not home.is_absolute():
        raise StopExecution("authorization account home is not absolute")
    return home / AUTHORIZATION_STATE_RELATIVE


def prepare_authorization_state_root() -> Path:
    root = authorization_state_root()
    if root.is_symlink():
        raise StopExecution("authorization state root symlink forbidden")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    metadata = root.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise StopExecution("authorization state root ownership or mode invalid")
    return root


def authorization_run_root(root: Path) -> Path:
    token = hashlib.sha256(AUTHORIZATION_ID.encode()).hexdigest()
    return root / ("authorization-" + token)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require_authorization_unclaimed(root: Path) -> Path:
    run_root = authorization_run_root(root)
    if run_root.exists() or run_root.is_symlink():
        raise StopExecution("authorization already claimed")
    return run_root


def claim_authorization(run_root: Path) -> None:
    try:
        run_root.mkdir(mode=0o700)
    except FileExistsError as error:
        raise StopExecution("authorization already claimed") from error
    if run_root.is_symlink() or not run_root.is_dir():
        raise StopExecution("authorization claim directory invalid")
    metadata = run_root.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise StopExecution("authorization claim directory ownership or mode invalid")
    fsync_directory(run_root.parent)


def run_preflight(args: argparse.Namespace) -> int:
    require_preflight(Path(args.preflight_json), args.port)
    board = fresh_board_preclaim(args.port, Path(args.release_bundle))
    print("SCOPED_NVS_RESET_PREEXECUTION=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"NVS_OFFSET={hex(NVS_OFFSET)}")
    print(f"NVS_SIZE={hex(NVS_SIZE)}")
    print("NVS_ERASE_EXECUTED=false")
    print("PERSISTENT_MUTATION=false")
    print(f"REQUIRED_AUTHORIZATION_ID={AUTHORIZATION_ID}")
    print(f"REQUIRED_CONFIRMATION={CONFIRMATION}")
    return 0


def run_execute(args: argparse.Namespace) -> int:
    if args.authorization_id != AUTHORIZATION_ID:
        raise StopExecution("authorization id invalid")
    if args.confirm != CONFIRMATION:
        raise StopExecution("confirmation invalid")

    state_root = prepare_authorization_state_root()
    run_root = require_authorization_unclaimed(state_root)

    preflight = require_preflight(Path(args.preflight_json), args.port)
    board = fresh_board_preclaim(args.port, Path(args.release_bundle))

    with tempfile.TemporaryDirectory(
        prefix="n3w-board-d-scoped-nvs-backup-",
        dir=state_root,
    ) as backup_dir:
        backup_staging = Path(backup_dir) / "nvs-before.bin"
        backup_sha = noreset_read(
            args.port,
            NVS_OFFSET,
            NVS_SIZE,
            backup_staging,
            before_no_reset=False,
        )
        backup_staging.chmod(0o600)
        backup_non_ff = non_ff_count(backup_staging)

        claim_authorization(run_root)
        backup = run_root / "nvs-before.bin"
        os.replace(backup_staging, backup)
        backup.chmod(0o600)
        fsync_directory(run_root)

    erased = run_root / "nvs-erased-preboot.bin"
    bootloader = run_root / "bootloader-post.bin"
    partition = run_root / "partition-table-post.bin"
    claim_path = run_root / "claim.json"
    result_path = run_root / "result.json"

    claim = {
        "schema": CLAIM_SCHEMA,
        "status": "CLAIMED",
        "authorization_id": args.authorization_id,
        "authorization_consumed": True,
        "replay_allowed": False,
        "claimed_at": utc_now().isoformat(),
        "preflight_sha256": sha256_file(Path(args.preflight_json)),
        "preflight_created_at": preflight["created_at"],
        "hardware_id_sha256": board["hardware_id_sha256"],
        "bootloader_sha256": board["bootloader_sha256"],
        "partition_table_sha256": board["partition_table_sha256"],
        "nvs_offset": hex(NVS_OFFSET),
        "nvs_size": NVS_SIZE,
        "nvs_backup_sha256": backup_sha,
        "nvs_backup_non_ff_bytes": backup_non_ff,
    }
    write_private_json(claim_path, claim)
    fsync_directory(run_root)

    try:
        erase_nvs_noreset(args.port)
        erased_sha = noreset_read(args.port, NVS_OFFSET, NVS_SIZE, erased, before_no_reset=True)
        erased.chmod(0o600)
        erased_non_ff = non_ff_count(erased)
        if erased_sha != ERASED_SHA256 or erased_non_ff != 0:
            raise StopExecution("preboot erased NVS oracle failed")

        bootloader_sha = noreset_read(
            args.port,
            base.BOOTLOADER_OFFSET,
            base.MEMBER_BINDINGS["bootloader.bin"][0],
            bootloader,
            before_no_reset=True,
        )
        bootloader.chmod(0o600)
        partition_sha = noreset_read(
            args.port,
            base.PARTITION_TABLE_OFFSET,
            base.MEMBER_BINDINGS["partitions.bin"][0],
            partition,
            before_no_reset=True,
        )
        partition.chmod(0o600)

        if bootloader_sha != EXPECTED_BOOTLOADER_SHA256:
            raise StopExecution("protected bootloader changed")
        if partition_sha != EXPECTED_PARTITION_TABLE_SHA256:
            raise StopExecution("protected partition table changed")

        result = {
            "schema": SCHEMA,
            "status": "CLOSED_PASS_PREBOOT",
            "authorization_consumed": True,
            "replay_allowed": False,
            "closed_at": utc_now().isoformat(),
            "hardware_id_sha256": board["hardware_id_sha256"],
            "nvs_offset": hex(NVS_OFFSET),
            "nvs_size": NVS_SIZE,
            "nvs_backup_sha256": backup_sha,
            "nvs_backup_non_ff_bytes": backup_non_ff,
            "nvs_erased_preboot_sha256": erased_sha,
            "nvs_erased_preboot_non_ff_bytes": erased_non_ff,
            "bootloader_sha256": bootloader_sha,
            "partition_table_sha256": partition_sha,
            "application_flash_rewrite": False,
            "full_flash_erase": False,
            "application_start_performed": False,
            "t1_mutation": False,
        }
        write_private_json(result_path, result)
    except Exception as error:
        failure = {
            "schema": SCHEMA,
            "status": "STOPPED_AFTER_CLAIM",
            "authorization_consumed": True,
            "replay_allowed": False,
            "closed_at": utc_now().isoformat(),
            "failure_type": type(error).__name__,
            "failure_detail_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
            "application_start_performed": False,
            "t1_mutation": False,
        }
        if not result_path.exists():
            write_private_json(result_path, failure)
        raise

    print("SCOPED_NVS_ERASE=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"NVS_BACKUP_SHA256={backup_sha}")
    print(f"NVS_BACKUP_NON_FF_BYTES={backup_non_ff}")
    print(f"NVS_ERASED_PREBOOT_SHA256={ERASED_SHA256}")
    print("NVS_ERASED_PREBOOT_NON_FF_BYTES=0")
    print("BOOTLOADER_UNCHANGED=true")
    print("PARTITION_TABLE_UNCHANGED=true")
    print("APPLICATION_FLASH_REWRITE=false")
    print("FULL_FLASH_ERASE=false")
    print("APPLICATION_START_PERFORMED=false")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_ALLOWED=false")
    print(f"PRIVATE_RESULT_SHA256={sha256_file(result_path)}")
    print(f"NEXT_REQUIRED_ACTION=START_APPLICATION_AFTER_SCOPED_NVS_RESET")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight")
    preflight.add_argument("--port", required=True)
    preflight.add_argument("--release-bundle", required=True)
    preflight.add_argument("--preflight-json", required=True)
    preflight.set_defaults(func=run_preflight)

    execute = commands.add_parser("execute")
    execute.add_argument("--port", required=True)
    execute.add_argument("--release-bundle", required=True)
    execute.add_argument("--preflight-json", required=True)
    execute.add_argument("--authorization-id", required=True)
    execute.add_argument("--confirm", required=True)
    execute.set_defaults(func=run_execute)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (StopExecution, base.StopExecution, OSError, RuntimeError, ValueError) as error:
        print(f"STOP={error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
