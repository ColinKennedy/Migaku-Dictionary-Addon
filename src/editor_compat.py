"""Smooth over the differences between Anki's editor implementations.

Anki 24.04 has a single editor, ``aqt.editor.Editor``. Newer Anki versions
(e.g. 26.09) add ``aqt.editor.NewEditor`` and use it for the Add Cards, Edit
Current and Browser windows. It is **not** a subclass of ``Editor`` and has a
different API (no ``.note`` attribute, ``loadNote()`` is now ``reload_note()``,
etc.).

Everything in this add-on that touches the editor's note should go through the
functions here so it works on both.

"""

from __future__ import annotations

import typing

from anki import notes as notes_
from aqt import editor as editor_
from aqt import utils as aqt_utils

if typing.TYPE_CHECKING:
    # NOTE: ``NewEditor`` does not exist in older Anki versions.
    AnyEditor = typing.Union[
        editor_.Editor,
        editor_.NewEditor,  # type: ignore[name-defined,unused-ignore]
    ]
else:
    AnyEditor = typing.Any


def editor_classes() -> tuple[typing.Any, ...]:
    """Get every editor class that exists in the running Anki version."""
    new = getattr(editor_, "NewEditor", None)

    if new is None:
        return (editor_.Editor,)

    return (editor_.Editor, new)


def new_dialog_classes() -> tuple[typing.Any, ...]:
    """Get the Add Cards / Edit Current windows that use ``NewEditor``, if any.

    Anki 26.x only uses these when the user opts into the new editor.

    """
    classes: list[typing.Any] = []

    for module_name, class_name in (
        ("aqt.addcards", "NewAddCards"),
        ("aqt.editcurrent", "NewEditCurrent"),
    ):
        module = __import__(module_name, fromlist=[class_name])
        class_ = getattr(module, class_name, None)

        if class_ is not None:
            classes.append(class_)

    return tuple(classes)


def has_note(editor: AnyEditor) -> bool:
    """Check if ``editor`` is currently editing a note."""
    if isinstance(editor, editor_.Editor):
        return bool(editor.note)

    # NOTE: A new, unsaved note (Add Cards) has no ID yet. The window is still
    # a valid target for the dictionary, even if we can't edit its fields.
    #
    return bool(editor.nid or editor.addMode)


def get_window_name(editor: AnyEditor) -> str:
    """Get the class name of the window ``editor`` lives in.

    e.g. ``"AddCards"``, ``"EditCurrent"`` or ``"Browser"``.

    """
    if isinstance(editor, editor_.Editor):
        # NOTE: The Browser embeds its editor in a plain ``QWidget``.
        name = type(editor.widget.parentWidget()).__name__

        return "Browser" if name == "QWidget" else name

    return type(editor.parentWindow).__name__


def get_note(editor: AnyEditor) -> typing.Optional[notes_.Note]:
    """Get the note ``editor`` is currently editing, if any."""
    if isinstance(editor, editor_.Editor):
        return editor.note

    if not editor.nid:
        return None

    note: notes_.Note = editor.mw.col.get_note(editor.nid)

    return note


def edit_note(
    editor: AnyEditor,
    edit: typing.Callable[[notes_.Note], None],
) -> None:
    """Apply ``edit`` to ``editor``'s current note and refresh the editor.

    Args:
        editor: The editor window to modify.
        edit: A function which mutates the note's fields in-place.

    """
    if isinstance(editor, editor_.Editor):
        note = editor.note

        if not note:
            return

        edit(note)
        editor.loadNote()

        return

    if not editor.nid:
        aqt_utils.tooltip(
            "Migaku Dictionary can't add to a new note in the experimental editor yet. "
            "Use Anki's standard editor, or save the note first."
        )

        return

    def _apply() -> None:
        note = get_note(editor)

        if not note:
            return

        edit(note)
        editor.mw.col.update_note(note)
        editor.reload_note()

    # NOTE: Flush any text the user typed but hasn't been saved yet, so we
    # don't overwrite it.
    #
    editor.call_after_note_saved(_apply)
