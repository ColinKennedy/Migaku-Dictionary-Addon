# -*- coding: utf-8 -*-

import typing

from anki import notes
from aqt import main


class miJHandler:

    def __init__(self, mw: main.AnkiQt) -> None:
        super().__init__()

        self._mw = mw
        self._activeNotes = self._getActiveNotes()

    def _getActiveNotes(self) -> dict[str, list[str]]:
        if not hasattr(self._mw, "CSSJSHandler"):
            # TODO: @ColinKennedy - add logging
            return {}

        # TODO: @ColinKennedy - This type-cast is a total guess. Check later.
        activeNotes: dict[str, list[str]]
        activeNotes, _ = self._mw.CSSJSHandler.getWrapperDict()

        for noteType in activeNotes:
            activeNotes[noteType] = list(
                dict.fromkeys([item[1] for item in activeNotes[noteType]])
            )

        return activeNotes

    def attemptGenerate(self, note: notes.Note) -> notes.Note:
        # TODO: @ColinKennedy - fetchParsedField doesn't exist. And the git
        # history says it never did. So this method can probably be removed.
        #
        # note[field] = self._mw.Exporter.fetchParsedField(note[field], note)
        # if self._activeNotes:
        # 	model = note.note_type()
        #
        # 	if not model:
        # 		raise RuntimeError(f'Note "{note}" has no note type.')
        #
        # 	fields = self._mw.col.models.field_names(model)
        #
        # 	if model['name'] in self._activeNotes:
        # 		for field in fields:
        # 			if field in self._activeNotes[model['name']] and note[field] != '':
        # 				note[field] = self._mw.Exporter.fetchParsedField(note[field], note)
        #
        return note

    def attemptFieldGenerate(
        self, text: str, field: str, model: str, note: notes.Note
    ) -> str:
        # TODO: @ColinKennedy - fetchParsedField doesn't exist. And the git
        # history says it never did. So this method can probably be removed.
        #
        # if self._activeNotes:
        # 	if model in self._activeNotes:
        # 		if field in self._activeNotes[model]:
        # 			text = self._mw.Exporter.fetchParsedField(text, note)
        #
        return text
