from aqt import mw
from aqt import addons
from . import dictdb
from anki.hooks import  wrap, addHook
from .miutils import miInfo
import time
from anki.httpclient import HttpClient

from . import dictdb, migaku_dictionary


addonId = 1655992655
dledIds = []


def shutdownDB(parent, mgr, ids, on_done, client, force_enable=True):
    global dledIds

    dledIds = ids
    if addonId in ids:
        miInfo('The Migaku Dictionary database will be diconnected so that the update may proceed. The add-on will not function properly until Anki is restarted after the update.')
        dictdb.get().closeConnection()
        dictdb.clear()
        migaku_dictionary.get().db.closeConnection()
        migaku_dictionary.get().db = None
        time.sleep(2)


def restartDB(*args: typing.Any) -> None:
    if addonId in dledIds:
        dictdb.set(dictdb.DictDB())
        migaku_dictionary.get().db = dictdb.DictDB()
        miInfo('The Migaku Dictionary has been updated, please restart Anki to start using the new version now!')

def wrapOnDone(self, *_: typing.Any) -> None:
    self.mgr.mw.progress.timer(50, lambda: restartDB(), False)

addons.download_addons = wrap(addons.download_addons, shutdownDB, 'before')
addons.DownloaderInstaller._download_done = wrap(addons.DownloaderInstaller._download_done, wrapOnDone)


