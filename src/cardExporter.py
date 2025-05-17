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
from aqt import dialogs, qt, sound
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
class _ProgressWindow(qt.QWidget):
    request_stop_bulk_text_import = qt.pyqtSignal()

    def __init__(self, text: str, parent: typing.Optional[qt.QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.currentValue = 0

        self._textDisplay = qt.QLabel()
        self._textDisplay.setText(text)

        self._bar = qt.QProgressBar()
        layout = qt.QVBoxLayout()
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

    def closeEvent(self, event: typing.Optional[qt.QCloseEvent]) -> None:
        self.request_stop_bulk_text_import.emit()

        if event:
            event.accept()


class MITextEdit(qt.QTextEdit):
    def __init__(
        self,
        dictInt: midict.DictInterface,
        parent: typing.Optional[qt.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._dictInt = dictInt
        self.setAcceptRichText(False)

    def contextMenuEvent(self, event: typing.Optional[qt.QContextMenuEvent]) -> None:
        menu = super().createStandardContextMenu()

        if not menu:
            raise RuntimeError(
                f'No standard menu for "{self.__class__.__name__}" could be created.'
            )

        search = qt.QAction("Search")
        search.triggered.connect(self.searchSelected)
        menu.addAction(search)

        if event:
            menu.exec(event.globalPos())
        else:
            menu.exec()

    def keyPressEvent(self, event: typing.Optional[qt.QKeyEvent]) -> None:
        if not event:
            super().keyPressEvent(event)

            return

        if event.modifiers() & qt.Qt.KeyboardModifier.ControlModifier:
            if event.key() == qt.Qt.Key.Key_B:
                cursor = self.textCursor()
                format = qt.QTextCharFormat()
                format.setFontWeight(
                    qt.QFont.Weight.Bold
                    if not cursor.charFormat().font().bold()
                    else qt.QFont.Weight.Normal
                )
                cursor.mergeCharFormat(format)

                return

            if event.key() == qt.Qt.Key.Key_I:
                cursor = self.textCursor()
                format = qt.QTextCharFormat()
                format.setFontItalic(
                    True if not cursor.charFormat().font().italic() else False
                )
                cursor.mergeCharFormat(format)

                return

            if event.key() == qt.Qt.Key.Key_U:
                cursor = self.textCursor()
                format = qt.QTextCharFormat()
                format.setUnderlineStyle(
                    qt.QTextCharFormat.UnderlineStyle.SingleUnderline
                    if not cursor.charFormat().font().underline()
                    else qt.QTextCharFormat.UnderlineStyle.NoUnderline
                )
                cursor.mergeCharFormat(format)

                return

        super().keyPressEvent(event)

    def searchSelected(self, in_browser: bool) -> None:
        if in_browser:
            b = dialogs.open("Browser", self._dictInt.mw)
            b.form.searchEdit.lineEdit().setText(
                "expression:*{0}*".format(self.selectedText())
            )
            b.onSearchActivated()
        else:
            self._dictInt.initSearch(self.selectedText())

    def selectedText(self) -> str:
        return self.textCursor().selectedText()


class MILineEdit(qt.QLineEdit):
    def __init__(
        self,
        dictInt: midict.DictInterface,
        parent: typing.Optional[qt.QWidget] = None,
    ):
        super().__init__(parent)
        self._dictInt = dictInt

    def contextMenuEvent(self, event: typing.Optional[qt.QContextMenuEvent]) -> None:
        menu = super().createStandardContextMenu()

        if not menu:
            raise RuntimeError("No standard context menu could be created.")

        search = qt.QAction("Search")
        search.triggered.connect(self.searchSelected)
        menu.addAction(search)

        if event:
            menu.exec(event.globalPos())

    def searchSelected(self, in_browser: bool) -> None:
        if in_browser:
            b = dialogs.open("Browser", self._dictInt.mw)
            b.form.searchEdit.lineEdit().setText(
                "Expression:*{0}*".format(self.selectedText())
            )
            b.onSearchActivated()
        else:
            self._dictInt.initSearch(self.selectedText())


class CardExporter:
    def __init__(
        self,
        dictInt: midict.DictInterface,
        sentence: str = "",
        word: str = "",
    ) -> None:
        self._shortcuts: list[qt.QShortcut] = []
        self._progress_bar_closed_and_finished_importing: dict[qt.QWidget, bool] = {}

        self._window = qt.QWidget()
        self.scrollArea = qt.QScrollArea()
        self.scrollArea.setWidget(self._window)
        self.scrollArea.setHorizontalScrollBarPolicy(
            qt.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scrollArea.setVerticalScrollBarPolicy(
            qt.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scrollArea.setWidgetResizable(True)
        self._window.setAutoFillBackground(True)
        self._dictInt = dictInt
        self._mw = self._dictInt.mw
        self._bulkTextImporting = False
        self._config = self._getConfig()
        self._definitionSettings = self._config["autoDefinitionSettings"]
        self._layout = qt.QVBoxLayout()
        self._decks = self._getDecks()
        self._templates = self._config["ExportTemplates"]
        self._templateCB = self._getTemplateCB()
        self._deckCB = self._getDeckCB()
        self._sentenceLE = MITextEdit(dictInt=dictInt)
        self._secondaryLE = MITextEdit(dictInt=dictInt)
        self._notesLE = MITextEdit(dictInt=dictInt)
        self._wordLE = MILineEdit(dictInt=dictInt)
        self._tagsLE = MILineEdit(dictInt=dictInt)
        self._definitions = self._getDefinitions()
        self._autoAdd = qt.QCheckBox("Add Extension Cards Automatically")
        self._autoAdd.setChecked(self._config["autoAddCards"])
        self._searchUnknowns = qt.QSpinBox()
        self._searchUnknowns.setValue(self._config.get("unknownsToSearch", 3))
        self._searchUnknowns.setMinimum(0)
        self._searchUnknowns.setMaximum(10)
        self._addDefinitionsCheckbox = qt.QCheckBox("Automatically Add Definitions")
        self._addDefinitionsCheckbox.setChecked(self._config["autoAddDefinitions"])
        self._definitionSettingsButton = qt.QPushButton("Automatic Definition Settings")
        self._clearButton = qt.QPushButton("Clear Current Card")
        self._cancelButton = qt.QPushButton("Cancel")
        self._addButton = qt.QPushButton("Add")
        self._audioMap = qt.QLabel("No Audio Selected")
        self._imageMap = qt.QLabel("No Image Selected")
        self._exportJS = self._config["jReadingCards"]
        self._imgName: typing.Optional[str] = None
        self._imgPath: typing.Optional[str] = None
        self._audioTag: typing.Optional[str] = None
        self._audioName: typing.Optional[str] = None
        self._audioPath: typing.Optional[str] = None
        self._audioPlay = qt.QPushButton("Play")
        self._audioPlay.clicked.connect(self._playAudio)
        self._audioPlay.hide()
        self._setupLayout()
        self._initHandlers()
        self.setColors()
        self._window.setLayout(self._layout)
        self._window.setMinimumSize(490, 650)
        self.scrollArea.setMinimumWidth(490)
        self.scrollArea.setMinimumHeight(400)
        self.scrollArea.resize(490, 654)
        self.scrollArea.setWindowIcon(
            qt.QIcon(join(self._dictInt.addonPath, "icons", "migaku.png"))
        )
        self.scrollArea.setWindowTitle("Migaku Card Exporter")
        self._definitionList: list[_Definition] = []
        self._initTooltips()
        self._restoreSizePos()
        self._setHotkeys()
        self.scrollArea.show()
        self.alwaysOnTop = self._config["dictAlwaysOnTop"]
        self._maybeSetToAlwaysOnTop()
        self._bulkMediaExportProgressWindow: typing.Optional[_ProgressWindow] = None

    def _closeProgressBar(self, progressBar: typing.Optional[qt.QWidget]) -> None:
        if not progressBar:
            return

        self._progress_bar_closed_and_finished_importing[progressBar] = True
        progressBar.close()
        progressBar.deleteLater()

    def _writeConfig(self, config: typer.Configuration) -> None:
        self._mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], config),
        )

    def _maybeSetToAlwaysOnTop(self) -> None:
        if self.alwaysOnTop:
            self.scrollArea.setWindowFlags(
                self.scrollArea.windowFlags() | qt.Qt.WindowType.WindowStaysOnTopHint
            )
            self.scrollArea.show()

    def _initTooltips(self) -> None:
        if self._config["tooltips"]:
            self._templateCB.setToolTip("Select the export template.")
            self._deckCB.setToolTip("Select the deck to export to.")
            self._clearButton.setToolTip("Clear the card exporter.")

    def _restoreSizePos(self) -> None:
        sizePos = self._config["exporterSizePos"]
        if sizePos:
            self.scrollArea.resize(sizePos[2], sizePos[3])
            self.scrollArea.move(sizePos[0], sizePos[1])
            ensureWidgetInScreenBoundaries(self.scrollArea)

    def _setHotkeys(self) -> None:
        self._shortcuts.append(
            qt.QShortcut(
                qt.QKeySequence("Ctrl+S"),
                self.scrollArea,
                lambda: self._attemptSearch(False),
            )
        )
        self._shortcuts.append(
            qt.QShortcut(
                qt.QKeySequence("Ctrl+F"),
                self.scrollArea,
                lambda: self._attemptSearch(True),
            )
        )

        shortcut = qt.QShortcut(qt.QKeySequence("Esc"), self.scrollArea)
        self._shortcuts.append(shortcut)
        shortcut.activated.connect(self.scrollArea.hide)

    def _attemptSearch(self, in_browser: bool) -> None:
        focused = self.scrollArea.focusWidget()

        if isinstance(focused, (MILineEdit, MITextEdit)):
            focused.searchSelected(in_browser)

    def _addNote(self, note: Note, did: int) -> bool:
        model = note.note_type()

        if not model:
            raise RuntimeError(f'Note "{note}" has no Note type.')

        model["did"] = int(did)
        ret = note.dupeOrEmpty()
        if ret == 1:
            if not miAsk(
                "Your note's sorting field will be empty with this configuration. Would you like to continue?",
                self.scrollArea,
                self._dictInt.nightModeToggler.day,
            ):
                return False
        if "{{cloze:" in model["tmpls"][0]["qfmt"]:
            if not self._mw.col.models._availClozeOrds(
                model, note.joined_fields(), False
            ):
                if not miAsk(
                    "You have a cloze deletion note type "
                    "but have not made any cloze deletions. Would you like to continue?",
                    self.scrollArea,
                    self._dictInt.nightModeToggler.day,
                ):
                    return False
        cards = self._mw.col.addNote(note)
        if not cards:
            miInfo(
                (
                    """\
The current input and template combination \
will lead to a blank card and therefore has not been added. \
Please review your template and notetype combination."""
                ),
                level="wrn",
                day=self._dictInt.nightModeToggler.day,
            )
            return False
        self._mw.col.save()
        self._mw.reset()

        return True

    def _getDecks(self) -> dict[str, int]:
        decksRaw = self._mw.col.decks.decks
        decks: dict[str, int] = {}

        for did, deck in decksRaw.items():
            if not deck["dyn"]:
                decks[deck["name"]] = did

        return decks

    def _getDeckCB(self) -> qt.QComboBox:
        cb = qt.QComboBox()
        decks = list(self._decks.keys())
        decks.sort()
        cb.addItems(decks)
        current = self._config["currentDeck"]
        if current and current in decks:
            cb.setCurrentText(current)
        cb.currentIndexChanged.connect(
            lambda: self._dictInt.writeConfig("currentDeck", cb.currentText())
        )
        return cb

    def _initHandlers(self) -> None:
        self._definitionSettingsButton.clicked.connect(self._definitionSettingsWidget)
        self._clearButton.clicked.connect(self._clearCurrent)
        self._cancelButton.clicked.connect(self.scrollArea.close)
        self._addButton.clicked.connect(self.addCard)
        self._addDefinitionsCheckbox.clicked.connect(self._saveAddDefinitionChecked)
        self._searchUnknowns.valueChanged.connect(self._saveSearchUnknowns)
        self._autoAdd.clicked.connect(self._saveAutoAddChecked)

    def _saveSearchUnknowns(self) -> None:
        config = self._getConfig()
        config["unknownsToSearch"] = self._searchUnknowns.value()
        self._config = config
        migaku_configuration.refresh_configuration(config)
        self._writeConfig(config)

    def _saveAutoAddChecked(self) -> None:
        config = self._getConfig()
        config["autoAddCards"] = self._autoAdd.isChecked()
        self._config = config
        migaku_configuration.refresh_configuration(config)
        self._writeConfig(config)

    def _saveAddDefinitionChecked(self) -> None:
        config = self._getConfig()
        config["autoAddDefinitions"] = self._addDefinitionsCheckbox.isChecked()
        self._config = config
        migaku_configuration.refresh_configuration(config)
        self._writeConfig(config)

    # TODO: @ColinKennedy - `word` might not be a str. Check later.
    def _automaticallyAddDefinitions(
        self, note: Note, word: str, template: typer.ExportTemplate
    ) -> Note:
        if not self._definitionSettings:
            return note

        dictToTable = self._getDictionaryNameToTableNameDictionary()
        unspecifiedDefinitionField = template["unspecified"]
        specificFields = template["specific"]
        dictionaries: list[typer.DictionaryConfiguration] = []
        for setting in self._definitionSettings:
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

    def _moveImageToMediaFolder(self) -> None:
        if self._imgPath and self._imgName:
            if exists(self._imgPath):
                path = join(self._mw.col.media.dir(), self._imgName)
                if not exists(path):
                    copyfile(self._imgPath, path)

    def _fieldValid(self, field: str) -> bool:
        return field != "Don't Export"

    def _getDictionaryEntries(self, dictionary: str) -> list[str]:
        finList: list[str] = []
        idxs: list[int] = []
        for idx, defList in enumerate(self._definitionList):
            if defList.dictionary == dictionary:
                finList.append(defList.field)
                idxs.append(idx)
        idxs.reverse()
        for idx in idxs:
            self._definitionList.pop(idx)
        return finList

    def _emptyValueIfEmptyHtml(self, value: str) -> str:
        pattern = r"(?:<[^<]+?>)"
        if re.sub(pattern, "", value) == "":
            return ""
        return value

    def _getFieldsValues(
        self,
        t: typer.ExportTemplate,
    ) -> tuple[dict[str, list[str]], typing.Optional[str], typing.Optional[str], str]:
        imgField: typing.Optional[str] = None
        audioField: typing.Optional[str] = None
        tagsField = ""
        fields: dict[str, list[str]] = {}
        sentenceText = self._cleanHTML(self._sentenceLE.toHtml())
        sentenceText = self._emptyValueIfEmptyHtml(sentenceText)
        if sentenceText != "":
            sentenceField = t["sentence"]
            if sentenceField != "Don't Export":
                if self._fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        secondaryText = self._cleanHTML(self._secondaryLE.toHtml())
        secondaryText = self._emptyValueIfEmptyHtml(secondaryText)
        if secondaryText != "" and "secondary" in t:
            secondaryField = t["secondary"]
            if secondaryField != "Don't Export":
                if secondaryField and self._fieldValid(secondaryField):
                    fields[secondaryField] = [secondaryText]
        notesText = self._cleanHTML(self._notesLE.toHtml())
        notesText = self._emptyValueIfEmptyHtml(notesText)
        if notesText != "" and "notes" in t:
            notesField = t["notes"]
            if notesField != "Don't Export":
                if self._fieldValid(notesField):
                    fields[notesField] = [notesText]
        wordText = self._wordLE.text()
        if wordText != "":
            wordField = t["word"]
            if wordField != "Don't Export":
                if self._fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self._tagsLE.text()
        if tagsText != "":
            tagsField = tagsText
        imgText = self._imageMap.text()
        if imgText != "No Image Selected" and self._imgName:
            imgField = t["image"]
            if imgField != "Don't Export":
                imgTag = '<img src="' + self._imgName + '">'
                if self._fieldValid(imgField):
                    if imgField not in fields:
                        fields[imgField] = [imgTag]
                    else:
                        fields[imgField].append(imgTag)
        audioText = self._imageMap.text()
        if audioText != "No Audio Selected" and "audio" in t and self._audioTag:
            audioField = t["audio"]
            if audioField != "Don't Export":
                if self._fieldValid(audioField):
                    if audioField not in fields:
                        fields[audioField] = [self._audioTag]
                    else:
                        fields[audioField].append(self._audioTag)
        specific = t["specific"]
        for field in specific:
            for dictionary in specific[field]:
                if field not in fields:
                    fields[field] = self._getDictionaryEntries(dictionary)
                else:
                    fields[field] += self._getDictionaryEntries(dictionary)
        unspecified = t["unspecified"]
        for idx, defList in enumerate(self._definitionList):
            if unspecified not in fields:
                fields[unspecified] = [defList.field]
            else:
                fields[unspecified].append(defList.field)
        return fields, imgField, audioField, tagsField

    def _clearCurrent(self) -> None:
        self._definitions.setRowCount(0)
        self._sentenceLE.clear()
        self._secondaryLE.clear()
        self._notesLE.clear()
        self._wordLE.clear()
        self._definitionList[:] = []
        self._audioMap.clear()
        self._audioMap.setText("No Audio Selected")
        self._audioPlay.hide()
        self._audioTag = None
        self._audioName = None
        self._audioPath = None
        self._imageMap.clear()
        self._imageMap.setText("No Image Selected")
        self._imgPath = None
        self._imgName = None

    def _getDefinitions(self) -> qt.QTableWidget:
        macLin = False
        if is_mac or is_lin:
            macLin = True
        definitions = qt.QTableWidget()
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
        vHeader.setSectionResizeMode(qt.QHeaderView.ResizeMode.ResizeToContents)
        tableHeader.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.Fixed)
        definitions.setColumnWidth(1, 100)
        tableHeader.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Fixed)
        definitions.setRowCount(0)
        definitions.setSortingEnabled(False)
        definitions.setEditTriggers(qt.QTableWidget.EditTrigger.NoEditTriggers)
        definitions.setSelectionBehavior(
            qt.QAbstractItemView.SelectionBehavior.SelectRows
        )
        definitions.setColumnWidth(2, 40)
        tableHeader.hide()
        return definitions

    def _getConfig(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration, self._mw.addonManager.getConfig(__name__)
        )

    def _setupLayout(self) -> None:
        tempLayout = qt.QHBoxLayout()
        tempLayout.addWidget(qt.QLabel("Template: "))
        self._templateCB.setFixedSize(120, 30)
        tempLayout.addWidget(self._templateCB)
        tempLayout.addWidget(qt.QLabel(" Deck: "))
        self._deckCB.setFixedSize(120, 30)
        tempLayout.addWidget(self._deckCB)
        tempLayout.addStretch()
        tempLayout.setSpacing(2)
        self._clearButton.setFixedSize(130, 30)
        tempLayout.addWidget(self._clearButton)
        self._layout.addLayout(tempLayout)
        sentenceL = qt.QLabel("Sentence")
        self._layout.addWidget(sentenceL)
        self._layout.addWidget(self._sentenceLE)
        secondaryL = qt.QLabel("Secondary")
        self._layout.addWidget(secondaryL)
        self._layout.addWidget(self._secondaryLE)
        wordL = qt.QLabel("Word")
        self._layout.addWidget(wordL)
        self._layout.addWidget(self._wordLE)
        notesL = qt.QLabel("User Notes")
        self._layout.addWidget(notesL)
        self._layout.addWidget(self._notesLE)

        self._sentenceLE.setMinimumHeight(60)
        self._secondaryLE.setMinimumHeight(60)
        self._notesLE.setMinimumHeight(90)
        self._sentenceLE.setMaximumHeight(120)
        self._secondaryLE.setMaximumHeight(120)
        f = self._sentenceLE.font()
        f.setPointSize(16)
        self._sentenceLE.setFont(f)
        self._secondaryLE.setFont(f)
        self._notesLE.setFont(f)
        f = self._wordLE.font()
        f.setPointSize(20)
        self._wordLE.setFont(f)

        self._wordLE.setFixedHeight(40)
        definitionsL = qt.QLabel("Definitions")
        self._layout.addWidget(definitionsL)
        self._layout.addWidget(self._definitions)

        self._layout.addWidget(qt.QLabel("Audio"))
        self._layout.addWidget(self._audioMap)
        self._layout.addWidget(self._audioPlay)
        self._layout.addWidget(qt.QLabel("Image"))
        self._layout.addWidget(self._imageMap)
        tagsL = qt.QLabel("Tags")
        self._layout.addWidget(tagsL)
        lastTags = self._config.get("exporterLastTags", "")
        self._tagsLE.setText(lastTags)
        self._layout.addWidget(self._tagsLE)

        unknownLayout = qt.QHBoxLayout()
        unknownLayout.addWidget(qt.QLabel("Number of unknown words to search: "))
        unknownLayout.addStretch()
        unknownLayout.addWidget(self._searchUnknowns)
        self._layout.addLayout(unknownLayout)

        autoDefLayout = qt.QHBoxLayout()
        autoDefLayout.addWidget(self._addDefinitionsCheckbox)
        autoDefLayout.addStretch()
        self._definitionSettingsButton.setFixedSize(202, 30)
        autoDefLayout.addWidget(self._definitionSettingsButton)
        self._layout.addLayout(autoDefLayout)

        buttonLayout = qt.QHBoxLayout()
        buttonLayout.addWidget(self._autoAdd)
        buttonLayout.addStretch()
        self._cancelButton.setFixedSize(100, 30)
        self._addButton.setFixedSize(100, 30)
        buttonLayout.addWidget(self._cancelButton)
        buttonLayout.addWidget(self._addButton)
        self._layout.addLayout(buttonLayout)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(2)

    def _getTemplateCB(self) -> qt.QComboBox:
        cb = qt.QComboBox()
        cb.addItems(self._templates)
        current = self._config["currentTemplate"]

        cb.currentIndexChanged.connect(
            lambda: self._dictInt.writeConfig("currentTemplate", cb.currentText())
        )
        if current and current in self._templates:
            cb.setCurrentText(current)
        return cb

    def _removeImgs(self, imgs: str) -> None:
        model = self._definitions.selectionModel()

        if not model:
            _LOGGER.error(f'Cannot remove "%s" images. No model was found.', imgs)

            return

        # TODO: @ColinKennedy - try/except
        try:
            row = model.currentIndex().row()
            self._definitions.removeRow(row)
            self._removeImgFromDefinitionList(imgs)
        except:
            return

    def _removeImgFromDefinitionList(self, imgs: str) -> None:
        for idx, entry in enumerate(self._definitionList):
            if entry.dictionary == "Google Images" and entry.images == imgs:
                self._definitionList.pop(idx)
                break

    def _moveAudioToMediaFolder(self) -> None:
        if self._audioPath and self._audioName:
            if exists(self._audioPath):
                path = join(self._mw.col.media.dir(), self._audioName)
                if not exists(path):
                    copyfile(self._audioPath, path)

    def _playAudio(self) -> None:
        if self._audioPath:
            sound.play(self._audioPath)

    def _removeFromDefinitionList(self, dictName: str, shortDef: str) -> None:
        for idx, entry in enumerate(self._definitionList):
            if entry.dictionary == dictName and entry.short_definition == shortDef:
                self._definitionList.pop(idx)
                break

    def _removeDefinition(self) -> None:
        # TODO: @ColinKennedy Remove later
        model = self._definitions.selectionModel()

        if not model:
            raise RuntimeError(f'No model found for "{self._definitions}" definitions.')

        row = model.currentIndex().row()

        dictName = _verify(self._definitions.item(row, 0)).text()
        shortDef = _verify(self._definitions.item(row, 1)).text()

        self._definitions.removeRow(row)
        self._removeFromDefinitionList(dictName, shortDef)

    def _getDictionaryNameToTableNameDictionary(self) -> dict[str, str]:
        dictToTable = collections.OrderedDict()
        dictToTable["None"] = "None"
        dictToTable["Forvo"] = "Forvo"
        dictToTable["Google Images"] = "Google Images"
        database = dictdb.get()

        for dictTableName in sorted(database.getAllDicts()):
            dictName = database.cleanDictName(dictTableName)
            dictToTable[dictName] = dictTableName

        return dictToTable

    def _definitionSettingsWidget(self) -> None:
        settingsWidget = qt.QWidget(self.scrollArea, qt.Qt.WindowType.Window)
        layout = qt.QVBoxLayout()
        dict1 = qt.QComboBox()
        dict2 = qt.QComboBox()
        dict3 = qt.QComboBox()

        dictToTable = self._getDictionaryNameToTableNameDictionary()
        dictNames = dictToTable.keys()
        dict1.addItems(dictNames)
        dict2.addItems(dictNames)
        dict3.addItems(dictNames)

        dict1Lay = qt.QHBoxLayout()
        dict1Lay.addWidget(qt.QLabel("1st Dictionary:"))
        dict1Lay.addStretch()
        dict1Lay.addWidget(dict1)
        dict2Lay = qt.QHBoxLayout()
        dict2Lay.addWidget(qt.QLabel("2nd Dictionary:"))
        dict2Lay.addStretch()
        dict2Lay.addWidget(dict2)
        dict3Lay = qt.QHBoxLayout()
        dict3Lay.addWidget(qt.QLabel("3rd Dictionary:"))
        dict3Lay.addStretch()
        dict3Lay.addWidget(dict3)

        howMany1 = qt.QSpinBox()
        howMany1.setValue(1)
        howMany1.setMinimum(1)
        howMany1.setMaximum(20)
        hmLay1 = qt.QHBoxLayout()
        hmLay1.addWidget(qt.QLabel("Max Definitions:"))
        hmLay1.addWidget(howMany1)

        howMany2 = qt.QSpinBox()
        howMany2.setValue(1)
        howMany2.setMinimum(1)
        howMany2.setMaximum(20)
        hmLay2 = qt.QHBoxLayout()
        hmLay2.addWidget(qt.QLabel("Max Definitions:"))
        hmLay2.addWidget(howMany2)

        howMany3 = qt.QSpinBox()
        howMany3.setValue(1)
        howMany3.setMinimum(1)
        howMany3.setMaximum(20)
        hmLay3 = qt.QHBoxLayout()
        hmLay3.addWidget(qt.QLabel("Max Definitions:"))
        hmLay3.addWidget(howMany3)

        layout.addLayout(dict1Lay)
        layout.addLayout(hmLay1)
        layout.addLayout(dict2Lay)
        layout.addLayout(hmLay2)
        layout.addLayout(dict3Lay)
        layout.addLayout(hmLay3)

        if self._definitionSettings:
            howManys = [howMany1, howMany2, howMany3]
            dicts = [dict1, dict2, dict3]
            for idx, setting in enumerate(self._definitionSettings):
                dictName = setting["name"]
                if dictName in dictToTable:
                    limit = setting["limit"]
                    dicts[idx].setCurrentText(dictName)
                    howManys[idx].setValue(limit)

        save = qt.QPushButton("Save Settings")
        layout.addWidget(save)
        layout.setContentsMargins(4, 4, 4, 4)
        save.clicked.connect(
            lambda: self._saveDefinitionSettings(
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
            qt.QIcon(join(self._dictInt.addonPath, "icons", "migaku.png"))
        )
        settingsWidget.setLayout(layout)
        settingsWidget.show()

    def _saveDefinitionSettings(
        self,
        settingsWidget: qt.QWidget,
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
        config = self._getConfig()
        self._definitionSettings = definitionSettings
        config["autoDefinitionSettings"] = definitionSettings
        self._writeConfig(config)
        settingsWidget.close()
        settingsWidget.deleteLater()

    def _cleanHTML(self, text: str) -> str:
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

    def _addTextCard(self, card: typer.Card) -> None:
        templateName = self._templateCB.currentText()
        sentence = card["primary"]
        word = ""
        unknowns = card["unknownWords"]
        if unknowns:
            word = unknowns[0]

        if templateName in self._templates:
            template = self._templates[templateName]
            noteType = template["noteType"]
            model = self._mw.col.models.by_name(noteType)
            if model:
                note = Note(self._mw.col, model)
                modelFields = self._mw.col.models.field_names(model)
                fieldsValues, tagsField = self._getFieldsValuesForTextCard(
                    template, word, sentence
                )
                if fieldsValues:
                    for field in fieldsValues:
                        if field in modelFields:
                            note[field] = template["separator"].join(
                                fieldsValues[field]
                            )
                    did: typing.Optional[int] = None
                    deck = self._deckCB.currentText()
                    if deck in self._decks:
                        did = self._decks[deck]
                    if did:
                        if word and self._addDefinitionsCheckbox.isChecked():
                            note = self._automaticallyAddDefinitions(
                                note, word, template
                            )
                        if self._exportJS:
                            note = self._dictInt.jHandler.attemptGenerate(note)
                        model["did"] = int(did)
                        self._mw.col.addNote(note)
                        self._mw.col.save()
                else:
                    print("Invalid field values")

    def _getFieldsValuesForTextCard(
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
                if self._fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        if wordText != "":
            wordField = t["word"]
            if wordField != "Don't Export":
                if self._fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self._tagsLE.text()
        if tagsText != "":
            tagsField = tagsText
        return fields, tagsField

    def _addMediaCard(self, card: typer.Card) -> None:
        templateName = self._templateCB.currentText()
        word = ""
        unknowns = card["unknownWords"]
        if unknowns:
            word = unknowns[0]
        if templateName in self._templates:
            template = self._templates[templateName]
            noteType = template["noteType"]
            model = self._mw.col.models.by_name(noteType)
            if model:
                note = Note(self._mw.col, model)
                modelFields = self._mw.col.models.field_names(model)
                fieldsValues, _ = self._getFieldsValuesForMediaCard(
                    template, word, card
                )

                if not fieldsValues:
                    print("Invalid field values")

                    return

                for field in fieldsValues:
                    if field in modelFields:
                        note[field] = template["separator"].join(fieldsValues[field])
                did: typing.Optional[int] = None
                deck = self._deckCB.currentText()
                if deck in self._decks:
                    did = self._decks[deck]
                if did:
                    if word and self._addDefinitionsCheckbox.isChecked():
                        note = self._automaticallyAddDefinitions(note, word, template)
                    if self._exportJS:
                        note = self._dictInt.jHandler.attemptGenerate(note)
                    model["did"] = int(did)
                    self._mw.col.addNote(note)
                    self._mw.col.save()

    def _getFieldsValuesForMediaCard(
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
                if self._fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        if secondaryText != "" and "secondary" in t:
            secondaryField = t["secondary"]
            if secondaryField and secondaryField != "Don't Export":
                if self._fieldValid(secondaryField):
                    fields[secondaryField] = [secondaryText]
        if wordText != "":
            wordField = t["word"]
            if wordField != "Don't Export":
                if self._fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self._tagsLE.text()
        if tagsText != "":
            tagsField = tagsText
        if image:
            imgField = t["image"]
            imgTag = '<img src="' + image + '">'
            if self._fieldValid(imgField):
                if imgField not in fields:
                    fields[imgField] = [imgTag]
                else:
                    fields[imgField].append(imgTag)
        if audio:
            audioField = t["audio"]
            if self._fieldValid(audioField):
                if audioField not in fields:
                    fields[audioField] = [audio]
                else:
                    fields[audioField].append(audio)
        return fields, tagsField

    def _getProgressBar(
        self,
        title: str,
        initialText: str,
    ) -> _ProgressWindow:

        def _cleanup_progress_window() -> None:
            if self._bulkMediaExportProgressWindow:
                currentValue = self._bulkMediaExportProgressWindow.currentValue
                self._bulkMediaExportProgressWindow = None

                if not self._progress_bar_closed_and_finished_importing[progressWidget]:
                    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = True
                    miInfo(
                        "Importing cancelled.\n\n{} cards were imported.".format(
                            currentValue
                        )
                    )

        def _disable_bulk_text() -> None:
            if self._bulkTextImporting:
                self._bulkTextImporting = False

        def _on_close() -> None:
            _disable_bulk_text()
            _cleanup_progress_window()

        progressWidget = _ProgressWindow(initialText)
        progressWidget.setWindowTitle(title)
        self._progress_bar_closed_and_finished_importing[progressWidget] = False
        progressWidget.setWindowIcon(
            qt.QIcon(join(self._dictInt.addonPath, "icons", "migaku.png"))
        )

        _center(progressWidget)
        progressWidget.setFixedSize(500, 100)
        progressWidget.setWindowModality(qt.Qt.WindowModality.ApplicationModal)
        progressWidget.show()
        progressWidget.setFocus()

        if self.alwaysOnTop:
            progressWidget.setWindowFlags(
                progressWidget.windowFlags() | qt.Qt.WindowType.WindowStaysOnTopHint
            )

        progressWidget.request_stop_bulk_text_import.connect(_on_close)
        self._mw.app.processEvents()

        return progressWidget

    def addCard(self) -> None:
        templateName = self._templateCB.currentText()
        if templateName in self._templates:
            template = self._templates[templateName]
            noteType = template["noteType"]
            model = self._mw.col.models.by_name(noteType)
            if model:
                note = Note(self._mw.col, model)
                modelFields = self._mw.col.models.field_names(model)
                fieldsValues, imgField, audioField, tagsField = self._getFieldsValues(
                    template
                )
                word = self._wordLE.text()
                if not fieldsValues:
                    miInfo(
                        "The currently selected template and values will lead to an invalid card. Please try again.",
                        level="wrn",
                        day=self._dictInt.nightModeToggler.day,
                    )
                    return
                for field in fieldsValues:
                    if field in modelFields:
                        note[field] = template["separator"].join(fieldsValues[field])
                did = 0
                deck = self._deckCB.currentText()
                if deck in self._decks:
                    did = self._decks[deck]
                if did:
                    if word and self._addDefinitionsCheckbox.isChecked():
                        note = self._automaticallyAddDefinitions(note, word, template)
                    if self._exportJS:
                        note = self._dictInt.jHandler.attemptGenerate(note)
                    if not self._addNote(note, did):
                        return
                if imgField and imgField in modelFields:
                    self._moveImageToMediaFolder()
                if audioField and audioField in modelFields:
                    self._moveAudioToMediaFolder()
                self._clearCurrent()
                return
            else:
                miInfo(
                    "The notetype for the currently selected template does not exist in the currently loaded profile.",
                    level="err",
                    day=self._dictInt.nightModeToggler.day,
                )
                return
        miInfo(
            "A card could not be added with this current configuration. Please ensure that your template is configured correctly for this collection.",
            level="err",
            day=self._dictInt.nightModeToggler.day,
        )

    def addDefinition(self, dictName: str, word: str, definition: str) -> None:
        self.focusWindow()
        if len(definition) > 40:
            shortDef = definition.replace("<br>", " ")[:40] + "..."
        else:
            shortDef = definition.replace("<br>", " ")
        defEntry = _Definition(dictName, shortDef, definition, None)
        if defEntry in self._definitionList:
            miInfo(
                "A card can not contain duplicate definitions.",
                level="not",
                day=self._dictInt.nightModeToggler.day,
            )
            return
        self._definitionList.append(defEntry)
        rc = self._definitions.rowCount()
        self._definitions.setRowCount(rc + 1)
        self._definitions.setItem(rc, 0, qt.QTableWidgetItem(dictName))
        self._definitions.setItem(rc, 1, qt.QTableWidgetItem(shortDef))
        deleteButton = qt.QPushButton("X")
        deleteButton.setFixedWidth(40)
        deleteButton.clicked.connect(self._removeDefinition)
        self._definitions.setCellWidget(rc, 2, deleteButton)
        self._definitions.resizeRowsToContents()
        if self._wordLE.text() == "":
            self._wordLE.setText(word)

    def addImgs(self, word: str, imgs: str, thumbs: qt.QWidget) -> None:
        self.focusWindow()
        defEntry = _Definition("Google Images", None, imgs, imgs)
        if defEntry in self._definitionList:
            miInfo(
                "A card cannot contain duplicate definitions.",
                level="not",
                day=self._dictInt.nightModeToggler.day,
            )
            return
        self._definitionList.append(defEntry)
        rc = self._definitions.rowCount()
        self._definitions.setRowCount(rc + 1)
        self._definitions.setItem(rc, 0, qt.QTableWidgetItem("Google Images"))
        self._definitions.setCellWidget(rc, 1, thumbs)
        deleteButton = qt.QPushButton("X")
        deleteButton.setFixedWidth(40)
        deleteButton.clicked.connect(lambda: self._removeImgs(imgs))
        self._definitions.setCellWidget(rc, 2, deleteButton)
        self._definitions.resizeRowsToContents()
        if self._wordLE.text() == "":
            self._wordLE.setText(word)

    def attemptAutoAdd(self, bulkExport: bool) -> None:
        if self._autoAdd.isChecked() or bulkExport:
            self.addCard()

    def bulkMediaExport(self, card: typer.Card) -> None:
        if global_state.IS_BULK_MEDIA_EXPORT_CANCELLED:
            return
        if not self._bulkMediaExportProgressWindow:
            total = card["total"]
            importingMessage = "Importing {} of " + str(total) + " cards."
            self._bulkMediaExportProgressWindow = self._getProgressBar(
                "Migaku Dictionary - Importing Media Cards", importingMessage.format(0)
            )
            self._bulkMediaExportProgressWindow.setMaximum(total)
            self._bulkMediaExportProgressWindow.currentValue = 0
        else:
            importingMessage = (
                "Importing {} of "
                + str(self._bulkMediaExportProgressWindow.getTotal())
                + " cards."
            )
        self._addMediaCard(card)

        # TODO: @ColinKennedy remove this try/except later
        try:
            if (
                global_state.IS_BULK_MEDIA_EXPORT_CANCELLED
                or not self._bulkMediaExportProgressWindow
            ):
                if self._bulkMediaExportProgressWindow:
                    self._closeProgressBar(self._bulkMediaExportProgressWindow)
                return
            self._bulkMediaExportProgressWindow.currentValue += 1
            self._bulkMediaExportProgressWindow.setValue(
                self._bulkMediaExportProgressWindow.currentValue
            )
            self._bulkMediaExportProgressWindow.setText(
                importingMessage.format(
                    self._bulkMediaExportProgressWindow.currentValue
                )
            )
            self._mw.app.processEvents()

            total = self._bulkMediaExportProgressWindow.getTotal()

            if self._bulkMediaExportProgressWindow.currentValue == total:
                if total == 1:
                    miInfo("{} card has been imported.".format(total))
                else:
                    miInfo("{} cards have been imported.".format(total))

                self._closeProgressBar(self._bulkMediaExportProgressWindow)
                self._bulkMediaExportProgressWindow = None
        except:
            pass

    def bulkMediaExportCancelledByBrowserRefresh(self) -> None:
        if not self._bulkMediaExportProgressWindow:
            return

        currentValue = self._bulkMediaExportProgressWindow.currentValue
        miInfo(
            "Importing cards from the extension has been cancelled from within the browser.\n\n {} cards were imported.".format(
                currentValue
            )
        )
        self._closeProgressBar(self._bulkMediaExportProgressWindow)
        self._bulkMediaExportProgressWindow = None
        global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = False

    def bulkTextExport(self, cards: typing.Sequence[typer.Card]) -> None:
        self._bulkTextImporting = True
        total = len(cards)
        importingMessage = "Importing {} of " + str(total) + " cards."
        progressWidget = self._getProgressBar(
            "Migaku Dictionary - Importing Text Cards", importingMessage.format(0)
        )
        progressWidget.setMaximum(total)
        for idx, card in enumerate(cards):
            if not self._bulkTextImporting:
                miInfo(
                    "Importing cards from the extension has been cancelled.\n\n{} of {} were added.".format(
                        idx, total
                    )
                )
                return
            self._addTextCard(card)
            progressWidget.setValue(idx + 1)
            progressWidget.setText(importingMessage.format(idx + 1))
            self._mw.app.processEvents()
        self._bulkTextImporting = False
        self._closeProgressBar(progressWidget)

    def exportAudio(self, path: str, tag: str, name: str) -> None:
        self._audioTag = tag
        self._audioName = name
        self._audioPath = path
        self._audioMap.setText(tag)
        self._audioPlay.show()

    def exportImage(self, path: str, name: str) -> None:
        self._imgName = name
        self._imgPath = path
        if self._imageMap:
            self._imageMap.setText("")
            screenshot = qt.QPixmap(path)
            screenshot = screenshot.scaled(
                200,
                200,
                qt.Qt.AspectRatioMode.KeepAspectRatio,
                qt.Qt.TransformationMode.SmoothTransformation,
            )
            self._imageMap.setPixmap(screenshot)

    def exportSentence(self, sentence: str) -> None:
        self.focusWindow()
        self._sentenceLE.setHtml(sentence)

    def exportSecondary(self, secondary: str) -> None:
        self._secondaryLE.setHtml(secondary)

    def exportWord(self, word: str) -> None:
        self._wordLE.setText(word)

    def focusWindow(self) -> None:
        self.scrollArea.show()
        if self.scrollArea.windowState() == qt.Qt.WindowState.WindowMinimized:
            self.scrollArea.setWindowState(qt.Qt.WindowState.WindowNoState)
        self.scrollArea.setFocus()
        self.scrollArea.activateWindow()

    def saveSizeAndPos(self) -> None:
        pos = self.scrollArea.pos()
        x = pos.x()
        y = pos.y()
        size = self.scrollArea.size()
        width = size.width()
        height = size.height()
        posSize = (x, y, width, height)
        self._dictInt.writeConfig("exporterSizePos", posSize)
        self._dictInt.writeConfig("exporterLastTags", self._tagsLE.text())

    def setColors(self) -> None:
        if self._dictInt.nightModeToggler.day:
            self.scrollArea.setPalette(self._dictInt.ogPalette)
            if is_mac:
                self._templateCB.setStyleSheet(self._dictInt.getMacComboStyle())
                self._deckCB.setStyleSheet(self._dictInt.getMacComboStyle())
                self._definitions.setStyleSheet(self._dictInt.getMacTableStyle())
            else:
                self._templateCB.setStyleSheet("")
                self._deckCB.setStyleSheet("")
                self._definitions.setStyleSheet("")
        else:
            self.scrollArea.setPalette(self._dictInt.nightPalette)
            if is_mac:
                self._templateCB.setStyleSheet(self._dictInt.getMacNightComboStyle())
                self._deckCB.setStyleSheet(self._dictInt.getMacNightComboStyle())
            else:
                self._templateCB.setStyleSheet(self._dictInt.getComboStyle())
                self._deckCB.setStyleSheet(self._dictInt.getComboStyle())
            self._definitions.setStyleSheet(self._dictInt.getTableStyle())

    def closeEvent(self, event: qt.QCloseEvent) -> None:
        self.scrollArea.closeEvent(
            event
        )  # TODO: @ColinKennedy - not sure if this is needed
        self._clearCurrent()
        self.saveSizeAndPos()
        event.accept()

    def hideEvent(self, event: qt.QHideEvent) -> None:
        self.scrollArea.hideEvent(
            event
        )  # TODO: @ColinKennedy - not sure if this is needed
        self.saveSizeAndPos()
        event.accept()


def _center(widget: qt.QWidget) -> None:
    screen = qt.QGuiApplication.primaryScreen()

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
