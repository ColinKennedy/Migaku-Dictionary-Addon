# -*- coding: utf-8 -*-

from __future__ import annotations

import typing

import aqt
from anki.lang import _
from aqt import main, qt

from . import miutils

if typing.TYPE_CHECKING:
    # TODO: @ColinKennedy - This line prevents a cyclic import. Fix later.
    from . import addonSettings

from . import typer

T = typing.TypeVar("T")
_Template = typer.ExportTemplate


class TemplateEditor(qt.QDialog):
    def __init__(
        self,
        mw: main.AnkiQt,
        parent: addonSettings.SettingsGui,
        dictionaries: typing.Optional[typing.Iterable[str]] = None,
        toEdit: typing.Optional[_Template] = None,
        tName: str = "",
    ) -> None:
        super().__init__(parent, qt.Qt.WindowType.Window)

        self._new = False
        dictionaries = dictionaries or None
        self._settings = parent
        self._mw = mw

        self.setMinimumSize(qt.QSize(400, 0))
        self.setWindowTitle("Add Export Template")

        self._templateName = qt.QLineEdit()
        self._noteType = qt.QComboBox()
        self._wordField = qt.QComboBox()
        self._sentenceField = qt.QComboBox()
        self._secondaryField = qt.QComboBox()
        self._notesField = qt.QComboBox()
        self._imageField = qt.QComboBox()
        self._audioField = qt.QComboBox()
        self._otherDictsField = qt.QComboBox()
        self._dictionaries = qt.QComboBox()
        self._fields = qt.QComboBox()
        self._addDictField = qt.QPushButton("Add")
        self._dictFieldsTable = self._getDictFieldsTable()
        self._entrySeparator = qt.QLineEdit()
        self._dictionaryNames = dictionaries
        self._cancelButton = qt.QPushButton("Cancel")
        self._saveButton = qt.QPushButton("Save")
        self._main_layout = qt.QVBoxLayout()
        self._notesFields = self._getNotesFields()
        self._setupLayout()
        self.loadTemplateEditor(toEdit, tName)
        self._initHandlers()
        self._initTooltips()

    def _initTooltips(self) -> None:
        self._templateName.setToolTip("The name of the export template.")
        self._noteType.setToolTip("The note type to export to.")
        self._wordField.setToolTip("The destination field for your target word.")
        self._sentenceField.setToolTip("The destination field for the sentence.")
        self._imageField.setToolTip(
            "The destination field for an image pasted from\nthe clipboard with Ctrl/⌘+shift+v."
        )
        self._audioField.setToolTip(
            "The destination field for an mp3 audio file pasted from\nthe clipboard with Ctrl/⌘+shift+v."
        )
        self._otherDictsField.setToolTip(
            "The destination field for any dictionary\nwithout a specific destination field set below."
        )
        self._dictionaries.setToolTip(
            "The dictionary to specify a particular field to.\nThe dictionaries will be prioritized and exported before\ndictionaries without a specified destination field."
        )
        self._fields.setToolTip("The dictionary's destination field.")
        self._addDictField.setToolTip(
            "Add this dictionary/destination field combination."
        )
        self._entrySeparator.setToolTip(
            'The separator that will be used in the case multiple\nitems(the sentence/word/image/definitions) are exported to the same destination field.\nBy default two line breaks are used ("<br><br>").'
        )

    def _clearTemplateEditor(self) -> None:
        self._templateName.clear()
        self.setWindowTitle("Add Export Template")
        self._templateName.setEnabled(True)
        self._noteType.clear()
        self._wordField.clear()
        self._sentenceField.clear()
        self._secondaryField.clear()
        self._notesField.clear()
        self._imageField.clear()
        self._audioField.clear()
        self._otherDictsField.clear()
        self._dictionaries.clear()
        self._fields.clear()
        self._dictFieldsTable.setRowCount(0)
        self._entrySeparator.clear()

    def _loadTemplateForEdit(self, t: _Template) -> None:
        self.setWindowTitle("Edit Export Template")
        self._templateName.setEnabled(False)
        self._noteType.setCurrentText(t["noteType"])
        self._sentenceField.setCurrentText(t["sentence"])
        self._secondaryField.setCurrentText(t.get("secondary", "Don't Export"))
        self._notesField.setCurrentText(t.get("notes", "Don't Export"))
        self._wordField.setCurrentText(t["word"])
        self._imageField.setCurrentText(t["image"])
        if "audio" in t:
            self._audioField.setCurrentText(t["audio"])
        self._otherDictsField.setCurrentText(t["unspecified"])
        self._entrySeparator.setText(t["separator"])

    def _loadTableForEdit(self, fieldsDicts: dict[str, list[str]]) -> None:
        for field, dictList in fieldsDicts.items():
            for dictName in dictList:
                self._addDictFieldRow(dictName, field)

    def _getConfig(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration, self._mw.addonManager.getConfig(__name__)
        )

    def _getSpecificDictFields(self) -> dict[str, list[str]]:
        dictFields: dict[str, list[str]] = {}

        for i in range(self._dictFieldsTable.rowCount()):
            dictn = typer.check_t(self._dictFieldsTable.item(i, 0)).text()
            fieldn = typer.check_t(self._dictFieldsTable.item(i, 1)).text()

            if fieldn not in dictFields:
                dictFields[fieldn] = [dictn]
            else:
                dictFields[fieldn].append(dictn)

        return dictFields

    def _saveExportTemplate(self) -> None:
        newConfig = self._getConfig()
        tn = self._templateName.text()
        if tn == "":
            miutils.miInfo("The export template must have a name.", level="wrn")
            return
        curGroups = newConfig["ExportTemplates"]
        if self._new and tn in curGroups:
            miutils.miInfo(
                "A new export template must have a unique name.", level="wrn"
            )
            return
        exportTemplate: typer.ExportTemplate = {
            "noteType": self._noteType.currentText(),
            "sentence": self._sentenceField.currentText(),
            "secondary": self._secondaryField.currentText(),
            "notes": self._notesField.currentText(),
            "word": self._wordField.currentText(),
            "image": self._imageField.currentText(),
            "audio": self._audioField.currentText(),
            "unspecified": self._otherDictsField.currentText(),
            "specific": self._getSpecificDictFields(),
            "separator": self._entrySeparator.text(),
        }
        curGroups[tn] = exportTemplate
        self._mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], newConfig),
        )
        self._settings.loadTemplateTable()
        self.hide()

    def _loadSepValue(self) -> None:
        self._entrySeparator.setText("<br><br>")

    def _getDictFieldsTable(self) -> qt.QTableWidget:
        dictFields = qt.QTableWidget()
        dictFields.setColumnCount(3)
        tableHeader = _verify(dictFields.horizontalHeader())
        tableHeader.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Fixed)
        dictFields.setRowCount(0)
        dictFields.setSortingEnabled(False)
        dictFields.setEditTriggers(qt.QTableWidget.EditTrigger.NoEditTriggers)
        dictFields.setSelectionBehavior(
            qt.QAbstractItemView.SelectionBehavior.SelectRows
        )
        dictFields.setColumnWidth(2, 40)
        tableHeader.hide()
        return dictFields

    def _initHandlers(self) -> None:
        self._noteType.currentIndexChanged.connect(self._loadNoteFields)
        self._addDictField.clicked.connect(self._addDictFieldRow)
        self._saveButton.clicked.connect(self._saveExportTemplate)
        self._cancelButton.clicked.connect(self.hide)

    def _notInTable(self, dictName: str) -> bool:
        for i in range(self._dictFieldsTable.rowCount()):
            if _verify(self._dictFieldsTable.item(i, 0)).text() == dictName:
                return False
        return True

    def _addDictFieldRow(self, dictName: str = "", fieldName: str = "") -> None:
        if not dictName:
            dictName = self._dictionaries.currentText()
        if not fieldName:
            fieldName = self._fields.currentText()

        if self._notInTable(dictName):
            rc = self._dictFieldsTable.rowCount()
            self._dictFieldsTable.setRowCount(rc + 1)
            self._dictFieldsTable.setItem(rc, 0, qt.QTableWidgetItem(dictName))
            self._dictFieldsTable.setItem(rc, 1, qt.QTableWidgetItem(fieldName))
            deleteButton = qt.QPushButton("X")
            deleteButton.setFixedWidth(40)
            deleteButton.clicked.connect(self._removeDictField)
            self._dictFieldsTable.setCellWidget(rc, 2, deleteButton)

    def _removeDictField(self) -> None:
        model = self._dictFieldsTable.selectionModel()

        if not model:
            raise RuntimeError("Expected a selection model. Cannot continue.")

        self._dictFieldsTable.removeRow(model.currentIndex().row())

    def _loadNoteFields(self) -> None:
        curNote = self._noteType.currentText()

        if curNote in self._notesFields:
            fields = self._notesFields[curNote]
            fields.sort()
            self._loadFieldsValues(fields)
            self._dictFieldsTable.setRowCount(0)

    def _getNotesFields(self) -> dict[str, list[str]]:
        notesFields: dict[str, list[str]] = {}
        models = self._mw.col.models.all()
        for model in models:
            notesFields[model["name"]] = []
            for fld in model["flds"]:
                notesFields[model["name"]].append(fld["name"])
        return notesFields

    def _loadDictionaries(self) -> None:
        self._dictionaries.addItems(self._dictionaryNames or [])
        self._dictionaries.addItem("Google Images")
        self._dictionaries.addItem("Forvo")

    def _initialNoteFieldsLoad(self, loadFields: bool = True) -> None:
        noteTypes = list(self._notesFields.keys())
        noteTypes.sort()
        self._noteType.addItems(noteTypes)
        if loadFields:

            fields = self._notesFields[noteTypes[0]]
            fields.sort()
            self._loadFieldsValues(fields)

    def _loadFieldsValues(self, fields: typing.Sequence[str]) -> None:
        self._sentenceField.clear()
        self._sentenceField.addItem("Don't Export")
        self._sentenceField.addItems(fields)
        self._secondaryField.clear()
        self._secondaryField.addItem("Don't Export")
        self._secondaryField.addItems(fields)
        self._notesField.clear()
        self._notesField.addItem("Don't Export")
        self._notesField.addItems(fields)
        self._wordField.clear()
        self._wordField.addItem("Don't Export")
        self._wordField.addItems(fields)
        self._imageField.clear()
        self._imageField.addItem("Don't Export")
        self._imageField.addItems(fields)
        self._audioField.clear()
        self._audioField.addItem("Don't Export")
        self._audioField.addItems(fields)
        self._otherDictsField.clear()
        self._otherDictsField.addItems(fields)
        self._fields.clear()
        self._fields.addItems(fields)

    def _setupLayout(self) -> None:
        tempNameLay = qt.QHBoxLayout()
        tempNameLay.addWidget(qt.QLabel("Name: "))
        tempNameLay.addWidget(self._templateName)
        self._main_layout.addLayout(tempNameLay)

        noteTypeLay = qt.QHBoxLayout()
        noteTypeLay.addWidget(qt.QLabel("Notetype: "))
        noteTypeLay.addWidget(self._noteType)
        self._main_layout.addLayout(noteTypeLay)

        sentenceLay = qt.QHBoxLayout()
        sentenceLay.addWidget(qt.QLabel("Sentence Field:"))
        sentenceLay.addWidget(self._sentenceField)
        self._main_layout.addLayout(sentenceLay)

        secondaryLay = qt.QHBoxLayout()
        secondaryLay.addWidget(qt.QLabel("Secondary Field:"))
        secondaryLay.addWidget(self._secondaryField)
        self._main_layout.addLayout(secondaryLay)

        wordLay = qt.QHBoxLayout()
        wordLay.addWidget(qt.QLabel("Word Field:"))
        wordLay.addWidget(self._wordField)
        self._main_layout.addLayout(wordLay)

        notesLay = qt.QHBoxLayout()
        notesLay.addWidget(qt.QLabel("User Notes:"))
        notesLay.addWidget(self._notesField)
        self._main_layout.addLayout(notesLay)

        imageLay = qt.QHBoxLayout()
        imageLay.addWidget(qt.QLabel("Image Field:"))
        imageLay.addWidget(self._imageField)
        self._main_layout.addLayout(imageLay)

        audioLay = qt.QHBoxLayout()
        audioLay.addWidget(qt.QLabel("Audio Field:"))
        audioLay.addWidget(self._audioField)
        self._main_layout.addLayout(audioLay)

        otherDictsLay = qt.QHBoxLayout()
        otherDictsLay.addWidget(qt.QLabel("Unspecified Dictionaries Field:"))
        otherDictsLay.addWidget(self._otherDictsField)
        self._main_layout.addLayout(otherDictsLay)

        dictFieldLay = qt.QHBoxLayout()
        dictFieldLay.addWidget(self._dictionaries)
        dictFieldLay.addWidget(self._fields)
        dictFieldLay.addWidget(self._addDictField)
        self._main_layout.addLayout(dictFieldLay)

        self._main_layout.addWidget(self._dictFieldsTable)

        separatorLay = qt.QHBoxLayout()
        separatorLay.addWidget(qt.QLabel("Entry Separator: "))
        separatorLay.addWidget(self._entrySeparator)
        separatorLay.addStretch()
        self._main_layout.addLayout(separatorLay)

        cancelSaveButtons = qt.QHBoxLayout()
        cancelSaveButtons.addStretch()
        cancelSaveButtons.addWidget(self._cancelButton)
        cancelSaveButtons.addWidget(self._saveButton)
        self._main_layout.addLayout(cancelSaveButtons)

        # TODO: @ColinKennedy - why would this line be needed?
        self.setLayout(self._main_layout)

    def loadTemplateEditor(
        self, toEdit: typing.Optional[_Template] = None, tName: str = ""
    ) -> None:
        self._clearTemplateEditor()

        self._loadDictionaries()
        if not toEdit:
            self._new = True
            self._loadSepValue()
            self._initialNoteFieldsLoad()
        else:
            self._new = False
            self._initialNoteFieldsLoad(False)
            self._templateName.setText(tName)
            self._loadTemplateForEdit(toEdit)
            self._loadTableForEdit(toEdit["specific"])


def _verify(item: typing.Optional[T]) -> T:
    if item is not None:
        return item

    raise ValueError("Item cannot be None.")
