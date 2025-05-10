from __future__ import annotations

from collections import abc
import collections
import dataclasses
import io
import json
import logging
import operator
import os
import re
import shutil
import typing
import zipfile

import aqt
from aqt.qt import *
from aqt import mw
from .dictionaryWebInstallWizard import DictionaryWebInstallWizard
from .freqConjWebWindow import FreqConjWebWindow
from PyQt6.QtWidgets import QMessageBox

from . import dictdb, typer


_DEFINITION_TABLE_SEPARATOR = ', '
_NOT_SET_FREQUENCY = 999999  # NOTE: This means "not frequent or frequency is not known"
_LOGGER = logging.getLogger(__name__)
_FrequencyDict = dict[tuple[str, str], int]


class _FrequencyEntryValue(typing.TypedDict):
    displayValue: str
    value: int


class _FrequencyReadingEntryValue(typing.TypedDict):
    reading: str
    frequency: _FrequencyEntryValue



class _FrequencyEntry(typing.NamedTuple):
    category: str
    frequency: typing.Union[_FrequencyEntryValue, _FrequencyReadingEntryValue]
    term: str


class _FlatDictionary:
    def __init__(
        self,
        # TODO: @ColinKennedy find these keys later
        term: str,
        altterm: str,
        pronunciation: str,
        reading: str,
        also_not_sure: int,
        definitions: list[str],
        i_dont_know: int,
        last_one: str,
    ) -> None:
        self._term = term
        self._altterm = altterm
        self._pronunication = pronunciation
        self._definitions = definitions

        # NOTE: These are extra attributes that a dictionary would not define but we may
        # be able to get from a frequency list and map manually, ourselves
        #
        self._frequency: typing.Optional[int] = None
        self._star_count: typing.Optional[str] = None

    @staticmethod
    def is_valid(data: typing.Any) -> bool:
        if len(data) != 8:
            return False

        # TODO: @ColinKennedy add a better example
        # Example: ['πâ╜', 'πâ╜', 'n', '', 0, ['repetition mark in katakana'], 0, '']
        index_types = {
            0: str,
            1: str,
            2: str,
            3: str,
            4: int,
            5: list,
            6: int,
            7: str,
        }

        for index, type_ in index_types.items():
            if not isinstance(data[index], type_):
                _LOGGER.debug(
                    'Rejected "%s" data because "%s" index is not "%s" type.',
                    data,
                    index,
                    type_,
                )

                return False

        return True

    @classmethod
    def deserialize(cls, data: list[typing.Union[str, int]]) -> _FlatDictionary:
        return cls(*data)  # type: ignore[arg-type]

    def get_frequency(self) -> typing.Optional[int]:
        return self._frequency

    def get_reading(self) -> str:
        if self._altterm:
            return self._altterm

        return self._term

    def get_term(self) -> str:
        return self._term

    def clear_frequency(self) -> None:
        self._frequency = None
        self._star_count = None

    def serialize(self) -> list[str]:
        term = getAdjustedTerm(self._term)
        reading = getAdjustedPronunciation(self.get_reading())
        definition = getAdjustedDefinition(_DEFINITION_TABLE_SEPARATOR.join(self._definitions))

        frequency: int

        if self._frequency is not None:
            frequency = self._frequency
        else:
            frequency = _NOT_SET_FREQUENCY

        return [
            term,
            '',
            reading,
            self._pronunication,
            definition,
            '',
            '',
            str(frequency),
            self._star_count or "",
        ]

    def set_frequency(self, frequency: int) -> None:
        self._frequency = frequency
        self._star_count = getStarCount(self._frequency)


class DictionaryManagerWidget(QWidget):

    def __init__(self, parent: typing.Optional[QWidget]=None) -> None:
        super().__init__(parent)

        lyt = QVBoxLayout()
        lyt.setContentsMargins(0, 0, 0, 0)
        self.setLayout(lyt)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        lyt.addWidget(splitter)


        left_side = QWidget()
        splitter.addWidget(left_side)
        left_lyt = QVBoxLayout()
        left_side.setLayout(left_lyt)

        self.dict_tree = QTreeWidget()
        self.dict_tree.setHeaderHidden(True)
        self.dict_tree.currentItemChanged.connect(self.on_current_item_change)
        left_lyt.addWidget(self.dict_tree)

        add_lang_btn = QPushButton('Add a Language')
        add_lang_btn.clicked.connect(self.add_lang)
        left_lyt.addWidget(add_lang_btn)

        web_installer_btn = QPushButton('Install Languages in Wizard')
        web_installer_btn.clicked.connect(self.web_installer)
        left_lyt.addWidget(web_installer_btn)


        right_side = QWidget()
        splitter.addWidget(right_side)
        right_lyt = QVBoxLayout()
        right_side.setLayout(right_lyt)


        self.lang_grp = QGroupBox('Language Options')
        right_lyt.addWidget(self.lang_grp)

        lang_lyt = QVBoxLayout()
        self.lang_grp.setLayout(lang_lyt)

        lang_lyt1 = QHBoxLayout()
        lang_lyt2 = QHBoxLayout()
        lang_lyt.addLayout(lang_lyt2)
        lang_lyt3 = QHBoxLayout()
        lang_lyt.addLayout(lang_lyt3)
        lang_lyt4 = QHBoxLayout()
        lang_lyt.addLayout(lang_lyt4)
        lang_lyt.addLayout(lang_lyt1)

        remove_lang_btn = QPushButton('Remove Language')
        remove_lang_btn.clicked.connect(self.remove_lang)
        lang_lyt1.addWidget(remove_lang_btn)

        web_installer_lang_btn = QPushButton('Install Dictionary in Wizard')
        web_installer_lang_btn.clicked.connect(self.web_installer_lang)
        lang_lyt2.addWidget(web_installer_lang_btn)

        import_dict_btn = QPushButton('Install Dictionary From File')
        import_dict_btn.clicked.connect(self.import_dict)
        lang_lyt2.addWidget(import_dict_btn)

        web_freq_data_btn = QPushButton('Install Frequency Data in Wizard')
        web_freq_data_btn.clicked.connect(self.web_freq_data)
        lang_lyt3.addWidget(web_freq_data_btn)

        set_freq_data_btn = QPushButton('Install Frequency Data From File')
        set_freq_data_btn.clicked.connect(self.set_freq_data)
        lang_lyt3.addWidget(set_freq_data_btn)

        web_conj_data_btn = QPushButton('Install Conjugation Data in Wizard')
        web_conj_data_btn.clicked.connect(self.web_conj_data)
        lang_lyt4.addWidget(web_conj_data_btn)

        set_conj_data_btn = QPushButton('Install Conjugation Data From File')
        set_conj_data_btn.clicked.connect(self.set_conj_data)
        lang_lyt4.addWidget(set_conj_data_btn)

        lang_lyt1.addStretch()
        lang_lyt2.addStretch()
        lang_lyt3.addStretch()
        lang_lyt4.addStretch()


        self.dict_grp = QGroupBox('Dictionary Options')
        right_lyt.addWidget(self.dict_grp)

        dict_lyt = QHBoxLayout()
        self.dict_grp.setLayout(dict_lyt)

        remove_dict_btn = QPushButton('Remove Dictionary')
        remove_dict_btn.clicked.connect(self.remove_dict)
        dict_lyt.addWidget(remove_dict_btn)

        set_term_headers_btn = QPushButton('Edit Definition Header')
        set_term_headers_btn.clicked.connect(self.set_term_header)
        dict_lyt.addWidget(set_term_headers_btn)

        dict_lyt.addStretch()


        right_lyt.addStretch()


        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)


        self.reload_tree_widget()

        self.on_current_item_change(None, None)

    def info(self, text: str) -> int:
        return QMessageBox.information(self, 'Migaku Dictionary', text, QMessageBox.StandardButton.Ok)

    def get_string(self, text: str, default_text: str='') -> tuple[str, int]:
        dlg = QInputDialog(self)
        dlg.setWindowTitle('Migaku Dictionary')
        dlg.setLabelText(text + ':')
        dlg.setTextValue(default_text)
        dlg.resize(350, dlg.sizeHint().height())
        ok = dlg.exec()
        txt = dlg.textValue()
        return txt, ok


    def reload_tree_widget(self) -> None:
        db = dictdb.get()

        langs = db.getCurrentDbLangs()
        dicts_by_langs: dict[str, list[str]] = {}

        for info in db.getAllDictsWithLang():
            lang = info['lang']

            dict_list = dicts_by_langs.get(lang, [])
            dict_list.append(info['dict'])
            dicts_by_langs[lang] = dict_list

        self.dict_tree.clear()

        for lang in langs:
            lang_item = QTreeWidgetItem([lang])
            lang_item.setData(0, Qt.ItemDataRole.UserRole+0, lang)
            lang_item.setData(0, Qt.ItemDataRole.UserRole+1, None)

            self.dict_tree.addTopLevelItem(lang_item)

            for d in dicts_by_langs.get(lang, []):
                dict_name = db.cleanDictName(d)
                dict_name = dict_name.replace('_', ' ')
                dict_item = QTreeWidgetItem([dict_name])
                dict_item.setData(0, Qt.ItemDataRole.UserRole+0, lang)
                dict_item.setData(0, Qt.ItemDataRole.UserRole+1, d)
                lang_item.addChild(dict_item)

            lang_item.setExpanded(True)


    def on_current_item_change(self, *_: typing.Any) -> None:

        lang, dict_ = self.get_current_lang_dict()

        self.lang_grp.setEnabled(lang is not None)
        self.dict_grp.setEnabled(dict_ is not None)


    def get_current_lang_dict(self) -> tuple[typing.Optional[str], typing.Optional[str]]:

        curr_item = self.dict_tree.currentItem()

        lang = None
        dict_ = None

        if curr_item:
            lang = curr_item.data(0, Qt.ItemDataRole.UserRole+0)
            dict_ = curr_item.data(0, Qt.ItemDataRole.UserRole+1)

        return lang, dict_


    def get_current_lang_item(self) -> typing.Optional[QTreeWidgetItem]:
        curr_item = self.dict_tree.currentItem()

        if curr_item:
            curr_item_parent = curr_item.parent()
            if curr_item_parent:
                return curr_item_parent

        return curr_item


    def get_current_dict_item(self) -> typing.Optional[QTreeWidgetItem]:

        curr_item = self.dict_tree.currentItem()

        if curr_item:
            curr_item_parent = curr_item.parent()
            if curr_item_parent is None:
                return None

        return curr_item


    def web_installer(self) -> None:

        DictionaryWebInstallWizard.execute_modal()
        self.reload_tree_widget()


    def add_lang(self) -> None:
        db = dictdb.get()

        text, ok = self.get_string('Select name of new language')
        if not ok:
            return

        name = text.strip()
        if not name:
            self.info('Language names may not be empty.')
            return

        try:
            db.addLanguages([name])
        except Exception as e:
            self.info('Adding language failed.')
            return

        lang_item = QTreeWidgetItem([name])
        lang_item.setData(0, Qt.ItemDataRole.UserRole+0, name)
        lang_item.setData(0, Qt.ItemDataRole.UserRole+1, None)

        self.dict_tree.addTopLevelItem(lang_item)
        self.dict_tree.setCurrentItem(lang_item)


    def remove_lang(self) -> None:
        db = dictdb.get()

        lang_item = self.get_current_lang_item()
        if lang_item is None:
            return
        lang_name = lang_item.data(0, Qt.ItemDataRole.UserRole+0)

        r = QMessageBox.question(
            self, 'Migaku Dictioanry',
            f'Do you really want to remove the language "{lang_name}"?\n\n'
            'All settings and dictionaries for it will be removed.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if r != QMessageBox.StandardButton.Yes:
            return

        # Remove language from db
        db.deleteLanguage(lang_name)

        # Remove frequency data
        try:
            path = os.path.join(addon_path, 'user_files', 'db', 'frequency', '%s.json' % lang_name)
            os.remove(path)
        except OSError:
            pass

        # Remove conjugation data
        try:
            path = os.path.join(addon_path, 'user_files', 'db', 'conjugation', '%s.json' % lang_name)
            os.remove(path)
        except OSError:
            pass

    def set_freq_data(self) -> None:
        lang_name = self.get_current_lang_dict()[0]
        if lang_name is None:
            return

        path = QFileDialog.getOpenFileName(self, 'Select the frequency list you want to import', os.path.expanduser('~'), 'JSON Files (*.json);;All Files (*.*)')[0]
        if not path:
            return

        freq_path = os.path.join(addon_path, 'user_files', 'db', 'frequency')
        os.makedirs(freq_path, exist_ok=True)

        dst_path = os.path.join(freq_path, '%s.json' % lang_name)

        try:
            shutil.copy(path, dst_path)
        except shutil.Error:
            self.info('Importing frequency data failed.')
            return

        self.info('Imported frequency data for "%s".\n\nNote that the frequency data is only applied to newly imported dictionaries for this language.' % lang_name)


    def web_freq_data(self) -> None:
        lang_item = self.get_current_lang_item()
        if lang_item is None:
            return
        lang_name = lang_item.data(0, Qt.ItemDataRole.UserRole+0)

        FreqConjWebWindow.execute_modal(lang_name, FreqConjWebWindow.Mode.Freq)


    def set_conj_data(self) -> None:
        lang_name = self.get_current_lang_dict()[0]
        if lang_name is None:
            return

        path = QFileDialog.getOpenFileName(self, 'Select the conjugation data you want to import', os.path.expanduser('~'), 'JSON Files (*.json);;All Files (*.*)')[0]
        if not path:
            return

        conj_path = os.path.join(addon_path, 'user_files', 'db', 'conjugation')
        os.makedirs(conj_path, exist_ok=True)

        dst_path = os.path.join(conj_path, '%s.json' % lang_name)

        try:
            shutil.copy(path, dst_path)
        except shutil.Error:
            self.info('Importing conjugation data failed.')
            return

        self.info('Imported conjugation data for "%s".' % lang_name)


    def web_conj_data(self) -> None:
        lang_item = self.get_current_lang_item()
        if lang_item is None:
            return
        lang_name = lang_item.data(0, Qt.ItemDataRole.UserRole+0)

        FreqConjWebWindow.execute_modal(lang_name, FreqConjWebWindow.Mode.Conj)


    def import_dict(self) -> None:
        lang_item = self.get_current_lang_item()
        if lang_item is None:
            return
        lang_name = lang_item.data(0, Qt.ItemDataRole.UserRole+0)

        path = QFileDialog.getOpenFileName(self, 'Select the dictionary you want to import',
                                           os.path.expanduser('~'), 'ZIP Files (*.zip);;All Files (*.*)')[0]
        if not path:
            return

        dict_name = os.path.splitext(os.path.basename(path))[0]
        dict_name, ok = self.get_string('Set name of dictionary', dict_name)

        try:
            importDict(lang_name, path, dict_name)
        except ValueError as e:
            self.info(str(e))
            return

        dict_item = QTreeWidgetItem([dict_name.replace('_', ' ')])
        dict_item.setData(0, Qt.ItemDataRole.UserRole+0, lang_name)
        dict_item.setData(0, Qt.ItemDataRole.UserRole+1, dict_name)

        lang_item.addChild(dict_item)
        self.dict_tree.setCurrentItem(dict_item)


    def web_installer_lang(self) -> None:
        lang_item = self.get_current_lang_item()
        if lang_item is None:
            return
        lang_name = lang_item.data(0, Qt.ItemDataRole.UserRole+0)

        DictionaryWebInstallWizard.execute_modal(lang_name)
        self.reload_tree_widget()


    def remove_dict(self) -> None:
        db = dictdb.get()

        dict_item = self.get_current_dict_item()
        if dict_item is None:
            return
        dict_name = dict_item.data(0, Qt.ItemDataRole.UserRole+1)
        dict_display = dict_item.data(0, Qt.ItemDataRole.DisplayRole)

        dlg = QMessageBox(
            QMessageBox.Icon.Question,
            'Migaku Dictionary',
            f'Do you really want to remove the dictionary "{dict_display}"?',
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            parent=self
        )

        r = dlg.exec()

        if r != QMessageBox.StandardButton.Yes:
            return

        db.deleteDict(dict_name)

    def set_term_header(self) -> None:
        db = dictdb.get()

        dict_name = self.get_current_lang_dict()[1]
        if dict_name is None:
            return

        dict_clean = db.cleanDictName(dict_name)

        term_txt = ', '.join(json.loads(db.getDictTermHeader(dict_clean)))

        term_txt, ok = self.get_string('Set term header for dictionary "%s"' % dict_clean.replace('_', ' '), term_txt)

        if not ok:
            return

        parts_txt = term_txt.split(',')
        parts = []
        valid_parts = ['term', 'altterm', 'pronunciation']

        for part_txt in parts_txt:
            part = part_txt.strip().lower()
            if part not in valid_parts:
                self.info('The term header part "%s" is not valid.' % part_txt)
                return
            parts.append(part)

        db.setDictTermHeader(dict_clean, json.dumps(parts))




addon_path = os.path.dirname(__file__)


def _get_frequency_entry(data: dict[typing.Any, typing.Any]) -> _FrequencyEntryValue:
    if "displayValue" not in data:
        raise RuntimeError(f'Data "{data}" has no displayValue information.')

    if not isinstance(data["displayValue"], str):
        raise RuntimeError(f'displayValue from "{data}" is not a string.')

    if "value" not in data:
        raise RuntimeError(f'Data "{data}" has no value information.')

    if not isinstance(data["displayValue"], int):
        raise RuntimeError(f'value from "{data}" is not a string.')

    return _FrequencyEntryValue(
        displayValue=data["displayValue"],
        value=data["value"],
    )


def _import_dictionary(table_name: str, jsonDict: typing.Iterable[_FlatDictionary]) -> None:
    database = dictdb.get()
    database.importToDict(table_name, [entry.serialize() for entry in jsonDict])
    database.commitChanges()


def _read_language_dictionary(zfile: zipfile.ZipFile) -> tuple[list[_FlatDictionary], bool]:
    is_yomichan = any(name.startswith('term_bank_') for name in zfile.namelist())
    dict_files: list[str] = []

    for name in zfile.namelist():
        if not name.endswith('.json'):
            continue

        if is_yomichan and not name.startswith('term_bank_'):
            continue

        dict_files.append(name)

    dict_files = natural_sort(dict_files)
    jsonDict: list[_FlatDictionary] = []

    for filename in dict_files:
        with zfile.open(filename, 'r') as jsonDictFile:
            all_data = json.loads(jsonDictFile.read())

            if not isinstance(all_data, abc.MutableSequence):
                raise NotImplementedError(
                    f'Data "{type(all_data)}" is not supported yet. '
                    'Please ask the maintainer to add it!',
                )

            for entry in all_data:
                if not _FlatDictionary.is_valid(entry):
                    raise NotImplementedError(
                        f'Entry "{entry}" is not supported yet. '
                        'Please ask the maintainer to add it!',
                    )

                jsonDict.append(_FlatDictionary.deserialize(entry))

    return jsonDict, is_yomichan


def _recommend_table_name(lang: str, dictName: str) -> str:
    return 'l' + str(dictdb.get().getLangId(lang)) + 'name' + dictName


def importDict(
    lang_name: str,
    path: typing.Union[io.BytesIO, str],
    dict_name: str,
) -> None:
    db = dictdb.get()

    with zipfile.ZipFile(path) as zfile:
        jsonDict, is_yomichan = _read_language_dictionary(zfile)

    frequency_dict: typing.Optional[_FrequencyDict] = None
    is_hyouki = False  # TODO: @ColinKennedy not sure about this default value

    try:
        frequency_dict, is_hyouki = getFrequencyDict(lang_name)
    except RuntimeError:
        _LOGGER.info('Unable to get a frequency list for "%s" language.', lang_name)

    dict_name = dict_name.replace(' ', '_')
    term_header = json.dumps(['term', 'altterm', 'pronunciation'])

    try:
        db.addDict(dict_name, lang_name, term_header)
    except Exception:
        raise ValueError(
            'Creating dictionary failed. '
            'Make sure that no other dictionary with the same name exists. '
            'Several special characters are also no supported in dictionary names.'
        )

    table = _recommend_table_name(lang_name, dict_name)

    if is_yomichan:
        loadDictYomi(
            jsonDict,
            table,
            frequency_dict,
            is_hyouki=is_hyouki,
        )
    # TODO: @ColinKennedy add this later
    # else:
    #     loadDictMigaku(
    #         jsonDict,
    #         table,
    #         frequency_dict,
    #         is_hyouki=is_hyouki,
    #     )


def natural_sort(l: typing.Iterable[str]) -> list[str]:
    def convert(text: str) -> typing.Union[int, str]:
        if text.isdigit():
            return int(text)

        return text

    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]

    return sorted(l, key=alphanum_key)


# def loadDictMigaku(
#     jsonDict: list[_FlatDictionary],
#     table: str,
#     frequencyDict: typing.Optional[_FrequencyDict],
#     is_hyouki: bool,
# ) -> None:
#     if frequencyDict:
#         jsonDict = organizeMigakuDictionaryByFrequency(
#             jsonDict,
#             frequencyDict,
#             readingHyouki=is_hyouki,
#         )
#
#         for count, entry in enumerate(jsonDict):
#             handleMigakuDictEntry(jsonDict, count, entry, freq=True)
#
#     _import_dictionary(table, jsonDict)


def loadDictYomi(
    jsonDict: typing.Sequence[_FlatDictionary],
    table: str,
    frequencyDict: typing.Optional[_FrequencyDict],
    is_hyouki: bool,
) -> None:
    if frequencyDict:
        computeYomiDictionaryByFrequency(
            jsonDict,
            frequencyDict,
            readingHyouki=is_hyouki,
        )

        jsonDict = sorted(jsonDict, key=lambda item: item.get_frequency() or _NOT_SET_FREQUENCY)

    _import_dictionary(table, jsonDict)


def getAdjustedTerm(term: str) -> str:
    term = term.replace('\n', '')

    if len(term) > 1:
        term = term.replace('=', '')

    return term


def getAdjustedPronunciation(pronunciation: str) -> str:
    return pronunciation.replace('\n', '')


def getAdjustedDefinition(definition: str) -> str:
    definition = definition.replace('<br>','◟')
    definition = definition.replace('<', '&lt;').replace('>', '&gt;')
    definition = definition.replace('◟','<br>').replace('\n', '<br>')
    return re.sub(r'<br>$', '', definition)


# def handleMigakuDictEntry(
#     jsonDict,
#     count: int,
#     entry: typer.DictionaryFrequencyResult,
#     freq: bool = False,
# ) -> None:
#     starCount = ''
#     frequency = ''
#     if freq:
#         starCount = entry['starCount']
#         frequency = entry['frequency']
#     reading = entry['pronunciation']
#     if reading == '':
#         reading = entry['term']
#     term = getAdjustedTerm(entry['term'])
#     altTerm = getAdjustedTerm(entry['altterm'])
#     reading = getAdjustedPronunciation(reading)
#     definition = getAdjustedDefinition(entry['definition'])
#     jsonDict[count] = (
#         term,
#         altTerm,
#         reading,
#         entry['pos'],
#         definition,
#         '',
#         '',
#         frequency,
#         starCount,
#     )


def kaner(to_translate: str, hiraganer: bool = False) -> str:
    hiragana = u"がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ" \
               u"あいうえおかきくけこさしすせそたちつてと" \
               u"なにぬねのはひふへほまみむめもやゆよらりるれろ" \
               u"わをんぁぃぅぇぉゃゅょっゐゑ"
    katakana = u"ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ" \
               u"アイウエオカキクケコサシスセソタチツテト" \
               u"ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ" \
               u"ワヲンァィゥェォャュョッヰヱ"

    if hiraganer:
        katakana_as_int = [ord(char) for char in katakana]
        translate_table = dict(zip(katakana_as_int, hiragana))
    else:
        hiragana_as_int = [ord(char) for char in katakana]
        translate_table = dict(zip(hiragana_as_int, katakana))

    return to_translate.translate(translate_table)


def adjustReading(reading: str) -> str:
    return kaner(reading)


# def organizeMigakuDictionaryByFrequency(
#     jsonDict: typing.Sequence[typer.DictionaryFrequencyResult],
#     frequencyDict: _FrequencyDict,
#     readingHyouki: bool,
# ) -> list[typer.DictionaryFrequencyResult]:
#     for idx, entry in enumerate(jsonDict):
#         if readingHyouki:
#             reading = entry['pronunciation']
#
#             if not reading:
#                 reading = entry['term']
#
#             adjusted = adjustReading(reading)
#
#         if not readingHyouki and entry['term'] in frequencyDict:
#             jsonDict[idx]['frequency'] = frequencyDict[entry['term']]
#             jsonDict[idx]['starCount'] = getStarCount(jsonDict[idx]['frequency'])
#         elif readingHyouki and entry['term'] in frequencyDict and adjusted in frequencyDict[entry['term']]:
#             jsonDict[idx]['frequency'] = frequencyDict[entry['term']][adjusted]
#             jsonDict[idx]['starCount'] = getStarCount(jsonDict[idx]['frequency'])
#         else:
#             jsonDict[idx]['frequency'] = 999999
#             jsonDict[idx]['starCount'] = getStarCount(jsonDict[idx]['frequency'])
#
#     return sorted(jsonDict, key=operator.itemgetter("frequency"))


def computeYomiDictionaryByFrequency(
    jsonDict: typing.Sequence[_FlatDictionary],
    frequencyDict: _FrequencyDict,
    readingHyouki: bool,
    # TODO: @ColinKennedy - The returned type is kind of "migaku-extended" to consider
) -> None:
    def _passthrough(value: str) -> str:
        return value

    modify_reading: typing.Callable[[str], str]

    if readingHyouki:
        modify_reading = adjustReading
    else:
        modify_reading = _passthrough

    for entry in jsonDict:
        reading = modify_reading(entry.get_reading())
        term = entry.get_term()

        if (term, reading) in frequencyDict:
            entry.set_frequency(frequencyDict[(term, reading)])
        else:
            entry.clear_frequency()


def getStarCount(freq: int) -> str:
    if freq < 1501:
        return '★★★★★'
    if freq < 5001:
        return '★★★★'
    if freq < 15001:
        return '★★★'
    if freq < 30001:
        return '★★'
    if freq < 60001:
        return '★'

    return ''


def getFrequencyDict(lang: str) -> tuple[_FrequencyDict, bool]:
    filePath = os.path.join(addon_path, 'user_files', 'db', 'frequency', '%s.json' % lang)

    if not os.path.exists(filePath):
        raise RuntimeError(f'Path "{filePath}" does not exist.')

    with open(filePath, 'r', encoding='utf-8-sig') as handler:
        data = typing.cast(
            typing.Union[dict[typing.Any, typing.Any], list[list[typing.Union[int, str]]]],
            json.load(handler),
        )

    if isinstance(data, abc.MutableMapping):
        raise RuntimeError(f'Frequency file "{filePath}" was not a list.')

    if not isinstance(data, list):
        raise RuntimeError(
            f'Unable to read from frequency file "{filePath}" '
            'because it is not a known layout.'
        )

    frequencyDict: _FrequencyDict = {}

    for item in data:
        # Examples:
        # ["の","freq",{"value":1,"displayValue":"1㋕"}]
        # ["其","freq",{"reading":"それ","frequency":{"value":17,"displayValue":"17㋕"}}]

        if len(item) != 3 or not isinstance(item[0], str) or not isinstance(item[1], str):
            raise RuntimeError(
                f'Unable to read "{item}" frequency item. Its structure is unknown.'
            )

        frequency_ = item[2]

        if not isinstance(frequency_, abc.MutableMapping):
            raise RuntimeError(f'Unable to read "{item}" frequency item. Its data is not a dict.')

        frequency: typing.Union[_FrequencyEntryValue, _FrequencyReadingEntryValue]
        term = item[0]

        if "reading" in frequency_:
            reading = frequency_["reading"]
            frequencyDict[(term, reading)] = frequency_["frequency"]["value"]
        else:
            frequencyDict[(term, term)] = frequency_["value"]

    is_hyouki = True

    if data and isinstance(data[0], str):
        # NOTE: In the past migaku code it had a line roughly like this:
        # `is_hyouki = frequencyDict['readingDictionaryType']`.
        # Since we aren't sure what this is about, maybe just keep it.
        #
        is_hyouki = False

    return frequencyDict, is_hyouki
