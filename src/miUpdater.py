import typing

from aqt import qt
from aqt import mw
from aqt import addons
from . import dictdb
from anki.hooks import  wrap, addHook
from .miutils import miInfo
import time
from anki.httpclient import HttpClient

from . import dictdb, migaku_dictionary


addonId = 1655992655
dledIds: list[int] = []


def shutdownDB(
    parent: qt.QWidget,
    mgr: addons.AddonManager,
    ids: typing.Sequence[int],
    on_done: typing.Callable[[list[addons.DownloadLogEntry]], None],
    client: typing.Optional[HttpClient] = None,
    force_enable: bool=True,
) -> None:
    global dledIds

    dledIds = list(ids)

    if addonId in dledIds:
        miInfo('The Migaku Dictionary database will be diconnected so that the update may proceed. The add-on will not function properly until Anki is restarted after the update.')
        dictdb.get().closeConnection()
        dictdb.clear()
        migaku_dictionary.get().db.closeConnection()
        migaku_dictionary.clear()
        time.sleep(2)


def restartDB(*args: typing.Any) -> None:
    if addonId in dledIds:
        dictdb.initialize(dictdb.DictDB())
        migaku_dictionary.get().db = dictdb.DictDB()
        miInfo('The Migaku Dictionary has been updated, please restart Anki to start using the new version now!')

def wrapOnDone(self: addons.DownloaderInstaller, *_: typing.Any) -> None:
    self.mgr.mw.progress.timer(50, lambda: restartDB(), False)

addons.download_addons = wrap(addons.download_addons, shutdownDB, 'before')
addons.DownloaderInstaller._download_done = wrap(  # type: ignore[method-assign]
    addons.DownloaderInstaller._download_done,
    wrapOnDone,
)
