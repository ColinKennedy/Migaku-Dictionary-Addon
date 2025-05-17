# -*- coding: utf-8 -*-
#

from __future__ import annotations

import codecs
import datetime
import functools
import json
import logging
import math
import ntpath
import os
import re
import shutil
import sys
import time
import typing
from urllib import request as request_

import aqt
import requests
from anki import utils
from anki.lang import _
from aqt import editor as editor_
from aqt import gui_hooks, main, qt
from aqt import reviewer as reviewer_
from aqt import utils as aqt_utils
from aqt import webview
from pynput import keyboard
from PyQt6 import QtSvgWidgets

from . import (
    addonSettings,
    cardExporter,
)
from . import dictdb as dictdb_
from . import (
    forvodl,
    googleimages,
    history,
    migaku_configuration,
    migaku_search,
    migaku_settings,
    miJapaneseHandler,
    miutils,
    typer,
    welcomer,
)

# TODO: @ColinKennedy - Clean these imports later


if typing.TYPE_CHECKING:
    import Quartz  # type: ignore[import-not-found]


_CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
_LOGGER = logging.getLogger(__name__)
_CGEventRef = (
    typing.Any
)  # TODO: @ColinKennedy - not sure how to refer to this in ``Quartz``.
_StringSequence = typing.TypeVar("_StringSequence", bound=list[str])
T = typing.TypeVar("T")


class _AddTypeGroup(typing.TypedDict):
    name: str
    type: typer.AddType


class MIDict(webview.AnkiWebView):

    def __init__(
        self,
        dictInt: "DictInterface",
        db: dictdb_.DictDB,
        path: str,
        day: bool,
        terms: typing.Optional[list[str]] = None,
        parent: typing.Optional[qt.QWidget] = None,
    ) -> None:
        super().__init__(parent=parent)

        _verify(_verify(self.page()).profile()).setHttpUserAgent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
        )

        self.db = db

        self._terms = terms or []
        self._dictInt = dictInt
        self.config = self._dictInt.getConfig()
        self._jSend = self.config["jReadingEdit"]
        self._maxW = self.config["maxWidth"]
        self._maxH = self.config["maxHeight"]
        self._termHeaders = self._formatTermHeaders(
            {
                key: list(value)
                for key, value in (self.db.getTermHeaders() or {}).items()
            }
        )
        self._dupHeaders = self.db.getDupHeaders()
        self._sType: typing.Optional[qt.QComboBox] = None
        self._radioCount = 0
        self._homeDir = path
        self._conjugations = self._loadConjugations()
        self._threadpool = qt.QThreadPool()
        self._customFontsLoaded: list[str] = []

        self.deinflect = True
        self.onBridgeCmd = self._handleDictAction  # NOTE: This name comes from aqt
        self.addWindow: typing.Optional[cardExporter.CardExporter] = None
        self.currentEditor: typing.Optional[editor_.Editor] = None
        self.reviewer: typing.Optional[reviewer_.Reviewer] = None

        gui_hooks.editor_did_init.append(self._on_editor_loaded)

    def _checkEditorClose(self, editor: editor_.Editor) -> None:
        if self.currentEditor == editor:
            self.closeEditor()

    def _on_editor_loaded(self, editor: editor_.Editor) -> None:
        self.currentEditor = editor

    def _resetConfiguration(self, config: typer.Configuration) -> None:
        self.config = config
        self._jSend = self.config["jReadingEdit"]
        self._maxW = self.config["maxWidth"]
        self._maxH = self.config["maxHeight"]

    def _showGoogleForvoMessage(self, message: str) -> None:
        miutils.miInfo(message, level="err")

    def _loadImageResults(self, results: tuple[str, str]) -> None:
        html, idName = results
        self.eval(
            "loadImageForvoHtml('%s', '%s');" % (html.replace('"', '\\"'), idName)
        )

    def _formatTermHeaders(
        self, ths: dict[str, typing.Iterable[str]]
    ) -> typing.Optional[dict[str, tuple[str, str]]]:
        formattedHeaders: dict[str, tuple[str, str]] = {}

        if not ths:
            return None

        for dictname in ths:
            headerString = ""
            sbHeaderString = ""
            for header in ths[dictname]:
                if header == "term":
                    headerString += '◳f<span class="term mainword">◳t</span>◳b'
                    sbHeaderString += '◳f<span class="listTerm">◳t</span>◳b'
                elif header == "altterm":
                    headerString += '◳x<span class="altterm  mainword">◳a</span>◳y'
                    sbHeaderString += '◳x<span class="listAltTerm">◳a</span>◳y'
                elif header == "pronunciation":
                    headerString += '<span class="pronunciation">◳p</span>'
                    sbHeaderString += '<span class="listPronunciation">◳p</span>'
            formattedHeaders[dictname] = (headerString, sbHeaderString)
        return formattedHeaders

    def _loadConjugations(self) -> dict[str, list[typer.Conjugation]]:
        langs = self.db.getCurrentDbLangs()
        conjugations: dict[str, list[typer.Conjugation]] = {}
        for lang in langs:
            filePath = os.path.join(
                self._homeDir, "user_files", "db", "conjugation", "%s.json" % lang
            )
            if not os.path.exists(filePath):
                filePath = os.path.join(
                    self._homeDir,
                    "user_files",
                    "dictionaries",
                    lang,
                    "conjugations.json",
                )
                if not os.path.exists(filePath):
                    continue
            with open(filePath, "r", encoding="utf-8") as conjugationsFile:
                conjugations[lang] = json.loads(conjugationsFile.read())
        return conjugations

    def _cleanTerm(self, term: str) -> str:
        return (
            term.replace("'", "'")
            .replace("%", "")
            .replace("_", "")
            .replace("「", "")
            .replace("」", "")
        )

    def _getFontFamily(
        self, group: typing.Union[typer.DictionaryGroup, typer.DictionaryGroup2]
    ) -> str:
        if not group["font"]:
            return " "
        if group["customFont"]:
            return ' style="font-family:' + re.sub(r"\..*$", "", group["font"]) + ';" '
        else:
            return ' style="font-family:' + group["font"] + ';" '

    def _injectFont(self, font: str) -> None:
        name = re.sub(r"\..*$", "", font)
        self.eval("addCustomFont('%s', '%s');" % (font, name))

    def _getTabMode(self) -> str:
        if self._dictInt.tabB.singleTab:
            return "true"
        return "false"

    def _getHTMLResult(
        self,
        term: str,
        selectedGroup: typer.DictionaryGroup2,
    ) -> tuple[str, str, str]:
        singleTab = self._getTabMode()
        cleaned = self._cleanTerm(term)
        font = self._getFontFamily(selectedGroup)
        dictDefs = self.config["dictSearch"]
        maxDefs = self.config["maxSearch"]
        html = self._prepareResults(
            self.db.searchTerm(
                term,
                selectedGroup,
                self._conjugations,
                typing.cast(typer.SearchTerm, _verify(self._sType).currentText()),
                self.deinflect,
                str(dictDefs),
                maxDefs,
            ),
            cleaned,
            font,
        )
        html = html.replace("\n", "")
        return html, cleaned, singleTab

    def _addResultWrappers(self, results: _StringSequence) -> _StringSequence:
        for idx, result in enumerate(results):
            if "dictionaryTitleBlock" not in result:
                results[idx] = '<div class="definitionBlock">' + result + "</div>"
        return results

    def _escapePunctuation(self, term: str) -> str:
        return re.sub(r"([.*+(\[\]{}\\?)!])", "\\\1", term)

    def _highlightTarget(self, text: str, term: str) -> str:
        if self.config["highlightTarget"]:
            return re.sub(
                "(" + self._escapePunctuation(term) + ")",
                r'<span class="targetTerm">\1</span>',
                text,
            )
        return text

    def _highlightExamples(self, text: str) -> str:
        if self.config["highlightSentences"]:
            return re.sub(
                "(「[^」]+」)", r'<span class="exampleSentence">\1</span>', text
            )
        return text

    def _getSideBar(
        self,
        results: dict[str, list[typer.DictionaryResult]],
        term: str,
        font: str,
        frontBracket: str,
        backBracket: str,
    ) -> str:
        html = "<div" + font + 'class="definitionSideBar"><div class="innerSideBar">'
        dictCount = 0
        entryCount = 0
        for dictName, dictResults in results.items():
            if dictName == "Google Images" or dictName == "Forvo":
                html += (
                    '<div data-index="'
                    + str(dictCount)
                    + '" class="listTitle">'
                    + dictName
                    + '</div><ol class="foundEntriesList"><li data-index="'
                    + str(entryCount)
                    + '">'
                    + self._getPreparedTermHeader(
                        dictName,
                        frontBracket,
                        backBracket,
                        term,
                        term,
                        term,
                        term,
                        True,
                    )
                    + "</li></ol>"
                )
                entryCount += 1
                dictCount += 1
                continue
            html += (
                '<div data-index="'
                + str(dictCount)
                + '" class="listTitle">'
                + dictName
                + '</div><ol class="foundEntriesList">'
            )
            dictCount += 1
            for idx, entry in enumerate(dictResults):
                html += (
                    '<li data-index="'
                    + str(entryCount)
                    + '">'
                    + self._getPreparedTermHeader(
                        dictName,
                        frontBracket,
                        backBracket,
                        term,
                        entry["term"],
                        entry["altterm"],
                        entry["pronunciation"],
                        True,
                    )
                    + "</li>"
                )
                entryCount += 1
            html += "</ol>"
        return (
            html
            + '<br></div><div class="resizeBar" onmousedown="hresize(event)"></div></div>'
        )

    def _getPreparedTermHeader(
        self,
        dictName: str,
        frontBracket: str,
        backBracket: str,
        target: str,
        term: str,
        altterm: str,
        pronunciation: str,
        sb: bool = False,
    ) -> str:
        altFB = frontBracket
        altBB = backBracket
        if pronunciation == term:
            pronunciation = ""
        if altterm == term:
            altterm = ""
        if altterm == "":
            altFB = ""
            altBB = ""
        if not self._termHeaders or (
            dictName == "Google Images" or dictName == "Forvo"
        ):
            if sb:
                header = '◳f<span class="term mainword">◳t</span>◳b◳x<span class="altterm  mainword">◳a</span>◳y<span class="pronunciation">◳p</span>'
            else:
                header = '◳f<span class="listTerm">◳t</span>◳b◳x<span class="listAltTerm">◳a</span>◳y<span class="listPronunciation">◳p</span>'
        else:
            if sb:
                header = self._termHeaders[dictName][1]
            else:
                header = self._termHeaders[dictName][0]

        # TODO: @ColinKennedy - this code is awful
        return (
            header.replace("◳t", self._highlightTarget(term, target))
            .replace("◳a", self._highlightTarget(altterm, target))
            .replace("◳p", self._highlightTarget(pronunciation, target))
            .replace("◳f", frontBracket)
            .replace("◳b", backBracket)
            .replace("◳x", altFB)
            .replace("◳y", altBB)
        )

    def _prepareResults(
        self,
        all_results: tuple[dictdb_.DictSearchResults, set[str]],
        term: str,
        font: str,
    ) -> str:
        frontBracket = self.config["frontBracket"]
        backBracket = self.config["backBracket"]
        results, known_dictionaries = all_results

        if results:
            html = self._getSideBar(results, term, font, frontBracket, backBracket)
            html += '<div class="mainDictDisplay">'
            dictCount = 0
            entryCount = 0
            imgTooltip = ""
            clipTooltip = ""
            sendTooltip = ""
            if self.config["tooltips"]:
                imgTooltip = ' title="Add this definition, or any selected text and this definition\'s header to the card exporter (opens the card exporter if it is not yet opened)." '
                clipTooltip = ' title="Copy this definition, or any selected text to the clipboard." '
                sendTooltip = " title=\"Send this definition, or any selected text and this definition's header to the card exporter to this dictionary's target fields. It will send it to the current target window, be it an Editor window, or the Review window.\" "

            if "Google Images" in known_dictionaries:
                html += self._getGoogleDictionaryResults(
                    term, dictCount, frontBracket, backBracket, entryCount, font
                )
                dictCount += 1
                entryCount += 1

            if "Forvo" in known_dictionaries:
                html += self._getForvoDictionaryResults(
                    term, dictCount, frontBracket, backBracket, entryCount, font
                )
                dictCount += 1
                entryCount += 1

            for dictName, dictResults in results.items():
                duplicateHeader = self._getDuplicateHeaderCB(dictName)
                overwrite = self._getOverwriteChecks(dictCount, dictName)
                select = self._getFieldChecks(dictName)
                html += (
                    '<div data-index="'
                    + str(dictCount)
                    + '" class="dictionaryTitleBlock"><div  '
                    + font
                    + '  class="dictionaryTitle">'
                    + dictName.replace("_", " ")
                    + '</div><div class="dictionarySettings">'
                    + duplicateHeader
                    + overwrite
                    + select
                    + '<div class="dictNav"><div onclick="navigateDict(event, false)" class="prevDict">▲</div><div onclick="navigateDict(event, true)" class="nextDict">▼</div></div></div></div>'
                )
                dictCount += 1
                for idx, entry in enumerate(dictResults):
                    html += (
                        '<div data-index="'
                        + str(entryCount)
                        + '" class="termPronunciation"><span '
                        + font
                        + ' class="tpCont">'
                        + self._getPreparedTermHeader(
                            dictName,
                            frontBracket,
                            backBracket,
                            term,
                            entry["term"],
                            entry["altterm"],
                            entry["pronunciation"],
                        )
                        + ' <span class="starcount">'
                        + entry["starCount"]
                        + '</span></span><div class="defTools"><div onclick="ankiExport(event, \''
                        + dictName
                        + '\')" class="ankiExportButton"><img '
                        + imgTooltip
                        + ' src="icons/anki.png"></div><div onclick="clipText(event)" '
                        + clipTooltip
                        + ' class="clipper">✂</div><div '
                        + sendTooltip
                        + " onclick=\"sendToField(event, '"
                        + dictName
                        + '\')" class="sendToField">➠</div><div class="defNav"><div onclick="navigateDef(event, false)" class="prevDef">▲</div><div onclick="navigateDef(event, true)" class="nextDef">▼</div></div></div></div><div'
                        + font
                        + ' class="definitionBlock">'
                        + self._highlightTarget(
                            self._highlightExamples(entry["definition"]), term
                        )
                        + "</div>"
                    )
                    entryCount += 1

        else:
            html = (
                '<style>.noresults{font-family: Arial;}.vertical-center{height: 400px; width: 60%; margin: 0 auto; display: flex; justify-content: center; align-items: center;}</style> </head> <div class="vertical-center noresults"> <div align="center"> <img src="icons/searchzero.svg" width="50px" height="40px"> <h3 align="center">No dictionary entries were found for "'
                + term
                + '".</h3> </div></div>'
            )
        return html.replace("'", "\\'")

    def _attemptFetchForvo(self, term: str, idName: str) -> str:
        forvo = forvodl.Forvo(self.config["ForvoLanguage"])
        forvo.setTermIdName(term, idName)
        forvo.signals.resultsFound.connect(self._loadForvoResults)
        forvo.signals.noResults.connect(self._showGoogleForvoMessage)
        self._threadpool.start(forvo)
        return "Loading..."

    def _loadForvoResults(self, results: tuple[str, str]) -> None:
        forvoData, idName = results
        if forvoData:
            html = "<div class=\\'forvo\\'  data-urls=\\'" + forvoData + "\\'></div>"
        else:
            html = '<div class="no-forvo">No Results Found.</div>'
        self.eval(
            "loadImageForvoHtml('%s', '%s');loadForvoDict(false, '%s');"
            % (html.replace('"', '\\"'), idName, idName)
        )

    def _getForvoDictionaryResults(
        self,
        term: str,
        dictCount: int,
        bracketFront: str,
        bracketBack: str,
        entryCount: int,
        font: str,
    ) -> str:
        dictName = "Forvo"
        overwrite = self._getOverwriteChecks(dictCount, dictName)
        select = self._getFieldChecks(dictName)
        idName = "fcon" + str(time.time())
        self._attemptFetchForvo(term, idName)
        html = (
            '<div data-index="'
            + str(dictCount)
            + '" class="dictionaryTitleBlock"><div class="dictionaryTitle">'
            + dictName
            + '</div><div class="dictionarySettings">'
            + overwrite
            + select
            + '<div class="dictNav"><div onclick="navigateDict(event, false)" class="prevDict">▲</div><div onclick="navigateDict(event, true)" class="nextDict">▼</div></div></div></div>'
        )
        html += (
            '<div  data-index="'
            + str(entryCount)
            + '"  class="termPronunciation"><span class="tpCont">'
            + bracketFront
            + "<span "
            + font
            + ' class="terms">'
            + self._highlightTarget(term, term)
            + "</span>"
            + bracketBack
            + ' <span></span></span><div class="defTools"><div onclick="ankiExport(event, \''
            + dictName
            + '\')" class="ankiExportButton"><img src="icons/anki.png"></div><div onclick="clipText(event)" class="clipper">✂</div><div onclick="sendToField(event, \''
            + dictName
            + '\')" class="sendToField">➠</div><div class="defNav"><div onclick="navigateDef(event, false)" class="prevDef">▲</div><div onclick="navigateDef(event, true)" class="nextDef">▼</div></div></div></div><div id="'
            + idName
            + '" class="definitionBlock">'
        )
        html += "Loading..."
        html += "</div>"
        return html

    def _getGoogleDictionaryResults(
        self,
        term: str,
        dictCount: int,
        bracketFront: str,
        bracketBack: str,
        entryCount: int,
        font: str,
    ) -> str:
        dictName = "Google Images"
        overwrite = self._getOverwriteChecks(dictCount, dictName)
        select = self._getFieldChecks(dictName)
        idName = "gcon" + str(time.time())
        html = (
            '<div data-index="'
            + str(dictCount)
            + '" class="dictionaryTitleBlock"><div class="dictionaryTitle">Google Images</div><div class="dictionarySettings">'
            + overwrite
            + select
            + '<div class="dictNav"><div onclick="navigateDict(event, false)" class="prevDict">▲</div><div onclick="navigateDict(event, true)" class="nextDict">▼</div></div></div></div>'
        )
        html += (
            '<div  data-index="'
            + str(entryCount)
            + '" class="termPronunciation"><span class="tpCont">'
            + bracketFront
            + "<span "
            + font
            + ' class="terms">'
            + self._highlightTarget(term, term)
            + "</span>"
            + bracketBack
            + ' <span></span></span><div class="defTools"><div onclick="ankiExport(event, \''
            + dictName
            + '\')" class="ankiExportButton"><img src="icons/anki.png"></div><div onclick="clipText(event)" class="clipper">✂</div><div onclick="sendToField(event, \''
            + dictName
            + '\')" class="sendToField">➠</div><div class="defNav"><div onclick="navigateDef(event, false)" class="prevDef">▲</div><div onclick="navigateDef(event, true)" class="nextDef">▼</div></div></div></div><div class="definitionBlock"><div class="imageBlock" id="'
            + idName
            + '">'
            + self._getGoogleImages(term, idName)
            + "</div></div>"
        )
        return html

    def _getGoogleImages(self, term: str, idName: str) -> str:
        imager = googleimages.Google()
        imager.setTermIdName(term, idName)
        imager.setSearchRegion(self.config["googleSearchRegion"])
        imager.setSafeSearch(self.config["safeSearch"])
        imager.signals.resultsFound.connect(self._loadImageResults)
        imager.signals.noResults.connect(self._showGoogleForvoMessage)
        self._threadpool.start(imager)

        return "Loading..."

    def _getCleanedUrls(self, urls: typing.Iterable[str]) -> list[str]:
        return [x.replace("\\", "\\\\") for x in urls]

    def _getDuplicateHeaderCB(self, dictName: str) -> str:
        tooltip = ""
        if self.config["tooltips"]:
            tooltip = ' title="Enable this option if this dictionary has the target word\'s header within the definition. Enabling this will prevent the addon from exporting duplicate header."'
        checked = " "
        className = "checkDict" + re.sub(r"\s", "", dictName)
        duplicates = self._dupHeaders or {}

        if dictName in duplicates:
            num = duplicates.get(dictName)
            if num == 1:
                checked = " checked "
        return (
            '<div class="dupHeadCB" data-dictname="'
            + dictName
            + '">Duplicate Header:<input '
            + checked
            + tooltip
            + ' class="'
            + className
            + '" onclick="handleDupChange(this, \''
            + className
            + '\')" type="checkbox"></div>'
        )

    def _maybeSearchTerms(self) -> None:
        for t in self._terms:
            self._dictInt.initSearch(t)
        self._terms = []

    def _handleDictAction(self, dAct: str) -> None:
        if dAct.startswith("MigakuDictionaryLoaded"):
            self._maybeSearchTerms()
        elif dAct.startswith("forvo:"):
            urls = json.loads(dAct[6:])
            self._downloadForvoAudio(urls)
        elif dAct.startswith("updateTerm:"):
            term = dAct[11:]
            self._dictInt.search.setText(term)
        elif dAct.startswith("saveFS:"):
            f1, f2 = dAct[7:].split(":")
            self._dictInt.writeConfig("fontSizes", (int(f1), int(f2)))
        elif dAct.startswith("setDup:"):
            dup, name = dAct[7:].split("◳")
            self._dictInt.db.setDupHeader(dup, name)
            self._dupHeaders = self.db.getDupHeaders()
        elif dAct.startswith("fieldsSetting:"):
            fields = json.loads(dAct[14:])
            if fields["dictName"] == "Google Images":
                self._dictInt.writeConfig("GoogleImageFields", fields["fields"])
            elif fields["dictName"] == "Forvo":
                self._dictInt.writeConfig("ForvoFields", fields["fields"])
            else:
                self._dictInt.updateFieldsSetting(fields["dictName"], fields["fields"])
        elif dAct.startswith("overwriteSetting:"):
            addType = _validate_add_type(json.loads(dAct[17:]))

            if addType["name"] == "Google Images":
                self._dictInt.writeConfig("GoogleImageAddType", addType["type"])
            elif addType["name"] == "Forvo":
                self._dictInt.writeConfig("ForvoAddType", addType["type"])
            else:
                self._dictInt.updateAddType(addType["name"], addType["type"])
        elif dAct.startswith("clipped:"):
            text = dAct[8:]

            if clipboard := self._dictInt.mw.app.clipboard():
                clipboard.setText(text.replace("<br>", "\n"))
            else:
                raise RuntimeError(f'Cannot do "{dAct}" action. No clipboard found.')
        elif dAct.startswith("sendToField:"):
            name, text = dAct[12:].split("◳◴")
            self._sendToField(name, text)
        elif dAct.startswith("sendAudioToField:"):
            urls = dAct[17:]
            self._sendAudioToField(urls)
        elif dAct.startswith("sendImgToField:"):
            urls = dAct[15:]
            self._sendImgToField(urls)
        elif dAct.startswith("addDef:"):
            dictName, word, text = dAct[7:].split("◳◴")
            self._addDefToExportWindow(dictName, word, text)
        elif dAct.startswith("audioExport:"):
            word, urls = dAct[12:].split("◳◴")
            self._addAudioToExportWindow(word, urls)
        elif dAct.startswith("imgExport:"):
            word, urls = dAct[10:].split("◳◴")
            self._addImgsToExportWindow(word, json.loads(urls))

    def _addImgsToExportWindow(self, word: str, urls: typing.Iterable[str]) -> None:
        self._initCardExporterIfNeeded()
        imgSeparator = ""
        imgs = []
        rawPaths = []
        for imgurl in urls:
            try:
                url = re.sub(r"\?.*$", "", imgurl)
                filename = (
                    str(time.time())[:-4].replace(".", "")
                    + re.sub(r"\..*$", "", url.strip().split("/")[-1])
                    + ".jpg"
                )
                fullpath = os.path.join(self._dictInt.mw.col.media.dir(), filename)
                self._saveQImage(imgurl, filename)
                rawPaths.append(fullpath)
                imgs.append('<img src="' + filename + '">')
            except:
                continue

        if imgs and self.addWindow:
            self.addWindow.addImgs(
                word, imgSeparator.join(imgs), self._getThumbs(rawPaths)
            )

    def _saveQImage(self, url: str, filename: str) -> None:
        req = request_.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
            },
        )
        file = request_.urlopen(req).read()
        image = qt.QImage()
        image.loadFromData(file)
        image = image.scaled(
            qt.QSize(self._maxW, self._maxH),
            qt.Qt.AspectRatioMode.KeepAspectRatio,
            qt.Qt.TransformationMode.SmoothTransformation,
        )
        image.save(filename)

    def _getThumbs(self, paths: typing.Iterable[str]) -> qt.QWidget:
        thumbCase = qt.QWidget()
        thumbCase.setContentsMargins(0, 0, 0, 0)
        vLayout = qt.QVBoxLayout()
        vLayout.setContentsMargins(0, 0, 0, 0)
        hLayout = qt.QHBoxLayout()
        hLayout.setContentsMargins(0, 0, 0, 0)
        vLayout.addLayout(hLayout)
        for idx, path in enumerate(paths):
            image = qt.QPixmap(path)
            image = image.scaled(
                qt.QSize(50, 50),
                qt.Qt.AspectRatioMode.KeepAspectRatio,
                qt.Qt.TransformationMode.SmoothTransformation,
            )
            label = qt.QLabel("")
            label.setPixmap(image)
            label.setFixedSize(40, 40)
            hLayout.addWidget(label)
            if idx > 0 and idx % 4 == 0:
                hLayout = qt.QHBoxLayout()
                hLayout.setContentsMargins(0, 0, 0, 0)
                vLayout.addLayout(hLayout)
        thumbCase.setLayout(vLayout)
        return thumbCase

    def _addDefToExportWindow(self, dictName: str, word: str, text: str) -> None:
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.addDefinition(dictName, word, text)

    def _initCardExporterIfNeeded(self) -> None:
        if not self.addWindow:
            self.addWindow = cardExporter.CardExporter(self._dictInt)

    def _getFieldContent(self, fContent: str, definition: str, addType: str) -> str:
        fieldText = ""

        if addType == "overwrite":
            fieldText = definition

        elif addType == "add":
            if fContent == "":
                fieldText = definition
            else:
                fieldText = fContent + "<br><br>" + definition
        elif addType == "no":
            if fContent == "":
                fieldText = definition

        return fieldText

    def _addAudioToExportWindow(self, word: str, urls: str) -> None:
        self._initCardExporterIfNeeded()
        audioSeparator = ""
        soundFiles = self._downloadForvoAudio(json.loads(urls))

        if soundFiles and self.addWindow:
            self.addWindow.addDefinition("Forvo", word, audioSeparator.join(soundFiles))

    def _sendAudioToField(self, urls: str) -> None:
        audioSeparator = ""
        soundFiles = self._downloadForvoAudio(json.loads(urls))
        self._sendToField("Forvo", audioSeparator.join(soundFiles))

    def _downloadForvoAudio(self, urls: typing.Iterable[str]) -> list[str]:
        tags: list[str] = []

        for url in urls:
            # TODO: @ColinKennedy - try/except
            try:
                req = request_.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
                    },
                )
                file = request_.urlopen(req).read()
                filename = str(time.time()) + ".mp3"
                open(
                    os.path.join(self._dictInt.mw.col.media.dir(), filename), "wb"
                ).write(file)
                tags.append("[sound:" + filename + "]")
            except:
                continue

        return tags

    def _sendImgToField(self, json_urls: str) -> None:
        if (self.reviewer and self.reviewer.card) or (
            self.currentEditor and self.currentEditor.note
        ):
            urlsList: list[str] = []
            imgSeparator = ""
            urls = typing.cast(list[str], json.loads(json_urls))

            for imgurl in urls:
                try:
                    url = re.sub(r"\?.*$", "", imgurl)
                    filename = (
                        str(time.time())[:-4].replace(".", "")
                        + re.sub(r"\..*$", "", url.strip().split("/")[-1])
                        + ".jpg"
                    )
                    self._saveQImage(imgurl, filename)
                    urlsList.append('<img src="' + filename + '">')
                except:
                    continue

            if len(urlsList) > 0:
                self._sendToField("Google Images", imgSeparator.join(urlsList))

    def _sendToField(self, name: str, definition: str) -> None:
        addType: str

        if self.reviewer and self.reviewer.card:
            if name == "Google Images":
                tFields = self.config["GoogleImageFields"]
                addType = self.config["GoogleImageAddType"]
            elif name == "Forvo":
                tFields = self.config["ForvoFields"]
                addType = self.config["ForvoAddType"]
            else:
                result = self.db.getAddTypeAndFields(name)

                if not result:
                    raise RuntimeError(f'Unable to get fields for "{name}" dictionary.')

                tFields, addType = result

            note = self.reviewer.card.note()
            model = note.note_type()

            if not model:
                raise RuntimeError(f'Note "{note}" has no Note Type.')

            fields = model["flds"]
            changed = False
            for field in fields:
                if field["name"] in tFields:
                    newField = self._getFieldContent(
                        note[field["name"]], definition, addType
                    )
                    if newField:
                        changed = True
                        if self._jSend:
                            note[field["name"]] = (
                                self._dictInt.jHandler.attemptFieldGenerate(
                                    newField,
                                    field["name"],
                                    model["name"],
                                    note,
                                )
                            )
                        else:
                            note[field["name"]] = newField
            if not changed:
                return
            note.flush()
            self._dictInt.mw.col.save()
            self.reviewer.card.load()
            if self.reviewer.state == "answer":
                self.reviewer._showAnswer()
            elif self.reviewer.state == "question":
                self.reviewer._showQuestion()
            if hasattr(self._dictInt.mw, "migakuReloadEditorAndBrowser"):
                self._dictInt.mw.migakuReloadEditorAndBrowser(note)
        if self.currentEditor and self.currentEditor.note:
            if name == "Google Images":
                tFields = self.config["GoogleImageFields"]
                addType = self.config["GoogleImageAddType"]
            elif name == "Forvo":
                tFields = self.config["ForvoFields"]
                addType = self.config["ForvoAddType"]
            else:
                result = self.db.getAddTypeAndFields(name)

                if not result:
                    raise RuntimeError(f'Unable to get fields for "{name}" dictionary.')

                tFields, addType = result

            note = self.currentEditor.note

            for field_name in tFields:
                field_index = next(
                    (i for i, f in enumerate(note.keys()) if f == field_name), None
                )
                if field_index is not None:
                    current_value = note.fields[field_index]

                    if addType == "overwrite":
                        new_value = definition
                    elif addType == "add":
                        new_value = current_value + "<br><br>" + definition
                    elif addType == "no":
                        if current_value.strip():
                            new_value = current_value
                        else:
                            new_value = definition
                    else:
                        new_value = definition
                    note.fields[field_index] = new_value
            self.currentEditor.loadNote()

    def _getOverwriteChecks(self, dictCount: int, dictName: str) -> str:
        addType: typer.AddType

        if dictName == "Google Images":
            addType = self.config["GoogleImageAddType"]
        elif dictName == "Forvo":
            addType = self.config["ForvoAddType"]
        else:
            found = self.db.getAddType(dictName)

            if not found:
                raise RuntimeError(f'Dictionary "{dictName}" has no adder-type.')

            addType = found

        tooltip = ""
        if self.config["tooltips"]:
            tooltip = " title=\"This determines the conditions for sending a definition (or a Google Image) to a field. Overwrite the target field's content. Add to the target field's current contents. Only add definitions to the target field if it is empty.\""
        if addType == "add":
            typeName = "&nbsp;Add"
        elif addType == "overwrite":
            typeName = "&nbsp;Overwrite"
        elif addType == "no":
            typeName = "&nbsp;If Empty"
        select = (
            '<div class="overwriteSelectCont"><div '
            + tooltip
            + ' class="overwriteSelect" onclick="showCheckboxes(event)">'
            + typeName
            + "</div>"
            + self._getSelectedOverwriteType(dictName, addType)
            + "</div>"
        )
        return select

    def _getSelectedOverwriteType(self, dictName: str, addType: str) -> str:
        count = str(self._radioCount)
        checked = ""
        if addType == "add":
            checked = " checked"
        add = (
            '<label class="inCheckBox"><input'
            + checked
            + ' onclick="handleAddTypeCheck(this)" class="inCheckBox radio'
            + dictName
            + '" type="radio" name="'
            + count
            + dictName
            + '" value="add"/>Add</label>'
        )
        checked = ""
        if addType == "overwrite":
            checked = " checked"
        overwrite = (
            '<label class="inCheckBox"><input'
            + checked
            + ' onclick="handleAddTypeCheck(this)" class="inCheckBox radio'
            + dictName
            + '" type="radio" name="'
            + count
            + dictName
            + '" value="overwrite"/>Overwrite</label>'
        )
        checked = ""
        if addType == "no":
            checked = " checked"
        ifempty = (
            '<label class="inCheckBox"><input'
            + checked
            + ' onclick="handleAddTypeCheck(this)" class="inCheckBox radio'
            + dictName
            + '" type="radio" name="'
            + count
            + dictName
            + '" value="no"/>If Empty</label>'
        )
        checks = (
            '<div class="overwriteCheckboxes" data-dictname="'
            + dictName
            + '">'
            + add
            + overwrite
            + ifempty
            + "</div>"
        )
        self._radioCount += 1
        return checks

    def _getFieldChecks(self, dictName: str) -> str:
        if dictName == "Google Images":
            selF = self.config["GoogleImageFields"]
        elif dictName == "Forvo":
            selF = self.config["ForvoFields"]
        else:
            selF = self.db.getFieldsSetting(dictName) or []

        tooltip = ""

        if self.config["tooltips"]:
            tooltip = ' title="Select this dictionary\'s target fields for when sending a definition(or a Google Image) to a card. If a field does not exist in the target card, then it is ignored, otherwise the definition is added to all fields that exist within the target card."'
        title = "&nbsp;Select Fields ▾"
        length = len(selF)
        if length > 0:
            title = "&nbsp;" + str(length) + " Selected"
        select = (
            '<div class="fieldSelectCont"><div class="fieldSelect" '
            + tooltip
            + ' onclick="showCheckboxes(event)">'
            + title
            + "</div>"
            + self._getCheckBoxes(dictName, selF)
            + "</div>"
        )
        return select

    def _getCheckBoxes(self, dictName: str, selF: typing.Sequence[str]) -> str:
        fields = self._getFieldNames()
        options = '<div class="fieldCheckboxes"  data-dictname="' + dictName + '">'

        for f in fields:
            checked = ""

            if f in selF:
                checked = " checked"

            options += (
                '<label class="inCheckBox"><input'
                + checked
                + ' onclick="handleFieldCheck(this)" class="inCheckBox" type="checkbox" value="'
                + f
                + '" />'
                + f
                + "</label>"
            )

        return options + "</div>"

    def _getFieldNames(self) -> list[str]:
        mw = self._dictInt.mw
        models = mw.col.models.all()
        fields: list[str] = []

        for model in models:
            for fld in model["flds"]:
                if fld["name"] not in fields:
                    fields.append(fld["name"])

        fields.sort()

        return fields

    def addNewTab(self, term: str, selectedGroup: typer.DictionaryGroup2) -> None:
        if (
            selectedGroup["customFont"]
            and selectedGroup["font"] not in self._customFontsLoaded
        ):
            self._customFontsLoaded.append(selectedGroup["font"])
            self._injectFont(selectedGroup["font"])
        html, cleaned, singleTab = self._getHTMLResult(term, selectedGroup)
        self.eval(
            "addNewTab('%s', '%s', %s);"
            % (html.replace("\r", "<br>").replace("\n", "<br>"), cleaned, singleTab)
        )

    def attemptAutoAdd(self, bulkExport: bool) -> None:
        if self.addWindow:
            self.addWindow.attemptAutoAdd(bulkExport)

    def bulkTextExport(self, cards: typing.Sequence[typer.Card]) -> None:
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.bulkTextExport(cards)

    def bulkMediaExport(self, card: typer.Card) -> None:
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.bulkMediaExport(card)

    def cancelBulkMediaExport(self) -> None:
        if self.addWindow:
            self.addWindow.bulkMediaExportCancelledByBrowserRefresh()

    def closeEditor(self) -> None:
        self.reviewer = None
        self.currentEditor = None
        self._dictInt.currentTarget.setText("")

    def exportAudio(self, audioList: tuple[str, str, str]) -> None:
        self._dictInt.ensureVisible()
        temp, tag, name = audioList
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.scrollArea.show()
            self.addWindow.exportAudio(temp, tag, name)

    def exportImage(self, pathAndName: tuple[str, str]) -> None:
        self._dictInt.ensureVisible()
        path, name = pathAndName
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.scrollArea.show()
            self.addWindow.exportImage(path, name)

    def exportSentence(self, sentence: str, secondary: str = "") -> None:
        self._dictInt.ensureVisible()
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.scrollArea.show()
            self.addWindow.exportSentence(sentence)
            self.addWindow.exportSecondary(secondary)

    def exportWord(self, word: str) -> None:
        self._dictInt.ensureVisible()
        self._initCardExporterIfNeeded()

        if self.addWindow:
            self.addWindow.scrollArea.show()
            self.addWindow.exportWord(word)

    def loadHTMLURL(self, html: str, url: qt.QUrl) -> None:
        _verify(self.page()).setHtml(html, url)

    def setCurrentEditor(self, editor: editor_.Editor, target: str = "") -> None:
        if editor == self.currentEditor:
            return

        self.currentEditor = editor
        self.reviewer = None
        self._dictInt.currentTarget.setText(target)

    def setReviewer(self, reviewer: reviewer_.Reviewer) -> None:
        self.reviewer = reviewer
        self.currentEditor = None
        self._dictInt.currentTarget.setText("Reviewer")

    def setSType(self, sType: qt.QComboBox) -> None:
        self._sType = sType


class HoverButton(qt.QPushButton):
    mouseHover = qt.pyqtSignal(bool)
    mouseOut = qt.pyqtSignal(bool)

    def __init__(self, parent: typing.Optional[qt.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)

    def enterEvent(self, event: typing.Optional[qt.QEvent]) -> None:
        self.mouseHover.emit(True)

    def leaveEvent(self, event: typing.Optional[qt.QEvent]) -> None:
        self.mouseHover.emit(False)
        self.mouseOut.emit(True)


class ClipThread(qt.QObject):

    sentence = qt.pyqtSignal(str)
    search = qt.pyqtSignal(str)
    colSearch = qt.pyqtSignal(str)
    add = qt.pyqtSignal(str)
    image = qt.pyqtSignal(list)
    test = qt.pyqtSignal(list)
    release = qt.pyqtSignal(list)
    extensionCardExport = qt.pyqtSignal(dict)
    searchFromExtension = qt.pyqtSignal(list)
    extensionFileNotFound = qt.pyqtSignal()
    bulkTextExport = qt.pyqtSignal(list)
    bulkMediaExport = qt.pyqtSignal(dict)
    pageRefreshDuringBulkMediaImport = qt.pyqtSignal()

    def __init__(self, mw: main.AnkiQt, path: str) -> None:
        if utils.is_mac:
            import Quartz

            self.kCGKeyboardEventKeycode = Quartz.kCGKeyboardEventKeycode
            self.CGEventGetIntegerValueField = Quartz.CGEventGetIntegerValueField

        super().__init__(mw)

        self.keyboard = keyboard
        self.addonPath = path
        self.mw = mw

        configuration = self.mw.addonManager.getConfig(__name__)

        if not configuration:
            raise EnvironmentError(f'Unable to load a configuration for "{__name__}".')

        self.config = configuration

    def _on_press(
        self, key: typing.Union[keyboard.Key, keyboard.KeyCode, None]
    ) -> None:
        self.test.emit([key])

    def _on_release(
        self, key: typing.Union[keyboard.Key, keyboard.KeyCode, None]
    ) -> None:
        self.release.emit([key])

    def _darwinIntercept(
        self,
        event_type: typing.Union[  # type: ignore[valid-type]
            typing.Literal[Quartz.kCGEventKeyDown],
            typing.Literal[Quartz.kCGEventKeyUp],
        ],
        event: _CGEventRef,
    ) -> typing.Optional[_CGEventRef]:
        # TODO: @ColinKennedy - cyclic import
        from . import keypress_tracker

        keycode = self.CGEventGetIntegerValueField(event, self.kCGKeyboardEventKeycode)
        pressed = keypress_tracker.get()

        if (
            ("Key.cmd" in pressed or "Key.cmd_r" in pressed)
            and "'c'" in pressed
            and keycode == 1
        ):
            self.handleSystemSearch()
            keypress_tracker.clear()

            return None

        return event

    def _moveAudioToTempFolder(
        self,
        path: str,
    ) -> tuple[typing.Optional[str], typing.Optional[str]]:
        # TODO: @ColinKennedy - remove try/except
        try:
            if os.path.exists(path):
                filename = str(time.time()).replace(".", "") + ".mp3"
                destpath = os.path.join(self.addonPath, "temp", filename)
                if not os.path.exists(destpath):
                    shutil.copyfile(path, destpath)
                    return destpath, filename
            return None, None
        except:
            return None, None

    def _checkDict(self) -> bool:
        # TODO: @ColinKennedy - Remove the cyclic dependency later
        from . import migaku_dictionary

        return not migaku_dictionary.get_visible_dictionary()

    def _saveScaledImage(self, imageTempPath: str, imageFileName: str) -> None:
        configuration = migaku_configuration.get()
        path = os.path.join(self.mw.col.media.dir(), imageFileName)
        image = qt.QImage(imageTempPath)
        image = image.scaled(
            qt.QSize(configuration["maxWidth"], configuration["maxHeight"]),
            qt.Qt.AspectRatioMode.KeepAspectRatio,
            qt.Qt.TransformationMode.SmoothTransformation,
        )
        image.save(path)

    def _removeFile(self, path: str) -> None:
        os.remove(path)

    def _checkFileExists(self, source: str) -> bool:
        now = time.time()
        while True:
            if os.path.exists(source):
                return True
            if time.time() - now > 15:
                return False

    def _moveExtensionFileToMediaFolder(self, source: str, filename: str) -> bool:
        if not os.path.exists(source):
            return False

        path = os.path.join(self.mw.col.media.dir(), filename)

        if not os.path.exists(path):
            shutil.copyfile(source, path)

            return True

        return False

    def _moveExtensionMp3ToMediaFolder(self, source: str, filename: str) -> None:
        suffix = ""
        if utils.is_win:
            suffix = ".exe"
        ffmpeg = os.path.join(
            os.path.dirname(__file__), "user_files", "ffmpeg", "ffmpeg" + suffix
        )
        path = os.path.join(self.mw.col.media.dir(), filename)
        import subprocess

        subprocess.call([ffmpeg, "-i", source, path])

    def getConfig(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration,
            self.mw.addonManager.getConfig(__name__),
        )

    def attemptAddCard(self) -> None:
        self.add.emit("add")

    def handleBulkTextExport(self, cards: list[typer.Card]) -> None:
        self.bulkTextExport.emit(cards)

    def handleColSearch(self) -> None:
        if clipboard := self.mw.app.clipboard():
            self.colSearch.emit(clipboard.text())
        else:
            raise RuntimeError("Cannot search columns. No clipboard was found.")

    def handleExtensionCardExport(self, card: typer.Card) -> None:
        config = self.getConfig()
        audioFileName = card["audio"]
        imageFileName = card["image"]
        bulk = card["bulk"]
        if audioFileName:
            audioTempPath = os.path.join(
                os.path.dirname(__file__), "temp", audioFileName
            )

            if not self._checkFileExists(audioTempPath):
                self.extensionFileNotFound.emit()

                return

            if config["mp3Convert"]:
                audioFileName = audioFileName.replace(".wav", ".mp3")
                self._moveExtensionMp3ToMediaFolder(audioTempPath, audioFileName)
                card["audio"] = audioFileName
            else:
                self._moveExtensionFileToMediaFolder(audioTempPath, audioFileName)

            self._removeFile(audioTempPath)

        if imageFileName:
            imageTempPath = os.path.join(
                os.path.dirname(__file__), "temp", imageFileName
            )

            if self._checkFileExists(imageTempPath):
                self._saveScaledImage(imageTempPath, imageFileName)
                self._removeFile(imageTempPath)

        if bulk:
            self.bulkMediaExport.emit(card)
        else:
            self.extensionCardExport.emit(card)

    def handleExtensionSearch(self, terms: list[str]) -> None:
        self.searchFromExtension.emit(terms)

    def handleImageExport(self) -> None:
        # TODO: @ColinKennedy - Invert this if statement later
        if self._checkDict():
            clipboard = self.mw.app.clipboard()

            if not clipboard:
                raise RuntimeError("No clipboard data was found.")

            mime = clipboard.mimeData()

            if not mime:
                raise RuntimeError("No MIME data was found.")

            clip = clipboard.text()

            if not clip.endswith(".mp3") and mime.hasImage():
                image = mime.imageData()
                filename = str(time.time()) + ".png"
                fullpath = os.path.join(self.addonPath, "temp", filename)
                maxW = max(self.config["maxWidth"], image.width())
                maxH = max(self.config["maxHeight"], image.height())
                image = image.scaled(
                    qt.QSize(maxW, maxH),
                    qt.Qt.AspectRatioMode.KeepAspectRatio,
                    qt.Qt.TransformationMode.SmoothTransformation,
                )
                image.save(fullpath)
                self.image.emit([fullpath, filename])
            elif clip.endswith(".mp3"):
                if not utils.is_lin:
                    if utils.is_mac:
                        clipboard = self.mw.app.clipboard()

                        if not clipboard:
                            _LOGGER.warning(
                                "No clipboard found, cannot emit stored data."
                            )

                            return

                        data = clipboard.mimeData()

                        if not data:
                            # TODO: @ColinKennedy - Add logging
                            return

                        try:
                            clip = str(data.urls()[0].url())
                        except:
                            return

                    if clip.startswith("file:///") and clip.endswith(".mp3"):
                        # TODO: @ColinKennedy - remove try/except
                        try:
                            if utils.is_mac:
                                path = clip.replace("file://", "", 1)
                            else:
                                path = clip.replace("file:///", "", 1)
                            temp, mp3 = self._moveAudioToTempFolder(path)
                            if temp and mp3:
                                self.image.emit([temp, "[sound:" + mp3 + "]", mp3])
                        except:
                            return

    def handlePageRefreshDuringBulkMediaImport(self) -> None:
        self.pageRefreshDuringBulkMediaImport.emit()

    def handleSentenceExport(self) -> None:
        if not self._checkDict():
            _LOGGER.info("Cannot export sentence. No visible dictionary.")

            return

        clipboard = self.mw.app.clipboard()

        if not clipboard:
            raise RuntimeError("Cannot do sentence export. No clipboard was found.")

        self.sentence.emit(clipboard.text())

    def handleSystemSearch(self) -> None:
        if clipboard := self.mw.app.clipboard():
            self.search.emit(clipboard.text())
        else:
            raise RuntimeError(
                f"Cannot search with the system clipboard. No clipboard was found."
            )

    def run(self) -> None:
        if utils.is_win:
            self.listener = self.keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release, suppress=True
            )
        elif utils.is_mac:
            self.listener = self.keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                darwin_intercept=self._darwinIntercept,
            )
        else:
            self.listener = self.keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
        self.listener.start()


class DictInterface(qt.QWidget):

    def __init__(
        self,
        dictdb: dictdb_.DictDB,
        mw: main.AnkiQt,
        path: str,
        welcome: str,
        parent: typing.Optional[qt.QWidget] = None,
        terms: typing.Optional[list[str]] = None,
    ):
        super().__init__(parent)
        self.db = dictdb
        self.alwaysOnTop = False
        self.verticalBar = False
        self.jHandler = miJapaneseHandler.miJHandler(mw)
        self.addonPath = path
        self.welcome = welcome
        self.setAutoFillBackground(True)
        self.ogPalette = self._getPalette(qt.QColor("#F0F0F0"))
        self.nightPalette = self._getPalette(qt.QColor("#272828"))
        self.blackBase = self._getFontColor(qt.QColor(qt.Qt.GlobalColor.black))
        self.blackBase = self._getFontColor(qt.QColor(qt.Qt.GlobalColor.black))
        self.mw = mw
        self.iconpath = os.path.join(path, "icons")
        self._startUp(terms or [])
        self._setHotkeys()
        aqt_utils.ensureWidgetInScreenBoundaries(self)

    def _setHotkeys(self) -> None:
        hotkey = qt.QShortcut(qt.QKeySequence("Esc"), self)
        hotkey.activated.connect(self.hide)
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+W"), self)
        hotkey.activated.connect(dictionaryInit)
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+S"), self)
        hotkey.activated.connect(functools.partial(migaku_search.searchTerm, self.dict))
        hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+Shift+B"), self)
        hotkey.activated.connect(functools.partial(migaku_search.searchCol, self.dict))

    def _getFontColor(self, color: qt.QColor) -> qt.QPalette:
        pal = qt.QPalette()
        # pal.setColor(qt.QPalette.ColorRole.Base, color)
        return pal

    def _getPalette(self, color: qt.QColor) -> qt.QPalette:
        pal = qt.QPalette()
        # pal.setColor(qt.QPalette.ColorRole.Background, color)
        return pal

    def _getStretchLay(self) -> qt.QHBoxLayout:
        stretch = qt.QHBoxLayout()
        stretch.setContentsMargins(0, 0, 0, 0)
        stretch.addStretch()
        return stretch

    def _setAlwaysOnTop(self) -> None:
        if self.alwaysOnTop:
            self.setWindowFlags(
                self.windowFlags() | qt.Qt.WindowType.WindowStaysOnTopHint
            )
            self.show()
        else:
            self.setWindowFlags(
                self.windowFlags() & ~qt.Qt.WindowType.WindowStaysOnTopHint
            )
            self.show()

    def _reloadConfig(self, config: typer.Configuration) -> None:
        self.config = config
        self.dict.config = config

    def _startUp(self, terms: list[str]) -> None:
        terms = self._refineToValidSearchTerms(terms)
        willSearch = False
        if terms:
            willSearch = True
        self.allGroups = self._getAllGroups()
        self.config = self.getConfig()
        self.defaultGroups = self.db.getDefaultGroups()
        self.userGroups = self._getUserGroups()
        self.searchOptions = [
            "Forward",
            "Backward",
            "Exact",
            "Anywhere",
            "Definition",
            "Example",
            "Pronunciation",
        ]
        self.setWindowTitle("Migaku Dictionary")
        self.dictGroups = self._setupDictGroups()
        self.nightModeToggler = self._setupNightModeToggle()
        self._setSvg(self.nightModeToggler, "theme")
        self.dict = MIDict(
            self, self.db, self.addonPath, self.nightModeToggler.day, terms
        )
        self.conjToggler = self._setupConjugationMode()
        self.minusB = self._setupMinus()
        self.plusB = self._setupPlus()
        self.tabB = self._setupTabMode()
        self.histB = self._setupOpenHistory()
        self.setB = self._setupOpenSettings()
        self.searchButton = self._setupSearchButton()
        self.insertHTMLJS = self._getInsertHTMLJS()
        self.search = self._setupSearch()
        self._sType = self._setupSearchType()
        self.openSB = self._setupOpenSB()
        self.openSB.opened = False
        self.currentTarget: qt.QLabel = qt.QLabel("")
        self.targetLabel = qt.QLabel(" Target:")
        self.stretch1 = self._getStretchLay()
        self.stretch2 = self._getStretchLay()
        self.layoutH2 = qt.QHBoxLayout()
        self.mainHLay = qt.QHBoxLayout()
        self.mainLayout = self._setupView()
        self.dict.setSType(self._sType)
        self.setLayout(self.mainLayout)
        self.resize(800, 600)
        self.setMinimumSize(350, 350)
        self.sbOpened = False
        self.historyModel = history.HistoryModel(self._getHistory(), self)
        self.historyBrowser = history.HistoryBrowser(self.historyModel, self)
        self.setWindowIcon(qt.QIcon(os.path.join(self.iconpath, "migaku.png")))
        self.readyToSearch = False
        self._restoreSizePos()

        if self.config["tooltips"]:
            self._initTooltips()

        self.show()
        self.search.setFocus()
        if self.nightModeToggler.day:
            self._loadDay()
        else:
            self._loadNight()
        html, url = self._getHTMLURL(willSearch, self.nightModeToggler.day)
        self.dict.loadHTMLURL(html, url)
        self.alwaysOnTop = self.config["dictAlwaysOnTop"]
        self._maybeSetToAlwaysOnTop()

    def _maybeSetToAlwaysOnTop(self) -> None:
        if self.alwaysOnTop:
            self.setWindowFlags(
                self.windowFlags() | qt.Qt.WindowType.WindowStaysOnTopHint
            )
            self.show()

    def _initTooltips(self) -> None:
        self.dictGroups.setToolTip("Select the dictionary group.")
        self._sType.setToolTip("Select the search type.")
        self.openSB.setToolTip("Open/Close the definition sidebar.")
        self.minusB.setToolTip("Decrease the dictionary's font size.")
        self.plusB.setToolTip("Increase the dictionary's font size.")
        self.tabB.setToolTip("Switch between single and multi-tab modes.")
        self.histB.setToolTip("Open the history viewer.")
        self.conjToggler.setToolTip("Turn deinflection mode on/off.")
        self.nightModeToggler.setToolTip("Enable/Disable night-mode.")
        self.setB.setToolTip("Open the dictionary settings.")

    def _restoreSizePos(self) -> None:
        sizePos = self.config["dictSizePos"]
        if sizePos:
            self.resize(sizePos[2], sizePos[3])
            self.move(sizePos[0], sizePos[1])

    def _refineToValidSearchTerms(self, terms: list[str]) -> list[str]:
        validTerms: list[str] = []

        for term in terms:
            term = term.strip()
            term = self._cleanTermBrackets(term)

            if term:
                validTerms.append(term)

            if validTerms:
                return validTerms

        return []

    def _getHTMLURL(self, willSearch: bool, day: bool) -> tuple[str, qt.QUrl]:
        nightStyle = '<style id="nightModeCss">body, .definitionSideBar, .defTools{color: white !important;background: black !important;} .termPronunciation{background: black !important;border-top:1px solid white !important;border-bottom:1px solid white !important;} .overwriteSelect, .fieldSelect, .overwriteCheckboxes, .fieldCheckboxes{background: black !important;} .fieldCheckboxes label:hover, .overwriteCheckboxes label:hover {background-color:   #282828 !important;} #tabs{background:black !important; color: white !important;} .tablinks:hover{background:gray !important;} .tablinks{color: white !important;} .active{background-image: linear-gradient(#272828, black); border-left: 1px solid white !important;border-right: 1px solid white !important;} .dictionaryTitleBlock{border-top: 2px solid white;border-bottom: 1px solid white;} .imageLoader, .forvoLoader{background-image: linear-gradient(#272828, black); color: white; border: 1px solid gray;}.definitionSideBar{border: 2px solid white;}</style>'
        htmlPath = os.path.join(self.addonPath, "dictionaryInit.html")

        with open(htmlPath, "r", encoding="utf-8") as fh:
            html = fh.read()
            fontSizes = self.config["fontSizes"]
            f1 = str(fontSizes[0])
            f2 = str(fontSizes[1])
            html = html.replace(
                "var fefs = 12, dbfs = 22;", "var fefs = " + f1 + ", dbfs = " + f2 + ";"
            )
            html = html.replace(
                '<style id="fontSpecs">.foundEntriesList{font-size: 12px;}.termPronunciation,.definitionBlock{font-size: 20px;}</style>',
                '<style id="fontSpecs">.foundEntriesList{font-size: '
                + f1
                + "px;}.termPronunciation,.definitionBlock{font-size: "
                + f2
                + "px;}.ankiExportButton img{height:"
                + f2
                + "px; width:"
                + f2
                + "px;}</style>",
            )
            if not day:
                html = html.replace('<style id="nightModeCss"></style>', nightStyle)
                html = html.replace("var nightMode = false;", "var nightMode = true;")
            if not willSearch:
                html = html.replace(
                    '<script id="initialValue"></script>',
                    '<script id="initialValue">addNewTab(\''
                    + self.welcome
                    + "'); document.getElementsByClassName('tablinks')[0].classList.add('active');</script>",
                )
            url = qt.QUrl.fromLocalFile(htmlPath)

        return html, url

    def _getAllGroups(self) -> typer.DictionaryGroup2:
        return {
            "dictionaries": self.db.getAllDictsWithLang(),
            "customFont": False,
            "font": "",
        }

    def _getInsertHTMLJS(self) -> str:
        insertHTML = os.path.join(self.addonPath, "js", "insertHTML.js")
        with open(insertHTML, "r", encoding="utf-8") as insertHTMLFile:
            return insertHTMLFile.read()

    def _focusWindow(self) -> None:
        self.show()
        if self.windowState() == qt.Qt.WindowState.WindowMinimized:
            self.setWindowState(qt.Qt.WindowState.WindowNoState)
        self.setFocus()
        self.activateWindow()

    def _resetDict(self, willSearch: bool, terms: list[str]) -> None:
        newDict = MIDict(
            self, self.db, self.addonPath, self.nightModeToggler.day, terms
        )
        newDict.setSType(self._sType)
        html, url = self._getHTMLURL(willSearch, self.nightModeToggler.day)
        newDict.loadHTMLURL(html, url)
        newDict.setSType(self._sType)
        if self.dict.addWindow and self.dict.addWindow.scrollArea.isVisible():
            # TODO: @colin.kennedy - Do we actually need to do this?
            self.dict.addWindow.saveSizeAndPos()
            self.dict.addWindow.scrollArea.close()
            self.dict.addWindow.scrollArea.deleteLater()
        self.currentTarget.setText("")
        self.dict.currentEditor = None
        self.dict.reviewer = None
        self.mainLayout.replaceWidget(self.dict, newDict)
        self.dict.close()
        self.dict.deleteLater()
        self.dict = newDict
        if self.config["deinflect"]:
            self.dict.deinflect = True
        else:
            self.dict.deinflect = False

    def _getUserGroups(self) -> dict[str, typer.DictionaryGroup2]:
        groups = self.config["DictionaryGroups"]
        userGroups: dict[str, typer.DictionaryGroup2] = {}

        for name, group in groups.items():
            userGroups[name] = {
                "dictionaries": self.db.getUserGroups(group["dictionaries"]),
                "customFont": group["customFont"],
                "font": group["font"],
            }

        return userGroups

    def _setupView(self) -> qt.QVBoxLayout:
        layoutV = qt.QVBoxLayout()
        layoutH = qt.QHBoxLayout()
        self.toolbarTopLayout = layoutH
        layoutH.addWidget(self.dictGroups)

        layoutH.addWidget(self._sType)

        layoutH.addWidget(self.search)
        layoutH.addWidget(self.searchButton)
        if not utils.is_win:
            self.dictGroups.setFixedSize(108, 38)
            self.search.setFixedSize(104, 38)
            self._sType.setFixedSize(92, 38)

        else:
            self._sType.setFixedHeight(38)
            self.dictGroups.setFixedSize(110, 38)
            self.search.setFixedSize(114, 38)

        layoutH.setContentsMargins(1, 1, 0, 0)
        layoutH.setSpacing(1)
        self.layoutH2.addWidget(self.openSB)

        self.layoutH2.addWidget(self.minusB)
        self.layoutH2.addWidget(self.plusB)
        self.layoutH2.addWidget(self.tabB)
        self.layoutH2.addWidget(self.histB)
        self.layoutH2.addWidget(self.conjToggler)
        self.layoutH2.addWidget(self.nightModeToggler)
        self.layoutH2.addWidget(self.setB)
        self.targetLabel.setFixedHeight(38)
        self.layoutH2.addWidget(self.targetLabel)
        self.currentTarget.setFixedHeight(38)
        self.layoutH2.addWidget(self.currentTarget)
        if not self.config["showTarget"]:
            self.currentTarget.hide()
            self.targetLabel.hide()
        self.layoutH2.addStretch()
        self.layoutH2.setContentsMargins(0, 1, 0, 0)
        self.layoutH2.setSpacing(1)
        self.mainHLay.setContentsMargins(0, 0, 0, 0)
        self.mainHLay.addLayout(layoutH)
        self.mainHLay.addLayout(self.layoutH2)
        self.mainHLay.addStretch()
        layoutV.addLayout(self.mainHLay)
        layoutV.addWidget(self.dict)
        layoutV.setContentsMargins(0, 0, 0, 0)
        layoutV.setSpacing(1)
        return layoutV

    def _toggleMenuBar(self, vertical: bool) -> None:
        if vertical:
            self.mainHLay.removeItem(self.layoutH2)
            self.mainLayout.insertLayout(1, self.layoutH2)
        else:
            self.mainLayout.removeItem(self.layoutH2)
            self.mainHLay.insertLayout(1, self.layoutH2)

    def _resizeEvent(self, event: typing.Optional[qt.QResizeEvent]) -> None:
        w = self.width()
        if w < 702 and not self.verticalBar:
            self.verticalBar = True
            self._toggleMenuBar(True)
        elif w > 701 and self.verticalBar:
            self.verticalBar = False
            self._toggleMenuBar(False)

        if event:
            event.accept()

    def _setupSearchButton(self) -> SVGPushButton:
        searchB = SVGPushButton(40, 40)
        self._setSvg(searchB, "search")
        searchB.clicked.connect(self.initSearch)
        return searchB

    def _setupOpenSB(self) -> SVGPushButton:
        openSB = SVGPushButton(40, 40)
        self._setSvg(openSB, "sidebaropen")
        openSB.clicked.connect(self._toggleSB)
        return openSB

    def _toggleSB(self) -> None:
        if not self.openSB.opened:
            self.openSB.opened = True
            self._setSvg(self.openSB, "sidebarclose")
        else:
            self.openSB.opened = False
            self._setSvg(self.openSB, "sidebaropen")
        self.dict.eval("openSidebar()")

    def _setupTabMode(self) -> SVGPushButton:
        TabMode = SVGPushButton(34, 34)
        if self.config["onetab"]:
            TabMode.singleTab = True
            icon = "onetab"
        else:
            TabMode.singleTab = False
            icon = "tabs"
        self._setSvg(TabMode, icon)
        TabMode.clicked.connect(self._toggleTabMode)
        return TabMode

    def _toggleTabMode(self) -> None:
        if self.tabB.singleTab:
            self.tabB.singleTab = False
            self._setSvg(self.tabB, "tabs")
            self.writeConfig("onetab", False)
        else:
            self.tabB.singleTab = True
            self._setSvg(self.tabB, "onetab")
            self.writeConfig("onetab", True)

    def _setupConjugationMode(self) -> SVGPushButton:
        conjugationMode = SVGPushButton(40, 40)
        if self.config["deinflect"]:
            self.dict.deinflect = True
            icon = "conjugation"
        else:
            self.dict.deinflect = False
            icon = "closedcube"
        self._setSvg(conjugationMode, icon)
        conjugationMode.clicked.connect(self._toggleConjugationMode)
        return conjugationMode

    def _setupOpenHistory(self) -> SVGPushButton:
        history = SVGPushButton(40, 40)
        self._setSvg(history, "history")
        history.clicked.connect(self._openHistory)
        return history

    def _openHistory(self) -> None:
        if not self.historyBrowser.isVisible():
            self.historyBrowser.show()

    def _toggleConjugationMode(self) -> None:
        if not self.dict.deinflect:
            self._setSvg(self.conjToggler, "conjugation")
            self.dict.deinflect = True
            self.writeConfig("deinflect", True)

        else:
            self._setSvg(self.conjToggler, "closedcube")
            self.dict.deinflect = False
            self.writeConfig("deinflect", False)

    def _loadDay(self) -> None:
        self.setPalette(self.ogPalette)
        if not utils.is_win:
            self.setStyleSheet(self._getMacOtherStyles())
            self.dictGroups.setStyleSheet(self.getMacComboStyle())
            self._sType.setStyleSheet(self.getMacComboStyle())
            self._setAllIcons()

        else:
            self.setStyleSheet("")
            self.dictGroups.setStyleSheet("")
            self._sType.setStyleSheet("")
            self._setAllIcons()
        if self.historyBrowser:
            self.historyBrowser.setColors()
        if self.dict.addWindow:
            self.dict.addWindow.setColors()

    def _loadNight(self) -> None:
        if not utils.is_win:
            self.setStyleSheet(self._getMacNightStyles())
            self.dictGroups.setStyleSheet(self.getMacNightComboStyle())
            self._sType.setStyleSheet(self.getMacNightComboStyle())
        else:
            self.setStyleSheet(self._getOtherStyles())
            self.dictGroups.setStyleSheet(self.getComboStyle())
            self._sType.setStyleSheet(self.getComboStyle())
        self.setPalette(self.nightPalette)
        self._setAllIcons()
        if self.dict.addWindow:
            self.dict.addWindow.setColors()
        if self.historyBrowser:
            self.historyBrowser.setColors()

    def _toggleNightMode(self) -> None:
        if not self.nightModeToggler.day:
            self.nightModeToggler.day = True
            self.writeConfig("day", True)
            self.dict.eval("nightModeToggle(false)")
            self._setSvg(self.nightModeToggler, "theme")
            self._loadDay()
        else:
            self.nightModeToggler.day = False
            self.dict.eval("nightModeToggle(true)")
            self._setSvg(self.nightModeToggler, "theme")
            self.writeConfig("day", False)
            self._loadNight()

    def _setSvg(self, widget: SVGPushButton, name: str) -> None:
        if self.nightModeToggler.day:
            widget._setSvg(os.path.join(self.iconpath, "dictsvgs", name + ".svg"))

        widget._setSvg(os.path.join(self.iconpath, "dictsvgs", name + "night.svg"))

    def _setAllIcons(self) -> None:
        self._setSvg(self.setB, "settings")
        self._setSvg(self.plusB, "plus")
        self._setSvg(self.minusB, "minus")
        self._setSvg(self.histB, "history")
        self._setSvg(self.searchButton, "search")
        self._setSvg(self.tabB, self._getTabStatus())
        self._setSvg(self.openSB, self._getSBStatus())
        self._setSvg(self.conjToggler, self._getConjStatus())

    def _getConjStatus(
        self,
    ) -> typing.Union[typing.Literal["closedcube"], typing.Literal["conjugation"]]:
        if self.dict.deinflect:
            return "conjugation"

        return "closedcube"

    def _getSBStatus(
        self,
    ) -> typing.Union[typing.Literal["sidebarclose"], typing.Literal["sidebaropen"]]:
        if self.openSB.opened:
            return "sidebarclose"

        return "sidebaropen"

    def _getTabStatus(
        self,
    ) -> typing.Union[typing.Literal["onetab"], typing.Literal["tabs"]]:
        if self.tabB.singleTab:
            return "onetab"

        return "tabs"

    def _setupNightModeToggle(self) -> SVGPushButton:
        nightToggle = SVGPushButton(40, 40)
        nightToggle.day = self.config["day"]
        nightToggle.clicked.connect(self._toggleNightMode)

        return nightToggle

    def _setupOpenSettings(self) -> SVGPushButton:
        settings = SVGPushButton(40, 40)
        self._setSvg(settings, "settings")
        settings.clicked.connect(self._openDictionarySettings)

        return settings

    def _openDictionarySettings(self) -> None:
        if not migaku_settings.get_unsafe():
            migaku_settings.initialize(
                addonSettings.SettingsGui(
                    self.mw, self.addonPath, self._openDictionarySettings
                )
            )

        settings = migaku_settings.get()
        settings.show()

        if settings.windowState() == qt.Qt.WindowState.WindowMinimized:
            # Window is minimized. Restore it.
            settings.setWindowState(qt.Qt.WindowState.WindowNoState)

        settings.setFocus()
        settings.activateWindow()

    def _setupPlus(self) -> SVGPushButton:
        plusB = SVGPushButton(40, 40)
        self._setSvg(plusB, "plus")
        plusB.clicked.connect(self._incFont)
        return plusB

    def _setupMinus(self) -> SVGPushButton:
        minusB = SVGPushButton(40, 40)
        self._setSvg(minusB, "minus")
        minusB.clicked.connect(self._decFont)
        return minusB

    def _decFont(self) -> None:
        self.dict.eval("scaleFont(false)")

    def _incFont(self) -> None:
        self.dict.eval("scaleFont(true)")

    def _setupDictGroups(
        self, dictGroups: typing.Optional[qt.QComboBox] = None
    ) -> qt.QComboBox:

        def _get_item(model: qt.QStandardItemModel, index: int) -> qt.QStandardItem:
            item = model.item(index)

            if item:
                return item

            raise RuntimeError(f'Model "{model}" has no "{index}" index.')

        if not dictGroups:
            dictGroups = qt.QComboBox()
            dictGroups.setFixedHeight(30)
            dictGroups.setFixedWidth(80)
            dictGroups.setContentsMargins(0, 0, 0, 0)

        model = dictGroups.model()

        if not model:
            raise RuntimeError("No dictionary group model could be found.")

        if not isinstance(model, qt.QStandardItemModel):
            raise RuntimeError(
                f'Expected QAbstractItemModel, from "{dictGroups}" '
                f'but got "{model}" instead.',
            )

        get_item = functools.partial(_get_item, model)

        ug = sorted(list(self.userGroups.keys()))
        dictGroups.addItems(ug)
        dictGroups.addItem("──────")
        item = get_item(dictGroups.count() - 1)
        item.setEnabled(False)
        item.setTextAlignment(qt.Qt.AlignmentFlag.AlignCenter)
        defaults = ["All", "Google Images", "Forvo"]
        dictGroups.addItems(defaults)
        dictGroups.addItem("──────")
        item = get_item(dictGroups.count() - 1)
        item.setEnabled(False)
        item.setTextAlignment(qt.Qt.AlignmentFlag.AlignCenter)
        dg = sorted(list(self.defaultGroups.keys()))
        dictGroups.addItems(dg)
        current = self.config["currentGroup"]
        if current in dg or current in ug or current in defaults:
            dictGroups.setCurrentText(current)
        group = typing.cast(typer.GroupName, dictGroups.currentText())
        dictGroups.currentIndexChanged.connect(
            lambda: self.writeConfig("currentGroup", group)
        )
        return dictGroups

    def _setupSearchType(self) -> qt.QComboBox:
        searchTypes = qt.QComboBox()
        searchTypes.addItems(self.searchOptions)
        current = self.config["searchMode"]
        if current in self.searchOptions:
            searchTypes.setCurrentText(current)
        searchTypes.setFixedHeight(30)
        searchTypes.setFixedWidth(80)
        searchTypes.setContentsMargins(0, 0, 0, 0)
        text = typing.cast(typer.SearchMode, searchTypes.currentText())
        searchTypes.currentIndexChanged.connect(
            lambda: self.writeConfig("searchMode", text)
        )
        return searchTypes

    def _getSelectedDictGroup(self) -> typer.DictionaryGroup2:
        cur = self.dictGroups.currentText()

        if cur in self.userGroups:
            return self.userGroups[cur]
        if cur == "All":
            return self.allGroups
        if cur == "Google Images":
            return {
                "dictionaries": [{"dict": "Google Images", "lang": ""}],
                "customFont": False,
                "font": "",
            }
        if cur == "Forvo":
            return {
                "dictionaries": [{"dict": "Forvo", "lang": ""}],
                "customFont": False,
                "font": "",
            }
        # TODO: @ColinKennedy - I don't think this code ever ran.
        # if cur in self.defaultGroups:
        #     return self.defaultGroups[cur]

        raise RuntimeError(
            f'Dictionary Group "{cur}" could not be mapped to a dict object.'
        )

    def _cleanTermBrackets(self, term: str) -> str:
        return re.sub(
            r"(?:\[.*\])|(?:\(.*\))|(?:《.*》)|(?:（.*）)|\(|\)|\[|\]|《|》|（|）",
            "",
            term,
        )[:30]

    def _addToHistory(self, term: str) -> None:
        date = str(datetime.date.today())
        self.historyModel.insertRows(term=term, date=date)
        self.saveHistory()

    def _getHistory(self) -> list[list[str]]:
        path = os.path.join(self.mw.col.media.dir(), "_searchHistory.json")
        if not os.path.exists(path):
            return []

        # TODO: @ColinKennedy - remove try/except, maybe. Or log it
        try:
            with open(path, "r", encoding="utf-8") as histFile:
                return [_validate_strings(item) for item in json.loads(histFile.read())]
        except:
            return []

    def _setupSearch(self) -> qt.QLineEdit:
        searchBox = qt.QLineEdit()
        searchBox.setFixedHeight(30)
        searchBox.setFixedWidth(100)
        searchBox.returnPressed.connect(self.initSearch)
        searchBox.setContentsMargins(0, 0, 0, 0)
        return searchBox

    def _getMacOtherStyles(self) -> str:
        return """
            QLabel {color: black;}
            QLineEdit {color: black; background: white;}
            QPushButton {border: 1px solid black; border-radius: 5px; color: black; background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);}
            QPushButton:hover{background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver); border-right: 2px solid black; border-bottom: 2px solid black;}"
            """

    def _getMacNightStyles(self) -> str:
        return """
            QLabel {color: white;}
            QLineEdit {color: white;}
            QPushButton {border: 1px solid gray; border-radius: 5px; color: white; background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);}
            QPushButton:hover{background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black); border: 1px solid white;}"
            """

    def _getOtherStyles(self) -> str:
        return """
            QLabel {color: white;}
            QLineEdit {color: white; background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);}
            QPushButton {border: 1px solid gray; border-radius: 5px; color: white; background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);}
            QPushButton:hover{background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black); border: 1px solid white;}"
            """

    def getMacComboStyle(self) -> str:
        return (
            """
QComboBox {color: black; border-radius: 3px; border: 1px solid black;}
QComboBox:hover {border: 1px solid black;}
QComboBox:editable {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);
}

QComboBox:!editable, QComboBox::drop-down:editable {
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);

}

QComboBox:!editable:on, QComboBox::drop-down:editable:on {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);

}

QComboBox:on {
    padding-top: 3px;
    padding-left: 4px;

}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    max-width:20px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;

}


QComboBox QAbstractItemView
    {
    min-width: 130px;
    }

QCombobox:selected{
    background: white;
}

QComboBox::down-arrow {
    image: url("""
            + os.path.join(self.iconpath, "blackdown.png").replace("\\", "/")
            + """);
}

QComboBox::down-arrow:on {
    top: 1px;
    left: 1px;
}

QComboBox QAbstractItemView{ width: 130px !important; background: white; border: 0px;color:black; selection-background-color: silver;}

QAbstractItemView:selected {
background:white;}

QScrollBar:vertical {
        border: 1px solid black;
        background:white;
        width:17px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);

    }
    QScrollBar::add-line:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);

        height: 0px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }
    QScrollBar::sub-line:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);

        height: 0 px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }"""
        )

    def getMacTableStyle(self) -> str:
        return """
        QAbstractItemView{color:black;}

        QHeaderView {
            color: black;
            background: silver;
            }
        QHeaderView::section
        {
            color:black;
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 white, stop: 1 silver);
            border: 1px solid black;
        }

        """

    def getComboStyle(self) -> str:
        return (
            """
QComboBox {color: white; border-radius: 3px; border: 1px solid gray;}
QComboBox:hover {border: 1px solid white;}
QComboBox:editable {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);
}

QComboBox:!editable, QComboBox::drop-down:editable {
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

}

QComboBox:!editable:on, QComboBox::drop-down:editable:on {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

}

QComboBox:on {
    padding-top: 3px;
    padding-left: 4px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QCombobox:selected{
    background: gray;
}

QComboBox::down-arrow {
    image: url("""
            + os.path.join(self.iconpath, "down.png").replace("\\", "/")
            + """);
}

QComboBox::down-arrow:on {
    top: 1px;
    left: 1px;
}

QComboBox QAbstractItemView{background: #272828; border: 0px;color:white; selection-background-color: gray;}

QAbstractItemView:selected {
background:gray;}

QScrollBar:vertical {
        border: 1px solid white;
        background:white;
        width:17px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

    }
    QScrollBar::add-line:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

        height: 0px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }
    QScrollBar::sub-line:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

        height: 0 px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }"""
        )

    def getConfig(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration,
            self.mw.addonManager.getConfig(__name__),
        )

    def getTableStyle(self) -> str:
        return """
        QAbstractItemView{color:white;}

        QHeaderView {
            background: black;
            }
        QHeaderView::section
        {
            color:white;
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);
            border: 1px solid white;
        }
         QTableWidget, QTableView {
         color:white;
         background-color: #272828;
         selection-background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);
     }
        QTableWidget QTableCornerButton::section, QTableView QTableCornerButton::section{
         background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);
         border: 1px solid white;
     }

        """

    def getMacNightComboStyle(self) -> str:
        return (
            """
QComboBox {color: white; border-radius: 3px; border: 1px solid gray;}
QComboBox:hover {border: 1px solid white;}
QComboBox:editable {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);
}

QComboBox:!editable, QComboBox::drop-down:editable {
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

}

QComboBox:!editable:on, QComboBox::drop-down:editable:on {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

}

QComboBox:on {
    padding-top: 3px;
    padding-left: 4px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QCombobox:selected{
    background: gray;
}

QComboBox QAbstractItemView
    {
    min-width: 130px;
    }

QComboBox::down-arrow {
    image: url("""
            + os.path.join(self.iconpath, "down.png").replace("\\", "/")
            + """);
}

QComboBox::down-arrow:on {
    top: 1px;
    left: 1px;
}

QComboBox QAbstractItemView{background: #272828; border: 0px;color:white; selection-background-color: gray;}

QAbstractItemView:selected {
background:gray;}

QScrollBar:vertical {
        border: 1px solid white;
        background:white;
        width:17px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

    }
    QScrollBar::add-line:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

        height: 0px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }
    QScrollBar::sub-line:vertical {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #272828, stop: 1 black);

        height: 0 px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }"""
        )

    def ensureVisible(self) -> None:
        if not self.isVisible():
            self.show()
        if self.windowState() == qt.Qt.WindowState.WindowMinimized:
            self.setWindowState(qt.Qt.WindowState.WindowNoState)
        self.setFocus()
        self.activateWindow()

    def initSearch(self, term: typing.Optional[str] = None) -> None:
        self.ensureVisible()
        selectedGroup = self._getSelectedDictGroup()

        if not term:
            term = self.search.text()
            term = term.strip()
        term = term.strip()
        term = self._cleanTermBrackets(term)
        if term == "":
            return
        self.search.setText(term.strip())
        self._addToHistory(term)
        self.dict.addNewTab(term, selectedGroup)
        self.search.setFocus()

    def resetConfiguration(self, terms: list[str]) -> None:
        terms = self._refineToValidSearchTerms(terms)
        willSearch = False

        if terms:
            willSearch = True

        self.search.setText("")
        self.allGroups = self._getAllGroups()
        self.config = self.getConfig()
        self.defaultGroups = self.db.getDefaultGroups()
        self.userGroups = self._getUserGroups()
        self.dictGroups.currentIndexChanged.disconnect()
        newDictGroupsCombo = self._setupDictGroups()
        self.toolbarTopLayout.replaceWidget(self.dictGroups, newDictGroupsCombo)
        self.dictGroups.close()
        self.dictGroups.deleteLater()
        self.dictGroups = newDictGroupsCombo
        previouslyOnTop = self.alwaysOnTop
        self.alwaysOnTop = self.config["dictAlwaysOnTop"]
        if previouslyOnTop != self.alwaysOnTop:
            self._setAlwaysOnTop()
        self._setAlwaysOnTop()
        if not self.config["showTarget"]:
            self.currentTarget.hide()
            self.targetLabel.hide()
        else:
            self.targetLabel.show()
            self.currentTarget.show()
        if self.config["tooltips"]:
            self.dictGroups.setToolTip("Select the dictionary group.")
        if not utils.is_win:
            self.dictGroups.setFixedSize(108, 38)
        else:
            self.dictGroups.setFixedSize(110, 38)
        if self.nightModeToggler.day:
            if not utils.is_win:
                self.dictGroups.setStyleSheet(self.getMacComboStyle())
            else:
                self.dictGroups.setStyleSheet("")
        else:
            if not utils.is_win:
                self.dictGroups.setStyleSheet(self.getMacNightComboStyle())
            else:
                self.dictGroups.setStyleSheet(self.getComboStyle())
        self._resetDict(willSearch, terms)

    def saveHistory(self) -> None:
        path = os.path.join(self.mw.col.media.dir(), "_searchHistory.json")

        with codecs.open(path, "w", "utf-8") as outfile:
            json.dump(self.historyModel.history, outfile, ensure_ascii=False)

    def saveSizeAndPos(self) -> None:
        pos = self.pos()
        x = pos.x()
        y = pos.y()
        size = self.size()
        width = size.width()
        height = size.height()
        posSize = [x, y, width, height]
        self.writeConfig("dictSizePos", posSize)

    def updateAddType(self, dictName: str, addType: str) -> None:
        self.db.setAddType(dictName, addType)

    def updateFieldsSetting(self, dictName: str, fields: list[str]) -> None:
        self.db.setFieldsSetting(dictName, json.dumps(fields, ensure_ascii=False))

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["GoogleImageAddType"], value: typer.AddType
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["GoogleImageFields"], value: list[str]
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["ForvoAddType"], value: typer.AddType
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["ForvoFields"], value: list[str]
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["currentDeck"], value: str
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self,
        attribute: typing.Literal["currentGroup"],
        value: typer.GroupName,
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self,
        attribute: typing.Literal["currentTemplate"],
        value: str,
    ) -> None: ...

    @typing.overload
    def writeConfig(self, attribute: typing.Literal["day"], value: bool) -> None: ...

    @typing.overload
    def writeConfig(
        self,
        attribute: typing.Literal["deinflect"],
        value: bool,
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["dictSizePos"], value: list[int]
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self,
        attribute: typing.Literal["exporterSizePos"],
        value: tuple[int, int, int, int],
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["exporterLastTags"], value: str
    ) -> None: ...

    @typing.overload
    def writeConfig(
        self, attribute: typing.Literal["fontSizes"], value: tuple[int, int]
    ) -> None: ...

    @typing.overload
    def writeConfig(self, attribute: typing.Literal["onetab"], value: bool) -> None: ...

    @typing.overload
    def writeConfig(
        self,
        attribute: typing.Literal["searchMode"],
        value: typer.SearchMode,
    ) -> None: ...

    def writeConfig(self, attribute: str, value: typing.Any) -> None:
        if attribute == "exporterSizePos":
            value = list(value)

        newConfig = self.getConfig()
        newConfig[attribute] = value  # type: ignore[literal-required]
        self.mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], newConfig),
        )
        self._reloadConfig(newConfig)

    # TODO: @ColinKennedy - return bool?
    def closeEvent(self, event: typing.Optional[qt.QCloseEvent]) -> None:
        self.hide()

    # TODO: @ColinKennedy - return bool?
    def hideEvent(self, event: typing.Optional[qt.QHideEvent]) -> None:
        self.saveSizeAndPos()

        if event:
            event.accept()


class MigakuSVG(QtSvgWidgets.QSvgWidget):
    clicked = qt.pyqtSignal()

    def __init__(self, parent: typing.Optional[qt.QWidget] = None):
        super().__init__(parent)

    # TODO: @ColinKennedy - Do I need return bool?
    def mousePressEvent(self, ev: typing.Optional[qt.QMouseEvent]) -> None:
        self.clicked.emit()


class SVGPushButton(qt.QPushButton):
    def __init__(
        self,
        width: int,
        height: int,
        parent: typing.Optional[qt.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.singleTab = False
        self.day: bool = False
        self.opened = False

        self.setFixedHeight(40)
        self.setFixedWidth(43)
        self.svgWidth = width
        self.svgHeight = height
        self._main_layout = qt.QHBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._main_layout)

    def _setSvg(self, svgPath: str) -> None:
        for i in reversed(range(self._main_layout.count())):
            item = self._main_layout.itemAt(i)

            if not item:
                raise RuntimeError(f'Expected layout item at "{i}" but got nothing.')

            widget = item.widget()

            if not widget:
                raise RuntimeError(
                    f'Expected layout item at "{i}" to have a widget but got nothing.'
                )

            widget.setParent(None)

        svg = QtSvgWidgets.QSvgWidget(svgPath)
        svg.setFixedSize(self.svgWidth, self.svgHeight)
        self._main_layout.addWidget(svg)


def _validate_add_type(item: typing.Any) -> _AddTypeGroup:
    # TODO: @ColinKennedy - Check this later
    return typing.cast(_AddTypeGroup, item)


def _validate_strings(item: typing.Any) -> list[str]:
    try:
        iter(item)
    except TypeError:
        return []

    output: list[str] = []

    for value in item:
        if not isinstance(value, str):
            raise RuntimeError(f'Value "{value}" is not a string.')

        output.append(item)

    return output


def _verify(item: typing.Optional[T]) -> T:
    if item is not None:
        return item

    raise RuntimeError("Expected item to exist but got none.")


def dictionaryInit(terms: typing.Union[list[str], str, None] = None) -> None:
    # TODO: @ColinKennedy - Remove the cyclic dependency later
    from . import migaku_dictionary

    if terms and isinstance(terms, str):
        terms = [terms]

    terms = typing.cast(list[str], terms)

    if not migaku_dictionary.get_unsafe():
        migaku_dictionary.set(
            DictInterface(
                dictdb_.get(),
                aqt.mw,
                _CURRENT_DIRECTORY,
                welcomer.welcomeScreen(),
                terms=terms,
            )
        )
        showAfterGlobalSearch()
    elif not migaku_dictionary.get_visible_dictionary():
        dictionary = migaku_dictionary.get()
        dictionary.show()
        dictionary.resetConfiguration(terms or [])
        showAfterGlobalSearch()
    else:
        dictionary = migaku_dictionary.get()
        dictionary.hide()


def showAfterGlobalSearch() -> None:
    # TODO: @ColinKennedy - Remove the cyclic dependency later
    from . import migaku_dictionary

    dictionary = migaku_dictionary.get()
    dictionary.activateWindow()

    if not utils.is_win:
        dictionary.setWindowState(
            dictionary.windowState() & ~qt.Qt.WindowState.WindowMinimized
            | qt.Qt.WindowState.WindowActive
        )
        dictionary.raise_()

        return

    dictionary.setWindowFlags(
        dictionary.windowFlags() | qt.Qt.WindowType.WindowStaysOnTopHint
    )
    dictionary.show()

    if not dictionary.alwaysOnTop:
        dictionary.setWindowFlags(
            dictionary.windowFlags() & ~qt.Qt.WindowType.WindowStaysOnTopHint
        )
        dictionary.show()
