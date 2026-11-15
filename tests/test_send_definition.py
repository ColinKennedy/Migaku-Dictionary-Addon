"""Tests for "Send this definition": merging text and adding readings."""

import sys
import types
import unittest
from unittest import mock

from . import _support

_MIA_NOTE_TYPE = {
    "name": "MIA Japanese Vocabulary J-J",
    "flds": [
        {"name": "Expression"},
        {"name": "J-J Meaning"},
        {"name": "J-E Meaning"},
        {"name": "Examples"},
        {"name": "Audio"},
    ],
    "tmpls": [
        {
            "qfmt": (
                '{{^Audio on Front}}<span class="expression-field">'
                '<div display-type="coloredhover" class="wrapped-japanese">'
                "{{Expression}}</div></span>{{/Audio on Front}}"
            ),
            "afmt": (
                '<div class="meaning-field">'
                '<div display-type="coloredhover" class="wrapped-japanese">'
                "{{J-J Meaning}}</div></div>{{Audio}}<BR>{{hint:J-E Meaning}}"
                "<BR>{{Examples}}"
            ),
        }
    ],
}


class _Modules(unittest.TestCase):
    def setUp(self) -> None:
        _support.load_addon()

        from migaku_dictionary_under_test import (
            field_merge,
            japanese_fields,
            miJapaneseHandler,
            readings,
        )

        self.field_merge = field_merge
        self.japanese_fields = japanese_fields
        self.handler_module = miJapaneseHandler
        self.readings = readings


class Merge(_Modules):
    def test_add_to_blank_field_has_no_leading_newlines(self) -> None:
        for blank in ("", " ", "<br>", "<br/>", "&nbsp;", "<br><br>", " \n<br> "):
            with self.subTest(blank=blank):
                self.assertEqual(
                    "【髪型】かみがた<br>hair style",
                    self.field_merge.merge(
                        blank, "【髪型】かみがた<br>hair style", "add"
                    ),
                )

    def test_add_to_existing_text_uses_two_newlines(self) -> None:
        self.assertEqual(
            "first<br><br>second",
            self.field_merge.merge("first", "second", "add"),
        )

    def test_overwrite(self) -> None:
        self.assertEqual("new", self.field_merge.merge("old", "new", "overwrite"))

    def test_no_only_fills_blank_fields(self) -> None:
        self.assertEqual("old", self.field_merge.merge("old", "new", "no"))
        self.assertEqual("new", self.field_merge.merge("<br>", "new", "no"))


class JapaneseFields(_Modules):
    def test_wrapped_fields_are_japanese(self) -> None:
        found = self.japanese_fields.get_japanese_fields(object(), _MIA_NOTE_TYPE)

        self.assertEqual({"Expression", "J-J Meaning"}, found)

    def test_english_and_plain_fields_are_not_japanese(self) -> None:
        found = self.japanese_fields.get_japanese_fields(object(), _MIA_NOTE_TYPE)

        self.assertNotIn("J-E Meaning", found)
        self.assertNotIn("Examples", found)

    def test_wrapping_a_field_makes_it_japanese(self) -> None:
        note_type = dict(_MIA_NOTE_TYPE)
        note_type["tmpls"] = [
            {
                "qfmt": "",
                "afmt": '<div class="wrapped-japanese" display-type="x">{{Examples}}</div>',
            }
        ]

        found = self.japanese_fields.get_japanese_fields(object(), note_type)

        self.assertEqual({"Examples"}, found)

    def test_migaku_registration_wins_when_installed(self) -> None:
        main_window = mock.Mock()
        main_window.CSSJSHandler.getWrapperDict.return_value = (
            {"MIA Japanese Vocabulary J-J": [("x", "Examples")]},
            None,
        )

        found = self.japanese_fields.get_japanese_fields(main_window, _MIA_NOTE_TYPE)

        self.assertEqual({"Examples"}, found)


class AttemptFieldGenerate(_Modules):
    def _handler(self) -> object:
        return self.handler_module.miJHandler(mock.Mock(spec=[]))

    def _note(self) -> mock.Mock:
        note = mock.Mock()
        note.note_type.return_value = _MIA_NOTE_TYPE

        return note

    def test_japanese_field_gets_readings(self) -> None:
        with mock.patch.object(
            self.readings, "generate_migaku_syntax", return_value="髪型[かみがた;h]"
        ) as generate:
            result = self._handler().attemptFieldGenerate(  # type: ignore[attr-defined]
                "髪型", "Expression", "MIA Japanese Vocabulary J-J", self._note()
            )

        self.assertEqual("髪型[かみがた;h]", result)
        generate.assert_called_once_with("髪型")

    def test_english_field_is_left_alone(self) -> None:
        with mock.patch.object(self.readings, "generate_migaku_syntax") as generate:
            result = self._handler().attemptFieldGenerate(  # type: ignore[attr-defined]
                "hair style", "J-E Meaning", "MIA Japanese Vocabulary J-J", self._note()
            )

        self.assertEqual("hair style", result)
        generate.assert_not_called()

    def test_keeps_text_if_readings_are_unavailable(self) -> None:
        with mock.patch.object(
            self.readings, "generate_migaku_syntax", return_value=None
        ):
            result = self._handler().attemptFieldGenerate(  # type: ignore[attr-defined]
                "髪型", "Expression", "MIA Japanese Vocabulary J-J", self._note()
            )

        self.assertEqual("髪型", result)


class Readings(_Modules):
    def test_missing_addon_returns_none(self) -> None:
        with mock.patch.dict(sys.modules):
            for name in [n for n in sys.modules if n.endswith(".ankilib.global_vars")]:
                del sys.modules[name]

            self.assertFalse(self.readings.is_available())
            self.assertIsNone(self.readings.generate_migaku_syntax("髪型"))

    def test_uses_the_readings_addon_converter(self) -> None:
        package = "fake_readings_addon"
        modules = {
            package: types.ModuleType(package),
            package + ".ankilib": types.ModuleType(package + ".ankilib"),
            package + ".pylib": types.ModuleType(package + ".pylib"),
        }

        global_vars = types.ModuleType(package + ".ankilib.global_vars")
        global_vars.convert_check = lambda: True  # type: ignore[attr-defined]
        global_vars.mecab_handle = mock.Mock()  # type: ignore[attr-defined]
        global_vars.mecab_handle.analyze.side_effect = lambda line: ("parsed", line)
        global_vars.prefs = mock.Mock()  # type: ignore[attr-defined]
        global_vars.dictionary = object()  # type: ignore[attr-defined]
        modules[global_vars.__name__] = global_vars

        conv_util = types.ModuleType(package + ".pylib.conv_util")
        conv_util.squash_newlines = lambda value: value  # type: ignore[attr-defined]
        conv_util.detect_syntax = lambda value: None  # type: ignore[attr-defined]
        modules[conv_util.__name__] = conv_util

        converter = types.ModuleType(package + ".pylib.converter")
        converter.convert = lambda parsed, *args: parsed  # type: ignore[attr-defined]
        modules[converter.__name__] = converter

        html_processing = types.ModuleType(package + ".pylib.html_processing")
        html_processing.strip_html = lambda value: value.split("<br>")  # type: ignore[attr-defined]
        modules[html_processing.__name__] = html_processing

        output = types.ModuleType(package + ".pylib.output")
        output.OutputType = types.SimpleNamespace(MIGAKU="migaku")  # type: ignore[attr-defined]
        output.fmt_migaku = lambda converted, prefs: "<" + converted[1] + ">"  # type: ignore[attr-defined]
        modules[output.__name__] = output

        modules[package + ".pylib.segments"] = types.ModuleType(
            package + ".pylib.segments"
        )

        with mock.patch.dict(sys.modules, modules):
            self.assertTrue(self.readings.is_available())
            result = self.readings.generate_migaku_syntax("髪型<br>hair, style")

        # The English line is left exactly as it was.
        self.assertEqual("<髪型><br>hair, style", result)
