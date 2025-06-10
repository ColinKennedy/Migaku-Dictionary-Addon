# -*- coding: utf-8 -*-

import codecs
import functools
import json
import os
import platform
import re
import subprocess
import sys
import time
import typing
import unicodedata
import urllib.parse

import aqt.utils
import requests
from anki import hooks
from anki import notes as notes_
from anki import utils
from aqt import editcurrent
from aqt import editor as editor_
from aqt import gui_hooks, qt
from aqt import reviewer as reviewer_
from aqt import tagedit
from aqt.addcards import AddCards
from aqt.browser import browser as browser_
from aqt.browser import previewer as previewer_
from PyQt6.QtCore import Qt
import aqt

from . import (
    addonSettings,
    dictdb,
    global_state,
    google_imager,
    googleimages,
    keypress_tracker,
    midict,
    migaku_configuration,
    migaku_dictionary,
    migaku_exporter,
    migaku_forvo,
    migaku_search,
    migaku_settings,
    migaku_widget_global,
    miutils,
    threader,
    typer,
)

_IS_EXPORTING_DEFINITIONS = False
_MENU = None
T = typing.TypeVar("T")


class _ExporterBaseWidget(qt.QWidget):
    def closeEvent(self, event: typing.Optional[qt.QCloseEvent]) -> None:
        _IS_EXPORTING_DEFINITIONS = False

        if event:
            event.accept()


class _ProgressWidget(_ExporterBaseWidget):
    def __init__(self, parent: typing.Optional[qt.QWidget] = None) -> None:
        super().__init__(parent=parent)

        main_layout = qt.QHBoxLayout()
        self.setLayout(main_layout)

        self._bar = qt.QProgressBar()
        self._label = qt.QLabel()

        main_layout.addWidget(self._bar)
        main_layout.addWidget(self._label)

        if utils.is_mac:
            self._bar.setFixedSize(380, 50)
        else:
            self._bar.setFixedSize(390, 50)

        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_maximum(self, value: int) -> None:
        self._bar.setMaximum(value)

    def set_minimum(self, value: int) -> None:
        self._bar.setMinimum(value)

    def set_value(self, value: int) -> None:
        self._bar.setValue(value)


def _get_configuration() -> typer.Configuration:
    return typing.cast(typer.Configuration, aqt.mw.addonManager.getConfig(__name__))


def _set_default_configuration() -> None:
    _CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

    with open(os.path.join(_CURRENT_DIRECTORY, "config.json"), "r") as handler:
        data = json.load(handler)

    # addonManager.writeConfig
    print("RUNNING WRITE CONFI")
    aqt.mw.addonManager.writeConfig(__name__, data)

    #     {
    #         autoAddCards: bool
    #         autoAddDefinitions: bool
    #         autoDefinitionSettings: typing.Optional[list[DefinitionSetting]]
    #         backBracket: str
    #         condensedAudioDirectory: typing.Optional[str]
    #         currentDeck: typing.Optional[str]
    #         currentGroup: GroupName
    #         currentTemplate: typing.Optional[str]
    #         day: bool
    #         deinflect: bool
    #         dictAlwaysOnTop: bool
    #         dictOnStart: bool
    #         dictSearch: int
    #         dictSizePos: typing.Union[tuple[int, int, int, int], typing.Literal[False]]
    #         disableCondensed: bool
    #         displayAgain: bool
    #         exporterLastTags: str
    #         exporterSizePos: typing.Union[tuple[int, int, int, int], typing.Literal[False]]
    #         failedFFMPEGInstallation: bool
    #         fontSizes: tuple[int, int]
    #         frontBracket: str
    #         globalHotkeys: bool
    #         googleSearchRegion: str
    #         highlightSentences: bool
    #         highlightTarget: bool
    #         jReadingCards: bool
    #         jReadingEdit: bool
    #         massGenerationPreferences: _GenerationPreferences
    #         maxHeight: int
    #         maxSearch: int
    #         maxWidth: int
    #         mp3Convert: bool
    #         onetab: bool
    #         openOnGlobal: bool
    #         safeSearch: bool
    #         searchMode: SearchMode
    #         showTarget: bool
    #         tooltips: bool
    #         unknownsToSearch: int
    #
    #         DictionaryGroups: dict[str, DictionaryGroup]
    #         ExportTemplates: dict[str, ExportTemplate]
    #         GoogleImageFields: list[str]
    #         ForvoFields: list[str]
    #         ForvoAddType: AddType
    #         ForvoLanguage: str  # typing.Literal["Japanese"]  # TODO: @ColinKennedy add more languages later
    #         GoogleImageAddType: AddType
    #     },
    # )


def _verify(item: typing.Optional[T]) -> T:
    if item is not None:
        return item

    raise RuntimeError("Expected item to exist but got none.")


def window_loaded() -> None:
    print("WINDOWLOADED IS RUNNING", aqt.mw)
    migaku_configuration.initialize_by_namespace()
    _IS_EXPORTING_DEFINITIONS = False
    migaku_settings.clear()
    dictdb.initialize(dictdb.DictDB())
    progressBar = False
    addon_path = os.path.dirname(__file__)
    currentNote = False
    currentField = False
    currentKey = False
    wrapperDict = False
    tmpdir = os.path.join(addon_path, "temp")
    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = False

    def removeTempFiles() -> None:
        filelist = [f for f in os.listdir(tmpdir)]
        for f in filelist:
            path = os.path.join(tmpdir, f)
            try:
                os.remove(path)
            except:
                innerDirFiles = [df for df in os.listdir(path)]
                for df in innerDirFiles:
                    innerPath = os.path.join(path, df)
                    os.remove(innerPath)
                os.rmdir(path)

    removeTempFiles()

    # TODO: @ColinKennedy What is this code doing? Remove?
    # js_file = QFile(':/qtwebchannel/qwebchannel.js')
    # assert js_file.open(QIODevice.OpenModeFlag.ReadOnly)
    # js = js_file.readAll().data().decode('utf-8')

    def exportSentence(sentence: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.exportSentence(sentence)
            showCardExporterWindow()

    def exportImage(img: typing.Sequence[str]) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            if img[1].startswith("[sound:"):
                # TODO: @ColinKennedy - check these type-hints later
                img = typing.cast(tuple[str, str, str], img)
                dictionary.dict.exportAudio(img)
            else:
                img = typing.cast(tuple[str, str], img)
                dictionary.dict.exportImage(img)
            showCardExporterWindow()

    def _initialize_dictionary_if_needed() -> midict.DictInterface:
        if not migaku_dictionary.get_visible_dictionary():
            midict.dictionaryInit()

        return migaku_dictionary.get()

    def extensionBulkTextExport(cards: typing.Sequence[typer.Card]) -> None:
        dictionary = _initialize_dictionary_if_needed()
        dictionary.dict.bulkTextExport(cards)

    def extensionBulkMediaExport(card: typer.Card) -> None:
        dictionary = _initialize_dictionary_if_needed()
        dictionary.dict.bulkMediaExport(card)

    def cancelBulkMediaExport() -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.cancelBulkMediaExport()

    def extensionCardExport(card: typer.Card) -> None:
        primary = card["primary"]
        secondary = card["secondary"]
        image = card["image"]
        audio = card["audio"]
        configuration = migaku_configuration.get()
        unknownsToSearch = configuration.get("unknownsToSearch", 3)
        autoExportCards = configuration.get("autoAddCards", False)
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
            dictionary.dict.exportWord("")

        if audio:
            dictionary.dict.exportAudio(
                (
                    os.path.join(aqt.mw.col.media.dir(), audio),
                    "[sound:" + audio + "]",
                    audio,
                )
            )

        if image:
            dictionary.dict.exportImage(
                (os.path.join(aqt.mw.col.media.dir(), image), image)
            )

        dictionary.dict.exportSentence(primary, secondary)
        _verify(dictionary.dict.addWindow).focusWindow()
        dictionary.dict.attemptAutoAdd(False)
        showCardExporterWindow()

    def showCardExporterWindow() -> None:
        adder = _verify(migaku_dictionary.get().dict.addWindow)
        cardWindow = adder.scrollArea

        if not utils.is_win:
            cardWindow.setWindowState(
                cardWindow.windowState() & ~Qt.WindowState.WindowMinimized
                | Qt.WindowState.WindowActive
            )
            cardWindow.raise_()
        else:
            cardWindow.setWindowFlags(
                cardWindow.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
            )
            cardWindow.show()

            if not adder.alwaysOnTop:
                cardWindow.setWindowFlags(
                    cardWindow.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint
                )
                cardWindow.show()

    def trySearch(term: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.initSearch(term)
            midict.showAfterGlobalSearch()
        elif (
            migaku_configuration.get()["openOnGlobal"]
            and not migaku_dictionary.get_visible_dictionary()
        ):
            midict.dictionaryInit([term])

    def attemptAddCard(*_: typing.Any, **__: typing.Any) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            window = dictionary.dict.addWindow

            if window and window.scrollArea.isVisible():
                time.sleep(0.3)
                window.addCard()

    def openDictionarySettings() -> None:
        if not migaku_settings.get_unsafe():
            migaku_settings.initialize(
                addonSettings.SettingsGui(aqt.mw, addon_path, openDictionarySettings)
            )

        settings = migaku_settings.get()
        settings.show()

        if settings.windowState() == Qt.WindowState.WindowMinimized:
            settings.setWindowState(Qt.WindowState.WindowNoState)

        settings.setFocus()
        settings.activateWindow()

    def initialize_menu() -> None:
        print(f"DEBUGPRINT[5]: main.py:270: mw={aqt.mw}")
        menu = qt.QMenu("Migaku", aqt.mw)

        settings_action = qt.QAction("Dictionary Settings", aqt.mw)
        settings_action.triggered.connect(openDictionarySettings)
        menu.addAction(settings_action)

        shortcut = "(Ctrl+W)"

        if utils.is_mac:
            shortcut = "⌘W"

        open_dictionary_action = qt.QAction(f"Open Dictionary {shortcut}", aqt.mw)
        open_dictionary_action.triggered.connect(midict.dictionaryInit)
        menu.addAction(open_dictionary_action)

        aqt.mw.form.menubar.insertMenu(aqt.mw.form.menuHelp.menuAction(), menu)

    initialize_menu()

    migaku_dictionary.clear()

    def searchTermList(terms: list[str]) -> None:
        configuration = migaku_configuration.get()
        limit = configuration.get("unknownsToSearch", 3)
        terms = terms[:limit]

        if not (dictionary := migaku_dictionary.get_visible_dictionary()):
            midict.dictionaryInit(terms)

            return

        for term in terms:
            dictionary.initSearch(term)

        midict.showAfterGlobalSearch()

    def extensionFileNotFound() -> None:
        miutils.miInfo(
            'The media files were not found in your "Download Directory", please make sure you have selected the correct directory.'
        )

    def initGlobalHotkeys() -> None:
        thread = threader.initialize(midict.ClipThread(aqt.mw, addon_path))
        thread.sentence.connect(exportSentence)
        thread.search.connect(trySearch)
        thread.colSearch.connect(migaku_search.performColSearch)
        thread.image.connect(exportImage)
        thread.bulkTextExport.connect(extensionBulkTextExport)
        thread.add.connect(attemptAddCard)
        thread.test.connect(keypress_tracker.capture_key)
        thread.release.connect(keypress_tracker.release_key)
        thread.pageRefreshDuringBulkMediaImport.connect(cancelBulkMediaExport)
        thread.bulkMediaExport.connect(extensionBulkMediaExport)
        thread.extensionCardExport.connect(extensionCardExport)
        thread.searchFromExtension.connect(searchTermList)
        thread.extensionFileNotFound.connect(extensionFileNotFound)
        thread.run()

    configuration = _get_configuration()

    if not configuration:
        _set_default_configuration()

    if _get_configuration()["globalHotkeys"]:
        initGlobalHotkeys()

    hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+W"), aqt.mw)
    hotkey.activated.connect(midict.dictionaryInit)

    hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+S"), aqt.mw)
    hotkey.activated.connect(lambda: migaku_search.searchTerm(aqt.mw.web))
    hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+Shift+B"), aqt.mw)
    hotkey.activated.connect(lambda: migaku_search.searchCol(aqt.mw.web))

    def addToContextMenu(self: editor_.EditorWebView, menu: qt.QMenu) -> None:
        def _add_action(menu: qt.QMenu, text: str) -> qt.QAction:
            if action := menu.addAction(text):
                return action

            raise RuntimeError(f'Action "{text}" could not be added.')

        a = _add_action(menu, "Search (Ctrl+S)")
        a.triggered.connect(functools.partial(migaku_search.searchTerm, self))
        b = _add_action(menu, "Search Collection (Ctrl/⌘+Shift+B)")
        b.triggered.connect(functools.partial(migaku_search.searchCol, self))

    # TODO: @ColinKennedy dedent
    def exportDefinitionsWidget(browser: browser_.Browser) -> None:
        import anki.find

        notes = list(browser.selectedNotes())

        if notes:
            fields = anki.find.fieldNamesForNotes(aqt.mw.col, notes)
            generateWidget = qt.QDialog(None, Qt.WindowType.Window)
            layout = qt.QHBoxLayout()
            origin = qt.QComboBox()
            origin.addItems(fields)
            addType = qt.QComboBox()
            addType.addItems(["Add", "Overwrite", "If Empty"])
            dicts = qt.QComboBox()
            dict2 = qt.QComboBox()
            dict3 = qt.QComboBox()
            dictDict = {}
            tempdicts = []
            database = dictdb.get()

            for d in database.getAllDicts():
                dictName = database.cleanDictName(d)
                dictDict[dictName] = d
                tempdicts.append(dictName)
            tempdicts.append("Google Images")
            tempdicts.append("Forvo")
            dicts.addItems(sorted(tempdicts))
            dict2.addItem("None")
            dict2.addItems(sorted(tempdicts))
            dict3.addItem("None")
            dict3.addItems(sorted(tempdicts))
            dictDict["Google Images"] = "Google Images"
            dictDict["Forvo"] = "Forvo"
            dictDict["None"] = "None"
            ex = qt.QPushButton("Execute")
            ex.clicked.connect(
                lambda: exportDefinitions(
                    origin.currentText(),
                    destination.currentText(),
                    addType.currentText(),
                    [
                        dictDict[dicts.currentText()],
                        dictDict[dict2.currentText()],
                        dictDict[dict3.currentText()],
                    ],
                    howMany.value(),
                    notes,
                    generateWidget,
                    [dicts.currentText(), dict2.currentText(), dict3.currentText()],
                )
            )
            destination = qt.QComboBox()
            destination.addItems(fields)
            howMany = qt.QSpinBox()
            howMany.setValue(1)
            howMany.setMinimum(1)
            howMany.setMaximum(20)
            oLayout = qt.QVBoxLayout()
            oh1 = qt.QHBoxLayout()
            oh2 = qt.QHBoxLayout()
            oh1.addWidget(qt.QLabel("Input Field:"))
            oh1.addWidget(origin)
            oh2.addWidget(qt.QLabel("Output Field:"))
            oh2.addWidget(destination)
            oLayout.addStretch()
            oLayout.addLayout(oh1)
            oLayout.addLayout(oh2)
            oLayout.addStretch()
            oLayout.setContentsMargins(6, 0, 6, 0)
            layout.addLayout(oLayout)
            dlay = qt.QHBoxLayout()
            dlay.addWidget(qt.QLabel("Dictionaries:"))
            dictLay = qt.QVBoxLayout()
            dictLay.addWidget(dicts)
            dictLay.addWidget(dict2)
            dictLay.addWidget(dict3)
            dlay.addLayout(dictLay)
            dlay.setContentsMargins(6, 0, 6, 0)
            layout.addLayout(dlay)
            bLayout = qt.QVBoxLayout()
            bh1 = qt.QHBoxLayout()
            bh2 = qt.QHBoxLayout()
            bh1.addWidget(qt.QLabel("Output Mode:"))
            bh1.addWidget(addType)
            bh2.addWidget(qt.QLabel("Max Per Dict:"))
            bh2.addWidget(howMany)
            bLayout.addStretch()
            bLayout.addLayout(bh1)
            bLayout.addLayout(bh2)
            bLayout.addStretch()
            bLayout.setContentsMargins(6, 0, 6, 0)
            layout.addLayout(bLayout)
            layout.addWidget(ex)
            layout.setContentsMargins(10, 6, 10, 6)
            generateWidget.setWindowFlags(
                generateWidget.windowFlags()
                | Qt.WindowType.MSWindowsFixedSizeDialogHint
            )
            generateWidget.setWindowTitle("Migaku Dictionary: Export Definitions")
            generateWidget.setWindowIcon(
                qt.QIcon(os.path.join(addon_path, "icons", "migaku.png"))
            )
            generateWidget.setLayout(layout)
            config = _get_configuration()
            savedPreferences = config.get("massGenerationPreferences")
            if savedPreferences:
                if dicts.findText(savedPreferences["dict1"]) != -1:
                    dicts.setCurrentText(savedPreferences["dict1"])
                if dict2.findText(savedPreferences["dict2"]) != -1:
                    dict2.setCurrentText(savedPreferences["dict2"])
                if dict3.findText(savedPreferences["dict3"]) != -1:
                    dict3.setCurrentText(savedPreferences["dict3"])
                if origin.findText(savedPreferences["origin"]) != -1:
                    origin.setCurrentText(savedPreferences["origin"])
                if destination.findText(savedPreferences["destination"]) != -1:
                    destination.setCurrentText(savedPreferences["destination"])
                addType.setCurrentText(savedPreferences["addType"])
                howMany.setValue(savedPreferences["limit"])
            generateWidget.exec()
        else:
            miutils.miInfo(
                "Please select some cards before attempting to export definitions.",
                level="not",
            )

    def getProgressWidgetDefs(
        parent: typing.Optional[qt.QWidget] = None,
    ) -> _ProgressWidget:
        progressWidget = _ProgressWidget(parent)
        progressWidget.setFixedSize(400, 70)
        progressWidget.setWindowIcon(
            qt.QIcon(os.path.join(addon_path, "icons", "migaku.png"))
        )
        progressWidget.setWindowTitle("Generating Definitions...")
        progressWidget.setWindowModality(Qt.WindowModality.ApplicationModal)

        return progressWidget

    def exportDefinitions(
        og: str,
        dest: str,
        addType: str,
        dictNs: list[str],
        howMany: int,
        notes: typing.Sequence[notes_.NoteId],
        generateWidget: qt.QWidget,
        rawNames: list[str],
    ) -> None:
        config = _get_configuration()
        config["massGenerationPreferences"] = {
            "dict1": rawNames[0],
            "dict2": rawNames[1],
            "dict3": rawNames[2],
            "origin": og,
            "destination": dest,
            "addType": addType,
            "limit": howMany,
        }
        aqt.mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], config),
        )
        aqt.mw.checkpoint("Definition Export")

        if not miutils.miAsk(
            'Are you sure you want to export definitions for the "'
            + og
            + '" field into the "'
            + dest
            + '" field?'
        ):
            return

        progress = getProgressWidgetDefs()
        progress.set_minimum(0)
        progress.set_maximum(len(notes))

        progress.show()

        val = 0
        fb = config["frontBracket"]
        bb = config["backBracket"]
        lang = config["ForvoLanguage"]
        _IS_EXPORTING_DEFINITIONS = True
        database = dictdb.get()

        for nid in notes:
            if not _IS_EXPORTING_DEFINITIONS:
                break

            note = aqt.mw.col.get_note(nid)
            note_type = note.note_type()

            if not note_type:
                raise RuntimeError(f'Note "{note}" has no note type.')

            fields = aqt.mw.col.models.field_names(note_type)

            if og in fields and dest in fields:
                term = re.sub(r"<[^>]+>", "", note[og])
                term = re.sub(r"\[[^\]]+?\]", "", term)

                if not term:
                    continue

                tresults: list[str] = []
                dCount = 0
                for dictN in dictNs:
                    if dictN == "Google Images":
                        tresults.append(google_imager.export_images(term, howMany))
                    elif dictN == "Forvo":
                        tresults.append(migaku_forvo.export_audio(term, howMany, lang))
                    elif dictN != "None":
                        dresults, dh, termHeader = database.getDefForMassExp(
                            term, dictN, str(howMany), rawNames[dCount]
                        )
                        tresults.append(
                            migaku_exporter.formatDefinitions(
                                dresults, termHeader, dh, fb, bb
                            )
                        )

                    dCount += 1

                results = "<br><br>".join([i for i in tresults if i != ""])

                if addType == "If Empty":
                    if note[dest] == "":
                        note[dest] = results
                elif addType == "Add":
                    if note[dest] == "":
                        note[dest] = results
                    else:
                        note[dest] += "<br><br>" + results
                else:
                    note[dest] = results

                note.flush()

            val += 1
            progress.set_value(val)
            aqt.mw.app.processEvents()

        aqt.mw.progress.finish()
        aqt.mw.reset()
        generateWidget.hide()
        generateWidget.deleteLater()

    def dictOnStart() -> None:
        configuration = _get_configuration()

        if configuration["dictOnStart"]:
            midict.dictionaryInit()

    def setupMenu(browser: browser_.Browser) -> None:
        a = qt.QAction("Export Definitions", browser)
        a.triggered.connect(lambda: exportDefinitionsWidget(browser))
        browser.form.menuEdit.addSeparator()
        browser.form.menuEdit.addAction(a)

    def closeDictionary() -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.saveSizeAndPos()
            dictionary.hide()

    hooks.addHook("unloadProfile", closeDictionary)
    hooks.addHook("EditorWebView.contextMenuEvent", addToContextMenu)
    hooks.addHook("AnkiWebView.contextMenuEvent", addToContextMenu)
    hooks.addHook("profileLoaded", dictOnStart)
    hooks.addHook("browser.setupMenus", setupMenu)

    def bridgeReroute(self: editor_.Editor, cmd: str) -> None:
        if cmd == "bodyClick":
            dictionary = migaku_dictionary.get_visible_dictionary()

            if not dictionary:
                return

            if not self.note:
                return

            widget = type(self.widget.parentWidget()).__name__

            if widget == "QWidget":
                widget = "Browser"

            target = migaku_search.getTarget(widget)

            if not target:
                raise RuntimeError(f"Widget has no target.")

            dictionary.dict.setCurrentEditor(self, target)

            if hasattr(aqt.mw, "migakuEditorLoaded"):
                ogReroute(self, cmd)

            return

        if cmd.startswith("focus"):
            if dictionary := migaku_dictionary.get_visible_dictionary():
                if self.note:
                    widget = type(self.widget.parentWidget()).__name__

                    if widget == "QWidget":
                        widget = "Browser"

                    target = migaku_search.getTarget(widget)

                    if not target:
                        raise RuntimeError(
                            f'No target was found for "{widget}" widget. '
                            "Cannot set the current editor to it.",
                        )

                    dictionary.dict.setCurrentEditor(self, target)
        ogReroute(self, cmd)

    ogReroute = editor_.Editor.onBridgeCmd
    editor_.Editor.onBridgeCmd = bridgeReroute  # type: ignore[method-assign]

    def setBrowserEditor(self: browser_.Browser) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            if self.editor and self.editor.note:
                dictionary.dict.setCurrentEditor(self.editor, "Browser")
            else:
                dictionary.dict.closeEditor()

    browser_.Browser.on_all_or_selected_rows_changed = hooks.wrap(  # type: ignore[method-assign]
        browser_.Browser.on_all_or_selected_rows_changed,
        setBrowserEditor,
    )

    def addEditActivated(
        self: typing.Union[AddCards, editcurrent.EditCurrent],
        event: typing.Optional[qt.QMouseEvent] = None,
    ) -> None:
        dictionary = migaku_dictionary.get_visible_dictionary()

        if not dictionary:
            raise RuntimeError("No visible dictionary found. Cannot edit activated.")

        widget = type(self).__name__
        target = migaku_search.getTarget(widget)

        if not target:
            raise RuntimeError(
                f'No target found for "{widget}". '
                "Cannot set the current dictionary editor to it.",
            )

        dictionary.dict.setCurrentEditor(self.editor, target)

    bodyClick = """document.addEventListener("click", function (ev) {
            pycmd("bodyClick")
        }, false);"""

    def addBodyClick(self: editor_.Editor) -> None:
        self.web.eval(bodyClick)

    AddCards.addCards = hooks.wrap(AddCards.addCards, addEditActivated)
    AddCards.onHistory = hooks.wrap(AddCards.onHistory, addEditActivated)  # type: ignore[method-assign]

    def addHotkeys(self: editor_.Editor) -> None:
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+S"), self.parentWindow)
        hotkey.activated.connect(lambda: migaku_search.searchTerm(self.web))
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+Shift+B"), self.parentWindow)
        hotkey.activated.connect(lambda: migaku_search.searchCol(self.web))
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+W"), self.parentWindow)
        hotkey.activated.connect(midict.dictionaryInit)

    def addHotkeysToPreview(self: previewer_.Previewer) -> None:
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+S"), self._web)
        hotkey.activated.connect(lambda: migaku_search.searchTerm(_verify(self._web)))
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+Shift+B"), self._web)
        hotkey.activated.connect(lambda: migaku_search.searchCol(_verify(self._web)))
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+W"), self._web)
        hotkey.activated.connect(midict.dictionaryInit)

    previewer_.Previewer.open = hooks.wrap(  # type: ignore[method-assign]
        previewer_.Previewer.open,
        addHotkeysToPreview,
    )

    def _get_parent_widget(widget: qt.QWidget) -> qt.QWidget:
        return _verify(widget.parentWidget())

    def addEditorFunctionality(self: editor_.Editor) -> None:
        migaku_widget_global.PARENT_EDITOR = self
        addBodyClick(self)
        addHotkeys(self)

    def gt(obj: typing.Any) -> str:
        return type(obj).__name__

    def announceParent(
        self: tagedit.TagEdit, event: typing.Optional[qt.QFocusEvent] = None
    ) -> None:
        dictionary = migaku_dictionary.get_visible_dictionary()

        if not dictionary:
            return

        get = _get_parent_widget
        parent = typing.cast(browser_.Browser, get(get(self)))
        pName = gt(parent)

        if gt(parent) not in ["AddCards", "EditCurrent"]:
            parent = typing.cast(
                browser_.Browser,
                aqt.DialogManager._dialogs["Browser"][1],
            )

            if not parent:
                return

            pName = "Browser"

        if not parent.editor:
            return

        dictionary.dict.setCurrentEditor(
            parent.editor, target=migaku_search.getTarget(pName) or ""
        )

    tagedit.TagEdit.focusInEvent = hooks.wrap(tagedit.TagEdit.focusInEvent, announceParent)  # type: ignore[method-assign]
    editor_.Editor.setupWeb = hooks.wrap(editor_.Editor.setupWeb, addEditorFunctionality)  # type: ignore[method-assign]
    AddCards.mousePressEvent = addEditActivated  # type: ignore[method-assign,assignment]
    editcurrent.EditCurrent.mousePressEvent = addEditActivated  # type: ignore[method-assign,assignment]

    # TODO: @ColinKennedy - replace with functools.partial
    def miLinks(self: reviewer_.Reviewer, cmd: str) -> None:
        if dictionary := migaku_dictionary.get_visible_dictionary():
            dictionary.dict.setReviewer(self)

        ogLinks(self, cmd)

    ogLinks = reviewer_.Reviewer._linkHandler
    reviewer_.Reviewer._linkHandler = miLinks  # type: ignore
    reviewer_.Reviewer.show = hooks.wrap(reviewer_.Reviewer.show, addBodyClick)  # type: ignore


def initialize() -> None:
    gui_hooks.main_window_did_init.append(window_loaded)
