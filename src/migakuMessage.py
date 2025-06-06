# -*- coding: utf-8 -*-

import os
import re
import typing

import aqt
import requests as req
from anki.hooks import addHook
from aqt import mw, qt, utils, webview

_MIGAKU_SHOULD_NOT_SHOW_MESSAGE = False
T = typing.TypeVar("T")


class _Config(typing.TypedDict):
    displayAgain: bool


def attemptOpenLink(cmd: str) -> None:
    if cmd.startswith("openLink:"):
        utils.openLink(cmd[9:])


addon_path = os.path.dirname(__file__)


def _verify(value: typing.Optional[T]) -> T:
    if value is None:
        raise TypeError("Got empty value. Cannot continue.")

    return value


def getConfig() -> _Config:
    return typing.cast(_Config, mw.addonManager.getConfig(__name__))


def saveConfiguration(newConf: dict[str, typing.Any]) -> None:
    mw.addonManager.writeConfig(__name__, newConf)


# TODO: @ColinKennedy remove try/except
def getLatestVideos() -> tuple[typing.Optional[str], typing.Optional[str]]:
    try:
        resp = req.get(
            "https://www.youtube.com/channel/UCQFe3x4WAgm7joN5daMm5Ew/videos"
        )
        pattern = '\{"videoId"\:"(.*?)"'
        matches = re.findall(pattern, resp.text)
        videoIds = list(dict.fromkeys(matches))

        videoEmbeds = []
        count = 0
        for vid in videoIds:
            if count > 6:
                break
            count += 1
            if count == 1:
                videoEmbeds.append("<h2>Check Out Our Latest Release:</h2>")
                videoEmbeds.append(
                    '<div class="iframe-wrapper"><div class="clickable-video-link" data-vid="'
                    + vid
                    + '"></div><iframe width="640" height="360" src="https://www.youtube.com/embed/'
                    + vid
                    + '" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>'
                )
            else:
                if count == 2:
                    videoEmbeds.append("<h2>Previous Videos:</h2>")
                videoEmbeds.append(
                    '<div class="iframe-wrapper" style="display:inline-block"><div class="clickable-video-link" data-vid="'
                    + vid
                    + '"></div><iframe width="320" height="180" src="https://www.youtube.com/embed/'
                    + vid
                    + '" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>'
                )
        return "".join(videoEmbeds), videoIds[0]
    except:
        return None, None


def miMessage(text: str, parent: typing.Optional[qt.QWidget] = None) -> bool:
    title = "Migaku"

    parent = parent or aqt.mw.app.activeWindow() or aqt.mw

    icon = qt.QIcon(os.path.join(addon_path, "icons", "migaku.png"))
    mb = qt.QMessageBox(parent)
    mb.setWindowIcon(icon)
    mb.setWindowTitle(title)
    cb = qt.QCheckBox("Don't show me the welcome screen again.")
    wv = webview.AnkiWebView()
    page = _verify(wv.page())
    page._bridge.onCmd = attemptOpenLink
    wv.setFixedSize(680, 450)
    page.setHtml(text)
    wide = qt.QWidget()
    wide.setFixedSize(18, 18)
    layout = typing.cast(qt.QGridLayout, _verify(mb.layout()))
    layout.addWidget(wv, 0, 1)
    layout.addWidget(wide, 0, 2)
    layout.setColumnStretch(0, 3)
    layout.addWidget(cb, 1, 1)

    b = _verify(mb.addButton(qt.QMessageBox.StandardButton.Ok))
    b.setFixedSize(100, 30)
    b.setDefault(True)
    mb.exec()
    wv.deleteLater()
    if cb.isChecked():
        return True
    else:
        return False


migakuMessage = """
<style>
    body{
    margin:0px;
    padding:0px;
    background-color: white !important;
    }
    h3 {
        margin-top:5px;
        margin-left:15px;
        font-weight: 600;
        font-family: NeueHaas, input mono, sans-serif;
        color: #404040;
    }
    div {
        margin-left:15px;
        line-height: 1.5;
        font-family: Helmet,Freesans,Helvetica,Arial,sans-serif;
        color: #404040;
    }

    span{
        margin-left:15px;
        color:gray;
        font-size:13;
        font-family: Helmet,Freesans,Helvetica,Arial,sans-serif;
    }

    .iframe-wrapper{
        position:relative;
        margin-left:0px;
        line-height: 1;
    }

    .clickable-video-link{
        position:absolute;
        v-index:10;
        width:100%%;
        top:0px;
        left;0px;
        height:20%%;
        margin-left:0px;
        line-height: 1;
        cursor:pointer;

    }
</style>
<body>
<h3><b>Thanks so much for using the Migaku Add-on series!</b></h3>
<div class="center-div">
    If you would like to ensure you don't miss any Migaku updates, or new releases.<br>
    Please consider visiting our <a href="https://migaku.io">website</a>, and following us on <a href="https://www.youtube.com/channel/UCQFe3x4WAgm7joN5daMm5Ew">YouTube</a> and <a href="https://twitter.com/Migaku_Yoga">Twitter</a>!
    <br>Also, please consider supporting Migaku on <a href="https://www.patreon.com/Migaku">Patreon</a> if you have found value in our work!
</div>
<div>
%s
</div>
<script>

        const vids = document.getElementsByClassName("clickable-video-link");
        for (var i = 0; i < vids.length; i++) {
            vids[i].addEventListener("click", function (e) {
                const vidId = e.target.dataset.vid;
                pycmd("openLink:https://www.youtube.com/watch?v=" + vidId);
            });
        }

</script>
</body>
"""


def disableMessage(config: _Config) -> None:
    config["displayAgain"] = False
    saveConfiguration(typing.cast(dict[str, typing.Any], config))
    _MIGAKU_SHOULD_NOT_SHOW_MESSAGE = True


def displayMessageMaybeDisableMessage(content: str, config: _Config) -> None:
    if miMessage(migakuMessage % content):
        disableMessage(config)


def attemptShowMigakuBrandUpdateMessage() -> None:
    global _MIGAKU_SHOULD_NOT_SHOW_MESSAGE

    config = getConfig()
    shouldShow = config["displayAgain"]
    if shouldShow and not _MIGAKU_SHOULD_NOT_SHOW_MESSAGE:
        videoIds, videoId = getLatestVideos()
        if videoIds:
            displayMessageMaybeDisableMessage(videoIds, config)
        else:
            displayMessageMaybeDisableMessage("", config)
    elif shouldShow and _MIGAKU_SHOULD_NOT_SHOW_MESSAGE:
        disableMessage(config)
    else:
        _MIGAKU_SHOULD_NOT_SHOW_MESSAGE = True


def initialize() -> None:
    addHook("profileLoaded", attemptShowMigakuBrandUpdateMessage)
