# -*- coding: utf-8 -*-
#
import argparse
import base64
import json
import os
import re
import typing
import urllib

import requests
from aqt import qt

languages = {
    "German": "de",
    "Tatar": "tt",
    "Russian": "ru",
    "English": "en",
    "Spanish": "es",
    "Japanese": "ja",
    "French": "fr",
    "Portuguese": "pt",
    "Polish": "pl",
    "Dutch": "nl",
    "Italian": "it",
    "Mandarin Chinese": "zh",
    "Ancient Greek": "grc",
    "Swedish": "sv",
    "Turkish": "tr",
    "Arabic": "ar",
    "Hungarian": "hu",
    "Korean": "ko",
    "Luxembourgish": "lb",
    "Czech": "cs",
    "Ukrainian": "uk",
    "Greek": "el",
    "Catalan": "ca",
    "Hebrew": "he",
    "Persian": "fa",
    "Mari": "chm",
    "Finnish": "fi",
    "Cantonese": "yue",
    "Urdu": "ur",
    "Esperanto": "eo",
    "Danish": "da",
    "Bulgarian": "bg",
    "Latin": "la",
    "Lithuanian": "lt",
    "Romanian": "ro",
    "Min Nan": "nan",
    "Norwegian Bokmål": "no",
    "Vietnamese": "vi",
    "Icelandic": "is",
    "Croatian": "hr",
    "Irish": "ga",
    "Basque": "eu",
    "Wu Chinese": "wuu",
    "Belarusian": "be",
    "Latvian": "lv",
    "Bashkir": "ba",
    "Kabardian": "kbd",
    "Hindi": "hi",
    "Slovak": "sk",
    "Punjabi": "pa",
    "Low German": "nds",
    "Serbian": "sr",
    "Hakka": "hak",
    "Uyghur": "ug",
    "Azerbaijani": "az",
    "Thai": "th",
    "Indonesian": "ind",
    "Estonian": "et",
    "Slovenian": "sl",
    "Tagalog": "tl",
    "Venetian": "vec",
    "Northern Sami": "sme",
    "Yiddish": "yi",
    "Galician": "gl",
    "Bengali": "bn",
    "Afrikaans": "af",
    "Welsh": "cy",
    "Interlingua": "ia",
    "Armenian": "hy",
    "Chuvash": "cv",
    "Kurdish": "ku",
}


class ForvoSignals(qt.QObject):
    resultsFound = qt.pyqtSignal(list)
    noResults = qt.pyqtSignal(str)
    finished = qt.pyqtSignal()


class Forvo(qt.QRunnable):
    resultsFound = qt.pyqtSignal(list)
    noResults = qt.pyqtSignal(str)

    def __init__(self, language: str) -> None:
        super().__init__()

        self._selLang = language
        self._langShortCut = languages[self._selLang]
        self._GOOGLE_SEARCH_URL = (
            "https://forvo.com/word/◳t/#" + self._langShortCut
        )  # ◳r
        self._session = requests.session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:10.0) \
                    Gecko/20100101 Firefox/10.0"
            }
        )
        self.signals = ForvoSignals()

    def _attemptFetchForvoLinks(
        self, term: str
    ) -> typing.Union[str, typing.Literal[False]]:
        urls = self.search(term)
        if len(urls) > 0:
            return json.dumps(urls)

        # TODO: @ColinKennedy remove False?
        return False

    def _forvo_search(self, query_gen: str) -> list[tuple[str, str, str, str]]:
        try:
            html = self._session.get(query_gen).text
        except:
            self.signals.noResults.emit(
                "The Forvo Dictionary could not be loaded, please confirm that your are connected to the internet and try again. "
            )
            return []
        results = html

        return self._generateURLS(results)

    # TODO: @ColinKennedy - Make a more specific type-hint instead of a hard-coded tuple
    def _generateURLS(self, results: str) -> list[tuple[str, str, str, str]]:
        matches = typing.cast(
            list[str], re.findall(r"var pronunciations = \[([\w\W\n]*?)\];", results)
        )
        if not matches:
            return []
        audio = matches[0]
        data = re.findall(
            self._selLang
            + r'.*?Pronunciation by (?:<a.*?>)?(\w+).*?class="lang_xx"\>(.*?)\<.*?,.*?,.*?,.*?,\'(.+?)\',.*?,.*?,.*?\'(.+?)\'',
            audio,
        )
        if not data:
            return []

        match = re.search(r"var _SERVER_HOST=\'(.+?)\';", results)

        if not match:
            raise RuntimeError(f'Results "{results}" has no server host.')

        server = match.group(1)
        match = re.search(r"var _AUDIO_HTTP_HOST=\'(.+?)\';", results)

        if not match:
            raise RuntimeError(f'Results "{results}" has no audio http host.')

        audiohost = match.group(1)
        protocol = "https:"
        urls: list[tuple[str, str, str, str]] = []

        for datum in data:
            url1, url2 = _decodeURL(datum[2], datum[3], protocol, audiohost, server)
            urls.append((datum[0], datum[1], url1, url2))

        return urls

    def setTermIdName(self, term: str, idName: str) -> None:
        self.idName = idName

    def search(
        self,
        term: str,
        lang: typing.Union[str, typing.Literal[False]] = False,
    ) -> list[tuple[str, str, str, str]]:
        if lang and self._selLang != lang:
            self._selLang = lang
            self._langShortCut = languages[self._selLang]
            self._GOOGLE_SEARCH_URL = "https://forvo.com/word/◳t/#" + self._langShortCut
        query = self._GOOGLE_SEARCH_URL.replace(
            "◳t", re.sub(r'[\/\'".,&*@!#()\[\]\{\}]', "", term)
        )
        return self._forvo_search(query)


def _decodeURL(
    url1: str,
    url2: str,
    protocol: str,
    audiohost: str,
    server: str,
) -> tuple[str, str]:
    url2 = protocol + "//" + server + "/player-mp3-highHandler.php?path=" + url2
    url1 = (
        protocol
        + "//"
        + audiohost
        + "/mp3/"
        + base64.b64decode(url1).decode("utf-8", "strict")
    )
    return url1, url2
