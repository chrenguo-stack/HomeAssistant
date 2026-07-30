from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_permission_independent_two_hop_shell_handoff_contract_20260730_v1.py"
SPEC = importlib.util.spec_from_file_location("handoff", TOOL)
assert SPEC and SPEC.loader
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPermissionIndependentTwoHopHandoff(unittest.TestCase):
    def make_chain(self, root: Path) -> tuple[Path, Path]:
        outer = root / "outer.sh"
        inner = root / "inner.sh"
        outer.write_text(
            '#!/bin/sh\nset -eu\nSCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)\n'
            'export PYTHONDONTWRITEBYTECODE=1\nexport GH_D2_17_OUTER_PACKAGE_ROOT="$SCRIPT_DIR"\n'
            ': "${GH_D2_17_DELIVERY_PROFILE:=public-ci}"\nexport GH_D2_17_DELIVERY_PROFILE\n'
            'exec "$SCRIPT_DIR/inner.sh" "$@"\n',
            encoding="utf-8",
        )
        inner.write_text(
            '#!/bin/sh\nset -eu\nSCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)\n'
            'export GH_D2_17_LAUNCHER_PACKAGE_ROOT="$SCRIPT_DIR"\n'
            'printf "%s\\n" "$GH_D2_17_OUTER_PACKAGE_ROOT" "$GH_D2_17_LAUNCHER_PACKAGE_ROOT" '
            '"$GH_D2_17_DELIVERY_PROFILE" "$PYTHONDONTWRITEBYTECODE"\n'
            'for arg in "$@"; do printf "<%s>\\n" "$arg"; done\n',
            encoding="utf-8",
        )
        os.chmod(outer, 0o600)
        os.chmod(inner, 0o600)
        return outer, inner

    def test_direct_outer_reproduces_permission_denied_but_repaired_handoff_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer, inner = self.make_chain(root)
            direct = subprocess.run(["/bin/sh", str(outer), "x"], capture_output=True, check=False)
            self.assertEqual(direct.returncode, 126)
            before = (stat.S_IMODE(outer.stat().st_mode), stat.S_IMODE(inner.stat().st_mode))
            cp = handoff.run_two_hop(
                package_root=root,
                outer_name=outer.name,
                outer_sha256=digest(outer),
                inner_name=inner.name,
                inner_sha256=digest(inner),
                arguments=["space value", "", "末尾"],
                delivery_profile="target-mac-static-check",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(cp.returncode, 0, cp.stderr.decode())
            lines = cp.stdout.decode().splitlines()
            self.assertEqual(lines[:4], [str(root.resolve()), str(root.resolve()), "target-mac-static-check", "1"])
            self.assertEqual(lines[4:], ["<space value>", "<>", "<末尾>"])
            after = (stat.S_IMODE(outer.stat().st_mode), stat.S_IMODE(inner.stat().st_mode))
            self.assertEqual(before, after)
            self.assertEqual(after, (0o600, 0o600))

    def test_outer_tamper_rejected_even_though_inner_is_invoked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer, inner = self.make_chain(root)
            outer_sha = digest(outer)
            outer.write_text(outer.read_text() + "# drift\n")
            with self.assertRaisesRegex(handoff.VerifiedTwoHopShellHandoffError, "CANONICAL_OUTER_DIGEST_DRIFT"):
                handoff.build_two_hop_command(
                    package_root=root,
                    outer_name=outer.name,
                    outer_sha256=outer_sha,
                    inner_name=inner.name,
                    inner_sha256=digest(inner),
                    arguments=[],
                )

    def test_inner_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer, inner = self.make_chain(root)
            inner_sha = digest(inner)
            inner.write_text(inner.read_text() + "# drift\n")
            with self.assertRaisesRegex(handoff.VerifiedTwoHopShellHandoffError, "INNER_LAUNCHER_DIGEST_DRIFT"):
                handoff.build_two_hop_command(
                    package_root=root,
                    outer_name=outer.name,
                    outer_sha256=digest(outer),
                    inner_name=inner.name,
                    inner_sha256=inner_sha,
                    arguments=[],
                )

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer, inner = self.make_chain(root)
            target = root / "target.sh"
            target.write_bytes(inner.read_bytes())
            inner.unlink()
            inner.symlink_to(target)
            with self.assertRaisesRegex(handoff.VerifiedTwoHopShellHandoffError, "INNER_LAUNCHER_NOT_REGULAR"):
                handoff.build_two_hop_command(
                    package_root=root,
                    outer_name=outer.name,
                    outer_sha256=digest(outer),
                    inner_name=inner.name,
                    inner_sha256=digest(target),
                    arguments=[],
                )

    def test_no_package_mutation_primitives(self):
        text = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("chmod(", text)
        self.assertNotIn("os.replace", text)
        self.assertNotIn("write_text", text)
        self.assertNotIn("write_bytes", text)


if __name__ == "__main__":
    unittest.main()
