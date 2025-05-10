# -*- coding: utf-8 -*-

from __future__ import annotations

import typing

import aqt
from anki.lang import _
from aqt import main
from aqt.qt import *

from .miutils import miAsk, miInfo

if typing.TYPE_CHECKING:
    # TODO: @ColinKennedy - This line prevents a cyclic import. Fix later.
    from . import addonSettings

from . import typer

T = typing.TypeVar("T")
_Template = typer.ExportTemplate
# class _Template(typing.TypedDict):
#     noteType: str
#     sentence: typing.Union[str, typing.Literal["Don't Export"]]
#     notes: typing.Union[str, typing.Literal["Don't Export"]]
#     word: str
#     image: str
#     audio: typing.Optional[str]
#     unspecified: str
#     separator: str


class TemplateEditor(QDialog):
    def __init__(
        self,
        mw: main.AnkiQt,
        parent: addonSettings.SettingsGui,
        dictionaries: typing.Optional[typing.Iterable[str]] = None,
        toEdit: typing.Optional[_Template] = None,
        tName: str = "",
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)

        self.new = False
        dictionaries = dictionaries or None
        self.settings = parent
        self.mw = mw

        self.setMinimumSize(QSize(400, 0))
        self.setWindowTitle("Add Export Template")

        self.templateName = QLineEdit()
        self.noteType = QComboBox()
        self.wordField = QComboBox()
        self.sentenceField = QComboBox()
        self.secondaryField = QComboBox()
        self.notesField = QComboBox()
        self.imageField = QComboBox()
        self.audioField = QComboBox()
        self.otherDictsField = QComboBox()
        self.dictionaries = QComboBox()
        self.fields = QComboBox()
        self.addDictField = QPushButton('Add')
        self.dictFieldsTable = self.getDictFieldsTable()
        self.entrySeparator = QLineEdit()
        self.dictionaryNames = dictionaries
        self.cancelButton = QPushButton('Cancel')
        self.saveButton = QPushButton('Save')
        self._main_layout = QVBoxLayout()
        self.notesFields = self.getNotesFields()
        self.setupLayout()
        self.loadTemplateEditor(toEdit, tName)
        self.initHandlers()
        self.initTooltips()

    def initTooltips(self) -> None:
        self.templateName.setToolTip('The name of the export template.')
        self.noteType.setToolTip('The note type to export to.')
        self.wordField.setToolTip('The destination field for your target word.')
        self.sentenceField.setToolTip('The destination field for the sentence.')
        self.imageField.setToolTip('The destination field for an image pasted from\nthe clipboard with Ctrl/⌘+shift+v.')
        self.audioField.setToolTip('The destination field for an mp3 audio file pasted from\nthe clipboard with Ctrl/⌘+shift+v.')
        self.otherDictsField.setToolTip('The destination field for any dictionary\nwithout a specific destination field set below.')
        self.dictionaries.setToolTip('The dictionary to specify a particular field to.\nThe dictionaries will be prioritized and exported before\ndictionaries without a specified destination field.')
        self.fields.setToolTip('The dictionary\'s destination field.')
        self.addDictField.setToolTip('Add this dictionary/destination field combination.')
        self.entrySeparator.setToolTip('The separator that will be used in the case multiple\nitems(the sentence/word/image/definitions) are exported to the same destination field.\nBy default two line breaks are used ("<br><br>").')

    def clearTemplateEditor(self) -> None:
        self.templateName.clear()
        self.setWindowTitle("Add Export Template")
        self.templateName.setEnabled(True)
        self.noteType.clear()
        self.wordField.clear()
        self.sentenceField.clear()
        self.secondaryField.clear()
        self.notesField.clear()
        self.imageField.clear()
        self.audioField.clear()
        self.otherDictsField.clear()
        self.dictionaries.clear()
        self.fields.clear()
        self.dictFieldsTable.setRowCount(0)
        self.entrySeparator.clear()

    def loadTemplateEditor(self, toEdit: typing.Optional[_Template] = None, tName: str = "") -> None:
        self.clearTemplateEditor()

        self.loadDictionaries()
        if not toEdit:
            self.new = True
            self.loadSepValue()
            self.initialNoteFieldsLoad()
        else:
            self.new = False
            self.initialNoteFieldsLoad(False)
            self.templateName.setText(tName)
            self.loadTemplateForEdit(toEdit)
            self.loadTableForEdit(toEdit['specific'])

    def loadTemplateForEdit(self, t: _Template) -> None:
        self.setWindowTitle("Edit Export Template")
        self.templateName.setEnabled(False)
        self.noteType.setCurrentText(t['noteType'])
        self.sentenceField.setCurrentText(t['sentence'])
        self.secondaryField.setCurrentText(t.get('secondary', "Don't Export"))
        self.notesField.setCurrentText(t.get('notes', "Don't Export"))
        self.wordField.setCurrentText(t['word'])
        self.imageField.setCurrentText(t['image'])
        if 'audio' in t:
            self.audioField.setCurrentText(t['audio'])
        self.otherDictsField.setCurrentText(t['unspecified'])
        self.entrySeparator.setText(t['separator'])

    def loadTableForEdit(self, fieldsDicts: dict[str, list[str]]) -> None:
        for field, dictList in fieldsDicts.items():
            for dictName in dictList:
                self.addDictFieldRow(dictName, field)

    def getConfig(self) -> typer.Configuration:
        return typing.cast(typer.Configuration, self.mw.addonManager.getConfig(__name__))

    def getSpecificDictFields(self) -> dict[str, list[str]]:
        dictFields: dict[str, list[str]] = {}

        for i in range(self.dictFieldsTable.rowCount()):
            dictn = typer.check_t(self.dictFieldsTable.item(i, 0)).text()
            fieldn = typer.check_t(self.dictFieldsTable.item(i, 1)).text()

            if fieldn not in dictFields:
                dictFields[fieldn] = [dictn]
            else:
                dictFields[fieldn].append(dictn)

        return dictFields

    def saveExportTemplate(self) -> None:
        newConfig = self.getConfig()
        tn = self.templateName.text()
        if tn  == '':
            miInfo('The export template must have a name.', level='wrn')
            return
        curGroups = newConfig['ExportTemplates']
        if self.new and tn in curGroups:
            miInfo('A new export template must have a unique name.', level='wrn')
            return
        exportTemplate: typer.ExportTemplate = {
            'noteType' : self.noteType.currentText(),
            'sentence' : self.sentenceField.currentText(),
            'secondary' : self.secondaryField.currentText(),
            'notes' : self.notesField.currentText(),
            'word' : self.wordField.currentText(),
            'image' : self.imageField.currentText(),
            'audio' :   self.audioField.currentText(),
            'unspecified' : self.otherDictsField.currentText(),
            'specific' : self.getSpecificDictFields(),
            'separator' : self.entrySeparator.text()
        }
        curGroups[tn] = exportTemplate
        self.mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], newConfig),
        )
        self.settings.loadTemplateTable()
        self.hide()

    def loadSepValue(self) -> None:
        self.entrySeparator.setText('<br><br>')

    def getDictFieldsTable(self) -> QTableWidget:
        dictFields = QTableWidget()
        dictFields.setColumnCount(3)
        tableHeader = _verify(dictFields.horizontalHeader())
        tableHeader.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        dictFields.setRowCount(0)
        dictFields.setSortingEnabled(False)
        dictFields.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        dictFields.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        dictFields.setColumnWidth(2, 40)
        tableHeader.hide()
        return dictFields

    def initHandlers(self) -> None:
        self.noteType.currentIndexChanged.connect(self.loadNoteFields)
        self.addDictField.clicked.connect(self.addDictFieldRow)
        self.saveButton.clicked.connect(self.saveExportTemplate)
        self.cancelButton.clicked.connect(self.hide)

    def notInTable(self, dictName: str) -> bool:
        for i in range(self.dictFieldsTable.rowCount()):
            if _verify(self.dictFieldsTable.item(i, 0)).text() == dictName:
                return False
        return True

    def addDictFieldRow(self, dictName: str = "", fieldName: str = "") -> None:
        if not dictName:
            dictName = self.dictionaries.currentText()
        if not fieldName:
            fieldName = self.fields.currentText()

        if self.notInTable(dictName):
            rc = self.dictFieldsTable.rowCount()
            self.dictFieldsTable.setRowCount(rc + 1)
            self.dictFieldsTable.setItem(rc, 0, QTableWidgetItem(dictName))
            self.dictFieldsTable.setItem(rc, 1, QTableWidgetItem(fieldName))
            deleteButton =  QPushButton("X");
            deleteButton.setFixedWidth(40)
            deleteButton.clicked.connect(self.removeDictField)
            self.dictFieldsTable.setCellWidget(rc, 2, deleteButton)

    def removeDictField(self) -> None:
        model = self.dictFieldsTable.selectionModel()

        if not model:
            raise RuntimeError("Expected a selection model. Cannot continue.")

        self.dictFieldsTable.removeRow(model.currentIndex().row())

    def loadNoteFields(self) -> None:
        curNote = self.noteType.currentText()

        if curNote in self.notesFields:
            fields = self.notesFields[curNote]
            fields.sort()
            self.loadFieldsValues(fields)
            self.dictFieldsTable.setRowCount(0)

    def getNotesFields(self) -> dict[str, list[str]]:
        notesFields: dict[str, list[str]] = {}
        models = self.mw.col.models.all()
        for model in models:
            notesFields[model['name']] = []
            for fld in model['flds']:
                notesFields[model['name']].append(fld['name'])
        return notesFields

    def loadDictionaries(self) -> None:
        self.dictionaries.addItems(self.dictionaryNames or [])
        self.dictionaries.addItem('Google Images')
        self.dictionaries.addItem('Forvo')

    def initialNoteFieldsLoad(self, loadFields: bool = True) -> None:
        noteTypes = list(self.notesFields.keys())
        noteTypes.sort()
        self.noteType.addItems(noteTypes)
        if loadFields:

            fields = self.notesFields[noteTypes[0]]
            fields.sort()
            self.loadFieldsValues(fields)

    def loadFieldsValues(self, fields: typing.Sequence[str]) -> None:
        self.sentenceField.clear()
        self.sentenceField.addItem("Don't Export")
        self.sentenceField.addItems(fields)
        self.secondaryField.clear()
        self.secondaryField.addItem("Don't Export")
        self.secondaryField.addItems(fields)
        self.notesField.clear()
        self.notesField.addItem("Don't Export")
        self.notesField.addItems(fields)
        self.wordField.clear()
        self.wordField.addItem("Don't Export")
        self.wordField.addItems(fields)
        self.imageField.clear()
        self.imageField.addItem("Don't Export")
        self.imageField.addItems(fields)
        self.audioField.clear()
        self.audioField.addItem("Don't Export")
        self.audioField.addItems(fields)
        self.otherDictsField.clear()
        self.otherDictsField.addItems(fields)
        self.fields.clear()
        self.fields.addItems(fields)

    def setupLayout(self) -> None:
        tempNameLay = QHBoxLayout()
        tempNameLay.addWidget(QLabel('Name: '))
        tempNameLay.addWidget(self.templateName)
        self._main_layout.addLayout(tempNameLay)

        noteTypeLay = QHBoxLayout()
        noteTypeLay.addWidget(QLabel('Notetype: '))
        noteTypeLay.addWidget(self.noteType)
        self._main_layout.addLayout(noteTypeLay)

        sentenceLay = QHBoxLayout()
        sentenceLay.addWidget(QLabel('Sentence Field:'))
        sentenceLay.addWidget(self.sentenceField)
        self._main_layout.addLayout(sentenceLay)

        secondaryLay = QHBoxLayout()
        secondaryLay.addWidget(QLabel('Secondary Field:'))
        secondaryLay.addWidget(self.secondaryField)
        self._main_layout.addLayout(secondaryLay)

        wordLay = QHBoxLayout()
        wordLay.addWidget(QLabel('Word Field:'))
        wordLay.addWidget(self.wordField)
        self._main_layout.addLayout(wordLay)

        notesLay = QHBoxLayout()
        notesLay.addWidget(QLabel('User Notes:'))
        notesLay.addWidget(self.notesField)
        self._main_layout.addLayout(notesLay)

        imageLay = QHBoxLayout()
        imageLay.addWidget(QLabel('Image Field:'))
        imageLay.addWidget(self.imageField)
        self._main_layout.addLayout(imageLay)

        audioLay = QHBoxLayout()
        audioLay.addWidget(QLabel('Audio Field:'))
        audioLay.addWidget(self.audioField)
        self._main_layout.addLayout(audioLay)

        otherDictsLay = QHBoxLayout()
        otherDictsLay.addWidget(QLabel('Unspecified Dictionaries Field:'))
        otherDictsLay.addWidget(self.otherDictsField)
        self._main_layout.addLayout(otherDictsLay)

        dictFieldLay = QHBoxLayout()
        dictFieldLay.addWidget(self.dictionaries)
        dictFieldLay.addWidget(self.fields)
        dictFieldLay.addWidget(self.addDictField)
        self._main_layout.addLayout(dictFieldLay)

        self._main_layout.addWidget(self.dictFieldsTable)

        separatorLay = QHBoxLayout()
        separatorLay.addWidget(QLabel('Entry Separator: '))
        separatorLay.addWidget(self.entrySeparator)
        separatorLay.addStretch()
        self._main_layout.addLayout(separatorLay)

        cancelSaveButtons = QHBoxLayout()
        cancelSaveButtons.addStretch()
        cancelSaveButtons.addWidget(self.cancelButton)
        cancelSaveButtons.addWidget(self.saveButton)
        self._main_layout.addLayout(cancelSaveButtons)

        # TODO: @ColinKennedy - why would this line be needed?
        self.setLayout(self._main_layout)


def _verify(item: typing.Optional[T]) -> T:
    if item is not None:
        return item

    raise ValueError("Item cannot be None.")
