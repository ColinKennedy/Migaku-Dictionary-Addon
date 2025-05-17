from anki import hooks, utils
from aqt import qt
from aqt import utils as aqt_utils

from . import miutils


def _checkForThirtyTwo() -> None:
    if utils.is_win or utils.is_mac:
        qVer = qt.QT_VERSION_STR
        invalid = ["5.12.6", "5.9.7"]
        if qVer in invalid:
            msg = "You are on 32-bit Anki!\n32-bit Anki has known compatibility issues with Migaku addons.\n\nMigaku add-ons and Browser Extension integration WILL NOT WORK CORRECTLY.\n\nIf you're on a 64-bit system, please update to the 64-bit version of Anki."
            if miutils.miAsk(msg, customText=["Download Now! 😄", "I like 32 bit. 🥺"]):
                aqt_utils.openLink(
                    "https://www.migaku.io/tools-guides/anki/guide#installation"
                )


def initialize() -> None:
    hooks.addHook("profileLoaded", _checkForThirtyTwo)
