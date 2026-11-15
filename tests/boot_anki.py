"""Boot a *real* Anki main window with the add-on installed, then report as JSON.

Usage: python boot_anki.py <base-dir> <addon-src-dir>

The add-on is copied to <base>/addons21/foobar, exactly where Anki loads it.
Run by ``tests/test_boot.py`` in a subprocess because it starts a whole Anki.

"""

import json
import os
import shutil
import sys

base, source = sys.argv[1], sys.argv[2]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
shutil.rmtree(base, ignore_errors=True)
shutil.copytree(
    source,
    os.path.join(base, "addons21", "foobar"),
    ignore=shutil.ignore_patterns("__pycache__", "user_files*", ".mypy_cache"),
)

# Skip Anki's first-run "Language" dialog by creating the prefs database up front.
from aqt.profiles import ProfileManager  # noqa: E402

_pm = ProfileManager(ProfileManager.get_created_base_folder(base))
_pm.setupMeta()
_pm.db.commit()
_pm.db.close()
del _pm

warnings: list[str] = []
uncaught: list[str] = []
report: dict = {}


def _finish() -> None:
    try:
        _collect()
    finally:
        report["uncaught_exceptions"] = list(uncaught)
        print("REPORT " + json.dumps(report), flush=True)
        os._exit(0)


def _collect() -> None:
    import aqt
    from aqt import editor as editor_

    report["anki_version"] = __import__("anki.buildinfo", fromlist=["version"]).version
    report["addon_modules_loaded"] = sorted(
        m for m in sys.modules if m.startswith("foobar.")
    )[:5]
    report["foobar_main_loaded"] = "foobar.main" in sys.modules
    report["startup_warnings"] = warnings

    patched = {}
    for name in ("Editor", "NewEditor"):
        cls = getattr(editor_, name, None)
        if cls is not None:
            patched[name] = {
                "onBridgeCmd": cls.onBridgeCmd.__name__,
                "setupWeb": getattr(cls.setupWeb, "__name__", "?"),
            }
    report["editor_patches"] = patched

    try:
        report["addon_errors"] = (
            aqt.mw.addonManager.addonConfigDefaults("foobar") is not None
        )
    except Exception as error:  # noqa: BLE001
        report["addon_config_error"] = repr(error)

    # Exercise a real editor window when this Anki has NewEditor.
    try:
        from aqt import dialogs

        window = dialogs.open("AddCards", aqt.mw)
        report["add_cards_editor"] = type(window.editor).__name__
        report["add_cards_bridge"] = type(window.editor).onBridgeCmd.__name__
    except Exception as error:  # noqa: BLE001
        report["add_cards_error"] = repr(error)

    if hasattr(editor_, "NewEditor"):
        try:
            from unittest import mock

            from aqt import dialogs

            migaku = sys.modules["foobar.migaku_dictionary"]
            seen: list[list[str]] = []
            fake = mock.MagicMock()
            fake.dict.setCurrentEditor.side_effect = lambda e, t: seen.append(
                [type(e).__name__, t]
            )
            migaku.get_visible_dictionary = lambda: fake

            new_window = dialogs.open("NewAddCards", aqt.mw)
            new_window.load_new_note()
            report["new_dialog"] = type(new_window).__name__
            report["new_editor"] = type(new_window.editor).__name__

            new_window.editor.onBridgeCmd("bodyClick")
            report["new_editor_bodyClick_targets"] = list(seen)

            from foobar import editor_compat

            report["new_editor_has_note_in_add_mode"] = editor_compat.has_note(
                new_window.editor
            )
            tips: list[str] = []
            import aqt.utils as _u

            _orig = _u.tooltip
            editor_compat.aqt_utils.tooltip = lambda text, *a, **k: tips.append(text)
            editor_compat.edit_note(new_window.editor, lambda note: None)
            editor_compat.aqt_utils.tooltip = _orig
            report["new_editor_add_mode_edit_tooltip"] = bool(tips)
        except Exception as error:  # noqa: BLE001
            import traceback

            report["new_editor_error"] = (
                repr(error) + " " + traceback.format_exc()[-400:]
            )


def _hook() -> None:
    import aqt
    from aqt import gui_hooks
    from aqt.qt import QTimer

    def _later() -> None:
        QTimer.singleShot(6000, _finish)

    gui_hooks.main_window_did_init.append(_later)

    # Capture "Add-on Startup Failed"-style dialogs instead of showing them.
    import aqt.addons
    import aqt.utils

    def _capture(text: str, *args: object, **kwargs: object) -> None:
        warnings.append(str(text)[:300])

    import aqt.errors

    def _record(self):  # type: ignore[no-untyped-def]
        text = self.pool[-1500:]
        self.pool = ""

        # NOTE: The add-on's HTTP server uses a fixed port. If the developer
        # already has Anki open, binding it fails. That isn't a bug.
        if "sock.bind(sockaddr)" in text and (
            "10048" in text or "Address already in use" in text
        ):
            report["server_port_in_use"] = True

            return

        uncaught.append(text)

    # Anki would show an "Anki encountered a problem" dialog; record it instead.
    aqt.errors.ErrorHandler.onTimeout = _record  # type: ignore[method-assign]

    aqt.addons.showWarning = _capture  # type: ignore[attr-defined]
    aqt.utils.showWarning = _capture  # type: ignore[assignment]
    aqt.addons.showInfo = _capture  # type: ignore[attr-defined]


import aqt

# NOTE: Don't collide with (or reuse) any Anki the developer already has open.
aqt.AnkiApp.KEY = f"migaku-boot-test-{os.getpid()}"

_orig_init = aqt.AnkiApp.__init__


def _init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    _orig_init(self, *args, **kwargs)
    from aqt.qt import QApplication, QLabel, QTimer

    def _watchdog() -> None:
        found = []
        for widget in QApplication.topLevelWidgets():
            if widget.isVisible():
                texts = [label.text()[:120] for label in widget.findChildren(QLabel)][
                    :4
                ]
                found.append([type(widget).__name__, widget.windowTitle(), texts])
        print("STALLED " + json.dumps([found, uncaught]), flush=True)

        import faulthandler

        faulthandler.dump_traceback(file=sys.stdout, all_threads=True)
        sys.stdout.flush()
        os._exit(3)

    QTimer.singleShot(90000, _watchdog)


aqt.AnkiApp.__init__ = _init
_hook()
sys.argv = ["anki", "--base", base, "--lang", "en_US"]
aqt.run()
