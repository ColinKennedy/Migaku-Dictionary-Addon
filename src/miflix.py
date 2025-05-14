from __future__ import annotations

import asyncio
import json
import logging
import os
import os.path
import re
import textwrap
import typing
import uuid
from os.path import dirname, exists, join
from threading import Thread, Timer

import aqt
import tornado.ioloop
import tornado.web
from anki.collection import Collection
from anki.utils import is_win
from aqt import main
from aqt import mw as mw_
from aqt.qt import QThread, pyqtSignal
from tornado import httputil

from . import global_state, threader, typer
from .miutils import miInfo

_LOGGER = logging.getLogger(__name__)
_PseudoNumber = typing.Union[int, str]


class _Field(typing.TypedDict):
    name: str
    ord: str


def getNextBatchOfCards(
    collection: Collection,
    start: _PseudoNumber,
    incrementor: _PseudoNumber,
) -> list[list[str]]:
    database = collection.db

    if not database:
        raise RuntimeError(f'Collection "{collection}" has no database.')

    return typing.cast(
        list[list[str]],
        database.all(
            "SELECT c.ivl, n.flds, c.ord, n.mid FROM cards AS c INNER JOIN notes AS n ON c.nid = n.id WHERE c.type != 0 ORDER BY c.ivl LIMIT %s, %s;"
            % (start, incrementor)
        ),
    )


class MigakuHTTPHandler(tornado.web.RequestHandler):

    def __init__(
        self,
        application: MigakuHTTPServer,
        request: httputil.HTTPServerRequest,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(application, request, **kwargs)
        self.application: MigakuHTTPServer

    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def initialize(self) -> None:
        self.mw = typing.cast(main.AnkiQt, self.application.settings.get("mw"))
        self.addonDirectory = dirname(__file__)
        self.tempDirectory = join(self.addonDirectory, "temp")
        self.alert = self.application.alert
        self.addCondensedAudioInProgressMessage = (
            self.application.addCondensedAudioInProgressMessage
        )
        self.removeCondensedAudioInProgressMessage = (
            self.application.removeCondensedAudioInProgressMessage
        )
        suffix = ""
        if is_win:
            suffix = ".exe"
        self.ffmpeg = join(
            self.addonDirectory, "user_files", "ffmpeg", "ffmpeg" + suffix
        )

    # TODO: @ColinKennedy not sure if this return value is right
    def checkVersion(self) -> bool:
        raw_version = self.get_body_argument("version", default=None)

        if not raw_version:
            # TODO: @ColinKennedy add logging later
            return False

        version = int(raw_version)

        return self.application.checkVersion(version)

    def getConfig(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration, self.mw.addonManager.getConfig(__name__)
        )


class ImportHandler(MigakuHTTPHandler):

    def get(self) -> None:
        self.finish("ImportHandler")

    def ffmpegExists(self) -> bool:
        return exists(self.ffmpeg)

    def removeTempFiles(self) -> None:
        tmpdir = self.tempDirectory
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

    def condenseAudioUsingFFMPEG(
        self,
        filename: str,
        timestamp: str,
        config: typer.Configuration,
    ) -> None:
        wavDir = join(self.tempDirectory, timestamp)
        if exists(wavDir):
            config = self.getConfig()
            mp3dir = config.get("condensedAudioDirectory")

            if not mp3dir:
                raise RuntimeError(f'Configuration "{config}" has no audio directory.')

            wavs = [f for f in os.listdir(wavDir)]
            wavs.sort()
            wavListFilePath = join(wavDir, "list.txt")
            wavListFile = open(wavListFilePath, "w+")
            filename = self.cleanFilename(filename + "\n") + "-condensed.mp3"
            mp3path = join(mp3dir, filename)
            for wav in wavs:
                wavListFile.write("file '{}'\n".format(join(wavDir, wav)))
            wavListFile.close()
            import subprocess

            subprocess.call(
                [
                    self.ffmpeg,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    wavListFilePath,
                    "-write_xing",
                    "0",
                    mp3path,
                ]
            )
            self.removeTempFiles()
            if not config.get("disableCondensed", False):
                self.alert(
                    textwrap.dedent(
                        f"""\
                        A Condensed Audio File has been generated.

                        The file: "{filename or '<No filename found>'}"
                        has been created in dir: {mp3dir}
                        """
                    )
                )

    def cleanFilename(self, filename: str) -> str:
        return re.sub(r"[\n:'\":/\|?*><!]", "", filename).strip()

    def post(self) -> None:
        # TODO: @ColinKennedy - dedent this
        if self.checkVersion():
            thread = threader.get()

            config = self.getConfig()
            previousBulkTimeStamp = self.application.settings.get(
                "previousBulkTimeStamp"
            )

            if self.parseBoolean(
                self.get_body_argument(
                    "pageRefreshCancelBulkMediaExporting", default=None
                )
            ):
                thread.handlePageRefreshDuringBulkMediaImport()
                self.removeCondensedAudioInProgressMessage()
                self.finish("Cancelled through browser.")

                return

            bulk = self.parseBoolean(self.get_body_argument("bulk", default=None))
            bulkExportWasCancelled = self.parseBoolean(
                self.get_body_argument("bulkExportWasCancelled", default=None)
            )
            timestamp = self.get_body_argument("timestamp", default=0)

            if not timestamp:
                raise RuntimeError("No timestamp was found in the body.")

            if bulkExportWasCancelled:
                if (
                    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED
                    and previousBulkTimeStamp == timestamp
                ):
                    self.finish("yes")
                else:
                    self.finish("no")

                return

            requestType = self.get_body_argument("type", default=None)

            if requestType == "finishedRecordingCondensedAudio":
                filename = self.get_body_argument("filename", default="audio")

                if not filename:
                    raise RuntimeError("No audio filename could be found.")

                self.condenseAudioUsingFFMPEG(filename, timestamp, config)
                self.removeCondensedAudioInProgressMessage()

                return

            if bulk and requestType == "text":
                raw_cards = self.get_body_argument("cards", default="[]") or "[]"
                cards = json.loads(raw_cards)
                thread.handleBulkTextExport(cards)
                self.finish("Bulk Text Export")
                return

            else:
                if (
                    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED
                    and previousBulkTimeStamp == timestamp
                ):
                    self.removeCondensedAudioInProgressMessage()
                    self.finish("Exporting was cancelled.")
                    return
                if previousBulkTimeStamp != timestamp or not bulk:
                    self.application.settings["previousBulkTimeStamp"] = timestamp
                    self.removeCondensedAudioInProgressMessage()
                    global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = False
                condensedAudio = self.parseBoolean(
                    self.get_body_argument("condensedAudio", default=None)
                )
                raw_total = self.get_body_argument("totalToRecord", default="1") or "1"
                total = int(raw_total)
                _LOGGER.debug('TOTAL "%s" records.', total)

                if condensedAudio:
                    mp3dir = config.get("condensedAudioDirectory", False)
                    if not mp3dir:
                        self.alert(
                            'You must specify a Condensed Audio Save Location.\n\nYou can do this by:\n1. Navigating to Migaku->Dictionary Settings in Anki\'s menu bar.\n2. Clicking "Choose Directory" for the "Condensed Audio Save Location"  in the bottom right of the settings window.'
                        )
                        global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = True
                        self.removeCondensedAudioInProgressMessage()
                        self.finish("Save location not set.")
                    elif self.ffmpegExists():
                        self.handleAudioFileInRequestAndReturnFilename(
                            self.copyFileToCondensedAudioDir
                        )
                        _LOGGER.info("File saved in temp dir")
                        self.addCondensedAudioInProgressMessage()
                        self.finish("Exporting Condensed Audio")
                    else:
                        self.alert(
                            'The FFMPEG media encoder must be installed in order to export condensedAudio.\n\nIn order to install FFMPEG please enable MP3 Conversion in the Dictionary Settings window and click "Apply".\nFFMPEG will then be downloaded and installed automatically.'
                        )
                        global_state.IS_BULK_MEDIA_EXPORT_CANCELLED = True
                        self.removeCondensedAudioInProgressMessage()
                        self.finish("FFMPEG not installed.")
                    return
                else:
                    audioFileName = self.handleAudioFileInRequestAndReturnFilename(
                        self.copyFileToTempDir
                    )

                    if not audioFileName:
                        self.finish("No audioFileName was found. Cannot continue.")

                        return

                    primary = self.get_body_argument("primary", default="") or ""
                    secondary = self.get_body_argument("secondary", default="") or ""
                    raw_unknown_words = (
                        self.get_body_argument("unknown", default="[]") or "[]"
                    )
                    unknownWords = json.loads(raw_unknown_words)
                    imageFileName: typing.Optional[str] = None
                    if "image" in self.request.files:
                        imageFile = self.request.files["image"][0]
                        imageFileName = imageFile["filename"]

                        if not imageFileName:
                            raise RuntimeError(f'Image File "{imageFile}" has no name.')

                        self.copyFileToTempDir(imageFile, imageFileName)
                    cardToExport: typer.Card = {
                        "primary": primary,
                        "secondary": secondary,
                        "unknownWords": unknownWords,
                        "bulk": bulk,
                        "audio": audioFileName,
                        "image": imageFileName,
                        "total": total,
                    }
                    thread.handleExtensionCardExport(cardToExport)
                    self.finish("Card Exported")
                    return
        self.finish("Invalid Request")

    def handleAudioFileInRequestAndReturnFilename(
        self,
        copyFileFunction: typing.Callable[[httputil.HTTPFile, str], None],
    ) -> typing.Optional[str]:
        if "audio" in self.request.files:
            audioFile = self.request.files["audio"][0]
            audioFileName: str = audioFile["filename"]
            copyFileFunction(audioFile, audioFileName)

            return audioFileName

        return None

    def parseBoolean(self, bulk: typing.Union[bool, str, None]) -> bool:
        if not bulk or bulk == "false":
            return False

        return True

    def copyFileToTempDir(self, handler: httputil.HTTPFile, filename: str) -> None:
        filePath = join(self.tempDirectory, filename)

        with open(filePath, "wb") as handler_:
            handler_.write(handler["body"].encode())

    def copyFileToCondensedAudioDir(
        self, handler: httputil.HTTPFile, filename: str
    ) -> None:
        timestamp_value = self.application.settings.get("previousBulkTimeStamp")

        if not timestamp_value:
            timestamp = "0"
        else:
            timestamp = str(timestamp_value)

        directoryPath = join(self.tempDirectory, timestamp)

        if not exists(directoryPath):
            os.mkdir(directoryPath)

        filePath = join(directoryPath, filename)

        with open(filePath, "wb") as handler_:
            handler_.write(handler["body"].encode())


class LearningStatusHandler(MigakuHTTPHandler):

    def get(self) -> None:
        self.finish("LearningStatusHandler")

    def post(self) -> None:
        if not self.checkVersion():
            self.finish("Invalid Request")

        fetchModels = self.get_body_argument("fetchModelsAndTemplates", default=None)

        if fetchModels:
            self.finish(self.fetchModelsAndTemplates())

            return

        start = self.get_body_argument("start", default=None)

        if start:
            incrementor = self.get_body_argument("incrementor", default=None)

            if not incrementor:
                raise RuntimeError("No incrementor was found.")

            self.finish(self.getCards(start, incrementor))

            return

    def getFieldOrdinateDictionary(
        self,
        fieldEntries: typing.Iterable[_Field],
    ) -> dict[str, str]:
        return {field["name"]: field["ord"] for field in fieldEntries}

    def getFields(
        self,
        templateSide: str,
        fieldOrdinatesDict: dict[str, str],
    ) -> typing.Optional[list[str]]:
        pattern = r"{{([^#^\/][^}]*?)}}"
        matches = re.findall(pattern, templateSide)
        fields = self.getCleanedFieldArray(matches)
        fieldsOrdinates = self.getFieldOrdinates(fields, fieldOrdinatesDict)
        return fieldsOrdinates

    def getFieldOrdinates(
        self,
        fields: typing.Iterable[str],
        fieldOrdinates: dict[str, str],
    ) -> list[str]:
        ordinates: list[str] = []
        for field in fields:
            if field in fieldOrdinates:
                ordinates.append(fieldOrdinates[field])
        return ordinates

    def getCleanedFieldArray(self, fields: typing.Iterable[str]) -> list[str]:
        noDupes: list[str] = []
        for field in fields:
            fieldName = self.getCleanedFieldName(field).strip()
            if not fieldName in noDupes and fieldName not in [
                "FrontSide",
                "Tags",
                "Subdeck",
                "Type",
                "Deck",
                "Card",
            ]:
                noDupes.append(fieldName)
        return noDupes

    def getCleanedFieldName(self, field: str) -> str:
        if ":" in field:
            split = field.split(":")
            return split[len(split) - 1]
        return field

    def fetchModelsAndTemplates(self) -> str:
        modelData = {}
        models = self.mw.col.models.all()
        for idx, model in enumerate(models):
            mid = str(model["id"])
            templates = model["tmpls"]
            templateArray = []
            fieldOrdinates = self.getFieldOrdinateDictionary(model["flds"])
            for template in templates:
                frontFields = self.getFields(template["qfmt"], fieldOrdinates)
                name = template["name"]
                backFields = self.getFields(template["afmt"], fieldOrdinates)

                templateArray.append(
                    {
                        "frontFields": frontFields,
                        "backFields": backFields,
                        "name": name,
                    }
                )
            if mid not in modelData:
                modelData[mid] = {
                    "templates": templateArray,
                    "fields": fieldOrdinates,
                    "name": model["name"],
                }
        return json.dumps(modelData)

    def getCards(self, start: _PseudoNumber, incrementor: _PseudoNumber) -> str:
        cards = getNextBatchOfCards(self.mw.col, start, incrementor)
        bracketPattern = "\[[^]\n]*?\]"
        for card in cards:
            card[1] = re.sub(bracketPattern, "", card[1])
        return json.dumps(cards)


class SearchHandler(MigakuHTTPHandler):

    def get(self) -> None:
        self.finish("SearchHandler")

    def post(self) -> None:
        if self.checkVersion():
            terms = self.get_body_argument("terms", default=None)

            if terms:
                threader.get().handleExtensionSearch(json.loads(terms))
                self.finish("Searched")

                return

        self.finish("Invalid Request")


class MigakuHTTPServer(tornado.web.Application):

    PROTOCOL_VERSION = 2

    def __init__(self, thread: MigakuServerThread, mw: main.AnkiQt) -> None:
        self.mw = mw
        self.previousBulkTimeStamp = 0
        self.thread = thread
        handlers: typing.Sequence[
            tuple[str, typing.Type[tornado.web.RequestHandler]]
        ] = [
            (r"/import", ImportHandler),
            (r"/learning-statuses", LearningStatusHandler),
            (r"/search", SearchHandler),
        ]

        settings: dict[str, typing.Any] = {"mw": mw}
        # TODO: @ColinKennedy - This type is complicated and probably fine to ignore for
        # the long-term. Come back to it later
        #
        super().__init__(handlers, **settings)  # type: ignore[arg-type]

    def run(self, port: int = 12345) -> None:
        self.listen(port)
        tornado.ioloop.IOLoop.instance().start()

    def alert(self, message: str) -> None:
        self.thread.alert(message)

    def addCondensedAudioInProgressMessage(self) -> None:
        self.thread.addCondensedAudioInProgressMessage()

    def removeCondensedAudioInProgressMessage(self) -> None:
        self.thread.removeCondensedAudioInProgressMessage()

    def checkVersion(self, version: typing.Optional[int]) -> bool:
        if version is None or version < self.PROTOCOL_VERSION:
            self.alert(
                "Your Migaku Dictionary Version is newer than and incompatible with your Immerse with Migaku Browser Extension installation. Please ensure you are using the latest version of the add-on and extension to resolve this issue."
            )
            return False
        elif version > self.PROTOCOL_VERSION:
            self.alert(
                "Your Immerse with Migaku Browser Extension Version is newer than and incompatible with this Migaku Dictionary installation. Please ensure you are using the latest version of the add-on and extension to resolve this issue."
            )
            return False
        return True


class MigakuServerThread(QThread):

    alertUser = pyqtSignal(str)
    exportingCondensed = pyqtSignal()
    notExportingCondensed = pyqtSignal()

    def __init__(self, mw: main.AnkiQt) -> None:
        self.mw = mw
        QThread.__init__(self)
        self.server = MigakuHTTPServer(self, mw)
        self.start()

    def run(self) -> None:
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.server.run()

    def alert(self, message: str) -> None:
        self.alertUser.emit(message)

    def addCondensedAudioInProgressMessage(self) -> None:
        self.exportingCondensed.emit()

    def removeCondensedAudioInProgressMessage(self) -> None:
        self.notExportingCondensed.emit()


def addCondensedAudioInProgressMessage() -> None:
    title = mw_.windowTitle()
    msg = " (Condensed Audio Exporting in Progress)"
    if msg not in title:
        mw_.setWindowTitle(title + msg)


def removeCondensedAudioInProgressMessage() -> None:
    title = mw_.windowTitle()
    msg = " (Condensed Audio Exporting in Progress)"
    if msg in title:
        mw_.setWindowTitle(title.replace(msg, ""))


def initialize() -> None:
    serverThread = MigakuServerThread(mw_)
    serverThread.alertUser.connect(miInfo)
    serverThread.exportingCondensed.connect(addCondensedAudioInProgressMessage)
    serverThread.notExportingCondensed.connect(removeCondensedAudioInProgressMessage)
