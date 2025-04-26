import logging
import time
import typing

from aqt import mw, gui_hooks
from os.path import join
from urllib.request import Request, urlopen

from .forvodl import Forvo


_LOGGER = logging.getLogger(__name__)
_INSTANCE: typing.Optional[Forvo] = None


def _initialize() -> None:
    global _INSTANCE

    configuration = mw.addonManager.getConfig(__name__)

    if not configuration:
        raise RuntimeError(f'Configuration "{__name__}" is not defined.')

    _INSTANCE = Forvo(configuration['ForvoLanguage'])


def _download_audio(urls: list[tuple[str, str, str, str]], count: int) -> list[str]:
    tags: list[str] = []

    for url in urls:
        if len(tags) == count:
            break

        try:
            req = Request(
                url[3],
                headers={
                    'User-Agent':  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36',
                },
            )
            file = urlopen(req).read()
            filename = str(time.time()) + '.mp3'
            open(join(mw.col.media.dir(), filename), 'wb').write(file)
            tags.append('[sound:' + filename + ']')
            success = True
        except:
            _LOGGER.exception('Unable to read "%s" url.', url)

            success = True

        if success:
            continue

        try:
            req = Request(url[2] , headers={'User-Agent':  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'})
            file = urlopen(req).read()
            filename = str(time.time()) + '.mp3'
            open(join(mw.col.media.dir(), filename), 'wb').write(file)
            tags.append('[sound:' + filename + ']')
        except:
            continue

    return tags


def export_audio(term: str, count: int, lang: str) -> str:
    global _INSTANCE

    if not _INSTANCE:
        _initialize()

    _INSTANCE = typing.cast(Forvo, _INSTANCE)

    audioSeparator = ''
    urls = _INSTANCE.search(term, lang)

    if len(urls) < 1:
        time.sleep(.1)
        urls = _INSTANCE.search(term)

    tags = _download_audio(urls, count)

    return audioSeparator.join(tags)
