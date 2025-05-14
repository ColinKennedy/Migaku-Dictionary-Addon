from anki.hooks import addHook
from anki.utils import is_mac, is_win
from aqt.qt import *
from aqt.utils import openLink

from .miutils import miAsk


def checkForThirtyTwo() -> None:
    if is_win or is_mac:
        qVer = QT_VERSION_STR
        invalid = ["5.12.6", "5.9.7"]
        if qVer in invalid:
            msg = "You are on 32-bit Anki!\n32-bit Anki has known compatibility issues with Migaku addons.\n\nMigaku add-ons and Browser Extension integration WILL NOT WORK CORRECTLY.\n\nIf you're on a 64-bit system, please update to the 64-bit version of Anki."
            if miAsk(msg, customText=["Download Now! 😄", "I like 32 bit. 🥺"]):
                openLink("https://www.migaku.io/tools-guides/anki/guide#installation")


def initialize() -> None:
    addHook("profileLoaded", checkForThirtyTwo)
