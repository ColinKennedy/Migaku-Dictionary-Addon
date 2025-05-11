# -*- coding: utf-8 -*-
# Thanks to Damien Elmes, this plugin is loosely based on his original Plugin and borrows slightly from his project
# Also thanks to the creators of the Japanese Pronunciation/Pitch Accent, Japanese Pitch Accent Notes, and pitch accent note button  which I also borrowed marginally from
#

import logging
import os
import sys

# TODO: @ColinKennedy - Move vendor libraries into a different folder later. Then
# replace this line to match it.
#
_CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _CURRENT_DIRECTORY)

from . import checkForThirtyTwo, ffmpegInstaller, main, miflix, migakuMessage, miUpdater

_LOGGER = logging.getLogger(__name__)
_HANDLER = logging.StreamHandler(sys.stdout)
_HANDLER.setLevel(logging.INFO)
_FORMATTER = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_HANDLER.setFormatter(_FORMATTER)
_LOGGER.addHandler(_HANDLER)
_LOGGER.setLevel(logging.INFO)
