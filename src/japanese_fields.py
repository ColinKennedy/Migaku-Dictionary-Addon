"""Find out which fields of a note type are Japanese.

A field is "Japanese" when the note type renders it through Migaku's Japanese
support, i.e. it sits inside a ``wrapped-japanese`` element in a card template::

    <div display-type="coloredhover" class="wrapped-japanese">{{Expression}}</div>

English fields (e.g. a ``J-E Meaning`` field) are not wrapped, so they are not
Japanese.

"""

import logging
import re
import typing

_LOGGER = logging.getLogger(__name__)

_WRAPPED = re.compile(
    r"<(?P<tag>\w+)\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bwrapped-japanese\b[^\"']*[\"'][^>]*>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.DOTALL | re.IGNORECASE,
)
_FIELD_REFERENCE = re.compile(r"\{\{([^{}]+?)\}\}")


def _from_templates(note_type: typing.Mapping[str, typing.Any]) -> set[str]:
    names = {field["name"] for field in note_type.get("flds", [])}
    found: set[str] = set()

    for template in note_type.get("tmpls", []):
        for side in ("qfmt", "afmt"):
            for wrapped in _WRAPPED.finditer(template.get(side, "")):
                for reference in _FIELD_REFERENCE.findall(wrapped.group("body")):
                    # ``{{#Field}}``, ``{{^Field}}``, ``{{/Field}}``, ``{{hint:Field}}``
                    name = reference.strip().lstrip("#^/").split(":")[-1].strip()

                    if name in names:
                        found.add(name)

    return found


def _from_migaku_registration(
    main_window: typing.Any,
    note_type_name: str,
) -> typing.Optional[set[str]]:
    """Ask Migaku's Japanese add-on which fields the user registered, if installed."""
    handler = getattr(main_window, "CSSJSHandler", None)

    if handler is None:
        return None

    try:
        registered, _ = handler.getWrapperDict()
        entries = registered.get(note_type_name)

        if not entries:
            return None

        return {entry[1] for entry in entries}
    except Exception:  # noqa: BLE001 - A third-party add-on. Never break the send.
        _LOGGER.exception("Could not read Migaku's registered Japanese fields.")

        return None


def get_japanese_fields(
    main_window: typing.Any,
    note_type: typing.Mapping[str, typing.Any],
) -> set[str]:
    """Get the names of every Japanese field in ``note_type``.

    Migaku's own registration is used when its add-on is installed. Otherwise
    the fields are read from the note type's card templates.

    """
    registered = _from_migaku_registration(main_window, note_type.get("name", ""))

    if registered is not None:
        return registered

    return _from_templates(note_type)
