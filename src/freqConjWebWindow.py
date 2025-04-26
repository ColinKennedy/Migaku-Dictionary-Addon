import typing

import os
from enum import Enum
from aqt.qt import *
from anki.httpclient import HttpClient

from . import typer, webConfig

addon_path = os.path.dirname(__file__)



class FreqConjWebWindow(QDialog):

    class Mode(Enum):
        Freq = 0,
        Conj = 1,

    MIN_SIZE = (400, 400)

    def __init__(
        self,
        dst_lang: str,
        index_data: typer.DictionaryLanguageIndex2Pack,
        mode: Mode,
        parent: typing.Optional[QWidget]=None,
    ) -> None:
        super().__init__()
        self.dst_lang = dst_lang
        self.mode = mode
        self.mode_str = 'frequency' if self.mode == self.Mode.Freq else 'conjugation'

        self.setWindowTitle('Migaku Dictionary - Web Installer')
        self.setWindowIcon(QIcon(os.path.join(addon_path, 'icons', 'migaku.png')))

        lyt = QVBoxLayout()
        self.setLayout(lyt)

        lbl = QLabel('Select the language you want to download %s data from' % self.mode_str)
        lbl.setWordWrap(True)
        lyt.addWidget(lbl)

        self.lst = QListWidget()
        lyt.addWidget(self.lst)

        for lang in index_data.get('languages') or []:
            url = lang.get(
                typing.cast(
                    typing.Union[
                        typing.Literal["conjugation_url"],
                        typing.Literal["frequency_url"],
                    ],
                    self.mode_str + '_url',
                )
            )

            if url is None:
                continue

            if not isinstance(url, str):
                raise RuntimeError(f'Unexpected "{url}" data. It should be a string.')

            if not url.startswith('http'):
                url = webConfig.normalize_url(webConfig.DEFAULT_SERVER + url)

            lang_str = lang.get('name_en', '<Unnamed>')

            if 'name_native' in lang:
                lang_str += ' (' + lang['name_native'] + ')'

            itm = QListWidgetItem(lang_str)
            itm.setData(Qt.ItemDataRole.UserRole, url)
            self.lst.addItem(itm)

        btn = QPushButton('Download')
        btn.clicked.connect(self.download)
        lyt.addWidget(btn)

        self.setMinimumSize(*self.MIN_SIZE)

    def download(self) -> None:
        idx = self.lst.currentIndex()

        if not idx.isValid():
            QMessageBox.information(self, self.windowTitle(), 'Please select a language.')

            return

        url = idx.data(Qt.ItemDataRole.UserRole)

        client = HttpClient()
        resp = client.get(url)

        if resp.status_code != 200:
            QMessageBox.information(
                self,
                self.windowTitle(),
                'Downloading %s data failed.' % self.mode_str,
            )

            return

        data = client.stream_content(resp)

        dir_path = os.path.join(addon_path, 'user_files', 'db', self.mode_str)
        os.makedirs(dir_path, exist_ok=True)

        dst_path = os.path.join(dir_path, '%s.json' % self.dst_lang)

        with open(dst_path, 'wb') as f:
            f.write(data)

        if self.mode == self.Mode.Freq:
            msg = 'Imported frequency data for "%s".\n\nNote that the frequency data is only applied to newly imported dictionaries for this language.' % self.dst_lang
        else:
            msg = 'Imported conjugation data for "%s".' % self.dst_lang
        QMessageBox.information(self, self.windowTitle(), msg)


        self.accept()

    @classmethod
    def execute_modal(
        cls,
        dst_lang: str,
        mode: Mode,
    ) -> typing.Union[QDialog.DialogCode, int]:
        index_data = webConfig.download_index()

        if index_data is None:
            QMessageBox.information(
                None,
                'Migaku Dictionary',
                'The dictionary server is not reachable at the moment.\n\n'
                'Please try again later.',
            )

            return QDialog.DialogCode.Rejected

        window = cls(dst_lang, index_data, mode)

        return window.exec()
