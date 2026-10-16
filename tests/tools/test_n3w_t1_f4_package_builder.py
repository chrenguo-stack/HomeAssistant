from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools/n3w_t1_f4_package_builder.py"
HOST = ROOT / "tools/n3w_t1_f4_activation_host.py"


def load(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_builder_emits_exact_host_install_map(tmp_path: Path) -> None:
    builder = load(BUILDER, "n3w_t1_f4_package_builder")
    host = load(HOST, "n3w_t1_f4_activation_host_for_package")
    destination = tmp_path / "package"
    source_head = "a" * 40

    report = builder.build_package(
        ROOT,
        destination,
        source_head=source_head,
    )

    manifest_path = destination / builder.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = {record["path"] for record in manifest["files"]}

    assert report["status"] == "PASS"
    assert report["source_head"] == source_head
    assert report["file_count"] == len(host.INSTALL_MAP)
    assert paths == set(host.INSTALL_MAP)
    assert manifest["schema"] == host.PACKAGE_SCHEMA
    assert manifest["secret_values_included"] is False
    assert manifest["production_service_start"] is False
    assert manifest["board_access"] is False

    for record in manifest["files"]:
        target = destination / record["path"]
        assert target.is_file()
        assert not target.is_symlink()
        assert record["size"] == target.stat().st_size
        assert record["sha256"] == builder._sha256(target)


def test_builder_rejects_reuse_and_invalid_source_head(
    tmp_path: Path,
) -> None:
    builder = load(BUILDER, "n3w_t1_f4_package_builder_reject")
    destination = tmp_path / "package"

    with pytest.raises(builder.PackageBuildError, match="source_head_invalid"):
        builder.build_package(
            ROOT,
            destination,
            source_head="not-a-sha",
        )

    builder.build_package(
        ROOT,
        destination,
        source_head="b" * 40,
    )
    with pytest.raises(
        builder.PackageBuildError,
        match="destination_already_exists",
    ):
        builder.build_package(
            ROOT,
            destination,
            source_head="b" * 40,
        )
