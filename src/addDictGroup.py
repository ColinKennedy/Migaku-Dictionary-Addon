# -*- coding: utf-8 -*-

import json
import math
import ntpath
import sys
import typing
from operator import itemgetter
from os.path import exists, join
from shutil import copyfile

import aqt
from anki.lang import _
from anki.utils import is_lin, is_mac
from aqt import main, qt
from PyQt6 import QtCore

from .miutils import miAsk, miInfo

if typing.TYPE_CHECKING:
    # TODO: @ColinKennedy - fix cyclic dependency "addonSettings.SettingsGui" later
    from . import addonSettings

from . import dictdb, typer


class DictGroupEditor(qt.QDialog):
    def __init__(
        self,
        mw: main.AnkiQt,
        # TODO: @ColinKennedy - fix cyclic dependency "addonSettings.SettingsGui" later
        parent: "addonSettings.SettingsGui",
        dictionaries: typing.Optional[typing.Iterable[str]] = None,
        group: typing.Optional[typer.DictionaryGroup] = None,
        groupName: str = "",
    ):
        super().__init__(parent, qt.Qt.WindowType.Window)

        dictionaries = dictionaries or []
        self._mw = mw
        self._settings = parent
        self.setWindowTitle("Add Dictionary Group")
        self._groupName = qt.QLineEdit()
        self._fontFromDropdown = qt.QRadioButton()
        self._fontFromFile = qt.QRadioButton()
        self._fontDropDown = self._getFontCB()
        self._fontFileName = qt.QLabel("None Selected")
        self._browseFontFile = qt.QPushButton("Browse")
        self._dictionaries = self._setupDictionaries()
        self._selectAll = qt.QPushButton("Select All")
        self._removeAll = qt.QPushButton("Remove All")
        self._cancelButton = qt.QPushButton("Cancel")
        self._saveButton = qt.QPushButton("Save")
        self._main_layout = qt.QVBoxLayout()
        self._setupLayout()
        self._fontToMove: typing.Optional[str] = None
        self._dictList = dictionaries
        self._loadDictionaries(dictionaries)
        self._new = True
        if group:
            self._new = False
            self._loadGroupEditor(group, groupName)
        else:
            self.clearGroupEditor()
        self._initHandlers()
        self._initTooltips()

    def _initTooltips(self) -> None:
        self._groupName.setToolTip("The name of the dictionary group.")
        self._fontFromDropdown.setToolTip("Select a font installed on your system.")
        self._fontDropDown.setToolTip("Select a font installed on your system.")
        self._fontFromFile.setToolTip("Select a font to import from a file.")
        self._browseFontFile.setToolTip("Select a font to import from a file.")
        self._selectAll.setToolTip("Select all dictionaries.")
        self._removeAll.setToolTip("Clear the current selection.")

    def _resetNew(self) -> None:
        self._new = True

    def _reloadDictTable(self) -> None:
        self._dictionaries.setRowCount(0)
        self._loadDictionaries(self._dictList)

    def _loadGroupEditor(self, group: typer.DictionaryGroup, groupName: str) -> None:
        self.clearGroupEditor()
        self._new = False
        self.setWindowTitle("Edit Dictionary Group")
        self._groupName.setText(groupName)
        self._groupName.setEnabled(False)

        if group["customFont"]:
            self._fontFromFile.setChecked(True)
            self._toggleFontType(True)
            self._fontFileName.setText(group["font"])
        else:
            self._fontDropDown.setCurrentText(group["font"])

        self._loadSelectedDictionaries(group["dictionaries"])

    def _loadSelectedDictionaries(self, dicts: typing.Iterable[str]) -> None:
        count = 1

        for d in dicts:
            for i in range(self._dictionaries.rowCount()):
                item = self._dictionaries.item(i, 0)

                if not item:
                    raise RuntimeError(f'Index "{i}" has no dictionary column==0 item.')

                if d != item.text():
                    continue

                item = self._dictionaries.item(i, 1)

                if not item:
                    raise RuntimeError(f'Index "{i}" has no dictionary column==1 item.')

                widget = typing.cast(
                    typing.Optional[qt.QCheckBox],
                    self._dictionaries.cellWidget(i, 2),
                )

                if not widget:
                    raise RuntimeError(
                        f'Index "{i}" has no dictionary column==2 widget.'
                    )

                item.setText(str(count))
                widget.setChecked(True)
                count += 1

    def _getConfig(self) -> typer.Configuration:
        # TODO: @ColinKennedy - fix cyclic dependency later
        from . import migaku_dictionary

        if configuration := migaku_dictionary.get().getConfig():
            return configuration

        raise RuntimeError("No configuration could be found.")

    def _initHandlers(self) -> None:
        self._browseFontFile.clicked.connect(self._grabFontFromFile)
        self._saveButton.clicked.connect(self._saveDictGroup)
        self._cancelButton.clicked.connect(self.hide)
        self._fontFromDropdown.clicked.connect(lambda: self._toggleFontType(False))
        self._fontFromFile.clicked.connect(lambda: self._toggleFontType(True))
        self._selectAll.clicked.connect(self._selectAllDicts)
        self._removeAll.clicked.connect(self._removeAllDicts)

    def _get_dict_checkboxes(self) -> list[qt.QCheckBox]:
        output: list[qt.QCheckBox] = []

        for i in range(self._dictionaries.rowCount()):
            widget = typing.cast(
                typing.Optional[qt.QCheckBox], self._dictionaries.cellWidget(i, 2)
            )

            if not widget:
                raise RuntimeError(f'Index "{i}" has no checkbox from column==2.')

            output.append(widget)

        return output

    def _selectAllDicts(self) -> None:
        for i, widget in enumerate(self._get_dict_checkboxes()):
            if not widget.isChecked():
                widget.setChecked(True)
                self._setDictionaryOrder(i)

    def _removeAllDicts(self) -> None:
        for i, widget in enumerate(self._get_dict_checkboxes()):
            if widget.isChecked():
                widget.setChecked(False)
                self._setDictionaryOrder(i)

    def _toggleFontType(self, fromFile: bool) -> None:
        if fromFile:
            self._fontDropDown.setEnabled(False)
            self._browseFontFile.setEnabled(True)
            self._fontFileName.setEnabled(True)
        else:
            self._fontDropDown.setEnabled(True)
            self._browseFontFile.setEnabled(False)
            self._fontFileName.setEnabled(False)

    def _grabFontFromFile(self) -> None:
        options = qt.QFileDialog.Option.DontUseNativeDialog
        fileName, _ = qt.QFileDialog.getOpenFileName(
            self,
            "Select a Custom Font",
            "",
            "Font Files (*.ttf *.woff *.woff2 *.eot)",
            options=options,
        )
        if fileName:
            if (
                not fileName.endswith(".ttf")
                and not fileName.endswith(".woff")
                and not fileName.endswith(".woff2")
                and not fileName.endswith(".eot")
            ):
                miInfo("Please select a font file.", level="err")
                return
            self._fontFileName.setText(ntpath.basename(fileName))
            self._fontToMove = fileName

    def _saveDictGroup(self) -> None:
        # TODO: @ColinKennedy - fix cyclic dependency later
        from . import migaku_dictionary

        newConfig = self._getConfig()
        gn = self._groupName.text()
        if gn == "":
            miInfo("The dictionary group must have a name.", level="wrn")
            return
        curGroups = newConfig["DictionaryGroups"]
        if self._new and gn in curGroups:
            miInfo("A new dictionary group must have a unique name.", level="wrn")
            return
        if self._fontFromDropdown.isChecked():
            fontName = self._fontDropDown.currentText()
            customFont = False

        else:
            fontName = self._fontFileName.text()
            if fontName == "None Selected":
                miInfo(
                    "You must select a file if you will be using a font from a file.",
                    level="wrn",
                )
                return
            customFont = True
            if not exists(
                join(self._settings.addonPath, "user_files", "fonts", fontName)
            ):
                if not self._fontToMove:
                    miInfo("Not font to move was found.", level="err")

                    return

                if not self._moveFontToFolder(self._fontToMove):
                    miInfo(
                        "The font file was unable to be loaded, please ensure your file exists in the target folder and try again.",
                        level="err",
                    )
                    return

        selectedDicts = self._getSelectedDictionaryNames()

        if len(selectedDicts) < 1:
            miInfo("You must select at least one dictionary.", level="wrn")

            return

        dictGroup: typer.DictionaryGroup = {
            "customFont": customFont,
            "dictionaries": selectedDicts,
            "font": fontName,
        }
        curGroups[gn] = dictGroup
        self._mw.addonManager.writeConfig(
            __name__, typing.cast(dict[str, typing.Any], newConfig)
        )
        self._settings.loadTemplateTable()
        self._settings.loadGroupTable()
        self.hide()

    def _getSelectedDictionaryNames(self) -> list[str]:
        return [item[2] for item in self._getSelectedDictionaries()]

    def _getSelectedDictionaries(self) -> list[typer.Dictionary]:
        dicts: list[typer.Dictionary] = []

        for i in range(self._dictionaries.rowCount()):
            item = self._dictionaries.item(i, 1)

            if not item:
                raise RuntimeError(f'Index "{i}" column==1 has no table item.')

            order = item.text()

            if not order:
                continue

            item = self._dictionaries.item(i, 0)

            if not item:
                raise RuntimeError(f'Index "{i}" column==0 has no table item.')

            dicts.append(typer.Dictionary(i, int(order), item.text()))

        return sorted(dicts, key=itemgetter(1))

    def _setDictionaryOrder(self, row: int) -> None:
        self._dictionaries.selectRow(row)
        widget = typing.cast(
            typing.Optional[qt.QCheckBox], self._dictionaries.cellWidget(row, 2)
        )

        if not widget:
            raise RuntimeError(f'Row "{row}" has no dictionary widget.')

        if not widget.isChecked():
            item = self._dictionaries.item(row, 1)

            if not item:
                raise RuntimeError(f'Row "{row}" column==1 has no cell item.')

            item.setText("")
            self._reorderDictionaries()

            return

        self._reorderDictionaries(row)

    def _reorderDictionaries(self, last: typing.Optional[int] = None) -> None:
        dicts = self._getSelectedDictionaries()

        for idx, d in enumerate(dicts):
            index = d[0]
            item = self._dictionaries.item(index, 1)

            if not item:
                raise RuntimeError(f'Last index "{index}" column==1 has no item.')

            item.setText(str(idx + 1))

        if last is not None:
            item = self._dictionaries.item(last, 1)

            if not item:
                raise RuntimeError(f'Last index "{last}" column==1 has no item.')

            item.setText(str(len(dicts) + 1))

    def _moveFontToFolder(self, filename: str) -> bool:
        try:
            basename = ntpath.basename(filename)

            if not exists(filename):
                # TODO: @ColinKennedy - Logging
                return False

            path = join(self._settings.addonPath, "user_files", "fonts", basename)

            if exists(path):
                if not miAsk(
                    "A font with the same name currently exists in your custom fonts folder. Would you like to overwrite it?",
                    self,
                ):
                    return False

            copyfile(filename, path)

            return True
        except:
            return False

    def _setOrder(self, x: int) -> typing.Callable[[], None]:
        return lambda: self._setDictionaryOrder(x)

    def _getFontCB(self) -> qt.QComboBox:
        fonts = qt.QComboBox()
        fams = qt.QFontDatabase.families()
        fonts.addItems(fams)
        return fonts

    def _loadDictionaries(self, dictionaries: typing.Iterable[str]) -> None:
        for dictName in dictionaries:
            rc = self._dictionaries.rowCount()
            self._dictionaries.setRowCount(rc + 1)
            self._dictionaries.setItem(rc, 0, qt.QTableWidgetItem(dictName))
            self._dictionaries.setItem(rc, 1, qt.QTableWidgetItem(""))
            checkBox = qt.QCheckBox()
            checkBox.setFixedWidth(40)
            checkBox.setStyleSheet("QCheckBox{padding-left:10px;}")
            self._dictionaries.setCellWidget(rc, 2, checkBox)
            checkBox.clicked.connect(self._setOrder(rc))
        self._addDefaultDict("Google Images")
        self._addDefaultDict("Forvo")

    def _addDefaultDict(self, name: str) -> None:
        rc = self._dictionaries.rowCount()
        self._dictionaries.setRowCount(rc + 1)
        self._dictionaries.setItem(rc, 0, qt.QTableWidgetItem(name))
        self._dictionaries.setItem(rc, 1, qt.QTableWidgetItem(""))
        checkBox = qt.QCheckBox()
        checkBox.setFixedWidth(40)
        checkBox.setStyleSheet("QCheckBox{padding-left:10px;}")
        checkBox.clicked.connect(self._setOrder(rc))
        self._dictionaries.setCellWidget(rc, 2, checkBox)

    def _setupDictionaries(self) -> qt.QTableWidget:
        macLin = False
        if is_mac or is_lin:
            macLin = True
        dictionaries = qt.QTableWidget()
        dictionaries.setColumnCount(3)
        tableHeader = dictionaries.horizontalHeader()

        if not tableHeader:
            raise RuntimeError(f'Expected "{dictionaries}" to have a header.')

        tableHeader.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Fixed)
        tableHeader.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Fixed)

        dictionaries.setRowCount(0)
        dictionaries.setSortingEnabled(False)
        dictionaries.setEditTriggers(qt.QTableWidget.EditTrigger.NoEditTriggers)
        dictionaries.setSelectionBehavior(
            qt.QAbstractItemView.SelectionBehavior.SelectRows
        )
        dictionaries.setColumnWidth(1, 40)

        if macLin:
            dictionaries.setColumnWidth(2, 40)
        else:
            dictionaries.setColumnWidth(2, 20)

        tableHeader.hide()

        return dictionaries

    def _setupLayout(self) -> None:
        nameLayout = qt.QHBoxLayout()
        nameLayout.addWidget(qt.QLabel("Name: "))
        nameLayout.addWidget(self._groupName)

        self._main_layout.addLayout(nameLayout)

        fontLayoutH1 = qt.QHBoxLayout()
        fontL1 = qt.QLabel("Font: ")
        fontL1.setFixedWidth(100)
        fontLayoutH1.addWidget(fontL1)
        self._fontDropDown.setFixedWidth(175)
        fontLayoutH1.addWidget(self._fontFromDropdown)
        fontLayoutH1.addWidget(self._fontDropDown)
        fontLayoutH1.addStretch()
        self._main_layout.addLayout(fontLayoutH1)

        fontLayoutH2 = qt.QHBoxLayout()
        fontL2 = qt.QLabel("Font From File:")
        fontL2.setFixedWidth(100)
        fontLayoutH2.addWidget(fontL2)
        fontLayoutH2.addWidget(self._fontFromFile)
        self._fontFileName.setFixedWidth(100)
        self._browseFontFile.setFixedWidth(72)
        fontLayoutH2.addWidget(self._fontFileName)
        fontLayoutH2.addWidget(self._browseFontFile)
        fontLayoutH2.addStretch()
        self._main_layout.addLayout(fontLayoutH2)

        self._main_layout.addWidget(qt.QLabel("Dictionaries"))
        self._main_layout.addWidget(self._dictionaries)

        selRemButtons = qt.QHBoxLayout()
        selRemButtons.addWidget(self._selectAll)
        selRemButtons.addWidget(self._removeAll)
        selRemButtons.addStretch()
        self._main_layout.addLayout(selRemButtons)

        cancelSaveButtons = qt.QHBoxLayout()
        cancelSaveButtons.addStretch()
        cancelSaveButtons.addWidget(self._cancelButton)
        cancelSaveButtons.addWidget(self._saveButton)

        self._main_layout.addLayout(cancelSaveButtons)
        self.setLayout(self._main_layout)

    def clearGroupEditor(self, new: bool = False) -> None:
        self._groupName.clear()
        self._groupName.setEnabled(True)
        self.setWindowTitle("Add Dictionary Group")
        self._fontFromDropdown.setChecked(True)
        self._toggleFontType(False)
        self._fontFileName.setText("None Selected")
        self._fontToMove = None
        self._fontDropDown.setCurrentIndex(0)
        self._reloadDictTable()

        if new:
            self._resetNew()
