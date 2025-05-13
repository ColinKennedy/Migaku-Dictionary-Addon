# -*- coding: utf-8 -*-
# Thanks to Damien Elmes, this plugin is loosely based on his original Plugin and borrows slightly from his project
# Also thanks to the creators of the Japanese Pronunciation/Pitch Accent, Japanese Pitch Accent Notes, and pitch accent note button  which I also borrowed marginally from
#

import logging
import os
import sys

from anki import utils

_LOGGER = logging.getLogger(__name__)
_HANDLER = logging.StreamHandler(sys.stdout)
_HANDLER.setLevel(logging.INFO)
_FORMATTER = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_HANDLER.setFormatter(_FORMATTER)
_LOGGER.addHandler(_HANDLER)
_LOGGER.setLevel(logging.INFO)

# TODO: @ColinKennedy - Move vendor libraries into a different folder later. Then
# replace this line to match it.
#
_CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
_VENDORS_DIRECTORY = os.path.join(_CURRENT_DIRECTORY, "vendors")
# NOTE: We need to add the vendors/ directory so third-party imports work as intended
sys.path.insert(0, _VENDORS_DIRECTORY)

sys.path.insert(0, _CURRENT_DIRECTORY)

if utils.is_mac:
    # NOTE: midict.py needs this so we can import `Quartz` Python package.
    import ssl

    ssl._create_default_https_context = ssl._create_unverified_context
    sys.path.insert(0, os.path.join(_VENDORS_DIRECTORY, "keyboardMac"))
elif utils.is_lin:
    sys.path.insert(0, os.path.join(_VENDORS_DIRECTORY, "linux"))

from . import checkForThirtyTwo, ffmpegInstaller, main, miflix, migakuMessage

checkForThirtyTwo.initialize()
ffmpegInstaller.initialize()
miflix.initialize()
migakuMessage.initialize()
main.initialize()
