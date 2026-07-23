from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from h3_n2_stage2d9_prepare_manifest_gate_20260722_v1 import (  # noqa: E402
    GateError,
    validate,
)
from h3_n2_stage2d9_prepare_model_20260722_v1 import (  # noqa: E402
    DurableStore,
    PrepareAuthorization,
    PrepareError,
    ProfileState,
    digest_profile,
    prepare_candidate,
)


class PrepareModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = {
            "broker_host": "isolated.invalid",
            "client_id": "stage2d9-candidate",
            "topic_prefix": "gh/stage2d9",
        }
        self.digest = digest_profile(self.profile)
        self.state = ProfileState(active_generation=0, active_digest="active-zero")
        self.auth = PrepareAuthorization(
            action="PREPARE_CANDIDATE",
            active_generation=0,
            candidate_generation=1,
            candidate_digest=self.digest,
            one_shot=True,
            replay_permitted=False,
            authorization_id="D2-STAGE2D9-HOST-MODEL-ONLY",
        )

    def test_success_commits_prepared_and_preserves_active(self) -> None:
        result = prepare_candidate(
            self.state,
            self.auth,
            DurableStore(),
            key_loaded=True,
        )
        self.assertEqual(result.active_generation, 0)
        self.assertEqual(result.active_digest, "active-zero")
        self.assertEqual(result.candidate_generation, 1)
        self.assertEqual(result.candidate_state, "PREPARED")
        self.assertTrue(result.prepare_authorization_consumed)
        self.assertFalse(result.active_session)
        self.assertFalse(result.candidate_session)

    def test_missing_key_fails_before_write(self) -> None:
        store = DurableStore()
        with self.assertRaisesRegex(PrepareError, "key not loaded"):
            prepare_candidate(self.state, self.auth, store, key_loaded=False)
        self.assertEqual(store.write_count, 0)

    def test_wrong_action_fails(self) -> None:
        auth = PrepareAuthorization(**{**self.auth.__dict__, "action": "ACTIVATE_PROFILE"})
        with self.assertRaisesRegex(PrepareError, "not PREPARE"):
            prepare_candidate(self.state, auth, DurableStore(), key_loaded=True)

    def test_stale_generation_fails(self) -> None:
        auth = PrepareAuthorization(**{**self.auth.__dict__, "active_generation": 1})
        with self.assertRaisesRegex(PrepareError, "generation binding"):
            prepare_candidate(self.state, auth, DurableStore(), key_loaded=True)

    def test_candidate_generation_must_be_next(self) -> None:
        auth = PrepareAuthorization(**{**self.auth.__dict__, "candidate_generation": 2})
        with self.assertRaisesRegex(PrepareError, "plus one"):
            prepare_candidate(self.state, auth, DurableStore(), key_loaded=True)

    def test_replay_is_denied(self) -> None:
        prepared = prepare_candidate(
            self.state,
            self.auth,
            DurableStore(),
            key_loaded=True,
        )
        with self.assertRaises(PrepareError):
            prepare_candidate(prepared, self.auth, DurableStore(), key_loaded=True)

    def test_failure_after_profile_write_recovers_empty(self) -> None:
        store = DurableStore()
        with self.assertRaisesRegex(PrepareError, "profile write"):
            prepare_candidate(
                self.state,
                self.auth,
                store,
                key_loaded=True,
                fail_after="profile_write",
            )
        recovered = store.recover(self.state)
        self.assertEqual(recovered.candidate_state, "EMPTY")
        self.assertEqual(recovered.candidate_generation, 0)
        self.assertEqual(recovered.active_generation, 0)

    def test_failure_after_commit_recovers_prepared(self) -> None:
        store = DurableStore()
        with self.assertRaisesRegex(PrepareError, "prepared commit"):
            prepare_candidate(
                self.state,
                self.auth,
                store,
                key_loaded=True,
                fail_after="prepared_commit",
            )
        recovered = store.recover(self.state)
        self.assertEqual(recovered.candidate_state, "PREPARED")
        self.assertEqual(recovered.candidate_generation, 1)
        self.assertEqual(recovered.active_generation, 0)

    def test_sessions_or_later_authorizations_fail(self) -> None:
        for state in (
            ProfileState(active_session=True),
            ProfileState(candidate_session=True),
            ProfileState(activate_authorization_present=True),
            ProfileState(cleanup_authorization_present=True),
        ):
            with self.assertRaises(PrepareError):
                prepare_candidate(state, self.auth, DurableStore(), key_loaded=True)


class ManifestGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).with_name(
            "stage2d9_prepare_manifest_template_20260722_v1.json"
        )
        cls.locked = json.loads(path.read_text(encoding="utf-8"))

    def test_locked_template_passes(self) -> None:
        self.assertEqual(validate(self.locked, "LOCKED"), "LOCKED")

    def test_activate_and_cleanup_gates_are_rejected(self) -> None:
        for gate in ("ACTIVATE_PROFILE", "CLEANUP_TEST_STATE"):
            manifest = copy.deepcopy(self.locked)
            manifest["gate"] = gate
            with self.assertRaises(GateError):
                validate(manifest)

    def test_prepare_requires_exact_scope(self) -> None:
        manifest = copy.deepcopy(self.locked)
        manifest.update(
            {
                "gate": "PREPARE_CANDIDATE",
                "execution_authorized": True,
                "writable_test_nvs_authorized": True,
                "source_sha": "1" * 64,
                "artifact_sha256": "2" * 64,
                "candidate_digest_sha256": "3" * 64,
                "allowed_nvs_partition": "gh2d8_p2d9",
                "allowed_nvs_namespace": "gh2d8_s2d9",
            }
        )
        manifest["prepare_authorization"]["authorization_id"] = "D2-EXAMPLE"
        self.assertEqual(validate(manifest), "PREPARE_CANDIDATE")
        manifest["mqtt_authorized"] = True
        with self.assertRaisesRegex(GateError, "mqtt_authorized"):
            validate(manifest)


if __name__ == "__main__":
    unittest.main()
