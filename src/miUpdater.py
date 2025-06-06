import time
import typing

from anki import hooks, httpclient
from aqt import addons, mw, qt

from . import dictdb, migaku_dictionary, miutils

addonId = 1655992655
dledIds: list[int] = []


def _shutdownDB(
    parent: qt.QWidget,
    mgr: addons.AddonManager,
    ids: typing.Sequence[int],
    on_done: typing.Callable[[list[addons.DownloadLogEntry]], None],
    client: typing.Optional[httpclient.HttpClient] = None,
    force_enable: bool = True,
) -> None:
    global dledIds

    dledIds = list(ids)

    if addonId in dledIds:
        miutils.miInfo(
            "The Migaku Dictionary database will be diconnected so that the update may proceed. The add-on will not function properly until Anki is restarted after the update."
        )
        dictdb.get().closeConnection()
        dictdb.clear()
        migaku_dictionary.get().db.closeConnection()
        migaku_dictionary.clear()
        time.sleep(2)


def _restartDB(*args: typing.Any) -> None:
    if addonId in dledIds:
        dictdb.initialize(dictdb.DictDB())
        migaku_dictionary.get().db = dictdb.DictDB()
        miutils.miInfo(
            "The Migaku Dictionary has been updated, please restart Anki to start using the new version now!"
        )


def _wrapOnDone(self: addons.DownloaderInstaller, *_: typing.Any) -> None:
    self.mgr.mw.progress.timer(50, lambda: _restartDB(), False)


addons.download_addons = hooks.wrap(addons.download_addons, _shutdownDB, "before")
addons.DownloaderInstaller._download_done = hooks.wrap(  # type: ignore[method-assign]
    addons.DownloaderInstaller._download_done,
    _wrapOnDone,
)
