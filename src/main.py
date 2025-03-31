# -*- coding: utf-8 -*-

import typing

from os.path import dirname, join, basename, exists, join
import sys, os, platform, re, subprocess, aqt.utils
from anki import notes as notes_
from anki.utils import stripHTML, is_win, is_mac, is_lin
from . import midict
import re
import unicodedata
import urllib.parse
from shutil import copyfile
from anki.hooks import addHook, wrap, runHook, runFilter
from aqt.utils import shortcut, saveGeom, saveSplitter, showInfo, askUser
from aqt import editor as editor_
import json
from aqt import mw, gui_hooks
from aqt.qt import *
from . import dictdb
from aqt.webview import AnkiWebView
from .miutils import miInfo, miAsk
from .addonSettings import SettingsGui
import codecs
from operator import itemgetter
from aqt.addcards import AddCards
from aqt.editcurrent import EditCurrent
from aqt import browser as browser_
from aqt.tagedit import TagEdit
from aqt.reviewer import Reviewer
from . import googleimages
from .forvodl import Forvo
from urllib.request import Request, urlopen
from aqt.previewer import Previewer
import requests
import time
import os
from aqt.qt import debug;
from PyQt6.QtCore import Qt

from . import google_imager, migaku_dictionary, migaku_configuration, threader, typer


class _DictionaryConfiguration(typing.TypedDict):
    dictName: str
    field: str
    limit: int
    tableName: str


def window_loaded() -> None:
    migaku_configuration.initialize_by_namespace()
    mw.MigakuExportingDefinitions = False
    mw.dictSettings = False
    dictdb.set(dictdb.DictDB())
    progressBar = False
    addon_path = dirname(__file__)
    currentNote = False
    currentField = False
    currentKey = False
    wrapperDict = False
    tmpdir = join(addon_path, 'temp')
    mw.migakuEditorLoadedAfterDictionary = False
    mw.MigakuBulkMediaExportWasCancelled = False

    def removeTempFiles() -> None:
        filelist = [ f for f in os.listdir(tmpdir)]
        for f in filelist:
            path = os.path.join(tmpdir, f)
            try:
                os.remove(path)
            except:
                innerDirFiles = [ df for df in os.listdir(path)]
                for df in innerDirFiles:
                    innerPath = os.path.join(path, df)
                    os.remove(innerPath)
                os.rmdir(path)

    removeTempFiles()

    def migaku(text: str) -> None:
        showInfo(text ,False,"", "info", "Migaku Dictionary Add-on")

    def showA(ar: typing.Iterable[typing.Hashable]) -> None:
        showInfo(json.dumps(ar, ensure_ascii=False))


    dictWidget  = False

    js = QFile(':/qtwebchannel/qwebchannel.js')
    assert js.open(QIODevice.ReadOnly)
    js = bytes(js.readAll()).decode('utf-8')


    def searchCol(self) -> None:
        text = selectedText(self)
        performColSearch(text)


    def performColSearch(text: str) -> None:
        if text:
            text = text.strip()
            browser = aqt.DialogManager._dialogs["Browser"][1]
            if not browser:
                mw.onBrowse()
                browser = aqt.DialogManager._dialogs["Browser"][1]
            if browser:
                browser.form.searchEdit.lineEdit().setText(text)
                browser.onSearchActivated()
                browser.activateWindow()
                if not is_win:
                    browser.setWindowState(browser.windowState() & ~Qt.WindowState.Minimized| Qt.WindowState.WindowActive)
                    browser.raise_()
                else:
                    browser.setWindowFlags(browser.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                    browser.show()
                    browser.setWindowFlags(browser.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
                    browser.show()


    mw.currentlyPressed = []

    def captureKey(keyList):
        key = keyList[0]
        char = str(key)
        if char not in mw.currentlyPressed:
                mw.currentlyPressed.append(char)
        if is_win:
            thread = threader.get()

            if 'Key.ctrl_l' in mw.currentlyPressed and "'c'" in mw.currentlyPressed and'Key.space'  in mw.currentlyPressed:
                thread.handleSystemSearch()
                mw.currentlyPressed = []
            elif 'Key.ctrl_l' in mw.currentlyPressed and "'c'" in mw.currentlyPressed and "'b'"  in mw.currentlyPressed:
                thread.handleColSearch()
                mw.currentlyPressed = []
            elif 'Key.ctrl_l' in mw.currentlyPressed and "'c'" in mw.currentlyPressed and 'Key.alt_l' in mw.currentlyPressed:
                thread.handleSentenceExport()
                mw.currentlyPressed = []
            elif 'Key.ctrl_l' in mw.currentlyPressed and 'Key.enter' in mw.currentlyPressed:
                thread.attemptAddCard()
                mw.currentlyPressed = []
            elif 'Key.ctrl_l' in mw.currentlyPressed and 'Key.shift' in mw.currentlyPressed and "'v'" in mw.currentlyPressed:
                thread.handleImageExport()
                mw.currentlyPressed = []
        elif is_lin:
            if 'Key.ctrl' in mw.currentlyPressed and "'c'" in mw.currentlyPressed and'Key.space'  in mw.currentlyPressed:
                thread.handleSystemSearch()
                mw.currentlyPressed = []
            elif 'Key.ctrl' in mw.currentlyPressed and "'c'" in mw.currentlyPressed and 'Key.alt' in mw.currentlyPressed:
                thread.handleSentenceExport()
                mw.currentlyPressed = []
            elif 'Key.ctrl' in mw.currentlyPressed and 'Key.enter' in mw.currentlyPressed:
                thread.attemptAddCard()
                mw.currentlyPressed = []
            elif 'Key.ctrl' in mw.currentlyPressed and 'Key.shift' in mw.currentlyPressed and "'v'" in mw.currentlyPressed:
                thread.handleImageExport()
                mw.currentlyPressed = []
        else:
            if ('Key.cmd' in mw.currentlyPressed or 'Key.cmd_r' in mw.currentlyPressed)  and "'c'" in mw.currentlyPressed and "'b'"  in mw.currentlyPressed:
                thread.handleColSearch()
                mw.currentlyPressed = []
            elif ('Key.cmd' in mw.currentlyPressed or 'Key.cmd_r' in mw.currentlyPressed) and "'c'" in mw.currentlyPressed and 'Key.ctrl' in mw.currentlyPressed:
                thread.handleSentenceExport()
                mw.currentlyPressed = []
            elif ('Key.cmd' in mw.currentlyPressed or 'Key.cmd_r' in mw.currentlyPressed) and 'Key.enter' in mw.currentlyPressed:
                thread.attemptAddCard()
                mw.currentlyPressed = []
            elif ('Key.cmd' in mw.currentlyPressed or 'Key.cmd_r' in mw.currentlyPressed) and 'Key.shift' in mw.currentlyPressed and "'v'" in mw.currentlyPressed:
                thread.handleImageExport()
                mw.currentlyPressed = []


    def releaseKey(keyList: list[str]) -> None:
        key = keyList[0]
        try:
            mw.currentlyPressed.remove(str(key))
        except:
            # TODO: @ColinKennedy - docstring / logging
            return


    def exportSentence(sentence: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.exportSentence(sentence)
            showCardExporterWindow()

    def exportImage(img: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            if img[1].startswith('[sound:'):
                dictionary.dict.exportAudio(img)
            else:
                dictionary.dict.exportImage(img)
            showCardExporterWindow()

    def _initialize_dictionary_if_needed() -> midict.DictInterface:
        if not migaku_dictionary.get_visible_dictionary():
            dictionaryInit()

        return migaku_dictionary.get()

    def extensionBulkTextExport(cards) -> None:
        dictionary = _initialize_dictionary_if_needed()
        dictionary.dict.bulkTextExport(cards)

    def extensionBulkMediaExport(card) -> None:
        dictionary = _initialize_dictionary_if_needed()
        dictionary.dict.bulkMediaExport(card)

    def cancelBulkMediaExport() -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.cancelBulkMediaExport()


    def extensionCardExport(card) -> None:
        primary = card["primary"]
        secondary = card["secondary"]
        image = card["image"]
        audio = card["audio"]
        unknownsToSearch = mw.MigakuDictConfig.get("unknownsToSearch", 3)
        autoExportCards = mw.MigakuDictConfig.get("autoAddCards", False)
        unknownWords = card["unknownWords"][:unknownsToSearch]
        if len(unknownWords) > 0:
            if not autoExportCards:
                searchTermList(unknownWords)
                dictionary = migaku_dictionary.get()
            else:
                dictionary = _initialize_dictionary_if_needed()

            dictionary.dict.exportWord(unknownWords[0])
        else:
            dictionary = _initialize_dictionary_if_needed()
            dictionary.dict.exportWord('')
        if audio:
            dictionary.dict.exportAudio([join(mw.col.media.dir(), audio), '[sound:' + audio +']', audio])
        if image:
            dictionary.dict.exportImage([join(mw.col.media.dir(), image), image])
        dictionary.dict.exportSentence(primary, secondary)
        dictionary.dict.addWindow.focusWindow()
        dictionary.dict.attemptAutoAdd(False)
        showCardExporterWindow()

    def showCardExporterWindow() -> None:
        adder = migaku_dictionary.get().dict.addWindow
        cardWindow = adder.scrollArea
        if not is_win:
            cardWindow.setWindowState(cardWindow.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            cardWindow.raise_()
        else:
            cardWindow.setWindowFlags(cardWindow.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            cardWindow.show()
            if not adder.alwaysOnTop:
                cardWindow.setWindowFlags(cardWindow.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
                cardWindow.show()

    def trySearch(term: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.initSearch(term)
            showAfterGlobalSearch()
        elif mw.MigakuDictConfig['openOnGlobal'] and not migaku_dictionary.get_visible_dictionary():
            dictionaryInit([term])

    def showAfterGlobalSearch() -> None:
        dictionary = migaku_dictionary.get()
        dictionary.activateWindow()

        if not is_win:
            dictionary.setWindowState(dictionary.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            dictionary.raise_()

            return

        dictionary.setWindowFlags(dictionary.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dictionary.show()

        if not dictionary.alwaysOnTop:
            dictionary.setWindowFlags(dictionary.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            dictionary.show()

    def attemptAddCard(*_, **__) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            if dictionary.dict.addWindow.scrollArea.isVisible():
                time.sleep(0.3)
                dictionary.dict.addWindow.addCard()


    def openDictionarySettings():
        if not mw.dictSettings:
            mw.dictSettings = SettingsGui(mw, addon_path, openDictionarySettings)
        mw.dictSettings.show()
        if mw.dictSettings.windowState() == Qt.WindowState.WindowMinimized:
            mw.dictSettings.setWindowState(Qt.WindowState.WindowNoState)
        mw.dictSettings.setFocus()
        mw.dictSettings.activateWindow()


    def getWelcomeScreen() -> str:
        htmlPath = join(addon_path, 'welcome.html')
        with open(htmlPath,'r', encoding="utf-8") as fh:
            file =  fh.read()
        return file

    def getMacWelcomeScreen() -> str:
        htmlPath = join(addon_path, 'macwelcome.html')
        with open(htmlPath,'r', encoding="utf-8") as fh:
            file =  fh.read()
        return file

    if is_mac:
        welcomeScreen = getMacWelcomeScreen()
    else:
        welcomeScreen = getWelcomeScreen()

    def dictionaryInit(terms: typing.Union[list[str], typing.Literal[False]]=False):
        if terms and isinstance(terms, str):
            terms = [terms]
        shortcut = '(Ctrl+W)'
        if is_mac:
            shortcut = '⌘W'
        if not migaku_dictionary.get_unsafe():
            migaku_dictionary.set(
                midict.DictInterface(dictdb.get(), mw, addon_path, welcomeScreen, terms = terms)
            )
            mw.openMiDict.setText("Close Dictionary " + shortcut)
            showAfterGlobalSearch()
        elif not migaku_dictionary.get_visible_dictionary():
            dictionary = migaku_dictionary.get()
            dictionary.show()
            dictionary.resetConfiguration(terms)
            mw.openMiDict.setText("Close Dictionary " + shortcut)
            showAfterGlobalSearch()
        else:
            dictionary = migaku_dictionary.get()
            dictionary.hide()

    mw.dictionaryInit = dictionaryInit

    def setupGuiMenu() -> None:
        addMenu = False
        if not hasattr(mw, 'MigakuMainMenu'):
            mw.MigakuMainMenu = QMenu('Migaku',  mw)
            addMenu = True
        if not hasattr(mw, 'MigakuMenuSettings'):
            mw.MigakuMenuSettings = []
        if not hasattr(mw, 'MigakuMenuActions'):
            mw.MigakuMenuActions = []

        setting = QAction("Dictionary Settings", mw)
        setting.triggered.connect(openDictionarySettings)
        mw.MigakuMenuSettings.append(setting)

        mw.openMiDict = QAction("Open Dictionary (Ctrl+W)", mw)
        mw.openMiDict.triggered.connect(dictionaryInit)
        mw.MigakuMenuActions.append(mw.openMiDict)

        mw.MigakuMainMenu.clear()
        for act in mw.MigakuMenuSettings:
            mw.MigakuMainMenu.addAction(act)
        mw.MigakuMainMenu.addSeparator()
        for act in mw.MigakuMenuActions:
            mw.MigakuMainMenu.addAction(act)

        if addMenu:
            mw.form.menubar.insertMenu(mw.form.menuHelp.menuAction(), mw.MigakuMainMenu)

    setupGuiMenu()

    migaku_dictionary.clear()

    def searchTermList(terms: list[str]) -> None:
        limit = mw.MigakuDictConfig.get("unknownsToSearch", 3)
        terms = terms[:limit]

        if not (dictionary := migaku_dictionary.get_visible_dictionary()):
            dictionaryInit(terms)

            return

        for term in terms:
            dictionary.initSearch(term)

        showAfterGlobalSearch()

    def extensionFileNotFound() -> None:
        miInfo("The media files were not found in your \"Download Directory\", please make sure you have selected the correct directory.")

    def initGlobalHotkeys() -> None:
        thread = threader.initialize(midict.ClipThread(mw, addon_path))
        thread.sentence.connect(exportSentence)
        thread.search.connect(trySearch)
        thread.colSearch.connect(performColSearch)
        thread.image.connect(exportImage)
        thread.bulkTextExport.connect(extensionBulkTextExport)
        thread.add.connect(attemptAddCard)
        thread.test.connect(captureKey)
        thread.release.connect(releaseKey)
        thread.pageRefreshDuringBulkMediaImport.connect(cancelBulkMediaExport)
        thread.bulkMediaExport.connect(extensionBulkMediaExport)
        thread.extensionCardExport.connect(extensionCardExport)
        thread.searchFromExtension.connect(searchTermList)
        thread.extensionFileNotFound.connect(extensionFileNotFound)
        thread.run()

    if mw.addonManager.getConfig(__name__)['globalHotkeys']:
        initGlobalHotkeys()

    mw.hotkeyW = QShortcut(QKeySequence("Ctrl+W"), mw)
    mw.hotkeyW.activated.connect(dictionaryInit)

    # TODO: @ColinKennedy - Replace False
    def selectedText(page) -> typing.Union[str, typing.Literal[False]]:
        text = page.selectedText()
        if not text:
            return False
        else:
            return text

    def searchTerm(self) -> None:
        text = selectedText(self)
        if text:
            text = re.sub(r'\[[^\]]+?\]', '', text)
            text = text.strip()
            if not migaku_dictionary.get_visible_dictionary():
                dictionaryInit([text])

            dictionary = migaku_dictionary.get()
            dictionary.ensureVisible()
            dictionary.initSearch(text)
            if self.title == 'main webview':
                if mw.state == 'review':
                    dictionary.dict.setReviewer(mw.reviewer)
            elif self.title == 'editor':
                target = getTarget(type(self.parentEditor.parentWindow).__name__)
                dictionary.dict.setCurrentEditor(self.parentEditor, target=target or "")
            showAfterGlobalSearch()





    mw.searchTerm = searchTerm
    mw.searchCol = searchCol



    mw.hotkeyS = QShortcut(QKeySequence("Ctrl+S"), mw)
    mw.hotkeyS.activated.connect(lambda: searchTerm(mw.web))
    mw.hotkeyS = QShortcut(QKeySequence("Ctrl+Shift+B"), mw)
    mw.hotkeyS.activated.connect(lambda: searchCol(mw.web))


    def addToContextMenu(self, m: QMenu) -> None:
        a = m.addAction("Search (Ctrl+S)")
        a.triggered.connect(self.searchTerm)
        b = m.addAction("Search Collection (Ctrl/⌘+Shift+B)")
        b.triggered.connect(self.searchCol)

    # TODO: @ColinKennedy dedent
    def exportDefinitionsWidget(browser: browser_.Browser) -> None:
        import anki.find
        notes = browser.selectedNotes()
        if notes:
            fields = anki.find.fieldNamesForNotes(mw.col, notes)
            generateWidget = QDialog(None, Qt.Window)
            layout = QHBoxLayout()
            origin = QComboBox()
            origin.addItems(fields)
            addType = QComboBox()
            addType.addItems(['Add','Overwrite', 'If Empty'])
            dicts = QComboBox()
            dict2 = QComboBox()
            dict3 = QComboBox()
            dictDict = {}
            tempdicts = []
            database = dictdb.get()

            for d in database.getAllDicts():
                dictName = database.cleanDictName(d)
                dictDict[dictName] = d;
                tempdicts.append(dictName)
            tempdicts.append('Google Images')
            tempdicts.append('Forvo')
            dicts.addItems(sorted(tempdicts))
            dict2.addItem('None')
            dict2.addItems(sorted(tempdicts))
            dict3.addItem('None')
            dict3.addItems(sorted(tempdicts))
            dictDict['Google Images'] = 'Google Images'
            dictDict['Forvo'] = 'Forvo'
            dictDict['None'] = 'None'
            ex =  QPushButton('Execute')
            ex.clicked.connect(lambda: exportDefinitions(origin.currentText(), destination.currentText(), addType.currentText(),
                [dictDict[dicts.currentText()], dictDict[dict2.currentText()] ,
                dictDict[dict3.currentText()]], howMany.value(), notes, generateWidget,
                [dicts.currentText(),dict2.currentText(), dict3.currentText()]))
            destination = QComboBox()
            destination.addItems(fields)
            howMany = QSpinBox()
            howMany.setValue(1)
            howMany.setMinimum(1)
            howMany.setMaximum(20)
            oLayout = QVBoxLayout()
            oh1 = QHBoxLayout()
            oh2 = QHBoxLayout()
            oh1.addWidget(QLabel('Input Field:'))
            oh1.addWidget(origin)
            oh2.addWidget(QLabel('Output Field:'))
            oh2.addWidget(destination)
            oLayout.add()
            oLayout.addLayout(oh1)
            oLayout.addLayout(oh2)
            oLayout.add()
            oLayout.setContentsMargins(6,0, 6, 0)
            layout.addLayout(oLayout)
            dlay = QHBoxLayout()
            dlay.addWidget(QLabel('Dictionaries:'))
            dictLay = QVBoxLayout()
            dictLay.addWidget(dicts)
            dictLay.addWidget(dict2)
            dictLay.addWidget(dict3)
            dlay.addLayout(dictLay)
            dlay.setContentsMargins(6,0, 6, 0)
            layout.addLayout(dlay)
            bLayout = QVBoxLayout()
            bh1 = QHBoxLayout()
            bh2 = QHBoxLayout()
            bh1.addWidget(QLabel('Output Mode:'))
            bh1.addWidget(addType)
            bh2.addWidget(QLabel('Max Per Dict:'))
            bh2.addWidget(howMany)
            bLayout.add()
            bLayout.addLayout(bh1)
            bLayout.addLayout(bh2)
            bLayout.add()
            bLayout.setContentsMargins(6,0, 6, 0)
            layout.addLayout(bLayout)
            layout.addWidget(ex)
            layout.setContentsMargins(10,6, 10, 6)
            generateWidget.setWindowFlags(generateWidget.windowFlags() | Qt.MSWindowsFixedSizeDialogHint)
            generateWidget.setWindowTitle("Migaku Dictionary: Export Definitions")
            generateWidget.setWindowIcon(QIcon(join(addon_path, 'icons', 'migaku.png')))
            generateWidget.setLayout(layout)
            config = mw.addonManager.getConfig(__name__)
            savedPreferences = config.get("massGenerationPreferences", False)
            if savedPreferences:
                if dicts.findText(savedPreferences["dict1"]) != -1:
                    dicts.setCurrentText(savedPreferences["dict1"])
                if dict2.findText(savedPreferences["dict2"]) != -1:
                    dict2.setCurrentText(savedPreferences["dict2"])
                if dict3.findText(savedPreferences["dict3"]) != -1:
                    dict3.setCurrentText(savedPreferences["dict3"])
                if origin.findText(savedPreferences["origin"]) != -1:
                    origin.setCurrentText(savedPreferences["origin"])
                if destination.findText(savedPreferences["destination"])  != -1:
                    destination.setCurrentText(savedPreferences["destination"])
                addType.setCurrentText(savedPreferences["addType"])
                howMany.setValue(savedPreferences["limit"])
            generateWidget.exec_()
        else:
            miInfo('Please select some cards before attempting to export definitions.', level='not')

    def getProgressWidgetDefs() -> tuple[QWidget, QProgressBar]:
        progressWidget = QWidget(None)
        layout = QVBoxLayout()
        progressWidget.setFixedSize(400, 70)
        progressWidget.setWindowIcon(QIcon(join(addon_path, 'icons', 'migaku.png')))
        progressWidget.setWindowTitle("Generating Definitions...")
        progressWidget.setWindowModality(Qt.WindowModality.ApplicationModal)
        bar = QProgressBar(progressWidget)
        if is_mac:
            bar.setFixedSize(380, 50)
        else:
            bar.setFixedSize(390, 50)
        bar.move(10,10)
        per = QLabel(bar)
        per.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progressWidget.show()
        return progressWidget, bar;

    def getTermHeaderText(th: str, entry: typer.HeaderTerm, fb: str, bb: str) -> str:
        term = entry['term']
        altterm = entry['altterm']
        if altterm == term:
            altterm == ''
        pron = entry['pronunciation']
        if pron == term:
            pron = ''

        termHeader = ''
        for header in th:
            if header == 'term':
                termHeader += fb + term + bb
            elif header == 'altterm':
                if altterm != '':
                    termHeader += fb + altterm + bb
            elif header == 'pronunciation':
                if pron != '':
                    if termHeader != '':
                        termHeader += ' '
                    termHeader  += pron + ' '
        termHeader += entry['starCount']
        return termHeader

    def formatDefinitions(results, th,dh, fb, bb):
        definitions = []
        for idx, r in enumerate(results):
            text = ''
            if dh == 0:

                text = getTermHeaderText(th, r, fb, bb) + '<br>' + r['definition']
            else:
                stars = r['starCount']
                text =  r['definition']
                if '】' in text:
                    text = text.replace('】',  '】' + stars + ' ', 1)
                elif '<br>' in text:
                    text = text.replace('<br>', stars+ '<br>', 1);
                else:
                    text = stars + '<br>' + text
            definitions.append(text)
        return '<br><br>'.join(definitions).replace('<br><br><br>', '<br><br>')

    forvoDler = False;

    def initForvo() -> None:
        global forvoDler
        forvoDler= Forvo(mw.addonManager.getConfig(__name__)['ForvoLanguage'])

    def exportForvoAudio(term: str, howMany: int, lang: str) -> str:
        if not forvoDler:
            initForvo()
        audioSeparator = ''
        urls = forvoDler.search(term, lang)
        if len(urls) < 1:
            time.sleep(.1)
            urls = forvoDler.search(term)
        tags = downloadForvoAudio(urls, howMany)

        return audioSeparator.join(tags)

    def downloadForvoAudio(urls: typing.Iterable[str], howMany: int) -> list[str]:
        tags: list[str] = []

        for url in urls:
            if len(tags) == howMany:
                break

            try:
                req = Request(url[3] , headers={'User-Agent':  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'})
                file = urlopen(req).read()
                filename = str(time.time()) + '.mp3'
                open(join(mw.col.media.dir(), filename), 'wb').write(file)
                tags.append('[sound:' + filename + ']')
                success = True
            except:
                success = True
            if success:
                continue
            else:
                try:
                    req = Request(url[2] , headers={'User-Agent':  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'})
                    file = urlopen(req).read()
                    filename = str(time.time()) + '.mp3'
                    open(join(mw.col.media.dir(), filename), 'wb').write(file)
                    tags.append('[sound:' + filename + ']')
                except:
                    continue
        return tags

    def closeBar(event: QCloseEvent) -> None:
        mw.MigakuExportingDefinitions = False
        event.accept()

    def addDefinitionsToCardExporterNote(
        note: notes_.Note,
        term: str,
        dictionaryConfigurations: _DictionaryConfiguration,
    ) -> notes_.Note:
        config = mw.addonManager.getConfig(__name__)
        fb = config['frontBracket']
        bb = config['backBracket']
        lang = config['ForvoLanguage']
        fields = mw.col.models.fieldNames(note.model())
        database = dictdb.get()

        for dictionary in dictionaryConfigurations:
            tableName = dictionary["tableName"]
            dictName  = dictionary["dictName"]
            limit = dictionary["limit"]
            targetField = dictionary["field"]
            if targetField in fields:
                term = re.sub(r'<[^>]+>', '', term)
                term = re.sub(r'\[[^\]]+?\]', '', term)

                if not term:
                    continue

                tresults: list[str] = []

                if tableName == 'Google Images':
                    tresults.append(google_imager.export_images(term, limit))
                elif tableName == 'Forvo':
                    tresults.append(exportForvoAudio(term, limit, lang))
                elif tableName != 'None':
                    dresults, dh, th = database.getDefForMassExp(term, tableName, str(limit), dictName)
                    tresults.append(formatDefinitions(dresults, th, dh, fb, bb))
                results = '<br><br>'.join([i for i in tresults if i != ''])
                if results != "":
                    if note[targetField] == '' or note[targetField] == '<br>':
                        note[targetField] = results
                    else:
                        note[targetField] += '<br><br>' + results
        return note

    mw.addDefinitionsToCardExporterNote = addDefinitionsToCardExporterNote

    def exportDefinitions(og: str, dest: str, addType: str, dictNs: list[str], howMany: int, notes: typing.Sequence[int], generateWidget: QWidget, rawNames) -> None:
        config = mw.addonManager.getConfig(__name__)
        config["massGenerationPreferences"] = {
            "dict1" : rawNames[0],
            "dict2" : rawNames[1],
            "dict3" : rawNames[2],
            "origin" : og,
            "destination" : dest,
            "addType" : addType,
            "limit" : howMany
        }
        mw.addonManager.writeConfig(__name__, config)
        mw.checkpoint('Definition Export')
        if not miAsk('Are you sure you want to export definitions for the "'+ og + '" field into the "' + dest +'" field?'):
            return
        progWid, bar = getProgressWidgetDefs()
        progWid.closeEvent = closeBar
        bar.setMinimum(0)
        bar.setMaximum(len(notes))
        val = 0;
        fb = config['frontBracket']
        bb = config['backBracket']
        lang = config['ForvoLanguage']
        mw.MigakuExportingDefinitions = True
        database = dictdb.get()

        for nid in notes:
            if not mw.MigakuExportingDefinitions:
                break
            note = mw.col.getNote(nid)
            fields = mw.col.models.fieldNames(note.model())
            if og in fields and dest in fields:
                term = re.sub(r'<[^>]+>', '', note[og])
                term = re.sub(r'\[[^\]]+?\]', '', term)
                if term == '':
                    continue
                tresults = []
                dCount = 0
                for dictN in dictNs:
                    if dictN == 'Google Images':
                        tresults.append(google_imager.export_images(term, howMany))
                    elif dictN == 'Forvo':
                        tresults.append(exportForvoAudio( term, howMany, lang))
                    elif dictN != 'None':
                        dresults, dh, th = database.getDefForMassExp(term, dictN, str(howMany), rawNames[dCount])
                        tresults.append(formatDefinitions(dresults, th, dh, fb, bb))
                    dCount+= 1
                results = '<br><br>'.join([i for i in tresults if i != ''])
                if addType == 'If Empty':
                    if note[dest] == '':
                        note[dest] = results
                elif addType == 'Add':
                    if note[dest] == '':
                        note[dest] = results
                    else:
                        note[dest] += '<br><br>' + results
                else:
                    note[dest] = results
                note.flush()
            val+=1;
            bar.setValue(val)
            mw.app.processEvents()
        mw.progress.finish()
        mw.reset()
        generateWidget.hide()
        generateWidget.deleteLater()

    def dictOnStart() -> None:
        if mw.addonManager.getConfig(__name__)['dictOnStart']:
            mw.dictionaryInit()

    def setupMenu(browser: browser_.Browser):
        a = QAction("Export Definitions", browser)
        a.triggered.connect(lambda: exportDefinitionsWidget(browser))
        browser.form.menuEdit.addSeparator()
        browser.form.menuEdit.addAction(a)

    def closeDictionary() -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.saveSizeAndPos()
            dictionary.hide()
            mw.openMiDict.setText("Open Dictionary (Ctrl+W)")


    addHook("unloadProfile", closeDictionary)
    AnkiWebView.searchTerm = searchTerm
    AnkiWebView.searchCol = searchCol
    addHook("EditorWebView.contextMenuEvent", addToContextMenu)
    addHook("AnkiWebView.contextMenuEvent", addToContextMenu)
    addHook("profileLoaded", dictOnStart)
    addHook("browser.setupMenus", setupMenu)

    def bridgeReroute(self, cmd: str) -> None:
        if cmd == "bodyClick":
            if dictionary := migaku_dictionary.get_visible_dictionary():
                if self.note:
                    widget = type(self.widget.parentWidget()).__name__

                    if widget == 'QWidget':
                        widget = 'Browser'

                    target = getTarget(widget)
                    dictionary.dict.setCurrentEditor(self, target)
            if hasattr(mw, "migakuEditorLoaded"):
                    ogReroute(self, cmd)
        else:
            if cmd.startswith("focus"):
                if dictionary := migaku_dictionary.get_visible_dictionary():
                    if self.note:
                        widget = type(self.widget.parentWidget()).__name__

                        if widget == 'QWidget':
                            widget = 'Browser'

                        target = getTarget(widget)
                        dictionary.dict.setCurrentEditor(self, target)
            ogReroute(self, cmd)

    ogReroute = editor_.Editor.onBridgeCmd
    editor_.Editor.onBridgeCmd = bridgeReroute

    def setBrowserEditor(self: browser_.Browser) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            if self.editor.note:
                dictionary.dict.setCurrentEditor(self.editor, "Browser")
            else:
                dictionary.dict.closeEditor()

    browser_.Browser.on_all_or_selected_rows_changed = wrap(
        browser_.Browser.on_all_or_selected_rows_changed,
        setBrowserEditor,
    )

    def addEditActivated(self, event: bool = False) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.setCurrentEditor(self.editor, getTarget(type(self).__name__))

    bodyClick = '''document.addEventListener("click", function (ev) {
            pycmd("bodyClick")
        }, false);'''

    def addBodyClick(self) -> None:
        self.web.eval(bodyClick)

    AddCards.addCards = wrap(AddCards.addCards, addEditActivated)
    AddCards.onHistory = wrap(AddCards.onHistory, addEditActivated)


    def addHotkeys(self) -> None:
        self.parentWindow.hotkeyS = QShortcut(QKeySequence("Ctrl+S"), self.parentWindow)
        self.parentWindow.hotkeyS.activated.connect(lambda: searchTerm(self.web))
        self.parentWindow.hotkeyS = QShortcut(QKeySequence("Ctrl+Shift+B"), self.parentWindow)
        self.parentWindow.hotkeyS.activated.connect(lambda: searchCol(self.web))
        self.parentWindow.hotkeyW = QShortcut(QKeySequence("Ctrl+W"), self.parentWindow)
        self.parentWindow.hotkeyW.activated.connect(dictionaryInit)


    def addHotkeysToPreview(self) -> None:
        self._web.hotkeyS = QShortcut(QKeySequence("Ctrl+S"), self._web)
        self._web.hotkeyS.activated.connect(lambda: searchTerm(self._web))
        self._web.hotkeyS = QShortcut(QKeySequence("Ctrl+Shift+B"), self._web)
        self._web.hotkeyS.activated.connect(lambda: searchCol(self._web))
        self._web.hotkeyW = QShortcut(QKeySequence("Ctrl+W"), self._web)
        self._web.hotkeyW.activated.connect(dictionaryInit)

    Previewer.open = wrap(Previewer.open, addHotkeysToPreview)


    def addEditorFunctionality(self: editor_.Editor) -> None:
        self.web.parentEditor = self
        addBodyClick(self)
        addHotkeys(self)

    def gt(obj: typing.Any) -> str:
        return type(obj).__name__

    def getTarget(name: str) -> typing.Optional[str]:
        if name == 'AddCards':
            return 'Add'
        elif name == "EditCurrent" or name == "MigakuEditCurrent":
            return 'Edit'
        elif name == 'Browser':
            return name

        return None

    def announceParent(self, event: bool = False) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            parent = self.parentWidget().parentWidget().parentWidget()
            pName = gt(parent)

            if gt(parent) not in ['AddCards', 'EditCurrent']:
                parent =  aqt.DialogManager._dialogs["Browser"][1]
                pName = 'Browser'

                if not parent:
                    return

            dictionary.dict.setCurrentEditor(parent.editor, target=getTarget(pName) or "")

    TagEdit.focusInEvent = wrap(TagEdit.focusInEvent, announceParent)
    editor_.Editor.setupWeb = wrap(editor_.Editor.setupWeb, addEditorFunctionality)
    AddCards.mousePressEvent = addEditActivated
    EditCurrent.mousePressEvent = addEditActivated

    # TODO: @ColinKennedy - replace with funtools.partial
    def miLinks(self, cmd: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.setReviewer(self)

        ogLinks(self, cmd)

    ogLinks = Reviewer._linkHandler
    Reviewer._linkHandler = miLinks  # type: ignore
    Reviewer.show = wrap(Reviewer.show, addBodyClick)  # type: ignore

gui_hooks.main_window_did_init.append(window_loaded)
