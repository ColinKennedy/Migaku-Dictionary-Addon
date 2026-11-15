"""Add readings and pitch accents to Japanese text, in Migaku syntax.

This reuses the converter of the "Japanese Readings and Pitch Accent" add-on,
the same one behind its "(Re)generate readings and accents with Migaku syntax"
editor button. If that add-on isn't installed, nothing happens.

"""

import importlib
import logging
import re
import sys
import typing

_LOGGER = logging.getLogger(__name__)

_GLOBAL_VARS = ".ankilib.global_vars"

# Hiragana, katakana (incl. half-width) and CJK ideographs.
_JAPANESE = re.compile("[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]")


def _find_package() -> typing.Optional[str]:
    # NOTE: Anki names an add-on's package after its folder (e.g. "1845503807"),
    # so find it by looking for its modules instead of hard-coding that.
    #
    for name in list(sys.modules):
        if name.endswith(_GLOBAL_VARS):
            return name[: -len(_GLOBAL_VARS)]

    return None


def is_available() -> bool:
    """Check if the readings add-on is installed and loaded."""
    return _find_package() is not None


def generate_migaku_syntax(text: str) -> typing.Optional[str]:
    """Convert ``text`` to Migaku syntax, e.g. ``"髪型"`` -> ``"髪型[かみがた;h]"``.

    Returns:
        The converted text. This is None if it can't be done (the add-on is
        missing or its dictionaries aren't loaded). Callers should keep the
        original text then.

    """
    package = _find_package()

    if package is None:
        return None

    try:
        global_vars = importlib.import_module(package + ".ankilib.global_vars")
        conv_util = importlib.import_module(package + ".pylib.conv_util")
        converter = importlib.import_module(package + ".pylib.converter")
        html_processing = importlib.import_module(package + ".pylib.html_processing")
        output = importlib.import_module(package + ".pylib.output")
        segments = importlib.import_module(package + ".pylib.segments")

        if not global_vars.convert_check():
            return None

        def _lines(value: str) -> typing.Iterator[str]:
            lines = html_processing.strip_html(value)
            syntax = conv_util.detect_syntax(value)

            if not syntax:
                yield from lines

                return

            # NOTE: Already has readings. Strip them so they are regenerated.
            parser = (
                segments.parse_migaku
                if syntax == output.OutputType.MIGAKU
                else segments.parse_jrp
            )

            for line in lines:
                yield "".join(unit.text() for unit in parser(line))

        value = conv_util.squash_newlines(text)
        rendered: list[str] = []

        for line in _lines(value):
            # NOTE: Leave non-Japanese lines (e.g. an English gloss) exactly as
            # they are. The converter would respace them as if they were Japanese.
            if not _JAPANESE.search(line):
                rendered.append(line)

                continue

            parsed = global_vars.mecab_handle.analyze(line)
            converted = converter.convert(
                parsed, global_vars.prefs.convert, global_vars.dictionary
            )
            rendered.append(output.fmt_migaku(converted, global_vars.prefs.output))

        return "<br>".join(rendered)
    except Exception:  # noqa: BLE001 - Never lose the user's definition over this.
        _LOGGER.exception("Could not generate readings. Keeping the text as-is.")

        return None
