import typing
import os

from anki.utils import is_mac


_CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))


def getWelcomeScreen() -> str:
    htmlPath = os.path.join(_CURRENT_DIRECTORY, 'welcome.html')

    with open(htmlPath,'r', encoding="utf-8") as fh:
        return fh.read()


def getMacWelcomeScreen() -> str:
    htmlPath = os.path.join(_CURRENT_DIRECTORY, 'macwelcome.html')

    with open(htmlPath,'r', encoding="utf-8") as fh:
        return fh.read()

if is_mac:
    welcomeScreen = getMacWelcomeScreen
else:
    welcomeScreen = getWelcomeScreen
