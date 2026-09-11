from __future__ import annotations

import ast
import binascii
import hashlib
import importlib.util
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "n3w_ota_guard.py"
spec = importlib.util.spec_from_file_location("n3w_ota_guard_r2", MODULE_PATH)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def entry(seq: int, state: int, label: bytes = b"L" * 20, *, crc: int | None = None) -> bytes:
    if crc is None:
        crc = m.esp_ota_crc(seq)
    return struct.pack("<I", seq) + label + struct.pack("<II", state, crc)


def otadata(copy0: bytes, copy1: bytes, *, fill0: int = 0xFF, fill1: int = 0xFF) -> bytes:
    a = bytearray(bytes([fill0]) * m.OTADATA_SECTOR_SIZE)
    b = bytearray(bytes([fill1]) * m.OTADATA_SECTOR_SIZE)
    a[:32] = copy0
    b[:32] = copy1
    return bytes(a + b)


def active_app1(target_state: int | None = None) -> bytes:
    if target_state is None:
        target_state = int(m.OtaState.UNDEFINED)
    return otadata(
        entry(1, target_state, b"A" * 20),
        entry(2, int(m.OtaState.UNDEFINED), b"B" * 20),
    )


def frozen_binding(path: Path) -> m.AppPayloadBinding:
    return m.AppPayloadBinding(
        slot=m.APP0_SLOT,
        offset=m.APP0_OFFSET,
        size=m.APP0_PAYLOAD_SIZE,
        sha256=m.APP0_EXPECTED_SHA256,
        source_path=str(path),
    )


def example_mac(last_octet: str) -> str:
    return ":".join(("02", "00", "00", "00", "00", last_octet))


class FakeESP:
    IS_STUB = False
    FLASH_WRITE_SIZE = 0x400
    FLASH_SECTOR_SIZE = 0x1000

    def __init__(self, port, baud, *, observed_mac, observed_md5, stub=False, secure=False, blocks=1):
        self.port = port
        self.baud = baud
        self.observed_mac = observed_mac
        self.observed_md5 = observed_md5
        self.sync_stub_detected = stub
        self.secure_download_mode = secure
        self.blocks = blocks
        self.events: list[tuple] = []

    def __enter__(self):
        self.events.append(("enter",))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append(("exit", exc_type.__name__ if exc_type else None))
        return False

    def connect(self, mode, attempts):
        self.events.append(("connect", mode, attempts))

    def read_mac(self, kind):
        self.events.append(("read_mac", kind))
        return self.observed_mac

    def flash_set_parameters(self, size):
        self.events.append(("flash_set_parameters", size))

    def flash_md5sum(self, offset, size):
        self.events.append(("flash_md5sum", offset, size))
        return self.observed_md5

    def flash_begin(self, size, offset):
        self.events.append(("flash_begin", size, offset))
        return self.blocks

    def flash_block(self, data, seq):
        self.events.append(("flash_block", len(data), seq, bytes(data[:32])))

    def flash_finish(self, reboot=False):
        self.events.append(("flash_finish", reboot))


class GuardTests(unittest.TestCase):
    def test_01_crc_matches_idf_formula(self):
        seq = 3
        expected = binascii.crc32(struct.pack("<I", seq), 0xFFFFFFFF) & 0xFFFFFFFF
        self.assertEqual(m.esp_ota_crc(seq), expected)

    def test_02_parse_selects_highest_valid_sequence(self):
        snap = m.parse_otadata(active_app1())
        self.assertEqual((snap.active_index, snap.selected_slot), (1, 1))

    def test_03_parse_rejects_equal_valid_sequences(self):
        raw = otadata(
            entry(1, int(m.OtaState.UNDEFINED)),
            entry(1, int(m.OtaState.UNDEFINED)),
        )
        with self.assertRaisesRegex(m.GuardError, "equal ota_seq"):
            m.parse_otadata(raw)

    def test_04_parse_rejects_unknown_state(self):
        raw = otadata(entry(1, 0x12345678), entry(2, int(m.OtaState.UNDEFINED)))
        with self.assertRaisesRegex(m.GuardError, "unknown ota_state"):
            m.parse_otadata(raw)

    def test_05_parse_uses_only_crc_valid_copy(self):
        bad = entry(9, int(m.OtaState.UNDEFINED), crc=0)
        good = entry(2, int(m.OtaState.UNDEFINED))
        snap = m.parse_otadata(otadata(bad, good))
        self.assertEqual(snap.active_index, 1)

    def test_06_parse_rejects_unsafe_active_state(self):
        raw = otadata(entry(1, int(m.OtaState.VALID)), entry(2, int(m.OtaState.NEW)))
        with self.assertRaisesRegex(m.GuardError, "unsafe"):
            m.parse_otadata(raw)

    def test_07_plan_preserves_state_label_and_changes_only_seq_crc(self):
        plan = m.plan_ota_switch_to_app0(active_app1(int(m.OtaState.VALID)), frozen_binding(Path("x")))
        self.assertEqual(plan.new_seq, 3)
        self.assertEqual(plan.preserved_ota_state, int(m.OtaState.VALID))
        self.assertEqual(plan.entry_image[4:24], b"A" * 20)
        self.assertEqual(struct.unpack_from("<I", plan.entry_image, 24)[0], int(m.OtaState.VALID))
        for start, end in plan.changed_entry_byte_ranges:
            self.assertTrue((0 <= start and end <= 4) or (28 <= start and end <= 32))

    def test_08_plan_requires_frozen_app0_hash(self):
        bad = m.AppPayloadBinding(0, m.APP0_OFFSET, m.APP0_PAYLOAD_SIZE, "00" * 32, "x")
        with self.assertRaisesRegex(m.GuardError, "frozen firmware authority"):
            m.plan_ota_switch_to_app0(active_app1(), bad)

    def test_09_plan_rejects_if_app0_already_selected(self):
        raw = otadata(entry(3, int(m.OtaState.UNDEFINED)), entry(2, int(m.OtaState.UNDEFINED)))
        with self.assertRaisesRegex(m.GuardError, "already selected"):
            m.plan_ota_switch_to_app0(raw, frozen_binding(Path("x")))

    def test_10_plan_erased_target_preserves_undefined(self):
        raw = otadata(b"\xff" * 32, entry(2, int(m.OtaState.UNDEFINED)))
        plan = m.plan_ota_switch_to_app0(raw, frozen_binding(Path("x")))
        self.assertEqual(plan.preserved_ota_state, int(m.OtaState.UNDEFINED))
        self.assertEqual(plan.entry_image[4:24], b"\xff" * 20)

    def test_11_plan_rejects_unsafe_target_state(self):
        raw = active_app1(int(m.OtaState.PENDING_VERIFY))
        with self.assertRaisesRegex(m.GuardError, "cannot be safely preserved"):
            m.plan_ota_switch_to_app0(raw, frozen_binding(Path("x")))

    def test_12_postverify_accepts_one_sector_erase_plus_32_byte_write(self):
        pre = active_app1()
        plan = m.plan_ota_switch_to_app0(pre, frozen_binding(Path("x")))
        post = bytearray(pre)
        rel = m.OTADATA_COPY_OFFSETS[plan.target_copy_index]
        post[rel : rel + m.OTADATA_SECTOR_SIZE] = b"\xff" * m.OTADATA_SECTOR_SIZE
        post[rel : rel + 32] = plan.entry_image
        m.verify_ota_switch(pre, bytes(post), plan)

    def test_13_postverify_rejects_non_target_change(self):
        pre = active_app1()
        plan = m.plan_ota_switch_to_app0(pre, frozen_binding(Path("x")))
        post = bytearray(pre)
        rel = m.OTADATA_COPY_OFFSETS[plan.target_copy_index]
        post[rel : rel + m.OTADATA_SECTOR_SIZE] = b"\xff" * m.OTADATA_SECTOR_SIZE
        post[rel : rel + 32] = plan.entry_image
        other = m.OTADATA_COPY_OFFSETS[1 - plan.target_copy_index]
        post[other + 0x100] ^= 1
        with self.assertRaisesRegex(m.GuardError, "non-target"):
            m.verify_ota_switch(pre, bytes(post), plan)

    def test_14_postverify_rejects_unexpected_target_sector_byte(self):
        pre = active_app1()
        plan = m.plan_ota_switch_to_app0(pre, frozen_binding(Path("x")))
        post = bytearray(pre)
        rel = m.OTADATA_COPY_OFFSETS[plan.target_copy_index]
        post[rel : rel + m.OTADATA_SECTOR_SIZE] = b"\xff" * m.OTADATA_SECTOR_SIZE
        post[rel : rel + 32] = plan.entry_image
        post[rel + 100] = 0
        with self.assertRaisesRegex(m.GuardError, r"erase\+32-byte-write"):
            m.verify_ota_switch(pre, bytes(post), plan)

    def test_15_next_seq_normal(self):
        self.assertEqual(m._next_seq_for_target(2, 0), 3)
        self.assertEqual(m._next_seq_for_target(4, 0), 5)

    def test_16_next_seq_near_uint32_max_fails_closed(self):
        with self.assertRaisesRegex(m.GuardError, "overflow/erase marker"):
            m._next_seq_for_target(0xFFFFFFFE, 0)

    def test_17_next_seq_rejects_erase_marker(self):
        with self.assertRaisesRegex(m.GuardError, "supported range"):
            m._next_seq_for_target(0xFFFFFFFF, 0)

    def test_18_app0_read_argv_exact_contract(self):
        argv = m.build_app0_read_command("/python", "/idf/esptool.py", "/dev/serial-example", "/tmp/app0.bin")
        m.validate_esptool_read_argv(argv)
        self.assertEqual(argv[argv.index("--before") + 1], "no-reset")
        self.assertEqual(argv[argv.index("--after") + 1], "no-reset")
        self.assertIn("--no-stub", argv[: argv.index("read-flash")])
        self.assertEqual(argv[-5:-3], ["--flash-size", "8MB"])
        self.assertEqual(argv[-3:], [hex(m.APP0_OFFSET), str(m.APP0_PAYLOAD_SIZE), "/tmp/app0.bin"])

    def test_19_otadata_read_argv_exact_contract(self):
        argv = m.build_otadata_read_command("/python", "/idf/esptool.py", "/dev/serial-example", "/tmp/ota.bin")
        m.validate_esptool_read_argv(argv)
        self.assertEqual(argv[-3:], [hex(m.OTADATA_OFFSET), str(m.OTADATA_SIZE), "/tmp/ota.bin"])

    def test_20_identity_read_argv_exact_contract(self):
        argv = m.build_identity_read_command("/python", "/idf/esptool.py", "/dev/serial-example")
        m.validate_esptool_read_argv(argv)
        self.assertEqual(argv[-1], "read-mac")
        self.assertEqual(argv[argv.index("--connect-attempts") + 1], "1")

    def test_21_validator_rejects_hard_reset(self):
        argv = m.build_identity_read_command("/python", "/idf/esptool.py", "/dev/serial-example")
        argv[argv.index("no-reset")] = "hard-reset"
        with self.assertRaises(m.GuardError):
            m.validate_esptool_read_argv(argv)

    def test_22_validator_rejects_write_flash(self):
        argv = m._base_esptool_argv("/python", "/idf/esptool.py", "/dev/serial-example") + ["write-flash", "0x9000", "x.bin"]
        with self.assertRaises(m.GuardError):
            m.validate_esptool_read_argv(argv)

    def test_23_validator_rejects_non_allowlisted_read_geometry(self):
        argv = m._base_esptool_argv("/python", "/idf/esptool.py", "/dev/serial-example") + [
            "read-flash", "--flash-size", "8MB", "0x0", "4096", "/tmp/x.bin"
        ]
        with self.assertRaisesRegex(m.GuardError, "allowlist"):
            m.validate_esptool_read_argv(argv)

    def test_24_identity_output_requires_expected_mac(self):
        mac_a = example_mac("01")
        binding = m.verify_identity_output(f"MAC: {mac_a}", mac_a.upper())
        self.assertEqual(binding.observed_base_mac, mac_a)

    def test_25_identity_output_rejects_multiple_candidates(self):
        mac_a, mac_b = example_mac("01"), example_mac("02")
        with self.assertRaisesRegex(m.GuardError, "exactly one"):
            m.verify_identity_output(f"MAC: {mac_a} ALT: {mac_b}", mac_a)

    def test_26_evidence_store_refuses_nonempty_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            directory = Path(td) / "ev"
            directory.mkdir()
            (directory / "old").write_text("x")
            with self.assertRaisesRegex(m.GuardError, "not empty"):
                m.EvidenceStore(directory)

    def test_27_evidence_store_refuses_git_worktree(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            with self.assertRaisesRegex(m.GuardError, "Git worktree"):
                m.EvidenceStore(root / "private" / "ev")

    def test_28_esptool_config_is_single_attempt(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            store = m.EvidenceStore(Path(td) / "ev")
            cfg = store.ensure_esptool_config().read_text()
            self.assertIn("connect_attempts = 1", cfg)
            self.assertIn("write_block_attempts = 1", cfg)
            self.assertIn("open_port_attempts = 1", cfg)

    def test_29_cli_exposes_no_fresh_deploy_or_app_write(self):
        text = m._parser().format_help()
        self.assertNotIn("fresh-deploy", text)
        self.assertNotIn("write-app0", text)
        self.assertEqual(m.TOOL_MODE, "BOARD_B_RECOVERY_ONLY")

    def test_30_source_has_no_high_level_write_flash_call(self):
        tree = ast.parse(MODULE_PATH.read_text())
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr == "write_flash":
                    calls.append(node)
                if isinstance(fn, ast.Name) and fn.id == "write_flash":
                    calls.append(node)
        self.assertEqual(calls, [])

    def test_31_direct_mutation_request_is_strictly_allowlisted(self):
        m._validate_direct_write_request(0x9000, b"x" * 32)
        m._validate_direct_write_request(0xA000, b"x" * 32)
        with self.assertRaises(m.GuardError):
            m._validate_direct_write_request(0xB000, b"x" * 32)
        with self.assertRaises(m.GuardError):
            m._validate_direct_write_request(0x9000, b"x" * 31)

    def _direct_fixture(self, td: str, *, md5_override=None, mac_override=None, stub=False, secure=False, blocks=1):
        root = Path(td)
        payload = b"R" * m.APP0_PAYLOAD_SIZE
        payload_path = root / "app0.bin"
        payload_path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        expected_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        mac = example_mac("11")
        observed_mac = tuple(int(x, 16) for x in (mac_override or mac).split(":"))
        observed_md5 = md5_override or expected_md5
        instances = []

        def factory(port, baud):
            esp = FakeESP(port, baud, observed_mac=observed_mac, observed_md5=observed_md5, stub=stub, secure=secure, blocks=blocks)
            instances.append(esp)
            return esp

        attached = []
        runtime = {
            "ESP32C6ROM": factory,
            "attach_flash": lambda esp: attached.append(esp),
            "flash_write_size": 0x400,
        }
        evidence = m.EvidenceStore(root / "ev")
        return payload_path, digest, mac, runtime, instances, attached, evidence

    def test_32_direct_mutation_has_one_connect_one_block_no_reboot(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            payload_path, digest, mac, runtime, instances, attached, evidence = self._direct_fixture(td)
            with mock.patch.object(m, "APP0_EXPECTED_SHA256", digest):
                binding = m.verify_app0_payload(payload_path, digest)
                m._perform_direct_otadata_write_once(
                    runtime,
                    port="/dev/example",
                    expected_base_mac=mac,
                    app_binding=binding,
                    offset=0x9000,
                    entry_data=b"E" * 32,
                    evidence=evidence,
                )
            events = instances[0].events
            self.assertEqual([e for e in events if e[0] == "connect"], [("connect", "no-reset", 1)])
            self.assertEqual([e for e in events if e[0] == "flash_begin"], [("flash_begin", 32, 0x9000)])
            block = [e for e in events if e[0] == "flash_block"]
            self.assertEqual(len(block), 1)
            self.assertEqual(block[0][1:3], (0x400, 0))
            self.assertEqual([e for e in events if e[0] == "flash_finish"], [("flash_finish", False)])
            self.assertEqual(len(attached), 1)

    def test_33_direct_mutation_identity_mismatch_stops_before_flash(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            payload_path, digest, mac, runtime, instances, _attached, evidence = self._direct_fixture(td, mac_override=example_mac("12"))
            with mock.patch.object(m, "APP0_EXPECTED_SHA256", digest):
                binding = m.verify_app0_payload(payload_path, digest)
                with self.assertRaisesRegex(m.GuardError, "identity mismatch"):
                    m._perform_direct_otadata_write_once(
                        runtime,
                        port="/dev/example",
                        expected_base_mac=mac,
                        app_binding=binding,
                        offset=0x9000,
                        entry_data=b"E" * 32,
                        evidence=evidence,
                    )
            self.assertFalse(any(e[0] == "flash_begin" for e in instances[0].events))

    def test_34_direct_mutation_md5_mismatch_stops_before_flash(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            payload_path, digest, mac, runtime, instances, _attached, evidence = self._direct_fixture(td, md5_override="0" * 32)
            with mock.patch.object(m, "APP0_EXPECTED_SHA256", digest):
                binding = m.verify_app0_payload(payload_path, digest)
                with self.assertRaisesRegex(m.GuardError, "freshness"):
                    m._perform_direct_otadata_write_once(
                        runtime,
                        port="/dev/example",
                        expected_base_mac=mac,
                        app_binding=binding,
                        offset=0x9000,
                        entry_data=b"E" * 32,
                        evidence=evidence,
                    )
            self.assertFalse(any(e[0] == "flash_begin" for e in instances[0].events))

    def test_35_direct_mutation_stub_detected_stops_before_flash(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            payload_path, digest, mac, runtime, instances, _attached, evidence = self._direct_fixture(td, stub=True)
            with mock.patch.object(m, "APP0_EXPECTED_SHA256", digest):
                binding = m.verify_app0_payload(payload_path, digest)
                with self.assertRaisesRegex(m.GuardError, "stub"):
                    m._perform_direct_otadata_write_once(
                        runtime,
                        port="/dev/example",
                        expected_base_mac=mac,
                        app_binding=binding,
                        offset=0x9000,
                        entry_data=b"E" * 32,
                        evidence=evidence,
                    )
            self.assertFalse(any(e[0] == "flash_begin" for e in instances[0].events))

    def test_36_direct_mutation_bad_flash_begin_count_stops_before_block(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            payload_path, digest, mac, runtime, instances, _attached, evidence = self._direct_fixture(td, blocks=2)
            with mock.patch.object(m, "APP0_EXPECTED_SHA256", digest):
                binding = m.verify_app0_payload(payload_path, digest)
                with self.assertRaisesRegex(m.GuardError, "block count"):
                    m._perform_direct_otadata_write_once(
                        runtime,
                        port="/dev/example",
                        expected_base_mac=mac,
                        app_binding=binding,
                        offset=0x9000,
                        entry_data=b"E" * 32,
                        evidence=evidence,
                    )
            self.assertFalse(any(e[0] == "flash_block" for e in instances[0].events))

    def test_37_toolchain_rejects_python_interpreter_mismatch_before_import(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            wrapper = Path(td) / "esptool.py"
            wrapper.write_text("x")
            cfg = Path(td) / "esptool.cfg"
            cfg.write_text("[esptool]\nwrite_block_attempts=1\n")
            with self.assertRaisesRegex(m.GuardError, "exact bound Python"):
                m.bind_toolchain_runtime(
                    str(Path(td) / "not-python"),
                    str(wrapper),
                    config_path=cfg,
                    expected_wrapper_sha256=hashlib.sha256(b"x").hexdigest(),
                )

    def test_38_toolchain_rejects_prior_esptool_import(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            wrapper = Path(td) / "esptool.py"
            wrapper.write_text("x")
            cfg = Path(td) / "esptool.cfg"
            cfg.write_text("[esptool]\nwrite_block_attempts=1\n")
            marker = object()
            old = sys.modules.get("esptool.fake")
            sys.modules["esptool.fake"] = marker
            try:
                with self.assertRaisesRegex(m.GuardError, "imported before"):
                    m.bind_toolchain_runtime(
                        sys.executable,
                        str(wrapper),
                        config_path=cfg,
                        expected_wrapper_sha256=hashlib.sha256(b"x").hexdigest(),
                    )
            finally:
                if old is None:
                    sys.modules.pop("esptool.fake", None)
                else:
                    sys.modules["esptool.fake"] = old

    def test_39_recovery_workflow_fake_path_never_writes_app0(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence_dir = root / "ev"
            mac = example_mac("21")
            labels = []
            pre = active_app1()
            state = {"post": None}

            def runner(argv, store, label):
                labels.append(label)
                if label == "rom_identity_read":
                    return SimpleNamespace(stdout=f"MAC: {mac}")
                if label == "app0_existing_read":
                    Path(argv[-1]).write_bytes(b"X" * m.APP0_PAYLOAD_SIZE)
                    return SimpleNamespace(stdout="")
                if label == "otadata_pre_read":
                    Path(argv[-1]).write_bytes(pre)
                    return SimpleNamespace(stdout="")
                if label == "otadata_post_read":
                    Path(argv[-1]).write_bytes(state["post"])
                    return SimpleNamespace(stdout="")
                raise AssertionError(label)

            payload_digest = hashlib.sha256(b"X" * m.APP0_PAYLOAD_SIZE).hexdigest()

            def fake_bind(*args, **kwargs):
                return SimpleNamespace(public_dict=lambda: {"fake": True}), {"fake": True}

            def fake_mutator(runtime, *, port, expected_base_mac, app_binding, offset, entry_data, evidence):
                post = bytearray(pre)
                rel = offset - m.OTADATA_OFFSET
                post[rel : rel + m.OTADATA_SECTOR_SIZE] = b"\xff" * m.OTADATA_SECTOR_SIZE
                post[rel : rel + 32] = entry_data
                state["post"] = bytes(post)

            with mock.patch.object(m, "APP0_EXPECTED_SHA256", payload_digest), mock.patch.object(
                m, "bind_toolchain_runtime", side_effect=fake_bind
            ), mock.patch.object(
                m, "_perform_direct_otadata_write_once", side_effect=fake_mutator
            ):
                result = m.execute_recovery_app0_to_slot0(
                    sys.executable,
                    "/idf/esptool.py",
                    "/dev/example",
                    evidence_dir,
                    expected_base_mac=mac,
                    runner=runner,
                )
            self.assertEqual(result.ota_plan.target_slot, 0)
            self.assertEqual(
                labels,
                ["rom_identity_read", "app0_existing_read", "otadata_pre_read", "otadata_post_read"],
            )
            workflow = (evidence_dir / "workflow.json").read_text()
            self.assertIn('"app0_write_allowed": false', workflow)
            self.assertNotIn("app0_write", labels)

    def test_40_recovery_app0_mismatch_stops_before_otadata(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            evidence_dir = Path(td) / "ev"
            mac = example_mac("22")
            labels = []

            def runner(argv, store, label):
                labels.append(label)
                if label == "rom_identity_read":
                    return SimpleNamespace(stdout=f"MAC: {mac}")
                if label == "app0_existing_read":
                    Path(argv[-1]).write_bytes(b"Z" * m.APP0_PAYLOAD_SIZE)
                    return SimpleNamespace(stdout="")
                raise AssertionError("otadata stage should not execute")

            def fake_bind(*args, **kwargs):
                return SimpleNamespace(public_dict=lambda: {"fake": True}), {"fake": True}

            with mock.patch.object(m, "bind_toolchain_runtime", side_effect=fake_bind):
                with self.assertRaisesRegex(m.GuardError, "SHA256 mismatch"):
                    m.execute_recovery_app0_to_slot0(
                        sys.executable,
                        "/idf/esptool.py",
                        "/dev/example",
                        evidence_dir,
                        expected_base_mac=mac,
                        runner=runner,
                    )
            self.assertEqual(labels, ["rom_identity_read", "app0_existing_read"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
