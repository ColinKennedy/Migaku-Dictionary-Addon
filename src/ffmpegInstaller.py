import logging
import os
import requests
import stat
import typing

import aqt
from aqt import main
from anki.utils import is_mac, is_win, is_lin
from anki.hooks import addHook
from os.path import join, exists, dirname
from .miutils import miInfo
from aqt.qt import *
from aqt import mw as mw_, gui_hooks
import zipfile

from . import typer


_LOGGER = logging.getLogger(__name__)


class FFMPEGInstaller:

    def __init__(self, mw: main.AnkiQt) -> None:
        super().__init__()

        self.mw = mw
        self.addonPath = dirname(__file__)
        self.ffmpegDir = join(self.addonPath, 'user_files', 'ffmpeg')
        self.ffmpegFilename = "ffmpeg"
        # TODO: @ColinKennedy download these sources elsewhere
        if is_win:
            self.ffmpegFilename += ".exe"
            self.downloadURL = "http://dicts.migaku.io/ffmpeg/windows"
        elif is_lin:
            self.downloadURL = "http://dicts.migaku.io/ffmpeg/linux"
        elif is_mac:
            self.downloadURL = "http://dicts.migaku.io/ffmpeg/macos"
        self.ffmpegPath = join(self.ffmpegDir, self.ffmpegFilename)
        self.tempPath = join(self.addonPath, 'temp', 'ffmpeg')

    def _get_configuration(self) -> typer.Configuration:
        return typing.cast(typer.Configuration, self.mw.addonManager.getConfig(__name__))
    def _write_configuration(self, configuration: typer.Configuration) -> None:
        self.mw.addonManager.writeConfig(__name__, typing.cast(dict[str, typing.Any], configuration))

    def getFFMPEGProgressBar(
        self,
        title: str,
        initialText: str,
    ) -> tuple[QWidget, QProgressBar, QLabel]:
        progressWidget = QWidget(None)
        textDisplay = QLabel()
        progressWidget.setWindowIcon(QIcon(join(self.addonPath, 'icons', 'migaku.png')))
        progressWidget.setWindowTitle(title)
        textDisplay.setText(initialText)
        progressWidget.setFixedSize(500, 100)
        progressWidget.setWindowModality(Qt.WindowModality.ApplicationModal)
        bar = QProgressBar(progressWidget)
        layout = QVBoxLayout()
        layout.addWidget(textDisplay)
        layout.addWidget(bar)
        progressWidget.setLayout(layout) 
        bar.move(10,10)
        per = QLabel(bar)
        per.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progressWidget.show()
        progressWidget.setFocus()

        return progressWidget, bar, textDisplay;

    def toggleMP3Conversion(self, enable: bool) -> None:
        config = self._get_configuration()
        config["mp3Convert"] = enable
        self._write_configuration(config)

    def toggleFailedInstallation(self, failedInstallation: bool) -> None:
        config = self._get_configuration()
        config["failedFFMPEGInstallation"] = failedInstallation
        self._write_configuration(config)

    def roundToKb(self, value: typing.Union[float, int]) -> float:
        return round(value / 1000)

       
    def downloadFFMPEG(self) -> bool:
        progressWidget: typing.Optional[QWidget] = None
        try:
            with requests.get(self.downloadURL, stream=True) as ffmpegRequest:
                ffmpegRequest.raise_for_status()
                with open(self.tempPath, 'wb') as ffmpegFile:
                    downloadingText = "Downloading FFMPEG...\n{}kb of {}kb downloaded."
                    total = int(ffmpegRequest.headers['Content-Length'])
                    roundedTotal = self.roundToKb(total)
                    downloadedSoFar = 0
                    progressWidget, bar, textDisplay = self.getFFMPEGProgressBar("Migaku Dictionary - FFMPEG Download", downloadingText.format( self.roundToKb(downloadedSoFar), roundedTotal))
                    bar.setMaximum(total)
                    lastUpdated: typing.Union[float, int] = 0
                    for chunk in ffmpegRequest.iter_content(chunk_size=8192):
                        if chunk: 
                            downloadedSoFar += len(chunk)
                            roundedValue = self.roundToKb(downloadedSoFar)
                            if roundedValue - lastUpdated > 500:
                                lastUpdated = roundedValue
                                bar.setValue(downloadedSoFar)
                                textDisplay.setText(downloadingText.format(roundedValue, roundedTotal))
                                self.mw.app.processEvents()
                            ffmpegFile.write(chunk)
                            
                self.closeProgressBar(progressWidget)
            return True
        except Exception as error:
            _LOGGER.exception('Unabled to download FFMPEG.')
            if progressWidget:
                self.closeProgressBar(progressWidget)
            return False

    def closeProgressBar(self, progressBar: QWidget) -> None:
        progressBar.close()
        progressBar.deleteLater()

    def makeExecutable(self) -> bool:
        if not is_win:
            # TODO: @ColinKennedy - remove try/except later
            try:
                st = os.stat(self.ffmpegPath)
                os.chmod(self.ffmpegPath, st.st_mode | stat.S_IEXEC)
            except:
                return False
        return True
        
    def removeFailedInstallation(self) -> None:
        os.remove(self.ffmpegPath)

    def unzipFFMPEG(self) -> None:
        with zipfile.ZipFile(self.tempPath) as zf:
            zf.extractall(self.ffmpegDir)

    def couldNotInstall(self) -> None:
        self.toggleMP3Conversion(False)
        self.toggleFailedInstallation(True)
        miInfo("FFMPEG could not be installed. MP3 Conversion has been disabled. You will not be able to convert audio files imported from the Immerse with Migaku Browser Extension to MP3 format until it is installed. Migaku Dictionary will attempt to install it again on the next profile load.")
    

        
    def installFFMPEG(self) -> None:
        config = self._get_configuration()
        if (config["mp3Convert"] or config["failedFFMPEGInstallation"]) and not exists(self.ffmpegPath):
            currentStep = 1
            totalSteps = 3
            stepText = "Step {} of {}"
            progressWidget, progressBar, textL = self.getFFMPEGProgressBar("Migaku Dictionary - Installing FFMPEG", "Downloading FFMPEG.\n" + stepText.format(currentStep, totalSteps))
            progressBar.setMaximum(3)
            progressBar.setValue(currentStep)
            print("Downloading FFMPEG.")
            if not self.downloadFFMPEG():
                print("Could not download FFMPEG.")
                self.couldNotInstall()
                return
            try:
                print("Unzipping FFMPEG.")
                currentStep +=1
                progressBar.setValue(currentStep)
                self.mw.app.processEvents()
                textL.setText("Unzipping FFMPEG.\n" + stepText.format(currentStep, totalSteps))
                self.unzipFFMPEG()
                if not self.makeExecutable():
                    print("FFMPEG could not be made executable.")
                    self.removeFailedInstallation()
                    self.couldNotInstall()
                    return
                if config["failedFFMPEGInstallation"]: 
                    self.toggleMP3Conversion(True)
                    self.toggleFailedInstallation(False)
                print("Successfully installed FFMPEG.")
            except Exception as error:
                currentStep +=1
                progressBar.setValue(currentStep)
                self.mw.app.processEvents()
                print(error)
                print("Could not unzip FFMPEG.")
                self.couldNotInstall()
        else:
            print("FFMPEG already installed or conversion disabled.")

def window_loaded() -> None:
    ffmpegInstaller = FFMPEGInstaller(mw_)
    addHook("profileLoaded", ffmpegInstaller.installFFMPEG)
gui_hooks.main_window_did_init.append(window_loaded)
