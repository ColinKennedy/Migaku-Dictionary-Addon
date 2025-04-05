# -*- coding: utf-8 -*-
#

from __future__ import annotations

import collections
import typing

from aqt import dialogs
from aqt.qt import *
from anki.utils import is_mac, is_lin, is_win
from aqt.utils import ensureWidgetInScreenBoundaries
from os.path import join, exists
from shutil import copyfile
from .miutils import miInfo, miAsk
import json
from anki.notes import Note
from anki import sound
import re

if typing.TYPE_CHECKING:
    # TODO: @ColinKennedy - fix cyclic import
    from . import midict

from . import dictdb, global_state


class _DefinitionSetting(typing.TypedDict):
    name: str
    limit: int


class _Template(typing.TypedDict):
    audio: str
    image: str
    sentence: str
    word: str


class _Card(typing.TypedDict):
    audio: str
    image: str
    primary: str
    secondary: str
    total: int
    unknowns: list[str]


class MITextEdit(QTextEdit):
    def __init__(
        self,
        parent: typing.Optional[QWidget]= None,
        dictInt: typing.Optional["midict.DictInterface"] = None,
    ) -> None:
        super().__init__(parent)

        self.dictInt = dictInt
        self.setAcceptRichText(False)

    def contextMenuEvent(self, event: QEvent) -> None:
        menu = super().createStandardContextMenu()
        search = QAction('Search')
        search.triggered.connect(self.searchSelected)
        menu.addAction(search)
        menu.exec_(event.globalPos())

    def keyPressEvent(self, event: QEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_B:
                cursor = self.textCursor()
                format = QTextCharFormat()
                format.setFontWeight(QFont.Bold if not cursor.charFormat().font().bold() else QFont.Normal)
                cursor.mergeCharFormat(format)
                return
            elif event.key() == Qt.Key_I:
                cursor = self.textCursor()
                format = QTextCharFormat()
                format.setFontItalic(True if not cursor.charFormat().font().italic() else False)
                cursor.mergeCharFormat(format)
                return
            elif event.key() == Qt.Key_U:
                cursor = self.textCursor()
                format = QTextCharFormat()
                format.setUnderlineStyle(QTextCharFormat.SingleUnderline if not cursor.charFormat().font().underline() else QTextCharFormat.NoUnderline)
                cursor.mergeCharFormat(format)
                return

        super().keyPressEvent(event)

    def searchSelected(self, in_browser: bool) -> None:
        if in_browser:
            b = dialogs.open('Browser', self.dictInt.mw)
            b.form.searchEdit.lineEdit().setText('expression:*{0}*'.format(self.selectedText()))
            b.onSearchActivated()
        else:
            self.dictInt.initSearch(self.selectedText())

    def selectedText(self) -> str:
        return self.textCursor().selectedText()

class MILineEdit(QLineEdit):
    def __init__(
        self,
        parent: typing.Optional[QWidget] = None,
        dictInt: typing.Optional[midict.DictInterface] = None,
    ):
        super().__init__(parent)
        self.dictInt = dictInt

    def contextMenuEvent(self, event: QEvent) -> None:
        menu = super().createStandardContextMenu()
        search = QAction('Search')
        search.triggered.connect(self.searchSelected)
        menu.addAction(search)
        menu.exec_(event.globalPos())

    def searchSelected(self, in_browser: bool) -> None:
        if in_browser:
            b = dialogs.open('Browser', self.dictInt.mw)
            b.form.searchEdit.lineEdit().setText('Expression:*{0}*'.format(self.selectedText()))
            b.onSearchActivated()
        else:
            self.dictInt.initSearch(self.selectedText())

class CardExporter():
    def __init__(
        self,
        dictInt,
        dictWeb,
        templates = [],
        sentence = False,
        word = False,
        definition = False,
    ):
        self._progress_bar_closed_and_finished_importing: dict[QProgressBar, bool] = {}
        self.window = QWidget()
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidget(self.window)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scrollArea.setWidgetResizable(True)
        self.window.setAutoFillBackground(True);
        self.dictInt = dictInt
        self.mw = self.dictInt.mw
        self.bulkTextImporting = False
        self.config = self.getConfig()
        self.definitionSettings = self.config["autoDefinitionSettings"]
        self.dictWeb = dictWeb
        self.layout = QVBoxLayout()
        self.decks = self.getDecks()
        self.templates = self.config['ExportTemplates']
        self.templateCB = self.getTemplateCB()
        self.deckCB = self.getDeckCB()
        self.sentenceLE = MITextEdit(dictInt = dictInt)
        self.secondaryLE = MITextEdit(dictInt = dictInt)
        self.notesLE = MITextEdit(dictInt = dictInt)
        self.wordLE = MILineEdit(dictInt = dictInt)
        self.tagsLE = MILineEdit(dictInt = dictInt)
        self.definitions = self.getDefinitions()
        self.autoAdd = QCheckBox("Add Extension Cards Automatically")
        self.autoAdd.setChecked(self.config["autoAddCards"])
        self.searchUnknowns = QSpinBox()
        self.searchUnknowns.setValue(self.config.get("unknownsToSearch", 3))
        self.searchUnknowns.setMinimum(0)
        self.searchUnknowns.setMaximum(10)
        self.addDefinitionsCheckbox = QCheckBox("Automatically Add Definitions")
        self.addDefinitionsCheckbox.setChecked(self.config["autoAddDefinitions" ])
        self.definitionSettingsButton = QPushButton('Automatic Definition Settings')
        self.clearButton = QPushButton('Clear Current Card')
        self.cancelButton = QPushButton("Cancel")
        self.addButton = QPushButton("Add")
        self.exportJS = self.config['jReadingCards']
        self.imgName = False
        self.imgPath = False
        self.audioTag = False
        self.audioName = False
        self.audioPath = False
        self.audioPlayer = sound
        self.audioPlay = QPushButton('Play')
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
        self.scrollArea.setWindowIcon(QIcon(join(self.dictInt.addonPath, 'icons', 'migaku.png')))
        self.scrollArea.setWindowTitle('Migaku Card Exporter')
        self.definitionList = []
        self.word = ''
        self.sentence = ''
        self.initTooltips()
        self.restoreSizePos()
        self.scrollArea.closeEvent = self.closeEvent
        self.scrollArea.hideEvent = self.hideEvent
        self.setHotkeys()
        self.scrollArea.show()
        self.alwaysOnTop = self.config['dictAlwaysOnTop']
        self.maybeSetToAlwaysOnTop()
        self.bulkMediaExportProgressWindow: typing.Optional[QWidget] = None

    def maybeSetToAlwaysOnTop(self) -> None:
        if self.alwaysOnTop:
            self.scrollArea.setWindowFlags(self.scrollArea.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.scrollArea.show()

    def attemptAutoAdd(self, bulkExport: bool) -> None:
        if self.autoAdd.isChecked() or bulkExport:
            self.addCard()

    def initTooltips(self) -> None:
        if self.config['tooltips']:
            self.templateCB.setToolTip('Select the export template.')
            self.deckCB.setToolTip('Select the deck to export to.')
            self.clearButton.setToolTip('Clear the card exporter.')

    def restoreSizePos(self) -> None:
        sizePos = self.config['exporterSizePos']
        if sizePos:
            self.scrollArea.resize(sizePos[2], sizePos[3])
            self.scrollArea.move(sizePos[0], sizePos[1])
            ensureWidgetInScreenBoundaries(self.scrollArea)

    def setHotkeys(self) -> None:
        self.sentencehotkeyS = QShortcut(
            QKeySequence('Ctrl+S'), self.scrollArea, lambda : self.attemptSearch(False))
        self.sentencehotkeyS = QShortcut(
            QKeySequence('Ctrl+F'), self.scrollArea, lambda : self.attemptSearch(True))
        self.scrollArea.hotkeyEsc = QShortcut(QKeySequence("Esc"), self.scrollArea)
        self.scrollArea.hotkeyEsc.activated.connect(self.scrollArea.hide)

    def attemptSearch(self, in_browser) -> None:
        focused = self.scrollArea.focusWidget()
        if type(focused).__name__ in  ['MILineEdit', 'MITextEdit']:
            focused.searchSelected(in_browser)

    def setColors(self) -> None:
        if self.dictInt.nightModeToggler.day :
            self.scrollArea.setPalette(self.dictInt.ogPalette)
            if is_mac:
                self.templateCB.setStyleSheet(self.dictInt.getMacComboStyle())
                self.deckCB.setStyleSheet(self.dictInt.getMacComboStyle())
                self.definitions.setStyleSheet(self.dictInt.getMacTableStyle())
            else:
                self.templateCB.setStyleSheet('')
                self.deckCB.setStyleSheet('')
                self.definitions.setStyleSheet('')
        else:
            self.scrollArea.setPalette(self.dictInt.nightPalette)
            if is_mac:
                self.templateCB.setStyleSheet(self.dictInt.getMacNightComboStyle())
                self.deckCB.setStyleSheet(self.dictInt.getMacNightComboStyle())
            else:
                self.templateCB.setStyleSheet(self.dictInt.getComboStyle())
                self.deckCB.setStyleSheet(self.dictInt.getComboStyle())
            self.definitions.setStyleSheet(self.dictInt.getTableStyle())

    def addNote(self, note, did) -> bool:
        note.model()['did'] = int(did)
        ret = note.dupeOrEmpty()
        if ret == 1:
            if not miAsk('Your note\'s sorting field will be empty with this configuration. Would you like to continue?', self.scrollArea, self.dictInt.nightModeToggler.day):
                return False
        if '{{cloze:' in note.model()['tmpls'][0]['qfmt']:
            if not self.mw.col.models._availClozeOrds(
                    note.model(), note.joinedFields(), False):
                if not miAsk("You have a cloze deletion note type "
                "but have not made any cloze deletions. Would you like to continue?", self.scrollArea, self.dictInt.nightModeToggler.day):
                    return False
        cards = self.mw.col.addNote(note)
        if not cards:
            miInfo(("""\
The current input and template combination \
will lead to a blank card and therefore has not been added. \
Please review your template and notetype combination."""), level='wrn', day = self.dictInt.nightModeToggler.day)
            return False
        self.mw.col.save()
        self.mw.reset()

        return True

    def getDecks(self) -> dict[str, int]:
        decksRaw = self.mw.col.decks.decks
        decks: dict[str, int] = {}

        for did, deck in decksRaw.items():
            if not deck['dyn']:
                decks[deck['name']] = did

        return decks

    def getDeckCB(self) -> QComboBox:
        cb = QComboBox()
        decks = list(self.decks.keys())
        decks.sort()
        cb.addItems(decks)
        current = self.config['currentDeck']
        if current in decks:
            cb.setCurrentText(current)
        cb.currentIndexChanged.connect(lambda: self.dictInt.writeConfig('currentDeck', cb.currentText()))
        return cb

    def hideEvent(self, event: QEvent) -> None:
        self.saveSizeAndPos()
        event.accept()

    def closeEvent(self, event: QEvent) -> None:
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
        posSize = [x,y,width, height]
        self.dictInt.writeConfig('exporterSizePos', posSize)
        self.dictInt.writeConfig('exporterLastTags', self.tagsLE.text())

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
        self.mw.refreshMigakuDictConfig(config)
        self.mw.addonManager.writeConfig(__name__, config)

    def saveAutoAddChecked(self) -> None:
        config = self.getConfig()
        config["autoAddCards"] = self.autoAdd.isChecked()
        self.config = config
        self.mw.refreshMigakuDictConfig(config)
        self.mw.addonManager.writeConfig(__name__, config)

    def saveAddDefinitionChecked(self) -> None:
        config = self.getConfig()
        config["autoAddDefinitions"] = self.addDefinitionsCheckbox.isChecked()
        self.config = config
        self.mw.refreshMigakuDictConfig(config)
        self.mw.addonManager.writeConfig(__name__, config)

    def addCard(self) -> None:
        templateName = self.templateCB.currentText()
        if templateName in self.templates:
            template = self.templates[templateName]
            noteType = template['noteType']
            model = self.mw.col.models.byName(noteType)
            if model:
                note = Note(self.mw.col, model)
                modelFields = self.mw.col.models.fieldNames(note.model())
                fieldsValues, imgField, audioField, tagsField = self.getFieldsValues(template)
                word = self.wordLE.text()
                if not fieldsValues:
                    miInfo('The currently selected template and values will lead to an invalid card. Please try again.', level='wrn', day = self.dictInt.nightModeToggler.day)
                    return
                for field in fieldsValues:
                    if field in modelFields:
                        note[field] = template['separator'].join(fieldsValues[field])
                note.setTagsFromStr(tagsField)
                did = False
                deck = self.deckCB.currentText()
                if deck in self.decks:
                    did = self.decks[deck]
                if did:
                    if word and self.addDefinitionsCheckbox.isChecked():
                        note = self.automaticallyAddDefinitions(note, word,  template)
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
                miInfo('The notetype for the currently selected template does not exist in the currently loaded profile.', level='err', day = self.dictInt.nightModeToggler.day)
                return
        miInfo('A card could not be added with this current configuration. Please ensure that your template is configured correctly for this collection.', level='err', day = self.dictInt.nightModeToggler.day)

    def automaticallyAddDefinitions(self, note, word, template):
        if not self.definitionSettings:
            return note

        dictToTable = self.getDictionaryNameToTableNameDictionary()
        unspecifiedDefinitionField = template["unspecified"]
        specificFields = template["specific"]
        dictionaries = []
        for setting in self.definitionSettings:
            dictName = setting["name"]
            if dictName in dictToTable:
                table = dictToTable[dictName]
                limit = setting["limit"]
                targetField = unspecifiedDefinitionField
                for specificField, specificDictionaries in specificFields.items():
                    if dictName in specificDictionaries:
                        targetField = specificField
                dictionaries.append({
                    "tableName" : table,
                    "limit" : limit,
                    "field" : targetField,
                    "dictName" : dictName
                    })

        return self.mw.addDefinitionsToCardExporterNote(note, word, dictionaries)

    def moveImageToMediaFolder(self) -> None:
        if self.imgPath and self.imgName:
            if exists(self.imgPath):
                path = join(self.mw.col.media.dir(), self.imgName)
                if not exists(path):
                    copyfile(self.imgPath, path)

    def fieldValid(self, field: str) -> bool:
        return field != 'Don\'t Export'

    def getDictionaryEntries(self, dictionary: str) -> list[str]:
        finList: list[str] = []
        idxs: list[int] = []
        for idx, defList in enumerate(self.definitionList):
            if defList[0] == dictionary:
                finList.append(defList[2])
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

    def getFieldsValues(self, t):
        # TODO: tuple[fields, imgField, audioField, tagsField]
        imgField = False
        audioField = False
        tagsField = ''
        fields = {}
        sentenceText = self.cleanHTML(self.sentenceLE.toHtml())
        sentenceText = self.emptyValueIfEmptyHtml(sentenceText)
        if sentenceText != '':
            sentenceField = t['sentence']
            if sentenceField !=  "Don't Export":
                if self.fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        secondaryText = self.cleanHTML(self.secondaryLE.toHtml())
        secondaryText = self.emptyValueIfEmptyHtml(secondaryText)
        if secondaryText != '' and 'secondary' in t:
            secondaryField = t['secondary']
            if secondaryField !=  "Don't Export":
                if self.fieldValid(secondaryField):
                    fields[secondaryField] = [secondaryText]
        notesText = self.cleanHTML(self.notesLE.toHtml())
        notesText = self.emptyValueIfEmptyHtml(notesText)
        if notesText != '' and 'notes' in t:
            notesField = t['notes']
            if notesField !=  "Don't Export":
                if self.fieldValid(notesField):
                    fields[notesField] = [notesText]
        wordText = self.wordLE.text()
        if wordText != '':
            wordField = t['word']
            if wordField !=  "Don't Export":
                if self.fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self.tagsLE.text()
        if tagsText != '':
            tagsField = tagsText
        imgText = self.imageMap.text()
        if imgText != 'No Image Selected':
            imgField = t['image']
            if imgField !=  "Don't Export":
                imgTag = '<img src="'+ self.imgName +'">'
                if self.fieldValid(imgField):
                    if imgField not in fields:
                        fields[imgField] = [imgTag]
                    else:
                        fields[imgField].append(imgTag)
        audioText = self.imageMap.text()
        if audioText != 'No Audio Selected' and 'audio' in t and self.audioTag != False:
            audioField = t['audio']
            if audioField !=  "Don't Export":
                if self.fieldValid(audioField):
                    if audioField not in fields:
                        fields[audioField] = [self.audioTag]
                    else:
                        fields[audioField].append(self.audioTag)
        specific = t['specific']
        for field in specific:
            for dictionary in specific[field]:
                if field not in fields:
                    fields[field] = self.getDictionaryEntries(dictionary)
                else:
                    fields[field] += self.getDictionaryEntries(dictionary)
        unspecified = t['unspecified']
        for idx, defList in enumerate(self.definitionList):
            if unspecified not in fields:
                fields[unspecified] = [defList[2]]
            else:
                fields[unspecified].append(defList[2])
        return fields, imgField, audioField, tagsField;

    def clearCurrent(self) -> None:
        self.definitions.setRowCount(0)
        self.sentenceLE.clear()
        self.secondaryLE.clear()
        self.notesLE.clear()
        self.wordLE.clear()
        self.definitionList = []
        self.audioMap.clear()
        self.audioMap.setText('No Audio Selected')
        self.audioPlay.hide()
        self.audioTag = False
        self.audioName = False
        self.audioPath = False
        self.imageMap.clear()
        self.imageMap.setText('No Image Selected')
        self.imgPath = False
        self.imgName = False

    def getDefinitions(self) -> QTableWidget:
        macLin = False
        if is_mac  or is_lin:
            macLin = True
        definitions = QTableWidget()
        definitions.setMinimumHeight(100)
        definitions.setColumnCount(3)
        tableHeader = definitions.horizontalHeader()
        vHeader = definitions.verticalHeader()
        vHeader.setDefaultSectionSize(50);
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

    def getConfig(self):
        return self.mw.addonManager.getConfig(__name__)

    def setupLayout(self) -> None:
        tempLayout = QHBoxLayout()
        tempLayout.addWidget(QLabel('Template: '))
        self.templateCB.setFixedSize(120, 30)
        tempLayout.addWidget(self.templateCB)
        tempLayout.addWidget(QLabel(' Deck: '))
        self.deckCB.setFixedSize(120, 30)
        tempLayout.addWidget(self.deckCB)
        tempLayout.addStretch()
        tempLayout.setSpacing(2)
        self.clearButton.setFixedSize(130, 30)
        tempLayout.addWidget(self.clearButton)
        self.layout.addLayout(tempLayout)
        sentenceL = QLabel('Sentence')
        self.layout.addWidget(sentenceL)
        self.layout.addWidget(self.sentenceLE)
        secondaryL = QLabel('Secondary')
        self.layout.addWidget(secondaryL)
        self.layout.addWidget(self.secondaryLE)
        wordL = QLabel('Word')
        self.layout.addWidget(wordL)
        self.layout.addWidget(self.wordLE)
        notesL = QLabel('User Notes')
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
        definitionsL = QLabel('Definitions')
        self.layout.addWidget(definitionsL)
        self.layout.addWidget(self.definitions)

        self.layout.addWidget(QLabel('Audio'))
        self.audioMap = QLabel('No Audio Selected')
        self.layout.addWidget(self.audioMap)
        self.layout.addWidget(self.audioPlay)
        self.layout.addWidget(QLabel('Image'))
        self.imageMap = QLabel('No Image Selected')
        self.layout.addWidget(self.imageMap)
        tagsL = QLabel('Tags')
        self.layout.addWidget(tagsL)
        lastTags = self.config.get('exporterLastTags', '')
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
        current = self.config['currentTemplate']

        cb.currentIndexChanged.connect(lambda: self.dictInt.writeConfig('currentTemplate', cb.currentText()))
        if current in self.templates:
            cb.setCurrentText(current)
        return cb

    def addImgs(self, word: str, imgs: str, thumbs: QWidget) -> None:
        self.focusWindow()
        defEntry = ["Google Images", False, imgs, imgs]
        if defEntry in self.definitionList:
            miInfo('A card cannot contain duplicate definitions.', level='not', day = self.dictInt.nightModeToggler.day)
            return
        self.definitionList.append(defEntry)
        rc = self.definitions.rowCount()
        self.definitions.setRowCount(rc + 1)
        self.definitions.setItem(rc, 0, QTableWidgetItem("Google Images"))
        self.definitions.setCellWidget(rc, 1, thumbs)
        deleteButton =  QPushButton("X");
        deleteButton.setFixedWidth(40)
        deleteButton.clicked.connect(lambda: self.removeImgs(imgs))
        self.definitions.setCellWidget(rc, 2, deleteButton)
        self.definitions.resizeRowsToContents()
        if self.wordLE.text() == '':
            self.wordLE.setText(word)

    def exportWord(self, word: str) -> None:
        self.wordLE.setText(word)

    def removeImgs(self, imgs: str) -> None:
        # TODO: @ColinKennedy - try/except
        try:
            row = self.definitions.selectionModel().currentIndex().row()
            self.definitions.removeRow(row)
            self.removeImgFromDefinitionList(imgs)
        except:
            return

    def removeImgFromDefinitionList(self, imgs: str) -> None:
        for idx, entry in enumerate(self.definitionList):
            if entry[0] == 'Google Images' and entry[3] == imgs:
                self.definitionList.pop(idx)
                break

    def addDefinition(self, dictName: str, word: str, definition: str) -> None:
        self.focusWindow()
        if len(definition) > 40:
            shortDef = definition.replace('<br>', ' ')[:40] + '...'
        else:
            shortDef = definition.replace('<br>', ' ')
        defEntry = [dictName, shortDef, definition, False]
        if defEntry in self.definitionList:
            miInfo('A card can not contain duplicate definitions.', level='not', day = self.dictInt.nightModeToggler.day)
            return
        self.definitionList.append(defEntry)
        rc = self.definitions.rowCount()
        self.definitions.setRowCount(rc + 1)
        self.definitions.setItem(rc, 0, QTableWidgetItem(dictName))
        self.definitions.setItem(rc, 1, QTableWidgetItem(shortDef))
        deleteButton =  QPushButton("X");
        deleteButton.setFixedWidth(40)
        deleteButton.clicked.connect(self.removeDefinition)
        self.definitions.setCellWidget(rc, 2, deleteButton)
        self.definitions.resizeRowsToContents()
        if self.wordLE.text() == '':
            self.wordLE.setText(word)

    def exportImage(self, path: str, name: str) -> None:
        self.imgName = name
        self.imgPath = path
        if self.imageMap:
            self.imageMap.setText('')
            screenshot = QPixmap(path)
            screenshot = screenshot.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
            self.audioPlayer.play(self.audioPath)

    def exportSentence(self, sentence: str) -> None:
        self.focusWindow()
        self.sentenceLE.setHtml(sentence)

    def exportSecondary(self, secondary: str) -> None:
        self.secondaryLE.setHtml(secondary)

    def removeFromDefinitionList(self, dictName: str, shortDef: str) -> None:
        for idx, entry in enumerate(self.definitionList):
            if entry[0] == dictName and entry[1] == shortDef:
                self.definitionList.pop(idx)
                break

    def removeDefinition(self) -> None:
        # TODO: @ColinKennedy Remove later
        try:
            row = self.definitions.selectionModel().currentIndex().row()
            dictName = self.definitions.item(row, 0).text()
            shortDef = self.definitions.item(row, 1).text()
            self.definitions.removeRow(row)
            self.removeFromDefinitionList(dictName, shortDef)
        except:
            return

    def focusWindow(self) -> None:
        self.scrollArea.show()
        if self.scrollArea.windowState() == Qt.WindowState.WindowMinimized:
            self.scrollArea.setWindowState(Qt.WindowState.WindowNoState)
        self.scrollArea.setFocus()
        self.scrollArea.activateWindow()

    def getDictionaryNameToTableNameDictionary(self) -> dict[str, str]:
        dictToTable = collections.OrderedDict()
        dictToTable['None'] = 'None'
        dictToTable['Forvo'] = 'Forvo'
        dictToTable['Google Images'] = 'Google Images'
        database = dictdb.get()

        for dictTableName in sorted(database.getAllDicts()):
            dictName = database.cleanDictName(dictTableName)
            dictToTable[dictName] = dictTableName;

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

        save =  QPushButton('Save Settings')
        layout.addWidget(save)
        layout.setContentsMargins(4, 4, 4, 4)
        save.clicked.connect(lambda: self.saveDefinitionSettings(settingsWidget, dict1.currentText(), howMany1.value(), dict2.currentText(), howMany2.value(), dict3.currentText(), howMany3.value()))
        settingsWidget.setWindowTitle("Definition Settings")
        settingsWidget.setWindowIcon(QIcon(join(self.dictInt.addonPath, 'icons', 'migaku.png')))
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
    ):
        definitionSettings: list[_DefinitionSetting] = []
        definitionSettings.append({ "name": dict1, "limit" : limit1})
        definitionSettings.append({ "name": dict2, "limit" : limit2})
        definitionSettings.append({ "name": dict3, "limit" : limit3})
        config = self.getConfig()
        self.definitionSettings = definitionSettings
        config["autoDefinitionSettings"] = definitionSettings
        self.mw.addonManager.writeConfig(__name__, config)
        settingsWidget.close()
        settingsWidget.deleteLater()

    def cleanHTML(self, text: str) -> str:
        # Switch bold style to <b>
        text = re.sub(r'(<span style=\"[^\"]*?)font-weight:600;(.*?\">.*?</span>)', r'<b>\1\2</b>', text, flags=re.S)
        text = re.sub(r'(<span style=\"[^\"]*?)font-style:italic;(.*?\">.*?</span>)', r'<i>\1\2</i>', text, flags=re.S)
        text = re.sub(r'(<span style=\"[^\"]*?)text-decoration: underline;(.*?\">.*?</span>)', r'<u>\1\2</u>', text, flags=re.S)

        # Switch paragraphs to <br>
        text = re.sub(r'</p>', r'<br />', text, re.S)

        # Trim unneeded bits
        text = re.sub(r'.+</head>', r'', text, flags=re.S)
        text = re.sub(r'(<html[^>]*?>|</html>|<body[^>]*?>|</body>|<p[^>]*?>|<span[^>]*?>|</span>)', r'', text, flags=re.S)
        text = text.strip()

        # Remove any trailing <br /> (there can be two)
        text = re.sub(r'<br />$', r'', text)
        text = re.sub(r'<br />$', r'', text)

        # For debugging
        #text = html.escape(text)
        return text


    def addTextCard(self, card: typer.Card) -> None:
        templateName = self.templateCB.currentText()
        sentence = card["primary"]
        word = ""
        unknowns = card["unknowns"]
        if len(unknowns) > 0:
            word = unknowns[0]

        if templateName in self.templates:
            template = self.templates[templateName]
            noteType = template['noteType']
            model = self.mw.col.models.byName(noteType)
            if model:
                note = Note(self.mw.col, model)
                modelFields = self.mw.col.models.fieldNames(note.model())
                fieldsValues, tagsField = self.getFieldsValuesForTextCard(template, word, sentence)
                if fieldsValues:
                    for field in fieldsValues:
                        if field in modelFields:
                            note[field] = template['separator'].join(fieldsValues[field])
                    note.setTagsFromStr(tagsField)
                    did = False
                    deck = self.deckCB.currentText()
                    if deck in self.decks:
                        did = self.decks[deck]
                    if did:
                        if word and self.addDefinitionsCheckbox.isChecked():
                            note = self.automaticallyAddDefinitions(note, word,  template)
                        if self.exportJS:
                            note = self.dictInt.jHandler.attemptGenerate(note)
                        note.model()['did'] = int(did)
                        self.mw.col.addNote(note)
                        self.mw.col.save()
                else:
                    print("Invalid field values")

    def getFieldsValuesForTextCard(
        self,
        t: _Template,
        wordText: str,
        sentenceText: str,
    ) -> tuple[dict[str, list[str]], str]:
        tagsField = ''
        fields = {}
        if sentenceText != '':
            sentenceField = t['sentence']
            if sentenceField !=  "Don't Export":
                if self.fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        if wordText != '':
            wordField = t['word']
            if wordField !=  "Don't Export":
                if self.fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self.tagsLE.text()
        if tagsText != '':
            tagsField = tagsText
        return fields, tagsField

    def bulkTextExport(self, cards: typing.Sequence[typer.Card]) -> None:
        self.bulkTextImporting = True
        total = len(cards)
        importingMessage = "Importing {} of "+ str(total) + " cards."
        progressWidget, bar, textDisplay = self.getProgressBar("Migaku Dictionary - Importing Text Cards", importingMessage.format(0))
        bar.setMaximum(total)
        for idx, card in enumerate(cards):
            if not self.bulkTextImporting:
                miInfo("Importing cards from the extension has been cancelled.\n\n{} of {} were added.".format(idx, total))
                return
            self.addTextCard(card)
            bar.setValue(idx + 1)
            textDisplay.setText(importingMessage.format(idx + 1))
            self.mw.app.processEvents()
        self.bulkTextImporting = False
        self.closeProgressBar(progressWidget)

    def addMediaCard(self, card: typer.Card) -> None:
        templateName = self.templateCB.currentText()
        word = ""
        unknowns = card["unknownWords"]
        if len(unknowns) > 0:
            word = unknowns[0]
        if templateName in self.templates:
            template = self.templates[templateName]
            noteType = template['noteType']
            model = self.mw.col.models.byName(noteType)
            if model:
                note = Note(self.mw.col, model)
                modelFields = self.mw.col.models.fieldNames(note.model())
                fieldsValues, tagsField = self.getFieldsValuesForMediaCard(template, word, card)
                if fieldsValues:
                    for field in fieldsValues:
                        print(fieldsValues)
                        print(field)
                        if field in modelFields:
                            note[field] = template['separator'].join(fieldsValues[field])
                    note.setTagsFromStr(tagsField)
                    did = False
                    deck = self.deckCB.currentText()
                    if deck in self.decks:
                        did = self.decks[deck]
                    if did:
                        if word and self.addDefinitionsCheckbox.isChecked():
                            note = self.automaticallyAddDefinitions(note, word,  template)
                        if self.exportJS:
                            note = self.dictInt.jHandler.attemptGenerate(note)
                        note.model()['did'] = int(did)
                        self.mw.col.addNote(note)
                        self.mw.col.save()
                else:
                    print("Invalid field values")

    def getFieldsValuesForMediaCard(
        self,
        t: _Template,
        wordText: str,
        card: typer.Card,
    ) -> tuple[dict[str, list[str]], str]:
        sentenceText = card["primary"]
        secondaryText = card["secondary"]
        imageFile = card["image"]
        audioFile = card["audio"]
        audio = False
        image = False
        if audioFile:
            audio =  '[sound:' + audioFile +']'
        if imageFile:
            image = imageFile
        imgField = False
        audioField = False
        tagsField = ''
        fields = {}
        if sentenceText != '':
            sentenceField = t['sentence']
            if sentenceField !=  "Don't Export":
                if self.fieldValid(sentenceField):
                    fields[sentenceField] = [sentenceText]
        if secondaryText != '' and 'secondary' in t:
            secondaryField = t['secondary']
            if secondaryField !=  "Don't Export":
                if self.fieldValid(secondaryField):
                    fields[secondaryField] = [secondaryText]
        if wordText != '':
            wordField = t['word']
            if wordField !=  "Don't Export":
                if self.fieldValid(wordField):
                    if wordField not in fields:
                        fields[wordField] = [wordText]
                    else:
                        fields[wordField].append(wordText)
        tagsText = self.tagsLE.text()
        if tagsText != '':
            tagsField = tagsText
        if image:
            imgField = t['image']
            imgTag = '<img src="'+ image +'">'
            if self.fieldValid(imgField):
                if imgField not in fields:
                    fields[imgField] = [imgTag]
                else:
                    fields[imgField].append(imgTag)
        if audio:
            audioField = t['audio']
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
            importingMessage = "Importing {} of "+ str(total) + " cards."
            self.bulkMediaExportProgressWindow, self.bulkMediaExportProgressWindow.bar, self.bulkMediaExportProgressWindow.textDisplay = self.getProgressBar("Migaku Dictionary - Importing Media Cards", importingMessage.format(0))
            self.bulkMediaExportProgressWindow.bar.setMaximum(total)
            self.bulkMediaExportProgressWindow.currentValue = 0
            self.bulkMediaExportProgressWindow.total = total
        else:
            importingMessage = "Importing {} of "+ str(self.bulkMediaExportProgressWindow.total) + " cards."
        self.addMediaCard(card)

        # TODO: @ColinKennedy remove this try/except later
        try:
            if global_state.IS_BULK_MEDIA_EXPORT_CANCELLED or not self.bulkMediaExportProgressWindow:
                if self.bulkMediaExportProgressWindow:
                    self.closeProgressBar(self.bulkMediaExportProgressWindow)
                return
            self.bulkMediaExportProgressWindow.currentValue += 1
            self.bulkMediaExportProgressWindow.bar.setValue(self.bulkMediaExportProgressWindow.currentValue)
            self.bulkMediaExportProgressWindow.textDisplay.setText(importingMessage.format(self.bulkMediaExportProgressWindow.currentValue))
            self.mw.app.processEvents()
            if self.bulkMediaExportProgressWindow.currentValue == self.bulkMediaExportProgressWindow.total:
                total = self.bulkMediaExportProgressWindow.total
                if total == 1:
                    miInfo("{} card has been imported.".format(total))
                else:
                    miInfo("{} cards have been imported.".format(total))
                self.closeProgressBar(self.bulkMediaExportProgressWindow)
                self.bulkMediaExportProgressWindow = False
        except:
            pass

    def bulkMediaExportCancelledByBrowserRefresh(self) -> None:
        if not self.bulkMediaExportProgressWindow:
            return

        currentValue = self.bulkMediaExportProgressWindow.currentValue
        miInfo("Importing cards from the extension has been cancelled from within the browser.\n\n {} cards were imported.".format(currentValue))
        self.closeProgressBar(self.bulkMediaExportProgressWindow)
        self.bulkMediaExportProgressWindow = False
        global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = False

    def getProgressBar(
        self,
        title: str,
        initialText: str,
    ) -> tuple[QWidget, QProgressBar, QLabel]:
        progressWidget = QWidget()
        self._progress_bar_closed_and_finished_importing[progressWidget] = False
        def closedProgressBar(event):
            if self.bulkTextImporting:
                self.bulkTextImporting = False
            event.accept()
            progressWidget.deleteLater()
            if self.bulkMediaExportProgressWindow:
                currentValue = self.bulkMediaExportProgressWindow.currentValue
                self.bulkMediaExportProgressWindow = False
                if not self._progress_bar_closed_and_finished_importing[progressWidget]:
                    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = True
                    miInfo("Importing cancelled.\n\n{} cards were imported.".format(currentValue))

        progressWidget.exporter = self
        textDisplay = QLabel()
        progressWidget.setWindowIcon(QIcon(join(self.dictInt.addonPath, 'icons', 'migaku.png')))
        progressWidget.setWindowTitle(title)
        textDisplay.setText(initialText)

        bar = QProgressBar(progressWidget)
        layout = QVBoxLayout()
        layout.addWidget(textDisplay)
        layout.addWidget(bar)
        progressWidget.setLayout(layout)
        bar.move(10,10)
        per = QLabel(bar)
        per.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progressWidget.setFixedSize(500, 100)
        progressWidget.setWindowModality(Qt.WindowModality.ApplicationModal)
        if self.alwaysOnTop:
            progressWidget.setWindowFlags(progressWidget.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        screenGeometry = QApplication.desktop().screenGeometry();
        x = (screenGeometry.width() - progressWidget.width()) / 2;
        y = (screenGeometry.height() - progressWidget.height()) / 2;
        progressWidget.move(x, y);
        progressWidget.show()
        progressWidget.setFocus()
        progressWidget.closeEvent = closedProgressBar
        self.mw.app.processEvents()
        return progressWidget, bar, textDisplay

    def closeProgressBar(self, progressBar: typing.Optional[QProgressBar]) -> None:
        if progressBar:
            self._progress_bar_closed_and_finished_importing[progressWidget] = True
            progressBar.close()
            progressBar.deleteLater()
