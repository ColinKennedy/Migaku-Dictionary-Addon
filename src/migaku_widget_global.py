import typing

from aqt import editor


PARENT_EDITOR: typing.Optional[editor.Editor] = None


def get_parent_editor() -> editor.Editor:
    if PARENT_EDITOR:
        return PARENT_EDITOR

    raise RuntimeError("No parent editor was found.")
