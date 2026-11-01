from __future__ import annotations

import argparse
import hashlib
import json
import stat
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "8a57243fce0d347ebb20108f4ec5a2d5d4267486"
PRESERVED_PR_HEAD = "239ea594c643d4990d449187f8b0cabae619e3d7"

INCLUDED = (
    "docs/decisions/n3w-p5-two-board-isolated-e2e-prep-stage-entry.json",
    "protocols/transport/gh-n3w-p5-two-board-isolated-e2e-v1.md",
    "protocols/transport/schemas/gh.n3w-p5-private-input-1.schema.json",
    "protocols/transport/schemas/gh.n3w-p5-evidence-1.schema.json",
    "docs/decisions/n3w-p5-two-board-isolated-e2e-execution-plan.json",
    "firmware/esphome_rc/board_lab/n3w_p5_two_board/child.yml",
    "firmware/esphome_rc/board_lab/n3w_p5_two_board/relay.yml",
    "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/__init__.py",
    "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.h",
    "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp",
    "infra/compose/n3w-p5-two-board-isolated/docker-compose.yml",
    "infra/compose/n3w-p5-two-board-isolated/mosquitto.conf",
    "infra/compose/n3w-p5-two-board-isolated/acl",
    "infra/compose/n3w-p5-two-board-isolated/.env.example",
    "infra/compose/n3w-p5-two-board-isolated/lab_admin.py",
    "infra/compose/n3w-p5-two-board-isolated/homeassistant/configuration.yaml",
    "infra/compose/n3w-p5-two-board-isolated/homeassistant/core.config_entries.template.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_safe_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"unsafe template member: {path}")
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise SystemExit(f"template member is not regular: {path}")
    if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
        raise SystemExit(f"bytecode member rejected: {path}")


def deterministic_tar(source: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_dir():
                continue
            require_safe_file(path)
            relative = path.relative_to(source)
            info = archive.gettarinfo(str(path), arcname=str(relative))
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as handle:
                archive.addfile(info, handle)


def build(output: Path) -> dict[str, object]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="n3w-p5-template-") as temporary:
        package = Path(temporary) / "package"
        package.mkdir()
        manifest: dict[str, str] = {}
        for relative_text in INCLUDED:
            source = ROOT / relative_text
            require_safe_file(source)
            target = package / relative_text
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            manifest[relative_text] = sha256_file(source)

        binding = {
            "schema": "gh.n3w-p5-public-execution-template/1",
            "status": "TEMPLATE_ONLY_NOT_PHYSICAL_AUTHORIZATION",
            "base_sha": BASE_SHA,
            "preserved_pr": 276,
            "preserved_pr_head": PRESERVED_PR_HEAD,
            "physical_authorization_included": False,
            "board_mac_binding_included": False,
            "secret_values_included": False,
            "private_input_required": True,
            "files": manifest,
        }
        binding_path = package / "PUBLIC_TEMPLATE_BINDING.json"
        binding_path.write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for member in sorted(p for p in package.rglob("*") if p.is_file()):
            if member.name == "SHA256SUMS":
                continue
            sums.append(f"{sha256_file(member)}  {member.relative_to(package)}")
        (package / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        deterministic_tar(package, output)
    return {
        "schema": "gh.n3w-p5-public-execution-template-build/1",
        "status": "passed",
        "output": str(output),
        "sha256": sha256_file(output),
        "member_count": len(INCLUDED) + 2,
        "physical_authorization_included": False,
        "secret_values_included": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
