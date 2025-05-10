# -*- coding: utf-8 -*-
#

from __future__ import annotations

import collections
import json
import logging
import re
import typing
from os.path import exists, join
from shutil import copyfile

from anki.notes import Note
from anki.utils import is_lin, is_mac, is_win
from aqt import dialogs, sound
from aqt.qt import *
from aqt.utils import ensureWidgetInScreenBoundaries

from .miutils import miAsk, miInfo

if typing.TYPE_CHECKING:
    # TODO: @ColinKennedy - fix cyclic import
    from . import midict

from . import dictdb, global_state, migaku_configuration, migaku_exporter, typer

T = typing.TypeVar("T")
_LOGGER = logging.getLogger(__name__)


class _Definition(typing.NamedTuple):
    dictionary: str
    short_definition: typing.Optional[str]
    field: str
    images: typing.Optional[str]


# TODO: @ColinKennedy - This progress window is probably (visually) messed up. Fix later
class _ProgressWindow(QWidget):
    request_stop_bulk_text_import = pyqtSignal()

    def __init__(self, text: str, parent: typing.Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.currentValue = 0

        self._textDisplay = QLabel()
        self._textDisplay.setText(text)

        self._bar = QProgressBar()
        layout = QVBoxLayout()
        layout.addWidget(self._textDisplay)
        layout.addWidget(self._bar)
        self.setLayout(layout)

    def getTotal(self) -> int:
        return self._bar.maximum()

    def setMaximum(self, value: int) -> None:
        self._bar.setMaximum(value)

    def setValue(self, value: int) -> None:
        self._bar.setValue(value)

    def setText(self, text: str) -> None:
        self._textDisplay.setText(text)

    def closeEvent(self, event: typing.Optional[QCloseEvent]) -> None:
        self.request_stop_bulk_text_import.emit()

        if event:
            event.accept()


class MITextEdit(QTextEdit):
    def __init__(
        self,
        dictInt: midict.DictInterface,
        parent: typing.Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.dictInt = dictInt
        self.setAcceptRichText(False)

    def contextMenuEvent(self, event: typing.Optional[QContextMenuEvent]) -> None:
        menu = super().createStandardContextMenu()

        if not menu:
            raise RuntimeError(
                f'No standard menu for "{self.__class__.__name__}" could be created.'
            )

        search = QAction("Search")
        search.triggered.connect(self.searchSelected)
        menu.addAction(search)

        if event:
            menu.exec(event.globalPos())
        else:
            menu.exec()

    def keyPressEvent(self, event: typing.Optional[QKeyEvent]) -> None:
        if not event:
            super().keyPressEvent(event)

            return

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_B:
                cursor = self.textCursor()
                format = QTextCharFormat()
                format.setFontWeight(
                    QFont.Weight.Bold
                    if not cursor.charFormat().font().bold()
                    else QFont.Weight.Normal
                )
                cursor.mergeCharFormat(format)

                return

            if event.key() == Qt.Key.Key_I:
                cursor = self.textCursor()
                format = QTextCharFormat()
                format.setFontItalic(
                    True if not cursor.charFormat().font().italic() else False
                )
                cursor.mergeCharFormat(format)

                return

            if event.key() == Qt.Key.Key_U:
                cursor = self.textCursor()
                format = QTextCharFormat()
                format.setUnderlineStyle(
                    QTextCharFormat.UnderlineStyle.SingleUnderline
                    if not cursor.charFormat().font().underline()
                    else QTextCharFormat.UnderlineStyle.NoUnderline
                )
                cursor.mergeCharFormat(format)

                return

        super().keyPressEvent(event)

    def searchSelected(self, in_browser: bool) -> None:
        if in_browser:
            b = dialogs.open("Browser", self.dictInt.mw)
            b.form.searchEdit.lineEdit().setText(
                "expression:*{0}*".format(self.selectedText())
            )
            b.onSearchActivated()
        else:
            self.dictInt.initSearch(self.selectedText())

    def selectedText(self) -> str:
        return self.textCursor().selectedText()


class MILineEdit(QLineEdit):
    def __init__(
        self,
        dictInt: midict.DictInterface,
        parent: typing.Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.dictInt = dictInt

    def contextMenuEvent(self, event: typing.Optional[QContextMenuEvent]) -> None:
        menu = super().createStandardContextMenu()

        if not menu:
            raise RuntimeError("No standard context menu could be created.")

        search = QAction("Search")
        search.triggered.connect(self.searchSelected)
        menu.addAction(search)

        if event:
            menu.exec(event.globalPos())

    def searchSelected(self, in_browser: bool) -> None:
        if in_browser:
            b = dialogs.open("Browser", self.dictInt.mw)
            b.form.searchEdit.lineEdit().setText(
                "Expression:*{0}*".format(self.selectedText())
            )
            b.onSearchActivated()
        else:
            self.dictInt.initSearch(self.selectedText())


class CardExporter:
    def __init__(
        self,
        dictInt: midict.DictInterface,
        sentence: str = "",
        word: str = "",
    ) -> None:
        self._shortcuts: list[QShortcut] = []
        self._progress_bar_closed_and_finished_importing: dict[QWidget, bool] = {}

        self.window = QWidget()
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidget(self.window)
        self.scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scrollArea.setWidgetResizable(True)
        self.window.setAutoFillBackground(True)
        self.dictInt = dictInt
        self.mw = self.dictInt.mw
        self.bulkTextImporting = False
        self.config = self.getConfig()
        self.definitionSettings = self.config["autoDefinitionSettings"]
        self.layout = QVBoxLayout()
        self.decks = self.getDecks()
        self.templates = self.config["ExportTemplates"]
        self.templateCB = self.getTemplateCB()
        self.deckCB = self.getDeckCB()
        self.sentenceLE = MITextEdit(dictInt=dictInt)
        self.secondaryLE = MITextEdit(dictInt=dictInt)
        self.notesLE = MITextEdit(dictInt=dictInt)
        self.wordLE = MILineEdit(dictInt=dictInt)
        self.tagsLE = MILineEdit(dictInt=dictInt)
        self.definitions = self.getDefinitions()
        self.autoAdd = QCheckBox("Add Extension Cards Automatically")
        self.autoAdd.setChecked(self.config["autoAddCards"])
        self.searchUnknowns = QSpinBox()
        self.searchUnknowns.setValue(self.config.get("unknownsToSearch", 3))
        self.searchUnknowns.setMinimum(0)
        self.searchUnknowns.setMaximum(10)
        self.addDefinitionsCheckbox = QCheckBox("Automatically Add Definitions")
        self.addDefinitionsCheckbox.setChecked(self.config["autoAddDefinitions"])
        self.definitionSettingsButton = QPushButton("Automatic Definition Settings")
        self.clearButton = QPushButton("Clear Current Card")
        self.cancelButton = QPushButton("Cancel")
        self.addButton = QPushButton("Add")
        self.audioMap = QLabel("No Audio Selected")
        self.imageMap = QLabel("No Image Selected")
        self.exportJS = self.config["jReadingCards"]
        self.imgName: typing.Optional[str] = None
        self.imgPath: typing.Optional[str] = None
        self.audioTag: typing.Optional[str] = None
        self.audioName: typing.Optional[str] = None
        self.audioPath: typing.Optional[str] = None
        self.audioPlay = QPushButton("Play")
        self.audioPlay.clicked.connect(self.playAudio)
        self.audioPlay.hide()
        self.setupLayout()
        self.initHandlers()
        self.setColors()
        self.window.setLayout(self.layout)
        self.window.setMinimumSize(490, 650)
        self.scrollArea.setMinimumWidth(490)
        self.scrollArea.setMinimumHeight(400)
        self.scrollArea.resize(490, 654)
        self.scrollArea.setWindowIcon(
            QIcon(join(self.dictInt.addonPath, "icons", "migaku.png"))
        )
        self.scrollArea.setWindowTitle("Migaku Card Exporter")
        self.definitionList: list[_Definition] = []
        self.word = word
        self.sentence = sentence
        self.initTooltips()
        self.restoreSizePos()
        self.setHotkeys()
        self.scrollArea.show()
        self.alwaysOnTop = self.config["dictAlwaysOnTop"]
        self.maybeSetToAlwaysOnTop()
        self.bulkMediaExportProgressWindow: typing.Optional[_ProgressWindow] = None

    def _closeProgressBar(self, progressBar: typing.Optional[QWidget]) -> None:
        if not progressBar:
            return

        self._progress_bar_closed_and_finished_importing[progressBar] = True
        progressBar.close()
        progressBar.deleteLater()

    def _writeConfig(self, config: typer.Configuration) -> None:
        self.mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], config),
        )

    def maybeSetToAlwaysOnTop(self) -> None:
        if self.alwaysOnTop:
            self.scrollArea.setWindowFlags(
                self.scrollArea.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
            )
            self.scrollArea.show()

    def attemptAutoAdd(self, bulkExport: bool) -> None:
        if self.autoAdd.isChecked() or bulkExport:
            self.addCard()

    def initTooltips(self) -> None:
        if self.config["tooltips"]:
            self.templateCB.setToolTip("Select the export template.")
            self.deckCB.setToolTip("Select the deck to export to.")
            self.clearButton.setToolTip("Clear the card exporter.")

    def restoreSizePos(self) -> None:
        sizePos = self.config["exporterSizePos"]
        if sizePos:
            self.scrollArea.resize(sizePos[2], sizePos[3])
            self.scrollArea.move(sizePos[0], sizePos[1])
            ensureWidgetInScreenBoundaries(self.scrollArea)

    def setHotkeys(self) -> None:
        self._shortcuts.append(
            QShortcut(
                QKeySequence("Ctrl+S"),
                self.scrollArea,
                lambda: self.attemptSearch(False),
            )
        )
        self._shortcuts.append(
            QShortcut(
                QKeySequence("Ctrl+F"),
                self.scrollArea,
                lambda: self.attemptSearch(True),
            )
        )

        shortcut = QShortcut(QKeySequence("Esc"), self.scrollArea)
        self._shortcuts.append(shortcut)
        shortcut.activated.connect(self.scrollArea.hide)

    def attemptSearch(self, in_browser: bool) -> None:
        focused = self.scrollArea.focusWidget()

        if isinstance(focused, (MILineEdit, MITextEdit)):
            focused.searchSelected(in_browser)

    def setColors(self) -> None:
        if self.dictInt.nightModeToggler.day:
            self.scrollArea.setPalette(self.dictInt.ogPalette)
            if is_mac:
                self.templateCB.setStyleSheet(self.dictInt.getMacComboStyle())
                self.deckCB.setStyleSheet(self.dictInt.getMacComboStyle())
                self.definitions.setStyleSheet(self.dictInt.getMacTableStyle())
            else:
                self.templateCB.setStyleSheet("")
                self.deckCB.setStyleSheet("")
                self.definitions.setStyleSheet("")
        else:
            self.scrollArea.setPalette(self.dictInt.nightPalette)
            if is_mac:
                self.templateCB.setStyleSheet(self.dictInt.getMacNightComboStyle())
                self.deckCB.setStyleSheet(self.dictInt.getMacNightComboStyle())
            else:
                self.templateCB.setStyleSheet(self.dictInt.getComboStyle())
                self.deckCB.setStyleSheet(self.dictInt.getComboStyle())
            self.definitions.setStyleSheet(self.dictInt.getTableStyle())

    def addNote(self, note: Note, did: int) -> bool:
        model = note.note_type()

        if not model:
            raise RuntimeError(f'Note "{note}" has no Note type.')

        model["did"] = int(did)
        ret = note.dupeOrEmpty()
        if ret == 1:
            if not miAsk(
                "Your note's sorting field will be empty with this configuration. Would you like to continue?",
                self.scrollArea,
                self.dictInt.nightModeToggler.day,
            ):
                return False
        if "{{cloze:" in model["tmpls"][0]["qfmt"]:
            if not self.mw.col.models._availClozeOrds(
                model, note.joined_fields(), False
            ):
                if not miAsk(
                    "You have a cloze deletion note type "
                    "but have not made any cloze deletions. Would you like to continue?",
                    self.scrollArea,
                    self.dictInt.nightModeToggler.day,
                ):
                    return False
        cards = self.mw.col.addNote(note)
        if not cards:
            miInfo(
                (
                    """\
The current input and template combination \
will lead to a blank card and therefore has not been added. \
Please review your template and notetype combination."""
                ),
                level="wrn",
                day=self.dictInt.nightModeToggler.day,
            )
            return False
        self.mw.col.save()
        self.mw.reset()

        return True

    def getDecks(self) -> dict[str, int]:
        decksRaw = self.mw.col.decks.decks
        decks: dict[str, int] = {}

        for did, deck in decksRaw.items():
            if not deck["dyn"]:
                decks[deck["name"]] = did

        return decks

    def getDeckCB(self) -> QComboBox:
        cb = QComboBox()
        decks = list(self.decks.keys())
        decks.sort()
        cb.addItems(decks)
        current = self.config["currentDeck"]
        if current and current in decks:
            cb.setCurrentText(current)
        cb.currentIndexChanged.connect(
            lambda: self.dictInt.writeConfig("currentDeck", cb.currentText())
        )
        return cb

    def hideEvent(self, event: QHideEvent) -> None:
        self.scrollArea.hideEvent(
            event
        )  # TODO: @ColinKennedy - not sure if this is needed
        self.saveSizeAndPos()
        event.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.scrollArea.closeEvent(
            event
        )  # TODO: @ColinKennedy - not sure if this is needed
        self.clearCurrent()
        self.saveSizeAndPos()
        event.accept()

    def saveSizeAndPos(self) -> None:
        pos = self.scrollArea.pos()
        x = pos.x()
        y = pos.y()
        size = self.scrollArea.size()
        width = size.width()
        height = size.height()
        posSize = (x, y, width, height)
        self.dictInt.writeConfig("exporterSizePos", posSize)
        self.dictInt.writeConfig("exporterLastTags", self.tagsLE.text())

    def initHandlers(self) -> None:
        self.definitionSettingsButton.clicked.connect(self.definitionSettingsWidget)
        self.clearButton.clicked.connect(self.clearCurrent)
        self.cancelButton.clicked.connect(self.scrollArea.close)
        self.addButton.clicked.connect(self.addCard)
        self.addDefinitionsCheckbox.clicked.connect(self.saveAddDefinitionChecked)
        self.searchUnknowns.valueChanged.connect(self.saveSearchUnknowns)
        self.autoAdd.clicked.connect(self.saveAutoAddChecked)

    def saveSearchUnknowns(self) -> None:
        config = self.getConfig()
        config["unknownsToSearch"] = self.searchUnknowns.value()
        self.config = config
        migaku_configuration.refresh_configuration(config)
        self._writeConfig(config)

    def saveAutoAddChecked(self) -> None:
        config = self.getConfig()
        config["autoAddCards"] = self.autoAdd.isChecked()
        self.config = config
        migaku_configuration.refresh_configuration(config)
        self._writeConfig(config)

    def saveAddDefinitionChecked(self) -> None:
        config = self.getConfig()
        config["autoAddDefinitions"] = self.addDefinitionsCheckbox.isChecked()
        self.config = config
        migaku_configuration.refresh_configuration(config)
        self._writeConfig(config)

    def addCard(self) -> None:
        templateName = self.templateCB.currentText()
        if templateName in self.templates:
            template = self.templates[templateName]
            noteType = template["noteType"]
            model = self.mw.col.models.by_name(noteType)
            if model:
                note = Note(self.mw.col, model)
                modelFields = self.mw.col.models.field_names(model)
                fieldsValues, imgField, audioField, tagsField = self.getFieldsValues(
                    template
                )
                word = self.wordLE.text()
                if not fieldsValues:
                    miInfo(
                        "The currently selected template and values will lead to an invalid card. Please try again.",
                        level="wrn",
                        day=self.dictInt.nightModeToggler.day,
                    )
                    return
                for field in fieldsValues:
                    if field in modelFields:
                        note[field] = template["separator"].join(fieldsValues[field])
                did = 0
                deck = self.deckCB.currentText()
                if deck in self.decks:
                    did = self.decks[deck]
                if did:
                    if word and self.addDefinitionsCheckbox.isChecked():
                        note = self.automaticallyAddDefinitions(note, word, template)
                    if self.exportJS:
                        note = self.dictInt.jHandler.attemptGenerate(note)
                    if not self.addNote(note, did):
                        return
                if imgField and imgField in modelFields:
                    self.moveImageToMediaFolder()
                if audioField and audioField in modelFields:
                    self.moveAudioToMediaFolder()
                self.clearCurrent()
                return
            else:
                miInfo(
                    "The notetype for the currently selected template does not exist in the currently loaded profile.",
                    level="err",
                    day=self.dictInt.nightModeToggler.day,
                )
                return
        miInfo(
            "A card could not be added with this current configuration. Please ensure that your template is configured correctly for this collection.",
            level="err",
            day=self.dictInt.nightModeToggler.day,
        )

    # TODO: @ColinKennedy - `word` might not be a str. Check later.
    def automaticallyAddDefinitions(
        self, note: Note, word: str, template: typer.ExportTemplate
    ) -> Note:
        if not self.definitionSettings:
            return note

        dictToTable = self.getDictionaryNameToTableNameDictionary()
        unspecifiedDefinitionField = template["unspecified"]
        specificFields = template["specific"]
        dictionaries: list[typer.DictionaryConfiguration] = []
        for setting in self.definitionSettings:
            dictName = setting["name"]
            if dictName in dictToTable:
                table = dictToTable[dictName]
                limit = setting["limit"]
                targetField = unspecifiedDefinitionField
                for specificField, specificDictionaries in specificFields.items():
                    if dictName in specificDictionaries:
                        targetField = specificField
                dictionaries.append(
                    {
                        "tableName": table,
                        "limit": limit,
                        "field": targetField,
                        "dictName": dictName,
                    }
                )

        return migaku_exporter.addDefinitionsToCardExporterNote(
            note, word, dictionaries
        )

    def moveImageToMediaFolder(self) -> None:
        if self.imgPath and self.imgName:
            if exists(self.imgPath):
                path = join(self.mw.col.media.dir(), self.imgName)
                if not exists(path):
                    copyfile(self.imgPath, path)

    def fieldValid(self, field: str) -> bool:
        return field != "Don't Export"

    def getDictionaryEntries(self, dictionary: str) -> list[str]:
        finList: list[str] = []
        idxs: list[int] = []
        for idx, defList in enumerate(self.definitionList):
            if defList.dictionary == dictionary:
                finList.append(defList.field)
                idxs.append(idx)
        idxs.reverse()
        for idx in idxs:
            self.definitionList.pop(idx)
        return finList

    def emptyValueIfEmptyHtml(self, value: str) -> str:
        pattern = r"(?:<[^<]+?>)"
        if re.sub(pattern, "", value) == "":
            return ""
        return value

    def getFieldsValues(
        self,
        t: typer.ExportTemplate,
    ) -> tuple[dict[str, list[str]], typing.Optional[str], typing.Optional[str], str]:
        imgField: typing.Optional[str] = None
        audioField: typing.Optional[str] = None
        tagsField = ""
        fields: dict[str, list[str]] = {}
        sentenceText = self.cleanHTML(self.sentenceLE.toHtml())
        sentenceText = self.emptyValueIfEmptyHtml(sentenceText)
        if sentenceText != "":
            sentenceField = t["sentence"]
            if sentenceField != "Don't Export":
                if self.fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        secondaryText = self.cleanHTML(self.secondaryLE.toHtml())
        secondaryText = self.emptyValueIfEmptyHtml(secondaryText)
        if secondaryText != "" and "secondary" in t:
            secondaryField = t["secondary"]
            if secondaryField != "Don't Export":
                if secondaryField and self.fieldValid(secondaryField):
                    fields[secondaryField] = [secondaryText]
        notesText = self.cleanHTML(self.notesLE.toHtml())
        notesText = self.emptyValueIfEmptyHtml(notesText)
        if notesText != "" and "notes" in t:
            notesField = t["notes"]
            if notesField != "Don't Export":
                if self.fieldValid(notesField):
                    fields[notesField] = [notesText]
        wordText = self.wordLE.text()
        if wordText != "":
            wordField = t["word"]
            if wordField != "Don't Export":
                if self.fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self.tagsLE.text()
        if tagsText != "":
            tagsField = tagsText
        imgText = self.imageMap.text()
        if imgText != "No Image Selected" and self.imgName:
            imgField = t["image"]
            if imgField != "Don't Export":
                imgTag = '<img src="' + self.imgName + '">'
                if self.fieldValid(imgField):
                    if imgField not in fields:
                        fields[imgField] = [imgTag]
                    else:
                        fields[imgField].append(imgTag)
        audioText = self.imageMap.text()
        if audioText != "No Audio Selected" and "audio" in t and self.audioTag:
            audioField = t["audio"]
            if audioField != "Don't Export":
                if self.fieldValid(audioField):
                    if audioField not in fields:
                        fields[audioField] = [self.audioTag]
                    else:
                        fields[audioField].append(self.audioTag)
        specific = t["specific"]
        for field in specific:
            for dictionary in specific[field]:
                if field not in fields:
                    fields[field] = self.getDictionaryEntries(dictionary)
                else:
                    fields[field] += self.getDictionaryEntries(dictionary)
        unspecified = t["unspecified"]
        for idx, defList in enumerate(self.definitionList):
            if unspecified not in fields:
                fields[unspecified] = [defList.field]
            else:
                fields[unspecified].append(defList.field)
        return fields, imgField, audioField, tagsField

    def clearCurrent(self) -> None:
        self.definitions.setRowCount(0)
        self.sentenceLE.clear()
        self.secondaryLE.clear()
        self.notesLE.clear()
        self.wordLE.clear()
        self.definitionList[:] = []
        self.audioMap.clear()
        self.audioMap.setText("No Audio Selected")
        self.audioPlay.hide()
        self.audioTag = None
        self.audioName = None
        self.audioPath = None
        self.imageMap.clear()
        self.imageMap.setText("No Image Selected")
        self.imgPath = None
        self.imgName = None

    def getDefinitions(self) -> QTableWidget:
        macLin = False
        if is_mac or is_lin:
            macLin = True
        definitions = QTableWidget()
        definitions.setMinimumHeight(100)
        definitions.setColumnCount(3)
        tableHeader = definitions.horizontalHeader()

        if not tableHeader:
            raise RuntimeError(
                f'Expected a horizontal header for "{definitions}" widget.'
            )

        vHeader = definitions.verticalHeader()

        if not vHeader:
            raise RuntimeError(f'Expected a vertical for "{definitions}" widget.')

        vHeader.setDefaultSectionSize(50)
        vHeader.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tableHeader.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        definitions.setColumnWidth(1, 100)
        tableHeader.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        definitions.setRowCount(0)
        definitions.setSortingEnabled(False)
        definitions.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        definitions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        definitions.setColumnWidth(2, 40)
        tableHeader.hide()
        return definitions

    def getConfig(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration, self.mw.addonManager.getConfig(__name__)
        )

    def setupLayout(self) -> None:
        tempLayout = QHBoxLayout()
        tempLayout.addWidget(QLabel("Template: "))
        self.templateCB.setFixedSize(120, 30)
        tempLayout.addWidget(self.templateCB)
        tempLayout.addWidget(QLabel(" Deck: "))
        self.deckCB.setFixedSize(120, 30)
        tempLayout.addWidget(self.deckCB)
        tempLayout.addStretch()
        tempLayout.setSpacing(2)
        self.clearButton.setFixedSize(130, 30)
        tempLayout.addWidget(self.clearButton)
        self.layout.addLayout(tempLayout)
        sentenceL = QLabel("Sentence")
        self.layout.addWidget(sentenceL)
        self.layout.addWidget(self.sentenceLE)
        secondaryL = QLabel("Secondary")
        self.layout.addWidget(secondaryL)
        self.layout.addWidget(self.secondaryLE)
        wordL = QLabel("Word")
        self.layout.addWidget(wordL)
        self.layout.addWidget(self.wordLE)
        notesL = QLabel("User Notes")
        self.layout.addWidget(notesL)
        self.layout.addWidget(self.notesLE)

        self.sentenceLE.setMinimumHeight(60)
        self.secondaryLE.setMinimumHeight(60)
        self.notesLE.setMinimumHeight(90)
        self.sentenceLE.setMaximumHeight(120)
        self.secondaryLE.setMaximumHeight(120)
        f = self.sentenceLE.font()
        f.setPointSize(16)
        self.sentenceLE.setFont(f)
        self.secondaryLE.setFont(f)
        self.notesLE.setFont(f)
        f = self.wordLE.font()
        f.setPointSize(20)
        self.wordLE.setFont(f)

        self.wordLE.setFixedHeight(40)
        definitionsL = QLabel("Definitions")
        self.layout.addWidget(definitionsL)
        self.layout.addWidget(self.definitions)

        self.layout.addWidget(QLabel("Audio"))
        self.layout.addWidget(self.audioMap)
        self.layout.addWidget(self.audioPlay)
        self.layout.addWidget(QLabel("Image"))
        self.layout.addWidget(self.imageMap)
        tagsL = QLabel("Tags")
        self.layout.addWidget(tagsL)
        lastTags = self.config.get("exporterLastTags", "")
        self.tagsLE.setText(lastTags)
        self.layout.addWidget(self.tagsLE)

        unknownLayout = QHBoxLayout()
        unknownLayout.addWidget(QLabel("Number of unknown words to search: "))
        unknownLayout.addStretch()
        unknownLayout.addWidget(self.searchUnknowns)
        self.layout.addLayout(unknownLayout)

        autoDefLayout = QHBoxLayout()
        autoDefLayout.addWidget(self.addDefinitionsCheckbox)
        autoDefLayout.addStretch()
        self.definitionSettingsButton.setFixedSize(202, 30)
        autoDefLayout.addWidget(self.definitionSettingsButton)
        self.layout.addLayout(autoDefLayout)

        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.autoAdd)
        buttonLayout.addStretch()
        self.cancelButton.setFixedSize(100, 30)
        self.addButton.setFixedSize(100, 30)
        buttonLayout.addWidget(self.cancelButton)
        buttonLayout.addWidget(self.addButton)
        self.layout.addLayout(buttonLayout)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(2)

    def getTemplateCB(self) -> QComboBox:
        cb = QComboBox()
        cb.addItems(self.templates)
        current = self.config["currentTemplate"]

        cb.currentIndexChanged.connect(
            lambda: self.dictInt.writeConfig("currentTemplate", cb.currentText())
        )
        if current and current in self.templates:
            cb.setCurrentText(current)
        return cb

    def addImgs(self, word: str, imgs: str, thumbs: QWidget) -> None:
        self.focusWindow()
        defEntry = _Definition("Google Images", None, imgs, imgs)
        if defEntry in self.definitionList:
            miInfo(
                "A card cannot contain duplicate definitions.",
                level="not",
                day=self.dictInt.nightModeToggler.day,
            )
            return
        self.definitionList.append(defEntry)
        rc = self.definitions.rowCount()
        self.definitions.setRowCount(rc + 1)
        self.definitions.setItem(rc, 0, QTableWidgetItem("Google Images"))
        self.definitions.setCellWidget(rc, 1, thumbs)
        deleteButton = QPushButton("X")
        deleteButton.setFixedWidth(40)
        deleteButton.clicked.connect(lambda: self.removeImgs(imgs))
        self.definitions.setCellWidget(rc, 2, deleteButton)
        self.definitions.resizeRowsToContents()
        if self.wordLE.text() == "":
            self.wordLE.setText(word)

    def exportWord(self, word: str) -> None:
        self.wordLE.setText(word)

    def removeImgs(self, imgs: str) -> None:
        model = self.definitions.selectionModel()

        if not model:
            _LOGGER.error(f'Cannot remove "%s" images. No model was found.', imgs)

            return

        # TODO: @ColinKennedy - try/except
        try:
            row = model.currentIndex().row()
            self.definitions.removeRow(row)
            self.removeImgFromDefinitionList(imgs)
        except:
            return

    def removeImgFromDefinitionList(self, imgs: str) -> None:
        for idx, entry in enumerate(self.definitionList):
            if entry.dictionary == "Google Images" and entry.images == imgs:
                self.definitionList.pop(idx)
                break

    def addDefinition(self, dictName: str, word: str, definition: str) -> None:
        self.focusWindow()
        if len(definition) > 40:
            shortDef = definition.replace("<br>", " ")[:40] + "..."
        else:
            shortDef = definition.replace("<br>", " ")
        defEntry = _Definition(dictName, shortDef, definition, None)
        if defEntry in self.definitionList:
            miInfo(
                "A card can not contain duplicate definitions.",
                level="not",
                day=self.dictInt.nightModeToggler.day,
            )
            return
        self.definitionList.append(defEntry)
        rc = self.definitions.rowCount()
        self.definitions.setRowCount(rc + 1)
        self.definitions.setItem(rc, 0, QTableWidgetItem(dictName))
        self.definitions.setItem(rc, 1, QTableWidgetItem(shortDef))
        deleteButton = QPushButton("X")
        deleteButton.setFixedWidth(40)
        deleteButton.clicked.connect(self.removeDefinition)
        self.definitions.setCellWidget(rc, 2, deleteButton)
        self.definitions.resizeRowsToContents()
        if self.wordLE.text() == "":
            self.wordLE.setText(word)

    def exportImage(self, path: str, name: str) -> None:
        self.imgName = name
        self.imgPath = path
        if self.imageMap:
            self.imageMap.setText("")
            screenshot = QPixmap(path)
            screenshot = screenshot.scaled(
                200,
                200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.imageMap.setPixmap(screenshot)

    def exportAudio(self, path: str, tag: str, name: str) -> None:
        self.audioTag = tag
        self.audioName = name
        self.audioPath = path
        self.audioMap.setText(tag)
        self.audioPlay.show()

    def moveAudioToMediaFolder(self) -> None:
        if self.audioPath and self.audioName:
            if exists(self.audioPath):
                path = join(self.mw.col.media.dir(), self.audioName)
                if not exists(path):
                    copyfile(self.audioPath, path)

    def playAudio(self) -> None:
        if self.audioPath:
            sound.play(self.audioPath)

    def exportSentence(self, sentence: str) -> None:
        self.focusWindow()
        self.sentenceLE.setHtml(sentence)

    def exportSecondary(self, secondary: str) -> None:
        self.secondaryLE.setHtml(secondary)

    def removeFromDefinitionList(self, dictName: str, shortDef: str) -> None:
        for idx, entry in enumerate(self.definitionList):
            if entry.dictionary == dictName and entry.short_definition == shortDef:
                self.definitionList.pop(idx)
                break

    def removeDefinition(self) -> None:
        # TODO: @ColinKennedy Remove later
        model = self.definitions.selectionModel()

        if not model:
            raise RuntimeError(f'No model found for "{self.definitions}" definitions.')

        row = model.currentIndex().row()

        dictName = _verify(self.definitions.item(row, 0)).text()
        shortDef = _verify(self.definitions.item(row, 1)).text()

        self.definitions.removeRow(row)
        self.removeFromDefinitionList(dictName, shortDef)

    def focusWindow(self) -> None:
        self.scrollArea.show()
        if self.scrollArea.windowState() == Qt.WindowState.WindowMinimized:
            self.scrollArea.setWindowState(Qt.WindowState.WindowNoState)
        self.scrollArea.setFocus()
        self.scrollArea.activateWindow()

    def getDictionaryNameToTableNameDictionary(self) -> dict[str, str]:
        dictToTable = collections.OrderedDict()
        dictToTable["None"] = "None"
        dictToTable["Forvo"] = "Forvo"
        dictToTable["Google Images"] = "Google Images"
        database = dictdb.get()

        for dictTableName in sorted(database.getAllDicts()):
            dictName = database.cleanDictName(dictTableName)
            dictToTable[dictName] = dictTableName

        return dictToTable

    def definitionSettingsWidget(self) -> None:
        settingsWidget = QWidget(self.scrollArea, Qt.WindowType.Window)
        layout = QVBoxLayout()
        dict1 = QComboBox()
        dict2 = QComboBox()
        dict3 = QComboBox()

        dictToTable = self.getDictionaryNameToTableNameDictionary()
        dictNames = dictToTable.keys()
        dict1.addItems(dictNames)
        dict2.addItems(dictNames)
        dict3.addItems(dictNames)

        dict1Lay = QHBoxLayout()
        dict1Lay.addWidget(QLabel("1st Dictionary:"))
        dict1Lay.addStretch()
        dict1Lay.addWidget(dict1)
        dict2Lay = QHBoxLayout()
        dict2Lay.addWidget(QLabel("2nd Dictionary:"))
        dict2Lay.addStretch()
        dict2Lay.addWidget(dict2)
        dict3Lay = QHBoxLayout()
        dict3Lay.addWidget(QLabel("3rd Dictionary:"))
        dict3Lay.addStretch()
        dict3Lay.addWidget(dict3)

        howMany1 = QSpinBox()
        howMany1.setValue(1)
        howMany1.setMinimum(1)
        howMany1.setMaximum(20)
        hmLay1 = QHBoxLayout()
        hmLay1.addWidget(QLabel("Max Definitions:"))
        hmLay1.addWidget(howMany1)

        howMany2 = QSpinBox()
        howMany2.setValue(1)
        howMany2.setMinimum(1)
        howMany2.setMaximum(20)
        hmLay2 = QHBoxLayout()
        hmLay2.addWidget(QLabel("Max Definitions:"))
        hmLay2.addWidget(howMany2)

        howMany3 = QSpinBox()
        howMany3.setValue(1)
        howMany3.setMinimum(1)
        howMany3.setMaximum(20)
        hmLay3 = QHBoxLayout()
        hmLay3.addWidget(QLabel("Max Definitions:"))
        hmLay3.addWidget(howMany3)

        layout.addLayout(dict1Lay)
        layout.addLayout(hmLay1)
        layout.addLayout(dict2Lay)
        layout.addLayout(hmLay2)
        layout.addLayout(dict3Lay)
        layout.addLayout(hmLay3)

        if self.definitionSettings:
            howManys = [howMany1, howMany2, howMany3]
            dicts = [dict1, dict2, dict3]
            for idx, setting in enumerate(self.definitionSettings):
                dictName = setting["name"]
                if dictName in dictToTable:
                    limit = setting["limit"]
                    dicts[idx].setCurrentText(dictName)
                    howManys[idx].setValue(limit)

        save = QPushButton("Save Settings")
        layout.addWidget(save)
        layout.setContentsMargins(4, 4, 4, 4)
        save.clicked.connect(
            lambda: self.saveDefinitionSettings(
                settingsWidget,
                dict1.currentText(),
                howMany1.value(),
                dict2.currentText(),
                howMany2.value(),
                dict3.currentText(),
                howMany3.value(),
            )
        )
        settingsWidget.setWindowTitle("Definition Settings")
        settingsWidget.setWindowIcon(
            QIcon(join(self.dictInt.addonPath, "icons", "migaku.png"))
        )
        settingsWidget.setLayout(layout)
        settingsWidget.show()

    def saveDefinitionSettings(
        self,
        settingsWidget: QWidget,
        dict1: str,
        limit1: int,
        dict2: str,
        limit2: int,
        dict3: str,
        limit3: int,
    ) -> None:
        definitionSettings: list[typer.DefinitionSetting] = []
        definitionSettings.append({"name": dict1, "limit": limit1})
        definitionSettings.append({"name": dict2, "limit": limit2})
        definitionSettings.append({"name": dict3, "limit": limit3})
        config = self.getConfig()
        self.definitionSettings = definitionSettings
        config["autoDefinitionSettings"] = definitionSettings
        self._writeConfig(config)
        settingsWidget.close()
        settingsWidget.deleteLater()

    def cleanHTML(self, text: str) -> str:
        # Switch bold style to <b>
        text = re.sub(
            r"(<span style=\"[^\"]*?)font-weight:600;(.*?\">.*?</span>)",
            r"<b>\1\2</b>",
            text,
            flags=re.S,
        )
        text = re.sub(
            r"(<span style=\"[^\"]*?)font-style:italic;(.*?\">.*?</span>)",
            r"<i>\1\2</i>",
            text,
            flags=re.S,
        )
        text = re.sub(
            r"(<span style=\"[^\"]*?)text-decoration: underline;(.*?\">.*?</span>)",
            r"<u>\1\2</u>",
            text,
            flags=re.S,
        )

        # Switch paragraphs to <br>
        text = re.sub(r"</p>", r"<br />", text, re.S)

        # Trim unneeded bits
        text = re.sub(r".+</head>", r"", text, flags=re.S)
        text = re.sub(
            r"(<html[^>]*?>|</html>|<body[^>]*?>|</body>|<p[^>]*?>|<span[^>]*?>|</span>)",
            r"",
            text,
            flags=re.S,
        )
        text = text.strip()

        # Remove any trailing <br /> (there can be two)
        text = re.sub(r"<br />$", r"", text)
        text = re.sub(r"<br />$", r"", text)

        # For debugging
        # text = html.escape(text)
        return text

    def addTextCard(self, card: typer.Card) -> None:
        templateName = self.templateCB.currentText()
        sentence = card["primary"]
        word = ""
        unknowns = card["unknownWords"]
        if unknowns:
            word = unknowns[0]

        if templateName in self.templates:
            template = self.templates[templateName]
            noteType = template["noteType"]
            model = self.mw.col.models.by_name(noteType)
            if model:
                note = Note(self.mw.col, model)
                modelFields = self.mw.col.models.field_names(model)
                fieldsValues, tagsField = self.getFieldsValuesForTextCard(
                    template, word, sentence
                )
                if fieldsValues:
                    for field in fieldsValues:
                        if field in modelFields:
                            note[field] = template["separator"].join(
                                fieldsValues[field]
                            )
                    did: typing.Optional[int] = None
                    deck = self.deckCB.currentText()
                    if deck in self.decks:
                        did = self.decks[deck]
                    if did:
                        if word and self.addDefinitionsCheckbox.isChecked():
                            note = self.automaticallyAddDefinitions(
                                note, word, template
                            )
                        if self.exportJS:
                            note = self.dictInt.jHandler.attemptGenerate(note)
                        model["did"] = int(did)
                        self.mw.col.addNote(note)
                        self.mw.col.save()
                else:
                    print("Invalid field values")

    def getFieldsValuesForTextCard(
        self,
        t: typer.ExportTemplate,
        wordText: str,
        sentenceText: str,
    ) -> tuple[dict[str, list[str]], str]:
        tagsField = ""
        fields: dict[str, list[str]] = {}
        if sentenceText != "":
            sentenceField = t["sentence"]
            if sentenceField != "Don't Export":
                if self.fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        if wordText != "":
            wordField = t["word"]
            if wordField != "Don't Export":
                if self.fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self.tagsLE.text()
        if tagsText != "":
            tagsField = tagsText
        return fields, tagsField

    def bulkTextExport(self, cards: typing.Sequence[typer.Card]) -> None:
        self.bulkTextImporting = True
        total = len(cards)
        importingMessage = "Importing {} of " + str(total) + " cards."
        progressWidget = self.getProgressBar(
            "Migaku Dictionary - Importing Text Cards", importingMessage.format(0)
        )
        progressWidget.setMaximum(total)
        for idx, card in enumerate(cards):
            if not self.bulkTextImporting:
                miInfo(
                    "Importing cards from the extension has been cancelled.\n\n{} of {} were added.".format(
                        idx, total
                    )
                )
                return
            self.addTextCard(card)
            progressWidget.setValue(idx + 1)
            progressWidget.setText(importingMessage.format(idx + 1))
            self.mw.app.processEvents()
        self.bulkTextImporting = False
        self._closeProgressBar(progressWidget)

    def addMediaCard(self, card: typer.Card) -> None:
        templateName = self.templateCB.currentText()
        word = ""
        unknowns = card["unknownWords"]
        if unknowns:
            word = unknowns[0]
        if templateName in self.templates:
            template = self.templates[templateName]
            noteType = template["noteType"]
            model = self.mw.col.models.by_name(noteType)
            if model:
                note = Note(self.mw.col, model)
                modelFields = self.mw.col.models.field_names(model)
                fieldsValues, _ = self.getFieldsValuesForMediaCard(template, word, card)

                if not fieldsValues:
                    print("Invalid field values")

                    return

                for field in fieldsValues:
                    if field in modelFields:
                        note[field] = template["separator"].join(fieldsValues[field])
                did: typing.Optional[int] = None
                deck = self.deckCB.currentText()
                if deck in self.decks:
                    did = self.decks[deck]
                if did:
                    if word and self.addDefinitionsCheckbox.isChecked():
                        note = self.automaticallyAddDefinitions(note, word, template)
                    if self.exportJS:
                        note = self.dictInt.jHandler.attemptGenerate(note)
                    model["did"] = int(did)
                    self.mw.col.addNote(note)
                    self.mw.col.save()

    def getFieldsValuesForMediaCard(
        self,
        t: typer.ExportTemplate,
        wordText: str,
        card: typer.Card,
    ) -> tuple[dict[str, list[str]], str]:
        sentenceText = card["primary"]
        secondaryText = card["secondary"]
        imageFile = card["image"]
        audioFile = card["audio"]
        audio: typing.Optional[str] = None
        image: typing.Optional[str] = None
        if audioFile:
            audio = "[sound:" + audioFile + "]"
        if imageFile:
            image = imageFile
        imgField: typing.Optional[str] = None
        audioField: typing.Optional[str] = None
        tagsField = ""
        fields: dict[str, list[str]] = {}
        if sentenceText != "":
            sentenceField = t["sentence"]
            if sentenceField != "Don't Export":
                if self.fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        if secondaryText != "" and "secondary" in t:
            secondaryField = t["secondary"]
            if secondaryField and secondaryField != "Don't Export":
                if self.fieldValid(secondaryField):
                    fields[secondaryField] = [secondaryText]
        if wordText != "":
            wordField = t["word"]
            if wordField != "Don't Export":
                if self.fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self.tagsLE.text()
        if tagsText != "":
            tagsField = tagsText
        if image:
            imgField = t["image"]
            imgTag = '<img src="' + image + '">'
            if self.fieldValid(imgField):
                if imgField not in fields:
                    fields[imgField] = [imgTag]
                else:
                    fields[imgField].append(imgTag)
        if audio:
            audioField = t["audio"]
            if self.fieldValid(audioField):
                if audioField not in fields:
                    fields[audioField] = [audio]
                else:
                    fields[audioField].append(audio)
        return fields, tagsField

    def bulkMediaExport(self, card: typer.Card) -> None:
        if global_state.IS_BULK_MEDIA_EXPORT_CANCELLED:
            return
        if not self.bulkMediaExportProgressWindow:
            total = card["total"]
            importingMessage = "Importing {} of " + str(total) + " cards."
            self.bulkMediaExportProgressWindow = self.getProgressBar(
                "Migaku Dictionary - Importing Media Cards", importingMessage.format(0)
            )
            self.bulkMediaExportProgressWindow.setMaximum(total)
            self.bulkMediaExportProgressWindow.currentValue = 0
        else:
            importingMessage = (
                "Importing {} of "
                + str(self.bulkMediaExportProgressWindow.getTotal())
                + " cards."
            )
        self.addMediaCard(card)

        # TODO: @ColinKennedy remove this try/except later
        try:
            if (
                global_state.IS_BULK_MEDIA_EXPORT_CANCELLED
                or not self.bulkMediaExportProgressWindow
            ):
                if self.bulkMediaExportProgressWindow:
                    self._closeProgressBar(self.bulkMediaExportProgressWindow)
                return
            self.bulkMediaExportProgressWindow.currentValue += 1
            self.bulkMediaExportProgressWindow.setValue(
                self.bulkMediaExportProgressWindow.currentValue
            )
            self.bulkMediaExportProgressWindow.setText(
                importingMessage.format(self.bulkMediaExportProgressWindow.currentValue)
            )
            self.mw.app.processEvents()

            total = self.bulkMediaExportProgressWindow.getTotal()

            if self.bulkMediaExportProgressWindow.currentValue == total:
                if total == 1:
                    miInfo("{} card has been imported.".format(total))
                else:
                    miInfo("{} cards have been imported.".format(total))

                self._closeProgressBar(self.bulkMediaExportProgressWindow)
                self.bulkMediaExportProgressWindow = None
        except:
            pass

    def bulkMediaExportCancelledByBrowserRefresh(self) -> None:
        if not self.bulkMediaExportProgressWindow:
            return

        currentValue = self.bulkMediaExportProgressWindow.currentValue
        miInfo(
            "Importing cards from the extension has been cancelled from within the browser.\n\n {} cards were imported.".format(
                currentValue
            )
        )
        self._closeProgressBar(self.bulkMediaExportProgressWindow)
        self.bulkMediaExportProgressWindow = None
        global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = False

    def getProgressBar(
        self,
        title: str,
        initialText: str,
    ) -> _ProgressWindow:

        def _cleanup_progress_window() -> None:
            if self.bulkMediaExportProgressWindow:
                currentValue = self.bulkMediaExportProgressWindow.currentValue
                self.bulkMediaExportProgressWindow = None

                if not self._progress_bar_closed_and_finished_importing[progressWidget]:
                    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = True
                    miInfo(
                        "Importing cancelled.\n\n{} cards were imported.".format(
                            currentValue
                        )
                    )

        def _disable_bulk_text() -> None:
            if self.bulkTextImporting:
                self.bulkTextImporting = False

        def _on_close() -> None:
            _disable_bulk_text()
            _cleanup_progress_window()

        progressWidget = _ProgressWindow(initialText)
        progressWidget.setWindowTitle(title)
        self._progress_bar_closed_and_finished_importing[progressWidget] = False
        progressWidget.setWindowIcon(
            QIcon(join(self.dictInt.addonPath, "icons", "migaku.png"))
        )

        _center(progressWidget)
        progressWidget.setFixedSize(500, 100)
        progressWidget.setWindowModality(Qt.WindowModality.ApplicationModal)
        progressWidget.show()
        progressWidget.setFocus()

        if self.alwaysOnTop:
            progressWidget.setWindowFlags(
                progressWidget.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
            )

        progressWidget.request_stop_bulk_text_import.connect(_on_close)
        self.mw.app.processEvents()

        return progressWidget


def _center(widget: QWidget) -> None:
    screen = QGuiApplication.primaryScreen()

    if not screen:
        raise RuntimeError(f'Cannot center "{widget}". No screen to center with.')

    geometry = screen.geometry()
    x = (geometry.width() - widget.width()) // 2
    y = (geometry.height() - widget.height()) // 2
    widget.move(x, y)


def _verify(value: typing.Optional[T]) -> T:
    if value:
        return value

    raise RuntimeError("Value is not defined. Cannot continue.")
