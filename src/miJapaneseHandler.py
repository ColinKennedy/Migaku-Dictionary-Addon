# -*- coding: utf-8 -*-

from aqt import mw as mw_
from aqt.utils import  showInfo

class miJHandler:

	def __init__(self, mw: mw_) -> None:
		super().__init__()

		self.mw = mw
		self.activeNotes = self.getActiveNotes()

	def getActiveNotes(self) -> dict[str, list[str]]:
		if not hasattr(self.mw,'CSSJSHandler'):
			# TODO: @ColinKennedy add logging
			return {}

		activeNotes, _ = self.mw.CSSJSHandler.getWrapperDict()
		for noteType in activeNotes:
			activeNotes[noteType] = list(dict.fromkeys([item[1] for item in activeNotes[noteType]]))

		return activeNotes

	def attemptGenerate(self, note):
		if self.activeNotes:
			model = note.model()
			fields = self.mw.col.models.fieldNames(model)
			if model['name'] in self.activeNotes:
				for field in fields:
					if field in self.activeNotes[model['name']] and note[field] != '':
						note[field] = self.mw.Exporter.fetchParsedField(note[field], note)
		return note

	def attemptFieldGenerate(self, text: str, field: str, model: str, note: str) -> str:
		if self.activeNotes:
			if model in self.activeNotes:
				if field in self.activeNotes[model]:
					text = self.mw.Exporter.fetchParsedField(text, note)
		return text
