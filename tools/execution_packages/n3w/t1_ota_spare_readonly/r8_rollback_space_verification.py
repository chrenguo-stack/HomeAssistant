"""Reproduce R8 frozen-package capacity and rollback behavior offline.

Run with the exact ha-recovery.pyz from GitHub Actions artifact 14717720726.
Only the checked package's functions and in-memory fixtures are exercised.
"""

import argparse
from contextlib import nullcontext
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


RECOVERY_SHA = "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84"
SPARE_FREE_BYTES = 4755718144
TARGET_BYTES = 2447053824
PREDECESSOR_BYTES = 2448486400
USB_FREE_BYTES = 28148965376


def filesystem(free, total=None):
    return SimpleNamespace(f_bavail=free, f_bfree=free, f_blocks=total or free, f_frsize=1)


class FrozenRecoveryCases(unittest.TestCase):
    def test_admission_rejects_actual_free_space_before_release(self):
        # A one-byte allowance isolates the image-layer lower bound.
        budget = media.HaInstallSpaceBudget(1, 1, 1, 1)
        root = Path("/")
        verifier = media.HaMountedInstallMaterialVerifier(
            mountpoint=root, internal_storage=root, image_storage=root,
            ha_data_root=root, budget=lambda _: budget, verify_prestate=lambda _: True,
        )
        with (patch.object(media.os, "fstatvfs", return_value=filesystem(USB_FREE_BYTES, 32015122432)),
              patch.object(media.os, "statvfs", return_value=filesystem(SPARE_FREE_BYTES)),
              patch.object(media, "_ha_restore_workspace_bytes", return_value=1)):
            capacity, internal = verifier._capacity(42, budget, TARGET_BYTES, PREDECESSOR_BYTES)
        self.assertTrue(capacity.measured_floor_pass)
        self.assertFalse(capacity.capacity_pass)
        self.assertEqual(internal.install_required_bytes, TARGET_BYTES)
        self.assertEqual(internal.recovery_required_bytes, PREDECESSOR_BYTES + 2)

    def test_target_loader_still_demands_both_budgets_after_old_release(self):
        scenarios = (
            (SPARE_FREE_BYTES, SPARE_FREE_BYTES, "ha_usb_target_image_recovery_space_insufficient", False),
            (TARGET_BYTES + PREDECESSOR_BYTES + 2, PREDECESSOR_BYTES + 1,
             "ha_usb_target_image_recovery_reserve_lost", True),
        )
        for initial, after, reason, load_called in scenarios:
            with self.subTest(reason=reason):
                free = initial
                document = {"predecessor_release_admission": {
                    "install_required_bytes": TARGET_BYTES, "recovery_required_bytes": PREDECESSOR_BYTES + 2,
                }}
                backup = media.HaMountedBackupProvider(
                    store=SimpleNamespace(read=lambda: document), mountpoint=Path("/"),
                    internal_storage=Path("/"), backup=None, verify_quiesced=lambda: True,
                )
                def load(_source, _identity):
                    nonlocal free
                    free = after
                loader = Mock(side_effect=load)
                record = SimpleNamespace(kind="target", archive_size_bytes=0)
                with (patch.object(backup, "_document", return_value=document),
                      patch.object(backup, "_require_restore_quiesced"),
                      patch.object(media, "_open_transaction_directory", return_value=nullcontext((0, 0))),
                      patch.object(media, "_verified_archive", return_value=nullcontext((0, []))),
                      patch.object(media, "_authenticate_image", return_value=(object(), TARGET_BYTES)),
                      patch.object(media.os, "statvfs", side_effect=lambda _: filesystem(free))):
                    with self.assertRaisesRegex(media.UpdaterV2Error, reason):
                        backup._load_bound_image(document, record, loader)
                self.assertEqual(loader.called, load_called)

    def test_recovery_dispatch_loads_old_image_while_failed_target_remains(self):
        for data_written in (False, True):
            with self.subTest(data_written=data_written):
                events = []
                target_resident = True

                class AtPredecessorLoad(Exception):
                    pass

                class Store:
                    document = {
                        "phase": usb.U11 if data_written else usb.U10,
                        "status": "ACTIVE",
                        "transaction_id_sha256": "a" * 64,
                        "recovery_required": False,
                        "predecessor_release_intent": {"container_id": "b" * 64},
                        "target_activation": usb.TARGET_WRITES_POSSIBLE if data_written else usb.TARGET_BINDING,
                    }

                    def read(self):
                        return self.document

                    def write(self, document):
                        self.document = document

                    def lock(self):
                        return nullcontext()

                store = Store()

                def restore():
                    events.append("restore_data")
                    store.write({**store.read(), "ha_data_restore": {"step": "PUBLISHED"}})

                def ensure(*args):
                    events.append("load_old")
                    self.assertTrue(target_resident)
                    raise AtPredecessorLoad

                runtime = SimpleNamespace(
                    require_rollback_boot_guard=lambda: None,
                    quiesce_for_data_restore=lambda _: events.append("quiesce"),
                    verify_untouched_release_launch=lambda _: events.append("verify_launch"),
                    ensure_rollback_predecessor=ensure,
                )
                with self.assertRaises(AtPredecessorLoad):
                    usb.resume_host_recovery(
                        store, runtime, lambda _: SimpleNamespace(restore_preupgrade_data=restore),
                        lambda _: None,
                    )
                expected = ["quiesce", "restore_data", "load_old"] if data_written else ["verify_launch", "load_old"]
                self.assertEqual(events, expected)
                self.assertTrue(store.read()["recovery_required"])


def main():
    global media, usb
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recovery_pyz", type=Path)
    package = parser.parse_args().recovery_pyz
    if hashlib.sha256(package.read_bytes()).hexdigest() != RECOVERY_SHA:
        parser.error("recovery package SHA-256 mismatch")
    sys.path.insert(0, str(package.resolve()))
    import n3w_t1_core_updater_ha_mounted_media as media
    import n3w_t1_core_updater_ha_usb as usb

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FrozenRecoveryCases)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
