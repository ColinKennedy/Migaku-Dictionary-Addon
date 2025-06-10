# -*- coding: utf-8 -*-

import json
import math
import os
import platform
import re
import sys
import typing

from anki import utils
from anki.lang import _
from aqt import main
from aqt import qt
from aqt import utils as aqt_utils
from aqt import webview
from PyQt6 import QtSvgWidgets

from . import (
    addDictGroup,
    addTemplate,
    dictdb,
    dictionaryManager,
    ffmpegInstaller,
    migaku_configuration,
    miutils,
    typer,
)

verNumber = "1.3.8"
T = typing.TypeVar("T")


def attemptOpenLink(cmd: str) -> None:
    if cmd.startswith("openLink:"):
        aqt_utils.openLink(cmd[9:])


class MigakuSVG(QtSvgWidgets.QSvgWidget):
    clicked = qt.pyqtSignal()

    # TODO: @ColinKennedy Check if this returns bool
    def mousePressEvent(self, ev: typing.Optional[qt.QMouseEvent]) -> None:
        self.clicked.emit()


class MigakuLabel(qt.QLabel):
    clicked = qt.pyqtSignal()

    def __init__(self, parent: typing.Optional[qt.QWidget] = None):
        super().__init__(parent)

    # TODO: @ColinKennedy Check if this returns bool
    def mousePressEvent(self, ev: typing.Optional[qt.QMouseEvent]) -> None:
        self.clicked.emit()


class SettingsGui(qt.QTabWidget):
    def __init__(
        self, mw: main.AnkiQt, path: str, reboot: typing.Callable[[], None]
    ) -> None:
        super(SettingsGui, self).__init__()
        self._mw = mw
        self._ffmpegInstaller = ffmpegInstaller.FFMPEGInstaller(self._mw)
        self._reboot = reboot
        self._googleCountries = [
            "Afghanistan",
            "Albania",
            "Algeria",
            "American Samoa",
            "Andorra",
            "Angola",
            "Anguilla",
            "Antarctica",
            "Antigua and Barbuda",
            "Argentina",
            "Armenia",
            "Aruba",
            "Australia",
            "Austria",
            "Azerbaijan",
            "Bahamas",
            "Bahrain",
            "Bangladesh",
            "Barbados",
            "Belarus",
            "Belgium",
            "Belize",
            "Benin",
            "Bermuda",
            "Bhutan",
            "Bolivia",
            "Bosnia and Herzegovina",
            "Botswana",
            "Bouvet Island",
            "Brazil",
            "British Indian Ocean Territory",
            "Brunei Darussalam",
            "Bulgaria",
            "Burkina Faso",
            "Burundi",
            "Cambodia",
            "Cameroon",
            "Canada",
            "Cape Verde",
            "Cayman Islands",
            "Central African Republic",
            "Chad",
            "Chile",
            "China",
            "Christmas Island",
            "Cocos (Keeling) Islands",
            "Colombia",
            "Comoros",
            "Congo",
            "Congo, the Democratic Republic of the",
            "Cook Islands",
            "Costa Rica",
            "Cote D'ivoire",
            "Croatia (Hrvatska)",
            "Cuba",
            "Cyprus",
            "Czech Republic",
            "Denmark",
            "Djibouti",
            "Dominica",
            "Dominican Republic",
            "East Timor",
            "Ecuador",
            "Egypt",
            "El Salvador",
            "Equatorial Guinea",
            "Eritrea",
            "Estonia",
            "Ethiopia",
            "European Union",
            "Falkland Islands (Malvinas)",
            "Faroe Islands",
            "Fiji",
            "Finland",
            "France",
            "France, Metropolitan",
            "French Guiana",
            "French Polynesia",
            "French Southern Territories",
            "Gabon",
            "Gambia",
            "Georgia",
            "Germany",
            "Ghana",
            "Gibraltar",
            "Greece",
            "Greenland",
            "Grenada",
            "Guadeloupe",
            "Guam",
            "Guatemala",
            "Guinea",
            "Guinea-Bissau",
            "Guyana",
            "Haiti",
            "Heard Island and Mcdonald Islands",
            "Holy See (Vatican City State)",
            "Honduras",
            "Hong Kong",
            "Hungary",
            "Iceland",
            "India",
            "Indonesia",
            "Iran, Islamic Republic of",
            "Iraq",
            "Ireland",
            "Israel",
            "Italy",
            "Jamaica",
            "Japan",
            "Jordan",
            "Kazakhstan",
            "Kenya",
            "Kiribati",
            "Korea, Democratic People's Republic of",
            "Korea, Republic of",
            "Kuwait",
            "Kyrgyzstan",
            "Lao People's Democratic Republic",
            "Latvia",
            "Lebanon",
            "Lesotho",
            "Liberia",
            "Libyan Arab Jamahiriya",
            "Liechtenstein",
            "Lithuania",
            "Luxembourg",
            "Macao",
            "Macedonia, the Former Yugosalv Republic of",
            "Madagascar",
            "Malawi",
            "Malaysia",
            "Maldives",
            "Mali",
            "Malta",
            "Marshall Islands",
            "Martinique",
            "Mauritania",
            "Mauritius",
            "Mayotte",
            "Mexico",
            "Micronesia, Federated States of",
            "Moldova, Republic of",
            "Monaco",
            "Mongolia",
            "Montserrat",
            "Morocco",
            "Mozambique",
            "Myanmar",
            "Namibia",
            "Nauru",
            "Nepal",
            "Netherlands",
            "Netherlands Antilles",
            "New Caledonia",
            "New Zealand",
            "Nicaragua",
            "Niger",
            "Nigeria",
            "Niue",
            "Norfolk Island",
            "Northern Mariana Islands",
            "Norway",
            "Oman",
            "Pakistan",
            "Palau",
            "Palestinian Territory",
            "Panama",
            "Papua New Guinea",
            "Paraguay",
            "Peru",
            "Philippines",
            "Pitcairn",
            "Poland",
            "Portugal",
            "Puerto Rico",
            "Qatar",
            "Reunion",
            "Romania",
            "Russian Federation",
            "Rwanda",
            "Saint Helena",
            "Saint Kitts and Nevis",
            "Saint Lucia",
            "Saint Pierre and Miquelon",
            "Saint Vincent and the Grenadines",
            "Samoa",
            "San Marino",
            "Sao Tome and Principe",
            "Saudi Arabia",
            "Senegal",
            "Serbia and Montenegro",
            "Seychelles",
            "Sierra Leone",
            "Singapore",
            "Slovakia",
            "Slovenia",
            "Solomon Islands",
            "Somalia",
            "South Africa",
            "South Georgia and the South Sandwich Islands",
            "Spain",
            "Sri Lanka",
            "Sudan",
            "Suriname",
            "Svalbard and Jan Mayen",
            "Swaziland",
            "Sweden",
            "Switzerland",
            "Syrian Arab Republic",
            "Taiwan",
            "Tajikistan",
            "Tanzania, United Republic of",
            "Thailand",
            "Togo",
            "Tokelau",
            "Tonga",
            "Trinidad and Tobago",
            "Tunisia",
            "Turkey",
            "Turkmenistan",
            "Turks and Caicos Islands",
            "Tuvalu",
            "Uganda",
            "Ukraine",
            "United Arab Emirates",
            "United Kingdom",
            "United States",
            "United States Minor Outlying Islands",
            "Uruguay",
            "Uzbekistan",
            "Vanuatu",
            "Venezuela",
            "Vietnam",
            "Virgin Islands, British",
            "Virgin Islands, U.S.",
            "Wallis and Futuna",
            "Western Sahara",
            "Yemen",
            "Yugoslavia",
            "Zambia",
            "Zimbabwe",
        ]
        self._forvoLanguages = [
            "Afrikaans",
            "Ancient Greek",
            "Arabic",
            "Armenian",
            "Azerbaijani",
            "Bashkir",
            "Basque",
            "Belarusian",
            "Bengali",
            "Bulgarian",
            "Cantonese",
            "Catalan",
            "Chuvash",
            "Croatian",
            "Czech",
            "Danish",
            "Dutch",
            "English",
            "Esperanto",
            "Estonian",
            "Finnish",
            "French",
            "Galician",
            "German",
            "Greek",
            "Hakka",
            "Hebrew",
            "Hindi",
            "Hungarian",
            "Icelandic",
            "Indonesian",
            "Interlingua",
            "Irish",
            "Italian",
            "Japanese",
            "Kabardian",
            "Korean",
            "Kurdish",
            "Latin",
            "Latvian",
            "Lithuanian",
            "Low German",
            "Luxembourgish",
            "Mandarin Chinese",
            "Mari",
            "Min Nan",
            "Northern Sami",
            "Norwegian Bokmål",
            "Persian",
            "Polish",
            "Portuguese",
            "Punjabi",
            "Romanian",
            "Russian",
            "Serbian",
            "Slovak",
            "Slovenian",
            "Spanish",
            "Swedish",
            "Tagalog",
            "Tatar",
            "Thai",
            "Turkish",
            "Ukrainian",
            "Urdu",
            "Uyghur",
            "Venetian",
            "Vietnamese",
            "Welsh",
            "Wu Chinese",
            "Yiddish",
        ]
        self.setMinimumSize(850, 550)
        if not utils.is_win:
            self.resize(1034, 550)
        else:
            self.resize(920, 550)
        # self.setContextMenuPolicy(qt.Qt.NoContextMenu)
        self.setContextMenuPolicy(qt.Qt.ContextMenuPolicy.NoContextMenu)
        self.setWindowTitle("Migaku Dictionary Settings (Ver. " + verNumber + ")")
        self.addonPath = path
        self.setWindowIcon(
            qt.QIcon(os.path.join(self.addonPath, "icons", "migaku.png"))
        )
        self._addDictGroup = qt.QPushButton("Add Dictionary Group")
        self._addExportTemplate = qt.QPushButton("Add Export Template")
        self._dictGroups = self._getGroupTemplateTable()
        self._exportTemplates = self._getGroupTemplateTable()
        self._tooltipCB = qt.QCheckBox()
        self._tooltipCB.setFixedHeight(30)
        self._maxImgWidth = qt.QSpinBox()
        self._maxImgWidth.setRange(0, 9999)
        self._maxImgHeight = qt.QSpinBox()
        self._maxImgHeight.setRange(0, 9999)
        self._safeSearch = qt.QCheckBox()
        self._googleCountry = qt.QComboBox()
        self._googleCountry.addItems(self._googleCountries)
        self._forvoLang = qt.QComboBox()
        self._forvoLang.addItems(self._forvoLanguages)
        self._condensedAudioDirectoryLabel = qt.QLabel("Condensed Audio Save Location:")
        self._chooseAudioDirectory = qt.QPushButton("Choose Directory")
        self._convertToMp3 = qt.QCheckBox()
        self._disableCondensedMessages = qt.QCheckBox()
        self._dictOnTop = qt.QCheckBox()
        self._showTarget = qt.QCheckBox()
        self._totalDefs = qt.QSpinBox()
        self._totalDefs.setRange(0, 1000)
        self._dictDefs = qt.QSpinBox()
        self._dictDefs.setRange(0, 100)
        self._genJSExport = qt.QCheckBox()
        self._genJSEdit = qt.QCheckBox()
        self._frontBracket = qt.QLineEdit()
        self._backBracket = qt.QLineEdit()
        self._highlightTarget = qt.QCheckBox()
        self._highlightSentence = qt.QCheckBox()
        self._openOnStart = qt.QCheckBox()
        self._globalHotkeys = qt.QCheckBox()
        self._globalOpen = qt.QCheckBox()
        self._restoreButton = qt.QPushButton("Restore Defaults")
        self._cancelButton = qt.QPushButton("Cancel")
        self._applyButton = qt.QPushButton("Apply")
        self._main_layout = qt.QVBoxLayout()
        self._settingsTab = qt.QWidget(self)
        self._userGuideTab = self._getUserGuideTab()
        self._setupLayout()
        self.addTab(self._settingsTab, "Settings")
        self.addTab(dictionaryManager.DictionaryManagerWidget(), "Dictionaries")
        self.addTab(self._userGuideTab, "User Guide")
        self.addTab(self._getAboutTab(), "About")
        self.loadTemplateTable()
        self.loadGroupTable()
        self._initHandlers()
        self._loadConfig()
        self._initTooltips()
        self._hotkeyEsc = qt.QShortcut(qt.QKeySequence("Esc"), self)
        self._hotkeyEsc.activated.connect(self.close)

        self.show()

    def _get_group_text(self, row: int) -> str:
        item = self._dictGroups.item(row, 0)

        if not item:
            raise RuntimeError(f'No dict group could be found for "{row}"')

        return item.text()

    def _initTooltips(self) -> None:
        self._addDictGroup.setToolTip(
            "Add a new dictionary group.\nDictionary groups allow you to specify which dictionaries to search\nwithin. You can also set a specific font for that group."
        )
        self._addExportTemplate.setToolTip(
            "Add a new export template.\nExport templates allow you to specify a note type, and fields where\ntarget sentences, target words, definitions, and images will be sent to\n when using the Card Exporter to create cards."
        )
        self._tooltipCB.setToolTip(
            "Enable/disable tooltips within the dictionary and its sub-windows."
        )
        self._maxImgWidth.setToolTip("Images will be scaled according to this width.")
        self._maxImgHeight.setToolTip("Images will be scaled according to this height.")
        self._googleCountry.setToolTip(
            "Select the country or region to search Google Images from, the search region\ngreatly impacts search results so choose a location where your target language is spoken."
        )
        self._forvoLang.setToolTip(
            "Select the language to be used with the Forvo Dictionary."
        )
        self._showTarget.setToolTip(
            "Show/Hide the Target Identifier from the dictionary window. The Target Identifier\nlets you know which window is currently selected and will be used when sending\ndefinitions to a target field."
        )
        self._totalDefs.setToolTip(
            "This is the total maximum number of definitions which the dictionary will output."
        )
        self._dictDefs.setToolTip(
            "This is the maximum number of definitions which the dictionary will output for any given dictionary."
        )
        self._genJSExport.setToolTip(
            "If this is enabled and you have Migaku Japanese installed in Anki,\nthen when a card is exported, readings and accent information will automatically be generated for all\nactive fields. This generation is based on your Migaku Japanese Sentence Button (文) settings."
        )
        self._genJSEdit.setToolTip(
            "If this is enabled and you have Migaku Japanese installed in Anki,\nthen when a definition is sent to a field, readings and accent information will automatically be generated for all\nactive fields. This generation is based on your Migaku Japanese Sentence Button (文) settings."
        )
        self._frontBracket.setToolTip(
            "This is the text that will be placed in front of each term\n in the dictionary."
        )
        self._backBracket.setToolTip(
            "This is the text that will be placed after each term\nin the dictionary."
        )
        self._highlightTarget.setToolTip(
            "The dictionary will highlight the searched term in\nthe search results."
        )
        self._highlightSentence.setToolTip(
            "The dictionary will highlight example sentences in\nthe search results. This feature is experimental and currently only\nfunctions on Japanese monolingual dictionaries."
        )
        self._openOnStart.setToolTip(
            "Enable/Disable launching the Migaku Dictionary on profile load."
        )
        linNote = ""
        self._globalHotkeys.setToolTip("Enable/Disable global hotkeys." + linNote)
        self._globalOpen.setToolTip(
            "If enabled the dictionary will be opened on a global search."
        )
        self._safeSearch.setToolTip(
            "Whether or not to enable Safe Search for Google Images."
        )
        self._convertToMp3.setToolTip(
            "When enabled will convert extension WAV files into MP3 files.\nMP3 files are supported across every Anki platform and are much smaller than WAV files.\nWe recommend enabling this option."
        )
        self._disableCondensedMessages.setToolTip(
            "Disable messages shown when condensed audio files are successfully created."
        )

    def _getConfig(self) -> typer.Configuration:
        # TODO: @ColinKennedy Add validation here
        return typing.cast(
            typer.Configuration, self._mw.addonManager.getConfig(__name__)
        )

    def _loadConfig(self) -> None:
        config = self._getConfig()
        self._openOnStart.setChecked(config["dictOnStart"])
        self._highlightSentence.setChecked(config["highlightSentences"])
        self._highlightTarget.setChecked(config["highlightTarget"])
        self._totalDefs.setValue(config["maxSearch"])
        self._dictDefs.setValue(config["dictSearch"])
        self._genJSExport.setChecked(config["jReadingCards"])
        self._genJSEdit.setChecked(config["jReadingEdit"])
        self._googleCountry.setCurrentText(config["googleSearchRegion"])
        self._forvoLang.setCurrentText(config["ForvoLanguage"])
        self._maxImgWidth.setValue(config["maxWidth"])
        self._maxImgHeight.setValue(config["maxHeight"])
        self._frontBracket.setText(config["frontBracket"])
        self._backBracket.setText(config["backBracket"])
        self._showTarget.setChecked(config["showTarget"])
        self._tooltipCB.setChecked(config["tooltips"])
        self._globalHotkeys.setChecked(config["globalHotkeys"])
        self._globalOpen.setChecked(config["openOnGlobal"])
        self._safeSearch.setChecked(config["safeSearch"])
        self._convertToMp3.setChecked(config["mp3Convert"])
        self._disableCondensedMessages.setChecked(config["disableCondensed"])
        self._dictOnTop.setChecked(config["dictAlwaysOnTop"])
        if config.get("condensedAudioDirectory", False) is not False:
            self._chooseAudioDirectory.setText(config["condensedAudioDirectory"])
        else:
            self._chooseAudioDirectory.setText("Choose Directory")

    def _saveConfig(self) -> None:
        # TODO: @ColinKennedy fix the cyclic import later
        from . import migaku_dictionary

        nc = self._getConfig()
        nc["dictOnStart"] = self._openOnStart.isChecked()
        nc["highlightSentences"] = self._highlightSentence.isChecked()
        nc["highlightTarget"] = self._highlightTarget.isChecked()
        nc["maxSearch"] = self._totalDefs.value()
        nc["dictSearch"] = self._dictDefs.value()
        nc["jReadingCards"] = self._genJSExport.isChecked()
        nc["jReadingEdit"] = self._genJSEdit.isChecked()
        nc["googleSearchRegion"] = self._googleCountry.currentText()
        nc["ForvoLanguage"] = self._forvoLang.currentText()
        nc["maxWidth"] = self._maxImgWidth.value()
        nc["maxHeight"] = self._maxImgHeight.value()
        nc["frontBracket"] = self._frontBracket.text()
        nc["backBracket"] = self._backBracket.text()
        nc["showTarget"] = self._showTarget.isChecked()
        nc["tooltips"] = self._tooltipCB.isChecked()
        nc["globalHotkeys"] = self._globalHotkeys.isChecked()
        nc["openOnGlobal"] = self._globalOpen.isChecked()
        nc["mp3Convert"] = self._convertToMp3.isChecked()
        nc["disableCondensed"] = self._disableCondensedMessages.isChecked()
        nc["safeSearch"] = self._safeSearch.isChecked()
        nc["dictAlwaysOnTop"] = self._dictOnTop.isChecked()
        if self._chooseAudioDirectory.text() != "Choose Directory":
            nc["condensedAudioDirectory"] = self._chooseAudioDirectory.text()
        else:
            nc["condensedAudioDirectory"] = None
        self._mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], nc),
        )
        self.hide()
        migaku_configuration.initialize_by_namespace()

        if nc["mp3Convert"]:
            self._ffmpegInstaller.installFFMPEG()

        if migaku_dictionary.get_visible_dictionary():
            miutils.miInfo(
                "Please be aware that the dictionary window will not reflect any setting changes until it is closed and reopened.",
                level="not",
            )

    def _updateAudioDirectory(self) -> None:
        directory = str(
            qt.QFileDialog.getExistingDirectory(
                None, "Select Condensed Audio Directory"
            )
        )
        if directory:
            self._chooseAudioDirectory.setText(directory)
        else:
            self._chooseAudioDirectory.setText("Choose Directory")

    def _getGroupTemplateTable(self) -> qt.QTableWidget:
        macLin = False
        if utils.is_mac or utils.is_lin:
            macLin = True
        groupTemplates = qt.QTableWidget()
        groupTemplates.setColumnCount(3)
        tableHeader = groupTemplates.horizontalHeader()

        if not tableHeader:
            raise RuntimeError("Group templates has no horizontal header.")

        tableHeader.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.Stretch)
        tableHeader.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Fixed)
        tableHeader.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Fixed)
        groupTemplates.setRowCount(0)
        groupTemplates.setSortingEnabled(False)
        groupTemplates.setEditTriggers(qt.QAbstractItemView.EditTrigger.NoEditTriggers)
        groupTemplates.setSelectionBehavior(
            qt.QAbstractItemView.SelectionBehavior.SelectRows
        )
        if macLin:
            groupTemplates.setColumnWidth(1, 50)
            groupTemplates.setColumnWidth(2, 40)
        else:
            groupTemplates.setColumnWidth(1, 40)
            groupTemplates.setColumnWidth(2, 40)
        tableHeader.hide()
        return groupTemplates

    # TODO: @ColinKennedy Remove later
    def _removeGroupRow(self, x: int) -> typing.Callable[[], None]:
        return lambda: self._removeGroup(x)

    # TODO: @ColinKennedy Remove later
    def _editGroupRow(self, x: int) -> typing.Callable[[], None]:
        return lambda: self._editGroup(x)

    def _editGroup(self, row: int) -> None:
        groupName = self._get_group_text(row)
        dictGroups = self._getConfig()["DictionaryGroups"]
        if groupName in dictGroups:
            group = dictGroups[groupName]
            dictEditor = addDictGroup.DictGroupEditor(
                self._mw, self, self._getDictionaryNames(), group, groupName
            )
            dictEditor.exec()

    def _removeGroup(self, row: int) -> None:
        if not miutils.miAsk(
            "Are you sure you would like to remove this dictionary group? This action will happen immediately and is not un-doable.",
            self,
        ):
            return

        newConfig = self._getConfig()
        dictGroups = newConfig["DictionaryGroups"]
        groupName = self._get_group_text(row)
        del dictGroups[groupName]
        self._mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], newConfig),
        )
        self._dictGroups.removeRow(row)
        self.loadGroupTable()

    def _removeTemplate(self, row: int) -> None:
        if not miutils.miAsk(
            "Are you sure you would like to remove this template? This action will happen immediately and is not un-doable.",
            self,
        ):
            return

        newConfig = self._getConfig()
        exportTemplates = newConfig["ExportTemplates"]
        templateName = self._get_template_text(row)
        del exportTemplates[templateName]
        self._mw.addonManager.writeConfig(
            __name__,
            typing.cast(dict[typing.Any, typing.Any], newConfig),
        )
        self._exportTemplates.removeRow(row)
        self.loadTemplateTable()

    # TODO: @ColinKennedy Remove later
    def _removeTempRow(self, x: int) -> typing.Callable[[], None]:
        return lambda: self._removeTemplate(x)

    # TODO: @ColinKennedy Remove later
    def _editTempRow(self, x: int) -> typing.Callable[[], None]:
        return lambda: self._editTemplate(x)

    def _get_template_text(self, row: int) -> str:
        item = self._exportTemplates.item(row, 0)

        if item:
            return item.text()

        raise RuntimeError(f'Row / Column "{row} / column" has no item.')

    def _editTemplate(self, row: int) -> None:
        templateName = self._get_template_text(row)
        exportTemplates = self._getConfig()["ExportTemplates"]

        if templateName in exportTemplates:
            template = exportTemplates[templateName]
            templateEditor = addTemplate.TemplateEditor(
                self._mw,
                self,
                self._getDictionaryNames(),
                template,
                templateName,
            )
            templateEditor.loadTemplateEditor(template, templateName)
            templateEditor.exec()

    def _getDictionaryNames(self) -> list[str]:
        dictList = dictdb.get().getAllDictsWithLang()
        dictionaryList = []

        for dictionary in dictList:
            dictName = self._cleanDictName(dictionary["dict"])

            if dictName not in dictionaryList:
                dictionaryList.append(dictName)

        dictionaryList = sorted(dictionaryList, key=str.casefold)
        return dictionaryList

    def _initHandlers(self) -> None:
        self._addDictGroup.clicked.connect(self._addGroup)
        self._addExportTemplate.clicked.connect(self._addTemplate)
        self._restoreButton.clicked.connect(self._restoreDefaults)
        self._cancelButton.clicked.connect(self.close)
        self._applyButton.clicked.connect(self._saveConfig)
        self._chooseAudioDirectory.clicked.connect(self._updateAudioDirectory)

    def _restoreDefaults(self) -> None:
        if not miutils.miAsk(
            "This will remove any export templates and dictionary groups you have created, and is not undoable. Are you sure you would like to restore the default settings?"
        ):
            return

        directory = os.path.dirname(__file__)
        conf = self._mw.addonManager.addonConfigDefaults(directory)

        if not conf:
            raise EnvironmentError(
                f'Could not read a configuration file from "{directory}" directory.'
            )

        self._mw.addonManager.writeConfig(__name__, conf)
        self._userGuideTab.close()
        self._userGuideTab.deleteLater()
        self.close()
        self._reboot()

    def _addGroup(self) -> None:
        dictEditor = addDictGroup.DictGroupEditor(
            self._mw, self, self._getDictionaryNames()
        )
        dictEditor.clearGroupEditor(True)
        dictEditor.exec()

    def _addTemplate(self) -> None:
        templateEditor = addTemplate.TemplateEditor(
            self._mw, self, self._getDictionaryNames()
        )
        templateEditor.exec()

    def _miQLabel(self, text: str, width: int) -> qt.QLabel:
        label = qt.QLabel(text)
        label.setFixedHeight(30)
        label.setFixedWidth(width)
        return label

    def _getLineSeparator(self) -> qt.QFrame:
        line = qt.QFrame()
        line.setFrameShape(qt.QFrame.Shape.VLine)
        line.setFrameShadow(qt.QFrame.Shadow.Plain)
        line.setStyleSheet('QFrame[frameShape="5"]{color: #D5DFE5;}')
        return line

    def _setupLayout(self) -> None:
        groupLayout = qt.QHBoxLayout()
        dictsLayout = qt.QVBoxLayout()
        exportsLayout = qt.QVBoxLayout()

        dictsLayout.addWidget(qt.QLabel("Dictionary Groups"))
        dictsLayout.addWidget(self._addDictGroup)
        dictsLayout.addWidget(self._dictGroups)

        exportsLayout.addWidget(qt.QLabel("Export Templates"))
        exportsLayout.addWidget(self._addExportTemplate)
        exportsLayout.addWidget(self._exportTemplates)

        groupLayout.addLayout(dictsLayout)
        groupLayout.addLayout(exportsLayout)
        self._main_layout.addLayout(groupLayout)

        optionsBox = qt.QGroupBox("Options")
        optionsLayout = qt.QHBoxLayout()
        optLay1 = qt.QVBoxLayout()
        optLay2 = qt.QVBoxLayout()
        optLay3 = qt.QVBoxLayout()

        startupLay = qt.QHBoxLayout()
        startupLay.addWidget(self._miQLabel("Open on Startup:", 182))
        startupLay.addWidget(self._openOnStart)
        optLay1.addLayout(startupLay)

        highSentLay = qt.QHBoxLayout()
        highSentLay.addWidget(self._miQLabel("Highlight Examples Sentences:", 182))
        highSentLay.addWidget(self._highlightSentence)
        optLay1.addLayout(highSentLay)

        highWordLay = qt.QHBoxLayout()
        highWordLay.addWidget(self._miQLabel("Highlight Searched Term:", 182))
        highWordLay.addWidget(self._highlightTarget)
        optLay1.addLayout(highWordLay)

        expTargetLay = qt.QHBoxLayout()
        expTargetLay.addWidget(self._miQLabel("Show Export Target:", 182))
        expTargetLay.addWidget(self._showTarget)
        optLay1.addLayout(expTargetLay)

        toolTipLay = qt.QHBoxLayout()
        toolTipLay.addWidget(self._miQLabel("Dictionary Tooltips:", 182))
        toolTipLay.addWidget(self._tooltipCB)
        optLay1.addLayout(toolTipLay)

        gHLay = qt.QHBoxLayout()
        gHLay.addWidget(self._miQLabel("Global Hotkeys:", 182))
        gHLay.addWidget(self._globalHotkeys)
        optLay1.addLayout(gHLay)

        extensionMp3Lay = qt.QHBoxLayout()
        extensionMp3Lay.addWidget(self._miQLabel("Convert Extension Audio to MP3", 182))
        extensionMp3Lay.addWidget(self._convertToMp3)
        optLay1.addLayout(extensionMp3Lay)

        disableCondensedLay = qt.QHBoxLayout()
        disableCondensedLay.addWidget(
            self._miQLabel("Disable Condensed Audio Messages:", 182)
        )
        disableCondensedLay.addWidget(self._disableCondensedMessages)
        optLay1.addLayout(disableCondensedLay)

        globalOpenLay = qt.QHBoxLayout()
        globalOpenLay.addWidget(self._miQLabel("Open on Global Search:", 323))
        globalOpenLay.addWidget(self._globalOpen)
        optLay2.addLayout(globalOpenLay)

        totResLay = qt.QHBoxLayout()
        totResLay.addWidget(self._miQLabel("Max Total Search Results:", 180))
        totResLay.addWidget(self._totalDefs)
        self._totalDefs.setFixedWidth(160)
        optLay2.addLayout(totResLay)

        dictResLay = qt.QHBoxLayout()
        dictResLay.addWidget(self._miQLabel("Max Dictionary Search Results:", 180))
        dictResLay.addWidget(self._dictDefs)
        self._dictDefs.setFixedWidth(160)
        optLay2.addLayout(dictResLay)

        genJSExportLay = qt.QHBoxLayout()
        genJSExportLay.addWidget(
            self._miQLabel("Add Cards with Japanese Readings:", 323)
        )
        genJSExportLay.addWidget(self._genJSExport)
        optLay2.addLayout(genJSExportLay)

        genJSEditLay = qt.QHBoxLayout()
        genJSEditLay.addWidget(self._miQLabel("Japanese Readings on Edit:", 323))
        genJSEditLay.addWidget(self._genJSEdit)
        optLay2.addLayout(genJSEditLay)

        countryLay = qt.QHBoxLayout()
        countryLay.addWidget(self._miQLabel("Google Images Search Region:", 180))
        countryLay.addWidget(self._googleCountry)
        self._googleCountry.setFixedWidth(160)
        optLay2.addLayout(countryLay)

        safeLay = qt.QHBoxLayout()
        safeLay.addWidget(self._miQLabel("Safe Search:", 323))
        safeLay.addWidget(self._safeSearch)
        optLay2.addLayout(safeLay)

        optLay2.addStretch()

        maxWidLay = qt.QHBoxLayout()
        maxWidLay.addWidget(self._miQLabel("Maximum Image Width:", 140))
        maxWidLay.addWidget(self._maxImgWidth)
        optLay3.addLayout(maxWidLay)

        maxHeiLay = qt.QHBoxLayout()
        maxHeiLay.addWidget(self._miQLabel("Maximum Image Height:", 140))
        maxHeiLay.addWidget(self._maxImgHeight)
        optLay3.addLayout(maxHeiLay)

        frontBracketLay = qt.QHBoxLayout()
        frontBracketLay.addWidget(self._miQLabel("Surround Term (Front):", 140))
        frontBracketLay.addWidget(self._frontBracket)
        optLay3.addLayout(frontBracketLay)

        backBracketLay = qt.QHBoxLayout()
        backBracketLay.addWidget(self._miQLabel("Surround Term (Back):", 140))
        backBracketLay.addWidget(self._backBracket)
        optLay3.addLayout(backBracketLay)

        forvoLay = qt.QHBoxLayout()
        forvoLay.addWidget(self._miQLabel("Forvo Language:", 140))
        forvoLay.addWidget(self._forvoLang)
        optLay3.addLayout(forvoLay)

        dictOnTopLay = qt.QHBoxLayout()
        dictOnTopLay.addWidget(self._miQLabel("Always on Top:", 323))
        dictOnTopLay.addWidget(self._dictOnTop)
        optLay3.addLayout(dictOnTopLay)

        extensionAudioLay = qt.QHBoxLayout()
        extensionAudioLay.addWidget(self._condensedAudioDirectoryLabel)
        self._chooseAudioDirectory.setFixedWidth(100)
        extensionAudioLay.addWidget(self._chooseAudioDirectory)
        optLay3.addLayout(extensionAudioLay)

        optLay3.addStretch()

        optionsLayout.addLayout(optLay1)
        optionsLayout.addStretch()
        optionsLayout.addWidget(self._getLineSeparator())
        optionsLayout.addStretch()
        optionsLayout.addLayout(optLay2)
        optionsLayout.addStretch()
        optionsLayout.addWidget(self._getLineSeparator())
        optionsLayout.addStretch()
        optionsLayout.addLayout(optLay3)

        optionsBox.setLayout(optionsLayout)
        self._main_layout.addWidget(optionsBox)
        self._main_layout.addStretch()

        buttonsLayout = qt.QHBoxLayout()
        buttonsLayout.addWidget(self._restoreButton)
        buttonsLayout.addStretch()
        buttonsLayout.addWidget(self._cancelButton)
        buttonsLayout.addWidget(self._applyButton)

        self._main_layout.addLayout(buttonsLayout)
        self._settingsTab.setLayout(self._main_layout)

    def _cleanDictName(self, name: str) -> str:
        return re.sub(r"l\d+name", "", name)

    def _getSVGWidget(self, name: str) -> MigakuSVG:
        widget = MigakuSVG(os.path.join(self.addonPath, "icons", name))
        widget.setFixedSize(27, 27)
        return widget

    def _getHTML(self) -> tuple[str, qt.QUrl]:
        htmlPath = os.path.join(self.addonPath, "guide.html")
        url = qt.QUrl.fromLocalFile(htmlPath)
        with open(htmlPath, "r", encoding="utf-8") as fh:
            html = fh.read()
        return html, url

    def _getUserGuideTab(self) -> webview.AnkiWebView:
        guide = webview.AnkiWebView()
        profile = _verify(guide.page()).profile()

        if not profile:
            raise RuntimeError("No Anki profile could be found.")

        profile.setHttpUserAgent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
        )
        _verify(guide.page())._bridge.onCmd = attemptOpenLink
        html, url = self._getHTML()
        _verify(guide.page()).setHtml(html, url)
        guide.setObjectName("tab_4")
        return guide

    def _getAboutTab(self) -> qt.QWidget:
        tab_4 = qt.QWidget()
        tab_4.setObjectName("tab_4")
        tab4vl = qt.QVBoxLayout()
        migakuAbout = qt.QGroupBox()
        migakuAbout.setTitle("Migaku")
        migakuAboutVL = qt.QVBoxLayout()

        migakuAbout.setStyleSheet("QGroupBox { font-weight: bold; } ")
        migakuAboutText = qt.QLabel(
            "This an original Migaku add-on. Migaku seeks to be a comprehensive platform for acquiring foreign languages. The official Migaku website will be published soon!"
        )
        migakuAboutText.setWordWrap(True)
        migakuAboutText.setOpenExternalLinks(True)
        migakuAbout.setLayout(migakuAboutVL)
        migakuAboutLinksTitle = qt.QLabel("<b>Links<b>")

        migakuAboutLinksHL3 = qt.QHBoxLayout()

        migakuInfo = qt.QLabel("Migaku:")
        migakuInfoSite = self._getSVGWidget("migaku.svg")
        migakuInfoSite.setCursor(qt.QCursor(qt.Qt.CursorShape.PointingHandCursor))

        migakuInfoYT = self._getSVGWidget("Youtube.svg")
        migakuInfoYT.setCursor(qt.QCursor(qt.Qt.CursorShape.PointingHandCursor))

        migakuInfoTW = self._getSVGWidget("Twitter.svg")
        migakuInfoTW.setCursor(qt.QCursor(qt.Qt.CursorShape.PointingHandCursor))

        migakuPatreonIcon = self._getSVGWidget("Patreon.svg")
        migakuPatreonIcon.setCursor(qt.QCursor(qt.Qt.CursorShape.PointingHandCursor))
        migakuAboutLinksHL3.addWidget(migakuInfo)
        migakuAboutLinksHL3.addWidget(migakuInfoSite)
        migakuAboutLinksHL3.addWidget(migakuInfoYT)
        migakuAboutLinksHL3.addWidget(migakuInfoTW)
        migakuAboutLinksHL3.addWidget(migakuPatreonIcon)
        migakuAboutLinksHL3.addStretch()

        migakuAboutVL.addWidget(migakuAboutText)
        migakuAboutVL.addWidget(migakuAboutLinksTitle)
        migakuAboutVL.addLayout(migakuAboutLinksHL3)

        migakuContact = qt.QGroupBox()
        migakuContact.setTitle("Contact Us")
        migakuContactVL = qt.QVBoxLayout()
        migakuContact.setStyleSheet("QGroupBox { font-weight: bold; } ")
        migakuContactText = qt.QLabel(
            "If you would like to report a bug or contribute to the add-on, the best way to do so is by starting a ticket or pull request on GitHub. If you are looking for personal assistance using the add-on, check out the Migaku Patreon Discord Server."
        )
        migakuContactText.setWordWrap(True)

        gitHubIcon = self._getSVGWidget("Github.svg")
        gitHubIcon.setCursor(qt.QCursor(qt.Qt.CursorShape.PointingHandCursor))

        migakuThanks = qt.QGroupBox()
        migakuThanks.setTitle("A Word of Thanks")
        migakuThanksVL = qt.QVBoxLayout()
        migakuThanks.setStyleSheet("QGroupBox { font-weight: bold; } ")
        migakuThanksText = qt.QLabel(
            "Thanks so much to all Migaku supporters! We would not have been able to develop this add-on or any other Migaku project without your support!"
        )
        migakuThanksText.setOpenExternalLinks(True)
        migakuThanksText.setWordWrap(True)
        migakuThanksVL.addWidget(migakuThanksText)

        migakuContactVL.addWidget(migakuContactText)
        migakuContactVL.addWidget(gitHubIcon)
        migakuContact.setLayout(migakuContactVL)
        migakuThanks.setLayout(migakuThanksVL)
        tab4vl.addWidget(migakuAbout)
        tab4vl.addWidget(migakuContact)
        tab4vl.addWidget(migakuThanks)
        tab4vl.addStretch()
        tab_4.setLayout(tab4vl)

        migakuInfoSite.clicked.connect(lambda: aqt_utils.openLink("https://migaku.io"))
        migakuPatreonIcon.clicked.connect(
            lambda: aqt_utils.openLink("https://www.patreon.com/Migaku")
        )
        migakuInfoYT.clicked.connect(
            lambda: aqt_utils.openLink(
                "https://www.youtube.com/channel/UCQFe3x4WAgm7joN5daMm5Ew"
            )
        )
        migakuInfoTW.clicked.connect(
            lambda: aqt_utils.openLink("https://twitter.com/Migaku_Yoga")
        )
        gitHubIcon.clicked.connect(
            lambda: aqt_utils.openLink(
                "https://github.com/migaku-official/Migaku-Dictionary-Addon"
            )
        )

        return tab_4

    def loadGroupTable(self) -> None:
        self._dictGroups.setRowCount(0)
        dictGroups = self._getConfig()["DictionaryGroups"]
        for groupName in dictGroups:
            rc = self._dictGroups.rowCount()
            self._dictGroups.setRowCount(rc + 1)
            self._dictGroups.setItem(rc, 0, qt.QTableWidgetItem(groupName))
            editButton = qt.QPushButton("Edit")
            if utils.is_win:
                editButton.setFixedWidth(40)
            else:
                editButton.setFixedWidth(50)
                editButton.setFixedHeight(30)
            editButton.clicked.connect(self._editGroupRow(rc))
            self._dictGroups.setCellWidget(rc, 1, editButton)
            deleteButton = qt.QPushButton("X")
            if utils.is_win:
                deleteButton.setFixedWidth(40)
            else:
                deleteButton.setFixedWidth(40)
                deleteButton.setFixedHeight(30)
            deleteButton.clicked.connect(self._removeGroupRow(rc))
            self._dictGroups.setCellWidget(rc, 2, deleteButton)

    def loadTemplateTable(self) -> None:
        self._exportTemplates.setRowCount(0)
        exportTemplates = self._getConfig()["ExportTemplates"]
        for template in exportTemplates:
            rc = self._exportTemplates.rowCount()
            self._exportTemplates.setRowCount(rc + 1)
            self._exportTemplates.setItem(rc, 0, qt.QTableWidgetItem(template))
            editButton = qt.QPushButton("Edit")
            if utils.is_win:
                editButton.setFixedWidth(40)
            else:
                editButton.setFixedWidth(50)
                editButton.setFixedHeight(30)
            editButton.clicked.connect(self._editTempRow(rc))
            self._exportTemplates.setCellWidget(rc, 1, editButton)
            deleteButton = qt.QPushButton("X")
            if utils.is_win:
                deleteButton.setFixedWidth(40)
            else:
                deleteButton.setFixedWidth(40)
                deleteButton.setFixedHeight(30)
            deleteButton.clicked.connect(self._removeTempRow(rc))
            self._exportTemplates.setCellWidget(rc, 2, deleteButton)

    def closeEvent(self, event: typing.Optional[qt.QCloseEvent]) -> None:
        # TODO: @ColinKennedy - Fix this cyclic import
        from . import migaku_settings

        migaku_settings.clear()
        self._userGuideTab.close()
        self._userGuideTab.deleteLater()

        if event:
            event.accept()

    def hideEvent(self, event: typing.Optional[qt.QHideEvent]) -> None:
        # TODO: @ColinKennedy - Fix this cyclic import
        from . import migaku_settings

        migaku_settings.clear()
        self._userGuideTab.close()
        self._userGuideTab.deleteLater()

        if event:
            event.accept()


def _verify(item: typing.Optional[T]) -> T:
    if item is not None:
        return item

    raise RuntimeError("Expected item to exist but got none.")
