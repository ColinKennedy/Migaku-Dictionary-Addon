import logging
import os
import stat
import typing
import zipfile

import aqt
import requests
from anki import hooks, utils
from aqt import gui_hooks, main
from aqt import mw as mw_
from aqt import qt

from . import miutils, typer

_LOGGER = logging.getLogger(__name__)


class FFMPEGInstaller:

    def __init__(self, mw: main.AnkiQt) -> None:
        super().__init__()

        self._mw = mw
        self._addonPath = os.path.dirname(__file__)
        self._ffmpegDir = os.path.join(self._addonPath, "user_files", "ffmpeg")
        self._ffmpegFilename = "ffmpeg"
        # TODO: @ColinKennedy download these sources elsewhere
        if utils.is_win:
            self._ffmpegFilename += ".exe"
            self._downloadURL = "http://dicts.migaku.io/ffmpeg/windows"
        elif utils.is_lin:
            self._downloadURL = "http://dicts.migaku.io/ffmpeg/linux"
        elif utils.is_mac:
            self._downloadURL = "http://dicts.migaku.io/ffmpeg/macos"
        self._ffmpegPath = os.path.join(self._ffmpegDir, self._ffmpegFilename)
        self._tempPath = os.path.join(self._addonPath, "temp", "ffmpeg")

    def _get_configuration(self) -> typer.Configuration:
        return typing.cast(
            typer.Configuration, self._mw.addonManager.getConfig(__name__)
        )

    def _getFFMPEGProgressBar(
        self,
        title: str,
        initialText: str,
    ) -> tuple[qt.QWidget, qt.QProgressBar, qt.QLabel]:
        progressWidget = qt.QWidget(None)
        textDisplay = qt.QLabel()
        progressWidget.setWindowIcon(
            qt.QIcon(os.path.join(self._addonPath, "icons", "migaku.png"))
        )
        progressWidget.setWindowTitle(title)
        textDisplay.setText(initialText)
        progressWidget.setFixedSize(500, 100)
        progressWidget.setWindowModality(qt.Qt.WindowModality.ApplicationModal)
        bar = qt.QProgressBar(progressWidget)
        layout = qt.QVBoxLayout()
        layout.addWidget(textDisplay)
        layout.addWidget(bar)
        progressWidget.setLayout(layout)
        bar.move(10, 10)
        per = qt.QLabel(bar)
        per.setAlignment(qt.Qt.AlignmentFlag.AlignCenter)
        progressWidget.show()
        progressWidget.setFocus()

        return progressWidget, bar, textDisplay

    def _closeProgressBar(self, progressBar: qt.QWidget) -> None:
        progressBar.close()
        progressBar.deleteLater()

    def _couldNotInstall(self) -> None:
        self._toggleMP3Conversion(False)
        self._toggleFailedInstallation(True)
        miutils.miInfo(
            "FFMPEG could not be installed. MP3 Conversion has been disabled. You will not be able to convert audio files imported from the Immerse with Migaku Browser Extension to MP3 format until it is installed. Migaku Dictionary will attempt to install it again on the next profile load."
        )

    def _downloadFFMPEG(self) -> bool:
        progressWidget: typing.Optional[qt.QWidget] = None
        try:
            with requests.get(self._downloadURL, stream=True) as ffmpegRequest:
                ffmpegRequest.raise_for_status()
                with open(self._tempPath, "wb") as ffmpegFile:
                    downloadingText = "Downloading FFMPEG...\n{}kb of {}kb downloaded."
                    total = int(ffmpegRequest.headers["Content-Length"])
                    roundedTotal = _roundToKb(total)
                    downloadedSoFar = 0
                    progressWidget, bar, textDisplay = self._getFFMPEGProgressBar(
                        "Migaku Dictionary - FFMPEG Download",
                        downloadingText.format(
                            _roundToKb(downloadedSoFar), roundedTotal
                        ),
                    )
                    bar.setMaximum(total)
                    lastUpdated: typing.Union[float, int] = 0
                    for chunk in ffmpegRequest.iter_content(chunk_size=8192):
                        if chunk:
                            downloadedSoFar += len(chunk)
                            roundedValue = _roundToKb(downloadedSoFar)
                            if roundedValue - lastUpdated > 500:
                                lastUpdated = roundedValue
                                bar.setValue(downloadedSoFar)
                                textDisplay.setText(
                                    downloadingText.format(roundedValue, roundedTotal)
                                )
                                self._mw.app.processEvents()
                            ffmpegFile.write(chunk)

                self._closeProgressBar(progressWidget)
            return True
        except Exception as error:
            _LOGGER.exception("Unabled to download FFMPEG.")
            if progressWidget:
                self._closeProgressBar(progressWidget)
            return False

    def _makeExecutable(self) -> bool:
        if not utils.is_win:
            # TODO: @ColinKennedy - remove try/except later
            try:
                st = os.stat(self._ffmpegPath)
                os.chmod(self._ffmpegPath, st.st_mode | stat.S_IEXEC)
            except:
                return False
        return True

    def _removeFailedInstallation(self) -> None:
        os.remove(self._ffmpegPath)

    def _toggleMP3Conversion(self, enable: bool) -> None:
        config = self._get_configuration()
        config["mp3Convert"] = enable
        self._write_configuration(config)

    def _toggleFailedInstallation(self, failedInstallation: bool) -> None:
        config = self._get_configuration()
        config["failedFFMPEGInstallation"] = failedInstallation
        self._write_configuration(config)

    def _unzipFFMPEG(self) -> None:
        with zipfile.ZipFile(self._tempPath) as zf:
            zf.extractall(self._ffmpegDir)

    def _write_configuration(self, configuration: typer.Configuration) -> None:
        self._mw.addonManager.writeConfig(
            __name__, typing.cast(dict[str, typing.Any], configuration)
        )

    def installFFMPEG(self) -> None:
        config = self._get_configuration()
        if (
            config["mp3Convert"] or config["failedFFMPEGInstallation"]
        ) and not os.path.exists(self._ffmpegPath):
            currentStep = 1
            totalSteps = 3
            stepText = "Step {} of {}"
            progressWidget, progressBar, textL = self._getFFMPEGProgressBar(
                "Migaku Dictionary - Installing FFMPEG",
                "Downloading FFMPEG.\n" + stepText.format(currentStep, totalSteps),
            )
            progressBar.setMaximum(3)
            progressBar.setValue(currentStep)
            print("Downloading FFMPEG.")
            if not self._downloadFFMPEG():
                print("Could not download FFMPEG.")
                self._couldNotInstall()
                return
            try:
                print("Unzipping FFMPEG.")
                currentStep += 1
                progressBar.setValue(currentStep)
                self._mw.app.processEvents()
                textL.setText(
                    "Unzipping FFMPEG.\n" + stepText.format(currentStep, totalSteps)
                )
                self._unzipFFMPEG()
                if not self._makeExecutable():
                    print("FFMPEG could not be made executable.")
                    self._removeFailedInstallation()
                    self._couldNotInstall()
                    return
                if config["failedFFMPEGInstallation"]:
                    self._toggleMP3Conversion(True)
                    self._toggleFailedInstallation(False)
                print("Successfully installed FFMPEG.")
            except Exception as error:
                currentStep += 1
                progressBar.setValue(currentStep)
                self._mw.app.processEvents()
                print(error)
                print("Could not unzip FFMPEG.")
                self._couldNotInstall()
        else:
            print("FFMPEG already installed or conversion disabled.")


def _roundToKb(value: typing.Union[float, int]) -> float:
    return round(value / 1000)


def _window_loaded() -> None:
    ffmpegInstaller = FFMPEGInstaller(mw_)
    hooks.addHook("profileLoaded", ffmpegInstaller.installFFMPEG)


def initialize() -> None:
    gui_hooks.main_window_did_init.append(_window_loaded)
