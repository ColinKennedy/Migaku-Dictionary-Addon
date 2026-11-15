"""Decide what a note field should contain after "Send this definition"."""

import enum
import re
import typing

# NOTE: What Anki's editor leaves behind in an "empty" field.
_BLANK_PATTERN = re.compile(r"<br\s*/?>|&nbsp;|\s+", re.IGNORECASE)

_SEPARATOR = "<br><br>"


class AddType(str, enum.Enum):
    """How "Send this definition" combines text with a field's existing content."""

    ADD = "add"
    """Append, separated from any existing text."""

    NO = "no"
    """Only fill the field if it is empty."""

    OVERWRITE = "overwrite"
    """Replace whatever is there."""

    @classmethod
    def parse(cls, value: typing.Optional[str]) -> typing.Optional["AddType"]:
        """Convert a stored string (config / database) to an :class:`AddType`.

        Returns:
            None if ``value`` is None or isn't a known type.

        """
        try:
            return cls(value)
        except ValueError:
            return None


def is_blank(html: str) -> bool:
    """Check if ``html`` has no visible content (e.g. ``""`` or ``"<br>"``)."""
    return not _BLANK_PATTERN.sub("", html)


def merge(
    current: str,
    definition: str,
    add_type: typing.Optional[AddType],
) -> str:
    """Get the new field content.

    Args:
        current: What the field contains now.
        definition: The text being sent to the field.
        add_type: How to combine them. None (or an unknown type) overwrites.

    Returns:
        The new content. This is ``current`` unchanged if there is nothing to do.

    """
    if add_type == AddType.ADD:
        # NOTE: Only separate from existing text. A blank field must not start
        # with blank lines.
        #
        if is_blank(current):
            return definition

        return current + _SEPARATOR + definition

    if add_type == AddType.NO:
        return definition if is_blank(current) else current

    # ``AddType.OVERWRITE``, None, and anything unrecognized
    return definition
