from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/n3w-t1-s20-real-service-handoff-ci.yml"
IMAGE_LOCK = ROOT / "infra/n3w-t1/production/image-lock.json"
POLICY_MANIFEST = ROOT / "docs/development/N3W_CI_POLICY_MANIFEST_V1.json"

UPSTREAM_CI_IMAGE = (
    "docker.io/library/eclipse-mosquitto:2.1.2-alpine@"
    "sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408"
)
PRODUCTION_MIRROR_REF = (
    "m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine"
)
PRODUCTION_ARM64_MANIFEST = (
    "sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"
)


class S20CiImageIdentityContractTest(unittest.TestCase):
    def test_ci_uses_upstream_immutable_digest_not_mirror_repo_digest(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count(UPSTREAM_CI_IMAGE), 2)
        self.assertNotIn(PRODUCTION_MIRROR_REF, text)
        self.assertNotIn("RepoDigests", text)
        self.assertIn("cancel-in-progress:", text)

    def test_production_image_lock_remains_separate_arm64_authority(self) -> None:
        document = json.loads(IMAGE_LOCK.read_text(encoding="utf-8"))
        broker = document["broker"]
        self.assertEqual(broker["source_ref"], PRODUCTION_MIRROR_REF)
        self.assertEqual(
            broker["manifest_digest"],
            PRODUCTION_ARM64_MANIFEST,
        )
        self.assertEqual(broker["platform"], "linux/arm64")

    def test_policy_exception_is_retired_after_pr_cancellation_fix(self) -> None:
        document = json.loads(POLICY_MANIFEST.read_text(encoding="utf-8"))
        entry = document["workflows"][
            "n3w-t1-s20-real-service-handoff-ci.yml"
        ]
        self.assertEqual(entry["class"], "FAST")
        self.assertEqual(entry["draft_policy"], "run")
        self.assertEqual(entry["exceptions"], {})


if __name__ == "__main__":
    unittest.main()
