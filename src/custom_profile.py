"""Personal "profile" tweaks for "Send this definition".

Enabled by setting ``"custom_profile": "Colin"`` in the add-on's config. For any
other value (the default is ``""``) nothing in this module does anything.

When a J-J definition is sent to an empty "MIA Japanese Vocabulary J-J" note,
the rest of the note is filled in as well:

- ``Target`` is copied from ``Expression`` (Migaku readings removed).
- ``Examples`` is filled by the "Japanese Example Sentences" add-on.
- ``J-J Meaning`` gets readings and pitch accents, like the "(Re)generate" button.

If any of those fields already has content, nothing is changed.

"""

import importlib
import logging
import re
import sys
import typing

from anki import notes as notes_

from . import field_merge, readings

_LOGGER = logging.getLogger(__name__)

PROFILE_NAME = "Colin"
NOTE_TYPE = "MIA Japanese Vocabulary J-J"

EXPRESSION = "Expression"
TARGET = "Target"
EXAMPLES = "Examples"
MEANING = "J-J Meaning"

_HTML_TAG = re.compile(r"<[^>]*>")
_READING = re.compile(r"\[[^\]]*\]")
_EXAMPLES_MODULE = ".japanese_examples"


def is_enabled(config: typing.Mapping[str, typing.Any]) -> bool:
    """Check if the user opted into this profile."""
    return config.get("custom_profile") == PROFILE_NAME


def strip_readings(text: str) -> str:
    """Remove Migaku readings and HTML, e.g. ``"髪型[かみがた;h]"`` -> ``"髪型"``."""
    return _READING.sub("", _HTML_TAG.sub("", text)).replace("&nbsp;", " ").strip()


def _get(note: notes_.Note, name: str) -> typing.Optional[str]:
    return note[name] if name in note else None


def should_fill(
    config: typing.Mapping[str, typing.Any],
    note: notes_.Note,
    sent_fields: typing.Iterable[str],
) -> bool:
    """Check if sending to ``sent_fields`` should trigger :func:`fill`.

    This must be called **before** the definition is written to ``note``.

    """
    if not is_enabled(config):
        return False

    note_type = note.note_type()

    if not note_type or note_type.get("name") != NOTE_TYPE:
        return False

    if MEANING not in sent_fields:
        return False

    expression = _get(note, EXPRESSION)
    others = [_get(note, name) for name in (TARGET, EXAMPLES, MEANING)]

    if expression is None or field_merge.is_blank(expression):
        return False

    # NOTE: A missing field or any pre-existing content means "leave it alone".
    return all(value is not None and field_merge.is_blank(value) for value in others)


def _find_examples_module() -> typing.Optional[typing.Any]:
    for name in list(sys.modules):
        if name.endswith(_EXAMPLES_MODULE):
            module = sys.modules[name]

            if hasattr(module, "find_examples_multiple"):
                return module

    return None


def _fill_examples(note: notes_.Note) -> None:
    module = _find_examples_module()

    if module is None:
        _LOGGER.warning('"Japanese Example Sentences" isn\'t loaded. Skipping.')

        return

    try:
        found = module.find_examples_multiple(note, module.config["maxPermanent"])
        module._set_fields(note, found)
    except Exception:  # noqa: BLE001 - Includes the add-on's "nothing found".
        _LOGGER.debug("No examples were added.", exc_info=True)


def fill(note: notes_.Note) -> None:
    """Fill ``Target``, ``Examples`` and ``J-J Meaning`` on ``note`` in-place.

    Call this **after** the definition was written to ``J-J Meaning``.

    """
    target = strip_readings(note[EXPRESSION])

    if target:
        note[TARGET] = target

    # NOTE: ``Target`` must be filled first. The examples add-on searches it.
    _fill_examples(note)

    meaning = note[MEANING]

    if not field_merge.is_blank(meaning):
        note[MEANING] = readings.generate_migaku_syntax(meaning) or meaning
