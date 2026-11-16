"""Tests for the personal ``custom_profile`` auto-fill."""

import sys
import types
import unittest
from unittest import mock

from . import _support

_NOTE_TYPE = {"name": "MIA Japanese Vocabulary J-J"}


class _Note(dict):  # type: ignore[type-arg]
    def __init__(self, type_name: str = "MIA Japanese Vocabulary J-J", **fields: str):
        super().__init__(fields)
        self._type = {"name": type_name}

    def note_type(self) -> dict:  # type: ignore[type-arg]
        return self._type


def _note(**overrides: str) -> _Note:
    fields = {
        "Expression": "髪型[かみがた;h]",
        "Target": "",
        "Examples": "",
        "J-J Meaning": "",
    }
    fields.update(overrides)

    return _Note(**fields)


class CustomProfile(unittest.TestCase):
    def setUp(self) -> None:
        _support.load_addon()

        from migaku_dictionary_under_test import custom_profile

        self.module = custom_profile
        self.config = {"custom_profile": "Colin"}

    def test_strip_readings(self) -> None:
        self.assertEqual("髪型", self.module.strip_readings("髪型[かみがた;h]"))
        self.assertEqual("私は", self.module.strip_readings("私[わたし]は<br>"))

    def test_disabled_by_default(self) -> None:
        self.assertFalse(self.module.should_fill({}, _note(), ["J-J Meaning"]))
        self.assertFalse(
            self.module.should_fill({"custom_profile": ""}, _note(), ["J-J Meaning"])
        )

    def test_enabled_on_empty_note(self) -> None:
        self.assertTrue(self.module.should_fill(self.config, _note(), ["J-J Meaning"]))

    def test_other_note_type_is_ignored(self) -> None:
        note = _Note("Basic", **_note())
        self.assertFalse(self.module.should_fill(self.config, note, ["J-J Meaning"]))

    def test_must_send_to_meaning(self) -> None:
        self.assertFalse(self.module.should_fill(self.config, _note(), ["J-E Meaning"]))

    def test_existing_data_blocks_everything(self) -> None:
        for field in ("Target", "Examples", "J-J Meaning"):
            with self.subTest(field=field):
                note = _note(**{field: "x"})
                self.assertFalse(
                    self.module.should_fill(self.config, note, ["J-J Meaning"])
                )

    def test_blank_expression_blocks(self) -> None:
        self.assertFalse(
            self.module.should_fill(
                self.config, _note(Expression="<br>"), ["J-J Meaning"]
            )
        )

    def test_fill(self) -> None:
        note = _note(**{"J-J Meaning": "かみのかたち"})
        examples = types.ModuleType("fake.japanese_examples")
        examples.config = {"maxPermanent": 5}  # type: ignore[attr-defined]
        calls: list[str] = []

        def _find(found_note: _Note, count: int) -> tuple[str, ...]:
            calls.append(found_note["Target"])  # Target must already be filled.

            return ("example",)

        def _set(found_note: _Note, found: tuple[str, ...]) -> None:
            found_note["Examples"] = found[0]

        examples.find_examples_multiple = _find  # type: ignore[attr-defined]
        examples._set_fields = _set  # type: ignore[attr-defined]

        with mock.patch.dict(sys.modules, {"fake.japanese_examples": examples}):
            with mock.patch.object(
                self.module.readings, "generate_migaku_syntax", return_value="READ"
            ):
                self.module.fill(note)

        self.assertEqual("髪型", note["Target"])
        self.assertEqual(["髪型"], calls)
        self.assertEqual("example", note["Examples"])
        self.assertEqual("READ", note["J-J Meaning"])

    def test_fill_survives_missing_addons(self) -> None:
        note = _note(**{"J-J Meaning": "text"})

        with mock.patch.object(
            self.module.readings, "generate_migaku_syntax", return_value=None
        ):
            self.module.fill(note)

        self.assertEqual("髪型", note["Target"])
        self.assertEqual("text", note["J-J Meaning"])
