"""Shared helpers for loading the add-on the way Anki does."""

import importlib.util
import os
import pathlib
import sys
import types
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "src"
_NAME = "migaku_dictionary_under_test"


def load_addon() -> types.ModuleType:
    """Import ``src/`` as a package, exactly like Anki does for an add-on folder."""
    if _NAME in sys.modules:
        return sys.modules[_NAME]

    import aqt
    from aqt.qt import (  # Needs a QApplication before most aqt imports.
        QApplication,
        QThread,
    )

    if QApplication.instance() is None:
        QApplication([])

    if aqt.mw is None:
        # NOTE: Anki always has a main window by the time add-ons load.
        aqt.mw = mock.MagicMock()

    spec = importlib.util.spec_from_file_location(
        _NAME,
        _SOURCE / "__init__.py",
        submodule_search_locations=[str(_SOURCE)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[_NAME] = module
    # NOTE: Don't start the add-on's real HTTP server thread in unit tests. In
    # Anki it is owned by the real main window; here it would be torn down while
    # running, which aborts the whole process.
    with mock.patch.object(QThread, "start", lambda *args, **kwargs: None):
        spec.loader.exec_module(module)

    return module
