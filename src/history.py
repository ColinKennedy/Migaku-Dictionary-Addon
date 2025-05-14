# -*- coding: utf-8 -*-
#

from __future__ import annotations

import datetime
import json
import typing

from anki.utils import is_lin, is_mac, is_win
from aqt import qt
from aqt.utils import askUser, showInfo

from .miutils import miAsk, miInfo

if typing.TYPE_CHECKING:
    from . import midict


class HistoryModel(qt.QAbstractTableModel):

    # TODO: @ColinKennedy fix the cyclic dependency (midict -> history -> midict.DictInterface) later
    def __init__(
        self,
        history: list[list[str]],
        parent: "midict.DictInterface",
    ) -> None:
        super().__init__(parent)

        self.history = history
        self.dictInt = parent
        self.justTerms = [item[0] for item in history]

    def rowCount(self, index: qt.QModelIndex = qt.QModelIndex()) -> int:
        return len(self.history)

    def columnCount(self, index: qt.QModelIndex = qt.QModelIndex()) -> int:
        return 2

    def data(
        self,
        index: qt.QModelIndex,
        role: int = qt.Qt.ItemDataRole.DisplayRole,
    ) -> typing.Optional[str]:
        if not index.isValid():
            # TODO: @ColinKennedy this check is not necessary
            return None

        if not 0 <= index.row() < len(self.history):
            return None

        if (
            role == qt.Qt.ItemDataRole.DisplayRole
            or role == qt.Qt.ItemDataRole.EditRole
        ):
            term = self.history[index.row()][0]
            date = self.history[index.row()][1]

            if index.column() == 0:
                return term
            elif index.column() == 1:
                return date

        return None

    def headerData(
        self,
        section: int,
        orientation: qt.Qt.Orientation,
        role: int = qt.Qt.ItemDataRole.DisplayRole,
    ) -> typing.Optional[str]:
        if role != qt.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == qt.Qt.Orientation.Vertical:
            return str(section + 1)

        return None

    def insertRows(
        self,
        position: typing.Optional[int] = None,
        rows: int = 1,
        index: qt.QModelIndex = qt.QModelIndex(),
        term: str = "",
        date: str = "",
    ) -> bool:
        if not position:
            position = self.rowCount()

        if rows < 0:
            return False

        changed = False

        self.beginInsertRows(qt.QModelIndex(), position, position)

        for row in range(rows):
            if term and date:
                if term in self.justTerms:
                    index_ = self.justTerms.index(term)
                    self.removeRows(index_)

                    del self.justTerms[index_]

                self.history.insert(0, [term, date])
                self.justTerms.insert(0, term)

                changed = True

        self.endInsertRows()
        self.dictInt.saveHistory()

        return changed

    def removeRows(
        self,
        position: int,
        rows: int = 1,
        index: qt.QModelIndex = qt.QModelIndex(),
    ) -> bool:
        # TODO: @ColinKennedy add range-check here
        # TODO: @ColinKennedy this code probably doesn't work. Fix?
        self.beginRemoveRows(qt.QModelIndex(), position, position + rows - 1)
        del self.history[position : position + rows]
        self.endRemoveRows()
        self.dictInt.saveHistory()
        return True


class HistoryBrowser(qt.QWidget):
    def __init__(
        self,
        historyModel: HistoryModel,
        parent: midict.DictInterface,
    ) -> None:
        super().__init__(parent, qt.Qt.WindowType.Window)

        self.setAutoFillBackground(True)
        self.resize(300, 200)
        self.tableView = qt.QTableView()
        self.model = historyModel
        self.dictInt = parent
        self.tableView.setModel(self.model)
        self.clearHistory = qt.QPushButton("Clear History")
        self.clearHistory.clicked.connect(self.deleteHistory)
        self.tableView.doubleClicked.connect(self.searchAgain)
        self.setupTable()
        self.setLayout(self.getLayout())
        self.setColors()
        self.hotkeyEsc = qt.QShortcut(qt.QKeySequence("Esc"), self)
        self.hotkeyEsc.activated.connect(self.hide)

    def setupTable(self) -> None:
        tableHeader = self.tableView.horizontalHeader()

        if not tableHeader:
            raise RuntimeError(f'No horizontalHeader for "{self.tableView}" was found.')

        tableHeader.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Stretch)
        self.tableView.setSelectionBehavior(
            qt.QAbstractItemView.SelectionBehavior.SelectRows
        )
        tableHeader.hide()

    def searchAgain(self) -> None:
        date = str(datetime.date.today())
        model = self.tableView.selectionModel()

        if not model:
            raise RuntimeError(
                f'Cannot search again. "{self.tableView}" has no selection model.'
            )

        term = self.model.index(model.currentIndex().row(), 0).data()
        self.model.insertRows(term=term, date=date)
        self.dictInt.initSearch(term)

    def setColors(self) -> None:
        if self.dictInt.nightModeToggler.day:
            if is_mac:
                self.tableView.setStyleSheet(self.dictInt.getMacTableStyle())
            else:
                self.tableView.setStyleSheet("")
            self.setPalette(self.dictInt.ogPalette)
        else:
            self.setPalette(self.dictInt.nightPalette)
            self.tableView.setStyleSheet(self.dictInt.getTableStyle())

    def deleteHistory(self) -> None:
        if not miAsk(
            "Clearing your history cannot be undone. Would you like to proceed?", self
        ):
            return

        self.model.removeRows(0, len(self.model.history))

    def getLayout(self) -> qt.QVBoxLayout:
        vbox = qt.QVBoxLayout()
        vbox.addWidget(self.tableView)
        hbox = qt.QHBoxLayout()
        self.clearHistory.setFixedSize(100, 30)
        hbox.addStretch()
        hbox.addWidget(self.clearHistory)
        vbox.addLayout(hbox)
        vbox.setContentsMargins(2, 2, 2, 2)
        return vbox
