import re
import typing

from anki.utils import is_win
from aqt.qt import *
import aqt
from aqt import mw

from . import midict, migaku_dictionary


def _selectedText(page: QWebEngineView) -> typing.Optional[str]:
    text = page.selectedText()

    if not text:
        return None

    return text


def getTarget(name: str) -> typing.Optional[str]:
    if name == 'AddCards':
        return 'Add'
    elif name == "EditCurrent" or name == "MigakuEditCurrent":
        return 'Edit'
    elif name == 'Browser':
        return name

    return None


def performColSearch(text: str) -> None:
    if not text:
        return

    text = text.strip()
    browser = aqt.DialogManager._dialogs["Browser"][1]

    if not browser:
        mw.onBrowse()
        browser = aqt.DialogManager._dialogs["Browser"][1]

    if not browser:
        return

    browser.form.searchEdit.lineEdit().setText(text)
    browser.onSearchActivated()
    browser.activateWindow()

    if not is_win:
        browser.setWindowState(browser.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        browser.raise_()
    else:
        browser.setWindowFlags(browser.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        browser.show()
        browser.setWindowFlags(browser.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        browser.show()


def searchCol(self: QWebEngineView) -> None:
    text = _selectedText(self)

    if text:
        performColSearch(text)


def searchTerm(self: QWebEngineView) -> None:
    text = _selectedText(self)

    if not text:
        return

    text = re.sub(r'\[[^\]]+?\]', '', text)
    text = text.strip()

    if not migaku_dictionary.get_visible_dictionary():
        midict.dictionaryInit([text])

    dictionary = migaku_dictionary.get()
    dictionary.ensureVisible()
    dictionary.initSearch(text)

    title = self.title()

    if title == 'main webview':
        if mw.state == 'review':
            dictionary.dict.setReviewer(mw.reviewer)
    elif title == 'editor':
        target = getTarget(type(self.parentEditor.parentWindow).__name__)
        dictionary.dict.setCurrentEditor(self.parentEditor, target=target or "")

    midict.showAfterGlobalSearch()
