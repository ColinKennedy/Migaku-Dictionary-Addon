import typing

from . import editor_compat

PARENT_EDITOR: typing.Optional[editor_compat.AnyEditor] = None


def get_parent_editor() -> editor_compat.AnyEditor:
    if PARENT_EDITOR:
        return PARENT_EDITOR

    raise RuntimeError("No parent editor was found.")
