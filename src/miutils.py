# -*- coding: utf-8 -*-
# 

import typing
from os.path import dirname, join

import aqt
from aqt.qt import *
from aqt.webview import AnkiWebView

T = typing.TypeVar("T")
addon_path = dirname(__file__)


def _verify(item: typing.Optional[T]) -> T:
    if item is not None:
        return item

    raise RuntimeError('Expected item to exist but got none.')


def miInfo(
    text: str,
    parent: typing.Optional[QWidget]=None,
    level: str = 'msg',
    day: bool = True,
) -> int:
    if level == 'wrn':
        title = "Migaku Dictionary Warning"
    elif level == 'not':
        title = "Migaku Dictionary Notice"
    elif level == 'err':
        title = "Migaku Dictionary Error"
    else:
        title = "Migaku Dictionary"

    if not parent:
        parent = aqt.mw.app.activeWindow() or aqt.mw

    icon = QIcon(join(addon_path, 'icons', 'migaku.png'))
    mb = QMessageBox(parent)
    if not day:
        mb.setStyleSheet(" QMessageBox {background-color: #272828;}")
    mb.setText(text)
    mb.setWindowIcon(icon)
    mb.setWindowTitle(title)
    b = _verify(mb.addButton(QMessageBox.StandardButton.Ok))
    b.setFixedSize(100, 30)
    b.setDefault(True)

    return mb.exec()


def miAsk(text: str, parent: typing.Optional[QWidget]=None, day: bool=True, customText: typing.Sequence[str] = "") -> bool:
    msg = QMessageBox(parent)
    msg.setWindowTitle("Migaku Dictionary")
    msg.setText(text)
    icon = QIcon(join(addon_path, 'icons', 'migaku.png'))
    b = _verify(msg.addButton(QMessageBox.StandardButton.Yes))
    
    b.setFixedSize(100, 30)
    b.setDefault(True)
    c = _verify(msg.addButton(QMessageBox.StandardButton.No))
    c.setFixedSize(100, 30)

    if customText:
        b.setText(customText[0])
        c.setText(customText[1])
        b.setFixedSize(120, 40)
        c.setFixedSize(120, 40)

    if not day:
        msg.setStyleSheet(" QMessageBox {background-color: #272828;}")

    msg.setWindowIcon(icon)
    msg.exec()

    return msg.clickedButton() == b
