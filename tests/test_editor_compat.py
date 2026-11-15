"""Check ``editor_compat`` against Anki's real ``Editor`` / ``NewEditor`` classes."""

import typing
import unittest
from unittest import mock

from . import _support


def _make(class_: type) -> typing.Any:
    # NOTE: Skip ``__init__``, which needs a full Anki main window.
    return object.__new__(class_)


class _Note:
    def __init__(self) -> None:
        self.fields = ["old"]
        self.id = 7

    def keys(self) -> list[str]:
        return ["Front"]


class EditorCompat(unittest.TestCase):
    def setUp(self) -> None:
        _support.load_addon()

        from aqt import editor as editor_
        from migaku_dictionary_under_test import editor_compat

        self.editor_ = editor_
        self.compat = editor_compat

    def _require_new_editor(self) -> None:
        if not hasattr(self.editor_, "NewEditor"):
            self.skipTest("This Anki version has no NewEditor.")

    def test_classes_match_this_anki(self) -> None:
        classes = self.compat.editor_classes()

        self.assertIn(self.editor_.Editor, classes)
        self.assertEqual(
            hasattr(self.editor_, "NewEditor"),
            len(classes) == 2,
        )

    def test_old_editor(self) -> None:
        editor = _make(self.editor_.Editor)
        editor.note = _Note()
        editor.loadNote = mock.Mock()

        self.assertTrue(self.compat.has_note(editor))
        self.assertIs(editor.note, self.compat.get_note(editor))

        self.compat.edit_note(editor, lambda note: note.fields.__setitem__(0, "new"))

        self.assertEqual(["new"], editor.note.fields)
        editor.loadNote.assert_called_once_with()

    def test_old_editor_without_note(self) -> None:
        editor = _make(self.editor_.Editor)
        editor.note = None
        editor.loadNote = mock.Mock()

        self.assertFalse(self.compat.has_note(editor))
        self.assertIsNone(self.compat.get_note(editor))

        self.compat.edit_note(editor, lambda note: self.fail("Should not be called."))
        editor.loadNote.assert_not_called()

    def test_new_editor(self) -> None:
        self._require_new_editor()

        note = _Note()
        editor = _make(self.editor_.NewEditor)
        editor.nid = note.id
        editor.addMode = False
        editor.mw = mock.Mock()
        editor.mw.col.get_note.return_value = note
        editor.reload_note = mock.Mock()
        # Run the "after saved" callback immediately, like Anki does when saved.
        editor.call_after_note_saved = lambda callback, keepFocus=False: callback()

        self.assertTrue(self.compat.has_note(editor))
        self.assertIs(note, self.compat.get_note(editor))

        self.compat.edit_note(editor, lambda n: n.fields.__setitem__(0, "new"))

        self.assertEqual(["new"], note.fields)
        editor.mw.col.update_note.assert_called_once_with(note)
        editor.reload_note.assert_called_once_with()

    def test_new_editor_without_note(self) -> None:
        self._require_new_editor()

        editor = _make(self.editor_.NewEditor)
        editor.nid = None
        editor.addMode = False

        self.assertFalse(self.compat.has_note(editor))
        self.assertIsNone(self.compat.get_note(editor))

    def test_new_editor_add_mode(self) -> None:
        self._require_new_editor()

        editor = _make(self.editor_.NewEditor)
        editor.nid = None
        editor.addMode = True

        # An unsaved note is still a valid dictionary target ...
        self.assertTrue(self.compat.has_note(editor))
        self.assertIsNone(self.compat.get_note(editor))

        # ... but we can't edit it, so tell the user instead of failing.
        with mock.patch.object(self.compat.aqt_utils, "tooltip") as tooltip:
            self.compat.edit_note(editor, lambda note: self.fail("Not editable."))

        tooltip.assert_called_once()
