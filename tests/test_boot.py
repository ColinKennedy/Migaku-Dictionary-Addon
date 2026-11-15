"""Boot a real Anki main window with the add-on installed.

This is the closest thing to "does the add-on work in Anki" we can run in CI.

"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

_TESTS = pathlib.Path(__file__).resolve().parent
_SOURCE = _TESTS.parent / "src"


class Boot(unittest.TestCase):
    def test_boots_without_startup_errors(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            env = dict(
                os.environ,
                QT_QPA_PLATFORM="offscreen",
                PYTHONPATH=str(_SOURCE / "vendors"),
                # NOTE: Chromium needs these in containers / on CI runners.
                QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-W",
                    "ignore",
                    str(_TESTS / "boot_anki.py"),
                    os.path.join(base, "anki"),
                    str(_SOURCE),
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=240,
            )

        lines = [
            line for line in result.stdout.splitlines() if line.startswith("REPORT ")
        ]
        self.assertTrue(
            lines,
            f"Anki never finished starting.\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}",
        )
        report = json.loads(lines[-1][len("REPORT ") :])

        self.assertEqual([], report["startup_warnings"])
        self.assertTrue(report["foobar_main_loaded"])
        self.assertNotIn("add_cards_error", report)

        for name, patched in report["editor_patches"].items():
            self.assertEqual("bridgeReroute", patched["onBridgeCmd"], name)

        if "NewEditor" in report["editor_patches"]:
            self.assertNotIn("new_editor_error", report)
            # The experimental editor must map to the same dictionary targets.
            self.assertEqual(
                [["NewEditor", "Add"]], report["new_editor_bodyClick_targets"]
            )
            self.assertTrue(report["new_editor_add_mode_edit_tooltip"])
