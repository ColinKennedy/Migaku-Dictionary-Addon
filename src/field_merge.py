"""Decide what a note field should contain after "Send this definition"."""

import re
import typing

# NOTE: What Anki's editor leaves behind in an "empty" field.
_BLANK_PATTERN = re.compile(r"<br\s*/?>|&nbsp;|\s+", re.IGNORECASE)

_SEPARATOR = "<br><br>"


def is_blank(html: str) -> bool:
    """Check if ``html`` has no visible content (e.g. ``""`` or ``"<br>"``)."""
    return not _BLANK_PATTERN.sub("", html)


def merge(
    current: str,
    definition: str,
    add_type: typing.Optional[str],
) -> str:
    """Get the new field content.

    Args:
        current: What the field contains now.
        definition: The text being sent to the field.
        add_type: How to combine them. ``"overwrite"``, ``"add"`` or ``"no"``
            (only fill the field if it is empty).

    Returns:
        The new content. This is ``current`` unchanged if there is nothing to do.

    """
    if add_type == "add":
        # NOTE: Only separate from existing text. A blank field must not start
        # with blank lines.
        #
        if is_blank(current):
            return definition

        return current + _SEPARATOR + definition

    if add_type == "no":
        return definition if is_blank(current) else current

    # ``"overwrite"`` and anything unrecognized
    return definition
