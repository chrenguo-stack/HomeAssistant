from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNBOOK = ROOT / "docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md"


def test_runbook_identity_contract_and_fail_closed_rules() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    required = (
        "A -> STOP -> B -> STOP -> C -> STOP -> SUMMARY",
        "If an explicit `BASE MAC:` value exists, use that 6-byte value.",
        "require bytes 4-5 to be `ff:fe`",
        "Never truncate an eight-byte value to its first six bytes.",
        'hardware_id = "ghw-c6-" + compact',
        "OTADATA_EQUAL => DOES_NOT_PROVE_SAME_BOARD",
        "OTADATA_DIFFERENT => DOES_NOT_PROVE_DISTINCT_BOARD_IDENTITY",
        "EUI64_WITH_FF_FE_TO_BASE_MAC=TESTED",
        "EXPLICIT_BASE_MAC_PREFERRED=TESTED",
        "MALFORMED_EUI64_FAILS_CLOSED=TESTED",
        "RAW_MAC_NOT_PUBLISHED=TESTED",
        "historical first-six-byte parser is forbidden",
        "Post-reset OTA-data validation guard",
        "OTADATA_POSTRESET_OTA_SEQ=1",
        "OTADATA_POSTRESET_STATE=VALID",
        "OTADATA_POSTRESET_CRC=0x4743989a",
        "8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3",
        "post-reset comparison against the initial all-erased OTA-data image is not a",
    )

    for statement in required:
        assert statement in text


def test_runbook_keeps_preflight_read_only() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    required = (
        "PERSISTENT_BOARD_MUTATION=false",
        "write-flash",
        "erase-flash",
        "erase-region",
        "NVS mutation",
        "partition-table write",
        "bootloader write",
        "full-flash erase",
        "A successful board preflight is not permission to flash.",
    )

    for statement in required:
        assert statement in text
