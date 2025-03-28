# -*- coding: utf-8 -*-

import typing
import json
import sys
import math
from aqt.qt import *
from anki.utils import is_mac, is_lin
from anki.lang import _
from os.path import join, exists
import aqt
from PyQt6 import QtCore
from .miutils import miInfo, miAsk
from shutil import copyfile
from operator import itemgetter
import ntpath

if typing.TYPE_CHECKING:
    # TODO: @ColinKennedy - fix cyclic dependency "addonSettings.SettingsGui" later
    from . import addonSettings

from . import typer


class _Dictionary(typing.NamedTuple):
    index: int
    order: int
    text: str


class _Group(typing.TypedDict):
    customFont: bool
    dictionaries: typing.List[_Dictionary]
    font: str


class DictGroupEditor(QDialog):
    def __init__(
        self,
        mw: aqt.mw,
        # TODO: @ColinKennedy - fix cyclic dependency "addonSettings.SettingsGui" later
        parent: "addonSettings.SettingsGui",
        dictionaries: typing.Optional[typing.Iterable[str]]= None,
        group: typing.Optional[_Group]= None,
        groupName: str = False,
    ):
        super().__init__(parent, QtCore.Qt.Window)

        dictionaries = dictionaries or []
        self.mw = mw
        self.settings = parent
        self.setWindowTitle("Add Dictionary Group")
        self.groupName = QLineEdit()
        self.fontFromDropdown = QRadioButton()
        self.fontFromFile = QRadioButton()
        self.fontDropDown = self.getFontCB()
        self.fontFileName = QLabel('None Selected')
        self.browseFontFile = QPushButton('Browse')
        self.dictionaries = self.setupDictionaries()
        self.selectAll = QPushButton('Select All')
        self.removeAll = QPushButton('Remove All')
        self.cancelButton = QPushButton('Cancel')
        self.saveButton = QPushButton('Save')
        self._main_layout = QVBoxLayout()
        self.setupLayout()
        self.fontToMove = False
        self.dictList = dictionaries
        self.loadDictionaries(dictionaries)
        self.new = True
        if group:
            self.new = False
            self.loadGroupEditor(group, groupName)
        else:
            self.clearGroupEditor()
        self.initHandlers()
        self.initTooltips()

    def initTooltips(self) -> None:
        self.groupName.setToolTip('The name of the dictionary group.')
        self.fontFromDropdown.setToolTip('Select a font installed on your system.')
        self.fontDropDown.setToolTip('Select a font installed on your system.')
        self.fontFromFile.setToolTip('Select a font to import from a file.')
        self.browseFontFile.setToolTip('Select a font to import from a file.')
        self.selectAll.setToolTip('Select all dictionaries.')
        self.removeAll.setToolTip('Clear the current selection.')

    def resetNew(self) -> None:
        self.new = True

    def clearGroupEditor(self, new: bool = False) -> None:
        self.groupName.clear()
        self.groupName.setEnabled(True)
        self.setWindowTitle("Add Dictionary Group")
        self.fontFromDropdown.setChecked(True)
        self.toggleFontType(False)
        self.fontFileName.setText('None Selected')
        self.fontToMove = False
        self.fontDropDown.setCurrentIndex(0)
        self.reloadDictTable()
        if new:
            self.resetNew()

    def reloadDictTable(self) -> None:
        self.dictionaries.setRowCount(0)
        self.loadDictionaries(self.dictList)

    def loadGroupEditor(self, group: _Group, groupName: str) -> None:
        self.clearGroupEditor()
        self.new = False
        self.setWindowTitle("Edit Dictionary Group")
        self.groupName.setText(groupName)
        self.groupName.setEnabled(False)

        if group['customFont']:
            self.fontFromFile.setChecked(True)
            self.toggleFontType(True)
            self.fontFileName.setText(group['font'])
        else:
            self.fontDropDown.setCurrentText(group['font'])

        self.loadSelectedDictionaries(group['dictionaries'])

    def loadSelectedDictionaries(self, dicts: typing.Iterable[str]) -> None:
        count = 1
        for d in dicts:
            for i in range(self.dictionaries.rowCount()):
                item = self.dictionaries.item(i, 0)

                if not item:
                    raise RuntimeError(f'Index "{i}" has no dictionary column==0 item.')

                if d != item.text():
                    continue

                item = self.dictionaries.item(i, 1)

                if not item:
                    raise RuntimeError(f'Index "{i}" has no dictionary column==1 item.')

                widget = typing.cast(
                    typing.Optional[QCheckBox],
                    self.dictionaries.cellWidget(i, 2),
                )

                if not widget:
                    raise RuntimeError(f'Index "{i}" has no dictionary column==2 widget.')

                item.setText(str(count))
                widget.setChecked(True)
                count += 1

    def getConfig(self) -> typer.Configuration:
        return self.mw.addonManager.getConfig(__name__)

    def initHandlers(self) -> None:
        self.browseFontFile.clicked.connect(self.grabFontFromFile)
        self.saveButton.clicked.connect(self.saveDictGroup)
        self.cancelButton.clicked.connect(self.hide)
        self.fontFromDropdown.clicked.connect(lambda: self.toggleFontType(False))
        self.fontFromFile.clicked.connect(lambda: self.toggleFontType(True))
        self.selectAll.clicked.connect(self.selectAllDicts)
        self.removeAll.clicked.connect(self.removeAllDicts)

    def _get_dict_checkboxes(self) -> list[QCheckBox]:
        output: list[QCheckBox] = []

        for i in range(self.dictionaries.rowCount()):
            widget = typing.cast(typing.Optional[QCheckBox], self.dictionaries.cellWidget(i, 2))

            if not widget:
                raise RuntimeError(f'Index "{i}" has no checkbox from column==2.')

            output.append(widget)

        return output

    def selectAllDicts(self) -> None:
        for i, widget in enumerate(self._get_dict_checkboxes()):
            if not widget.isChecked():
                widget.setChecked(True)
                self.setDictionaryOrder(i)

    def removeAllDicts(self) -> None:
        for i, widget in enumerate(self._get_dict_checkboxes()):
            if widget.isChecked():
                widget.setChecked(False)
                self.setDictionaryOrder(i)

    def toggleFontType(self, fromFile: bool) -> None:
        if fromFile:
            self.fontDropDown.setEnabled(False)
            self.browseFontFile.setEnabled(True)
            self.fontFileName.setEnabled(True)
        else:
            self.fontDropDown.setEnabled(True)
            self.browseFontFile.setEnabled(False)
            self.fontFileName.setEnabled(False)

    def grabFontFromFile(self) -> None:
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"Select a Custom Font", "",'Font Files (*.ttf *.woff *.woff2 *.eot)', options=options)
        if fileName:
            if not fileName.endswith('.ttf') and not fileName.endswith('.woff') and not fileName.endswith('.woff2') and not fileName.endswith('.eot') :
                miInfo('Please select a font file.', level='err')
                return
            self.fontFileName.setText(ntpath.basename(fileName))
            self.fontToMove = fileName

    def saveDictGroup(self) -> None:
        newConfig = self.getConfig()
        gn = self.groupName.text()
        if gn  == '':
            miInfo('The dictionary group must have a name.', level='wrn')
            return
        curGroups = newConfig['DictionaryGroups']
        if self.new and gn in curGroups:
            miInfo('A new dictionary group must have a unique name.', level='wrn')
            return
        if self.fontFromDropdown.isChecked():
            fontName = self.fontDropDown.currentText()
            customFont = False

        else:
            fontName = self.fontFileName.text()
            if fontName == 'None Selected':
                miInfo('You must select a file if you will be using a font from a file.', level='wrn')
                return
            customFont = True
            if not exists(join(self.settings.addonPath,'user_files', 'fonts', fontName)):
                if not self.moveFontToFolder(self.fontToMove):
                    miInfo('The font file was unable to be loaded, please ensure your file exists in the target folder and try again.', level='err')
                    return
        selectedDicts = self.getSelectedDictionaryNames()

        if len(selectedDicts) < 1:
            miInfo('You must select at least one dictionary.', level='wrn')

            return

        dictGroup: _Group = {
            'customFont' : customFont,
            'dictionaries' : selectedDicts,
            'font' : fontName,
        }
        curGroups[gn] = dictGroup
        self.mw.addonManager.writeConfig(__name__, newConfig)
        self.settings.loadTemplateTable()
        self.settings.loadGroupTable()
        self.hide()

    def getSelectedDictionaryNames(self) -> list[str]:
        return [item[2] for item in self.getSelectedDictionaries()]

    def getSelectedDictionaries(self) -> list[_Dictionary]:
        dicts: list[_Dictionary] = []

        for i in range(self.dictionaries.rowCount()):
            item = self.dictionaries.item(i, 1)

            if not item:
                raise RuntimeError(f'Index "{i}" column==1 has no table item.')

            order = item.text()

            if not order:
                continue

            item = self.dictionaries.item(i, 0)

            if not item:
                raise RuntimeError(f'Index "{i}" column==0 has no table item.')

            dicts.append((i, int(order), item.text()))

        return sorted(dicts, key=itemgetter(1))

    def setDictionaryOrder(self, row: int) -> None:
        self.dictionaries.selectRow(row)
        widget = typing.cast(typing.Optional[QCheckBox], self.dictionaries.cellWidget(row, 2))

        if not widget:
            raise RuntimeError(f'Row "{row}" has no dictionary widget.')

        if not widget.isChecked():
            item = self.dictionaries.item(row, 1)

            if not item:
                raise RuntimeError(f'Row "{row}" column==1 has no cell item.')

            item.setText('')
            self.reorderDictionaries()

            return

        self.reorderDictionaries(row)

    def reorderDictionaries(self, last: typing.Optional[int]= None) -> None:
        dicts = self.getSelectedDictionaries()

        for idx, d in enumerate(dicts):
            index = d[0]
            item = self.dictionaries.item(index, 1)

            if not item:
                raise RuntimeError(f'Last index "{index}" column==1 has no item.')

            item.setText(str(idx + 1))

        if last is not None:
            item = self.dictionaries.item(last, 1)

            if not item:
                raise RuntimeError(f'Last index "{last}" column==1 has no item.')

            item.setText(str(len(dicts) + 1))

    def moveFontToFolder(self, filename: str) -> bool:
        try:
            basename = ntpath.basename(filename)

            if not exists(filename):
                # TODO: @ColinKennedy - Logging
                return False

            path = join(self.settings.addonPath, 'user_files', 'fonts', basename)

            if exists(path):
                if not miAsk('A font with the same name currently exists in your custom fonts folder. Would you like to overwrite it?', self):
                    return False

            copyfile(filename, path)

            return True
        except:
            return False

    def setOrder(self, x: int) -> typing.Callable[[], None]:
        return lambda: self.setDictionaryOrder(x)

    def getFontCB(self) -> QComboBox:
        fonts = QComboBox()
        fams = QFontDatabase.families()
        fonts.addItems(fams)
        return fonts

    def loadDictionaries(self, dictionaries: typing.Iterable[str]) -> None:
        for dictName in dictionaries:
            rc = self.dictionaries.rowCount()
            self.dictionaries.setRowCount(rc + 1)
            self.dictionaries.setItem(rc, 0, QTableWidgetItem(dictName))
            self.dictionaries.setItem(rc, 1, QTableWidgetItem(''))
            checkBox =  QCheckBox()
            checkBox.setFixedWidth(40)
            checkBox.setStyleSheet('QCheckBox{padding-left:10px;}')
            self.dictionaries.setCellWidget(rc, 2, checkBox)
            checkBox.clicked.connect(self.setOrder(rc))
        self.addDefaultDict('Google Images')
        self.addDefaultDict('Forvo')

    def addDefaultDict(self, name: str) -> None:
        rc = self.dictionaries.rowCount()
        self.dictionaries.setRowCount(rc + 1)
        self.dictionaries.setItem(rc, 0, QTableWidgetItem(name))
        self.dictionaries.setItem(rc, 1, QTableWidgetItem(''))
        checkBox =  QCheckBox()
        checkBox.setFixedWidth(40)
        checkBox.setStyleSheet('QCheckBox{padding-left:10px;}')
        checkBox.clicked.connect(self.setOrder(rc))
        self.dictionaries.setCellWidget(rc, 2, checkBox)

    def setupDictionaries(self) -> QTableWidget:
        macLin = False
        if is_mac  or is_lin:
            macLin = True
        dictionaries = QTableWidget()
        dictionaries.setColumnCount(3)
        tableHeader = dictionaries.horizontalHeader()

        if not tableHeader:
            raise RuntimeError(f'Expected "{dictionaries}" to have a header.')

        tableHeader.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        tableHeader.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)

        dictionaries.setRowCount(0)
        dictionaries.setSortingEnabled(False)
        dictionaries.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        dictionaries.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        dictionaries.setColumnWidth(1, 40)

        if macLin:
            dictionaries.setColumnWidth(2, 40)
        else:
            dictionaries.setColumnWidth(2, 20)

        tableHeader.hide()

        return dictionaries

    def setupLayout(self) -> None:
        nameLayout = QHBoxLayout()
        nameLayout.addWidget(QLabel('Name: '))
        nameLayout.addWidget(self.groupName)

        self._main_layout.addLayout(nameLayout)

        fontLayoutH1 = QHBoxLayout()
        fontL1 = QLabel('Font: ')
        fontL1.setFixedWidth(100)
        fontLayoutH1.addWidget(fontL1)
        self.fontDropDown.setFixedWidth(175)
        fontLayoutH1.addWidget(self.fontFromDropdown)
        fontLayoutH1.addWidget(self.fontDropDown)
        fontLayoutH1.addStretch()
        self._main_layout.addLayout(fontLayoutH1)

        fontLayoutH2 = QHBoxLayout()
        fontL2 = QLabel('Font From File:')
        fontL2.setFixedWidth(100)
        fontLayoutH2.addWidget(fontL2)
        fontLayoutH2.addWidget(self.fontFromFile)
        self.fontFileName.setFixedWidth(100)
        self.browseFontFile.setFixedWidth(72)
        fontLayoutH2.addWidget(self.fontFileName)
        fontLayoutH2.addWidget(self.browseFontFile)
        fontLayoutH2.addStretch()
        self._main_layout.addLayout(fontLayoutH2)

        self._main_layout.addWidget(QLabel('Dictionaries'))
        self._main_layout.addWidget(self.dictionaries)

        selRemButtons = QHBoxLayout()
        selRemButtons.addWidget(self.selectAll)
        selRemButtons.addWidget(self.removeAll)
        selRemButtons.addStretch()
        self._main_layout.addLayout(selRemButtons)

        cancelSaveButtons = QHBoxLayout()
        cancelSaveButtons.addStretch()
        cancelSaveButtons.addWidget(self.cancelButton)
        cancelSaveButtons.addWidget(self.saveButton)

        self._main_layout.addLayout(cancelSaveButtons)
        self.setLayout(self._main_layout)
