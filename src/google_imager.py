import time
import typing

from PyQt6.QtCore import Qt
from aqt import mw
from urllib.request import Request, urlopen
import aqt

from . import googleimages


_INSTANCE: typing.Optional[googleimages.Google] = None


def _initialize() -> None:
    global _INSTANCE

    _INSTANCE = googleimages.Google()
    config = mw.addonManager.getConfig(__name__)

    if not config:
        raise RuntimeError(f'Namespace "{__name__}" has no configuration.')

    _INSTANCE.setSearchRegion(config['googleSearchRegion'])
    _INSTANCE.setSafeSearch(config["safeSearch"])


# TODO: @ColinKennedy - replace str with False
def _download_image(
    url: str,
    maxW: int,
    maxH: int,
) -> typing.Union[str, typing.Literal[False]]:
    try:
        filename = str(time.time()).replace('.', '') + '.png'
        req = Request(url , headers={'User-Agent':  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'})
        file = urlopen(req).read()
        image = aqt.QImage()
        image.loadFromData(file)
        image = image.scaled(aqt.QSize(maxW,maxH), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        image.save(filename)
        return '<img src="' + filename + '">'
    except:
        return False


def export_images(term: str, howMany: int) -> str:
    global _INSTANCE

    config = mw.addonManager.getConfig(__name__)

    if not config:
        raise RuntimeError(f'Namespace "{__name__}" has no configuration.')

    maxW = config['maxWidth']
    maxH = config['maxHeight']

    if not _INSTANCE:
        _initialize()

    _INSTANCE = typing.cast(googleimages.Google, _INSTANCE)

    imgSeparator = ''
    imgs = []
    urls = _INSTANCE.search(term, 80)

    if len(urls) < 1:
        time.sleep(.1)
        urls = _INSTANCE.search(term, 80, 'countryUS')

    for url in urls:
        time.sleep(.1)

        if img := _download_image(url, maxW, maxH):
            imgs.append(img)

        if len(imgs) == howMany:
            break

    return imgSeparator.join(imgs)
