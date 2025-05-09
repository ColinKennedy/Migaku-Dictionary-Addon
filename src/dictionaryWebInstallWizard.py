import io
import json
import logging
import os
import typing

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from anki.httpclient import HttpClient
from aqt.qt import *
import aqt

from . import migaku_wizard
from . import webConfig

from . import dictdb, typer


addon_path = os.path.dirname(__file__)

_LOGGER = logging.getLogger(__name__)
T = typing.TypeVar("T")


class NoAutoSelectLineEdit(QLineEdit):

    # TODO: @ColinKennedy - Do I need return bool?
    def focusInEvent(self, e: typing.Optional[QFocusEvent]) -> None:
        super().focusInEvent(e)

        self.deselect()


class DictionaryWebInstallWizard(migaku_wizard.MiWizard):

    INITIAL_SIZE = (600, 400)

    def __init__(
        self,
        force_lang: typing.Optional[str]=None,
        parent: typing.Optional[QWidget]=None,
    ) -> None:
        super().__init__(parent)

        self.dictionary_index: typing.Optional[typer.DictionaryLanguageIndex2Pack] = None
        self.dictionary_install_index: list[typer.InstallLanguage] = []
        self.dictionary_install_frequency = False
        self.dictionary_install_conjugation = False
        self.dictionary_force_lang = force_lang
        self.dictionary_server_root: typing.Optional[str] = None

        self.setWindowTitle('Migaku Dictionary - Web Installer')
        self.setWindowIcon(QIcon(os.path.join(addon_path, 'icons', 'migaku.png')))

        server_add_page = self.add_page(ServerAskPage(self))
        dict_select_page = self.add_page(DictionarySelectPage(self), server_add_page)
        dict_confirm_page = self.add_page(DictionaryConfirmPage(self), dict_select_page)
        self.add_page(DictionaryInstallPage(self), dict_confirm_page)

        self.resize(*self.INITIAL_SIZE)


    @classmethod
    def execute_modal(cls, force_lang: typing.Optional[str]=None) -> int:
        wizard = cls(force_lang)
        return wizard.exec()



class ServerAskPage(migaku_wizard.MiWizardPage[DictionaryWebInstallWizard]):

    def __init__(self, wizard: DictionaryWebInstallWizard) -> None:
        super(ServerAskPage, self).__init__(wizard)

        self.title = 'Select Dictionary Server'

        lyt = QVBoxLayout()
        self.setLayout(lyt)

        lyt.addStretch()

        lbl = QLabel('Our dictionary server contains several free, open source dictionaries.\n\n'\
                     'You can also select a custom server to install other 3rd party dictionaries.\n')
        lbl.setWordWrap(True)
        lyt.addWidget(lbl)

        server_lyt = QHBoxLayout()
        lyt.addLayout(server_lyt)


        self.server_line = NoAutoSelectLineEdit()
        self.server_line.setPlaceholderText('Insert Dictionary Server Address')
        server_lyt.addWidget(self.server_line)

        self.server_reset_btn = QPushButton('Default')
        server_lyt.addWidget(self.server_reset_btn)

        lyt.addStretch()

        self.reset_server_line()

        self.server_reset_btn.clicked.connect(self.reset_server_line)


    def reset_server_line(self) -> None:
        self.server_line.setText(webConfig.DEFAULT_SERVER)


    def on_next(self) -> bool:
        if not self.wizard:
            raise RuntimeError("No Wizard is defined. Cannot call on_next.")

        server_url_usr = self.server_line.text().strip()
        server_url = webConfig.normalize_url(server_url_usr)

        index_data = webConfig.download_index(server_url)

        if index_data is None:
            QMessageBox.information(self, 'Migaku Dictioanry',
                                    'The server "%s" is not reachable.\n\n'\
                                    'Make sure you are connected to the internet and the url you entered is valid.' % server_url_usr)
            return False

        self.wizard.dictionary_index = index_data
        self.wizard.dictionary_server_root = server_url

        return True



class DictionarySelectPage(migaku_wizard.MiWizardPage[DictionaryWebInstallWizard]):

    def __init__(self, wizard: DictionaryWebInstallWizard) -> None:
        super(DictionarySelectPage, self).__init__(wizard)

        self.title = 'Select the dictionaries you want to install'

        lyt = QVBoxLayout()
        self.setLayout(lyt)

        self.dict_tree = QTreeWidget()
        self.dict_tree.setHeaderHidden(True)
        lyt.addWidget(self.dict_tree)

        options_lyt = QHBoxLayout()
        lyt.addLayout(options_lyt)

        self.install_freq = QCheckBox('Install Language Frequency Data')
        self.install_freq.setChecked(True)
        options_lyt.addWidget(self.install_freq)

        self.install_conj = QCheckBox('Install Language Conjugation Data')
        self.install_conj.setChecked(True)
        options_lyt.addWidget(self.install_conj)

        options_lyt.addStretch()


    def on_show(self, is_next: bool) -> None:
        if is_next:
            self.setup_entries()


    def on_next(self) -> bool:

        dictionaries_to_install: list[typer.DictionaryLanguageIndex] = []

        dict_root = _verify(self.dict_tree.invisibleRootItem())

        for li in range(dict_root.childCount()):
            lang_item = _verify(dict_root.child(li))
            language = typing.cast(
                typing.Optional[typer.DictionaryLanguageIndex],
                lang_item.data(0, Qt.ItemDataRole.UserRole+0),
            )
            if not language:
                raise RuntimeError(f'Language "{lang_item}" has no language index.')

            dictionaries: list[typer.IndexDictionary] = []

            def scan_tree(item: QTreeWidgetItem) -> None:
                for di in range(item.childCount()):
                    dict_item = _verify(item.child(di))
                    dictionary = typing.cast(
                        typing.Optional[typer.IndexDictionary],
                        dict_item.data(0, Qt.ItemDataRole.UserRole+1),
                    )

                    if dictionary:
                        if dict_item.checkState(0) == Qt.CheckState.Checked:
                            dictionaries.append(dictionary)
                    else:
                        scan_tree(dict_item)

            scan_tree(lang_item)

            if len(dictionaries) > 0:
                lang_w_enabled_dicts = language.copy()
                lang_w_enabled_dicts['dictionaries'] = dictionaries
                dictionaries_to_install.append(lang_w_enabled_dicts)

        if not self.wizard:
            raise RuntimeError("No Wizard is defined. Cannot call on_next.")

        self.wizard.dictionary_install_index = dictionaries_to_install
        self.wizard.dictionary_install_frequency = self.install_freq.isChecked()
        self.wizard.dictionary_install_conjugation = self.install_conj.isChecked()

        return True


    # TODO: Add whitelist functionality so only limited amount is displayed based on user target language, native language, etc
    def setup_entries(self) -> None:
        if not self.wizard:
            raise RuntimeError("No Wizard is defined. Cannot call setup_entries.")

        self.dict_tree.clear()

        dictionary_index = self.wizard.dictionary_index

        if not dictionary_index:
            raise RuntimeError(f'Wizard {self.wizard} has no dictionary index defined.')

        for language in dictionary_index.get('languages') or []:
            name_en = language.get('name_en')
            name_native = language.get('name_native')

            if not name_en:
                continue

            text = name_en
            if name_native:
                text += ' (' + name_native + ')'

            lang_item = QTreeWidgetItem([text])
            lang_item.setData(0, Qt.ItemDataRole.UserRole+0, language)
            lang_item.setData(0, Qt.ItemDataRole.UserRole+1, None)

            self.dict_tree.addTopLevelItem(lang_item)

            def load_dict_list(
                dictionaries: typing.Iterable[typer.DictionaryLanguagePair],
                parent_item: QTreeWidgetItem,
            ) -> None:
                for dictionary in dictionaries:
                    dictionary_name = dictionary["name"]
                    if not dictionary_name:
                        continue

                    dictionary_text = dictionary_name

                    dictionary_description = dictionary['description']
                    if dictionary_description:
                        dictionary_text += ' - ' + dictionary_description

                    dict_item = QTreeWidgetItem([dictionary_text])
                    dict_item.setCheckState(0, Qt.CheckState.Unchecked)
                    dict_item.setData(0, Qt.ItemDataRole.UserRole+0, None)
                    dict_item.setData(0, Qt.ItemDataRole.UserRole+1, dictionary)

                    parent_item.addChild(dict_item)

            for to_language in language.get('to_languages') or []:
                to_name_en = to_language.get('name_en')
                to_name_native = to_language.get('name_native')

                if not to_name_en:
                    continue

                text = to_name_en
                if to_name_native:
                    text += ' (' + to_name_native + ')'

                to_lang_item = QTreeWidgetItem([text])
                to_lang_item.setData(0, Qt.ItemDataRole.UserRole+0, None)
                to_lang_item.setData(0, Qt.ItemDataRole.UserRole+1, None)

                lang_item.addChild(to_lang_item)

                dictionaries = to_language.get('dictionaries', [])
                load_dict_list(dictionaries, to_lang_item)

            dictionaries = language.get('dictionaries', [])
            load_dict_list(dictionaries, lang_item)


class DictionaryConfirmPage(migaku_wizard.MiWizardPage[DictionaryWebInstallWizard]):

    def __init__(
        self,
        wizard: DictionaryWebInstallWizard,
        can_select_none: bool=False,
    ) -> None:
        super(DictionaryConfirmPage, self).__init__(wizard)

        self.can_select_none = can_select_none

        self.title = 'Confirm selected dictionaries'
        self.back_enabled = True
        self.next_enabled = True
        self.next_text = 'Confirm'

        lyt = QVBoxLayout()
        self.setLayout(lyt)

        self.box = QTextEdit()
        self.box.setReadOnly(True)
        lyt.addWidget(self.box)


    def on_show(self, is_next: bool) -> None:
        if not self.wizard:
            raise RuntimeError("No Wizard is defined. Cannot call on_show.")

        install_index = self.wizard.dictionary_install_index
        install_freq = self.wizard.dictionary_install_frequency
        install_conj = self.wizard.dictionary_install_conjugation

        has_selection = len(install_index) > 0
        has_multiple_langs = len(install_index) > 1
        force_lang = self.wizard.dictionary_force_lang

        can_continue = False

        if not has_selection:
            if self.can_select_none:
                self.box.setText('No dictionaries selected.<br><br>Are you sure that you want to continue?')
                can_continue = True
            else:
                self.box.setText('No dictionaries selected.<br><br>Please go back to the previous page and select the dictionaries that you want to install.')
        elif has_multiple_langs and force_lang:
            self.box.setText('You can only install dictionaries from a single language when adding dictionaries to an exisintg language.<br><br>'
                             'Please go back to the previous page and make sure only dictionaries from a single language are selected.')
        else:
            txt = ''
            for language in install_index:
                txt += '<b>'
                txt += language['name_en']
                if 'name_native' in language:
                    txt += ' (' + language['name_native'] + ')'
                if force_lang:
                    txt += ' into ' + force_lang
                txt += '</b><ul>'

                if install_freq:
                    if 'frequency_url' in language:
                        txt += '<li>Installing frequency data</li>'
                    else:
                        txt += '<li><b>No frequency data available</b></li>'
                if install_conj:
                    if 'conjugation_url' in language:
                        txt += '<li>Installing conjugation data</li>'
                    else:
                        txt += '<li><b>No conjugation data available</b></li>'

                for dictionary in language.get('dictionaries', []):
                    txt += '<li>'
                    txt += dictionary['name']
                    txt += '</li>'

                txt += '</ul>'

            self.box.setText(txt)
            can_continue = True


        self.next_enabled = can_continue
        self.refresh_wizard_states()


class DictionaryInstallPage(migaku_wizard.MiWizardPage[DictionaryWebInstallWizard]):
    def __init__(self, wizard: DictionaryWebInstallWizard, is_last_page: bool=True) -> None:
        super().__init__(wizard)
        self.is_last_page = is_last_page

        self.title = 'Installing selected dictionaries...'
        self.back_enabled = False
        self.next_enabled = False

        if self.is_last_page:
            self.next_text = 'Finish'

        lyt = QVBoxLayout()
        self.setLayout(lyt)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        lyt.addWidget(self.progress_bar)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        lyt.addWidget(self.log_box)

        self.is_complete = False
        self.install_thread: typing.Optional[InstallThread] = None


    def on_show(self, is_next: bool) -> None:
        if not is_next:
            _LOGGER.warn("Nothing to show next.")

            return

        self.is_complete = False
        self.install_thread = None
        self.progress_bar.setValue(0)
        self.log_box.clear()
        self.start_thread()


    def on_cancel(self) -> bool:
        if self.install_thread and self.install_thread.isRunning():
            r = QMessageBox.question(self, 'Migaku Dictioanry',
                              'Do you really want to cancel the import process?',
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if r != QMessageBox.StandardButton.Yes:
                return False

            self.install_thread.cancel_requested = True
            self.install_thread.wait()

        return True


    def add_log(self, txt: str) -> None:
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)

        if not _verify(self.log_box.document()).isEmpty():
            self.log_box.insertPlainText('\n')

        self.log_box.insertPlainText(txt)
        bar = _verify(self.log_box.verticalScrollBar())
        bar.setValue(bar.maximum())


    def update_progress(self, val: int) -> None:
        self.progress_bar.setValue(val)


    def start_thread(self) -> None:
        if self.install_thread:
            return

        if not self.wizard:
            raise RuntimeError("No Wizard is defined. Cannot call start_thread.")

        server_root = self.wizard.dictionary_server_root

        if not server_root:
            raise RuntimeError(
                f'Wizard "{self.wizard}" needs a server, cannot start a thread.'
            )

        install_index = self.wizard.dictionary_install_index
        install_freq = self.wizard.dictionary_install_frequency
        install_conj = self.wizard.dictionary_install_conjugation
        force_lang = self.wizard.dictionary_force_lang

        self.install_thread = InstallThread(server_root, install_index, install_freq, install_conj, force_lang)
        self.install_thread.finished.connect(self.on_thread_finish)
        self.install_thread.progress_update.connect(self.update_progress)
        self.install_thread.log_update.connect(self.add_log)
        self.install_thread.start()


    def on_thread_finish(self) -> None:
        self.progress_bar.setValue(100)
        self.next_enabled = True

        if self.is_last_page:
            self.cancel_enabled = False

        self.refresh_wizard_states()


class InstallThread(QThread):

    progress_update = pyqtSignal(int)
    log_update = pyqtSignal(str)

    def __init__(
        self,
        server_root: str,
        install_index: typing.Sequence[typer.InstallLanguage],
        install_freq: bool,
        install_conj: bool,
        force_lang: typing.Optional[str]=None,
        parent: typing.Optional[QObject]=None,
    ) -> None:
        super().__init__(parent)

        self.server_root = server_root
        self.install_index = install_index
        self.install_freq = install_freq
        self.install_conj = install_conj
        self.force_lang = force_lang
        self.cancel_requested = False

    def construct_url(self, url: str) -> str:
        if not url.startswith('http'):
            return self.server_root + url
        return url

    def run(self) -> None:
        from .dictionaryManager import importDict

        client = HttpClient()

        num_dicts = 0
        num_installed = 0

        def update_dict_progress(amt: typing.Union[float, int]) -> None:
            progress = 0
            if num_dicts > 0:
                progress = num_installed // num_dicts
                progress += int(amt // num_dicts)
            progress_percent = round(progress * 100)
            self.progress_update.emit(progress_percent)

        for l in self.install_index:
            num_dicts += len(l.get('dictionaries', []))

        self.log_update.emit('Installing %d dictionaries...' % num_dicts)

        freq_path = os.path.join(addon_path, 'user_files', 'db', 'frequency')
        os.makedirs(freq_path, exist_ok=True)

        conj_path = os.path.join(addon_path, 'user_files', 'db', 'conjugation')
        os.makedirs(conj_path, exist_ok=True)

        for l in self.install_index:
            if self.cancel_requested:
                return

            lname = self.force_lang
            if not lname:
                lname = l.get('name_en')
            if not lname:
                continue

            # Create Language
            try:
                dictdb.get().addLanguages([lname])
            except Exception as e:
                # Lanugage already exists
                pass

            # Install frequency data
            if self.install_freq:
                furl = l.get('frequency_url')
                if furl:
                    self.log_update.emit('Installing %s frequency data...' % lname)
                    furl = self.construct_url(furl)
                    dl_resp = client.get(furl)
                    if dl_resp.status_code == 200:
                        fdata = client.stream_content(dl_resp)
                        dst_path = os.path.join(freq_path, '%s.json' % lname)
                        with open(dst_path, 'wb') as f:
                            f.write(fdata)
                    else:
                        self.log_update.emit(' ERROR: Download failed (%d).' % dl_resp.status_code)

            # Install conjugation data
            if self.install_conj:
                curl = l.get('conjugation_url')
                if curl:
                    self.log_update.emit('Installing %s conjugation data...' % lname)
                    curl = self.construct_url(curl)
                    dl_resp = client.get(curl)
                    if dl_resp.status_code == 200:
                        cdata = client.stream_content(dl_resp)
                        dst_path = os.path.join(conj_path, '%s.json' % lname)
                        with open(dst_path, 'wb') as f:
                            f.write(cdata)
                    else:
                        self.log_update.emit(' ERROR: Download failed (%d).' % dl_resp.status_code)

            # Install dictionaries
            for d in l.get('dictionaries', []):
                if self.cancel_requested:
                    return

                dname = d['name']
                durl = self.construct_url(d['url'])

                self.log_update.emit('Installing %s...' % dname)

                self.log_update.emit(' Downloading %s...' % durl)
                dl_resp = client.get(durl)

                if dl_resp.status_code == 200:
                    update_dict_progress(0.5)
                    self.log_update.emit(' Importing...')
                    ddata = client.stream_content(dl_resp)
                    try:
                        importDict(lname, io.BytesIO(ddata), dname)
                    except ValueError as e:
                        self.log_update.emit(' ERROR: %s' % str(e))
                else:
                    self.log_update.emit(' ERROR: Download failed (%d).' % dl_resp.status_code)

                update_dict_progress(1.0)
                num_installed += 1

            # Only once language can be installed when language is forced
            if self.force_lang:
                # Should never happen
                break

        self.progress_update.emit(100)
        self.log_update.emit('All done.')


def _verify(value: typing.Optional[T]) -> T:
    if value is not None:
        return value

    raise RuntimeError('Expected a value but got None.')
