"""Make sure the add-on loads on whichever Anki version is installed."""

import unittest

from . import _support


class Smoke(unittest.TestCase):
    def test_addon_imports(self) -> None:
        """The add-on's ``__init__`` (and every module it pulls in) must import.

        This is what Anki does at startup. If it fails, Anki shows the
        "Add-on Startup Failed" dialog.

        """
        _support.load_addon()

    def test_vendored_six_supports_this_python(self) -> None:
        """Old vendored ``six`` broke on Python 3.12+ (``six.moves`` import)."""
        _support.load_addon()

        from six.moves import queue  # type: ignore[import-untyped]

        self.assertTrue(hasattr(queue, "Queue"))
