import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
EXECUTOR = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_f_board_b_preflight/executor.py"

spec = spec_from_file_location("gate_f_board_b_preflight", EXECUTOR)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_frozen_binding_constants() -> None:
    assert module.PRODUCT_SOURCE == "b2419d17c198a85b7b50d9c1771544c2e3a0ab6b"
    assert module.PRODUCT_TREE == "c138ac3efa9b23b4d083f0cb5248089fef493416"
    assert module.ARTIFACT_ID == 11273613346
    assert module.ARTIFACT_ZIP_SHA256 == "57465f56362404b269f80adb21994a22ec0d1acdcc724f9a163c84b6df3eea4d"
    assert module.RELEASE_BUNDLE_SHA256 == "7bf9980e50d2baa26459ca020002e8947d8038409dcb564a0101131be1799a6a"
    assert module.APPLICATION_SHA256 == "474e738068fc894b20cfe5f647a6112b66c141aa86c873d414d8ed183679e43c"
    assert module.OTADATA_SHA256 == "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    assert module.PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"


def test_hardware_id_derivation_matches_product_contract() -> None:
    raw = ":".join(("02", "00", "00", "00", "00", "02"))
    expected_id = "ghw-c6-020000000002"
    assert module.public_identity_sha256(raw) == hashlib.sha256(expected_id.encode("utf-8")).hexdigest()


def test_preflight_is_read_only() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "read-flash" in source
    assert "get-security-info" in source
    assert "flash-id" in source
    assert "write-flash" not in source
    assert "erase-flash" not in source
    assert '"flash_write": False' in source
    assert '"persistent_mutation": False' in source


def test_preflight_age_bound_is_fifteen_minutes() -> None:
    assert module.PREFLIGHT_MAX_AGE_SECONDS == 900
