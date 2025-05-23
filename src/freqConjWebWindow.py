import enum
import os
import typing

from anki import httpclient
from aqt import qt

from . import typer, webConfig

addon_path = os.path.dirname(__file__)


class FreqConjWebWindow(qt.QDialog):

    class Mode(enum.Enum):
        Freq = (0,)
        Conj = (1,)

    MIN_SIZE = (400, 400)

    def __init__(
        self,
        dst_lang: str,
        index_data: typer.DictionaryLanguageIndex2Pack,
        mode: Mode,
        parent: typing.Optional[qt.QWidget] = None,
    ) -> None:
        super().__init__()
        self._dst_lang = dst_lang
        self._mode = mode
        self._mode_str = "frequency" if self._mode == self.Mode.Freq else "conjugation"

        self.setWindowTitle("Migaku Dictionary - Web Installer")
        self.setWindowIcon(qt.QIcon(os.path.join(addon_path, "icons", "migaku.png")))

        lyt = qt.QVBoxLayout()
        self.setLayout(lyt)

        lbl = qt.QLabel(
            "Select the language you want to download %s data from" % self._mode_str
        )
        lbl.setWordWrap(True)
        lyt.addWidget(lbl)

        self._lst = qt.QListWidget()
        lyt.addWidget(self._lst)

        for lang in index_data.get("languages") or []:
            url = lang.get(
                typing.cast(
                    typing.Union[
                        typing.Literal["conjugation_url"],
                        typing.Literal["frequency_url"],
                    ],
                    self._mode_str + "_url",
                )
            )

            if url is None:
                continue

            if not isinstance(url, str):
                raise RuntimeError(f'Unexpected "{url}" data. It should be a string.')

            if not url.startswith("http"):
                url = webConfig.normalize_url(webConfig.DEFAULT_SERVER + url)

            lang_str = lang.get("name_en", "<Unnamed>")

            if "name_native" in lang:
                lang_str += " (" + lang["name_native"] + ")"

            itm = qt.QListWidgetItem(lang_str)
            itm.setData(qt.Qt.ItemDataRole.UserRole, url)
            self._lst.addItem(itm)

        btn = qt.QPushButton("Download")
        btn.clicked.connect(self._download)
        lyt.addWidget(btn)

        self.setMinimumSize(*self.MIN_SIZE)

    def _download(self) -> None:
        idx = self._lst.currentIndex()

        if not idx.isValid():
            qt.QMessageBox.information(
                self, self.windowTitle(), "Please select a language."
            )

            return

        url = idx.data(qt.Qt.ItemDataRole.UserRole)

        client = httpclient.HttpClient()
        resp = client.get(url)

        if resp.status_code != 200:
            qt.QMessageBox.information(
                self,
                self.windowTitle(),
                "Downloading %s data failed." % self._mode_str,
            )

            return

        data = client.stream_content(resp)

        dir_path = os.path.join(addon_path, "user_files", "db", self._mode_str)
        os.makedirs(dir_path, exist_ok=True)

        dst_path = os.path.join(dir_path, "%s.json" % self._dst_lang)

        with open(dst_path, "wb") as f:
            f.write(data)

        if self._mode == self.Mode.Freq:
            msg = (
                'Imported frequency data for "%s".\n\nNote that the frequency data is only applied to newly imported dictionaries for this language.'
                % self._dst_lang
            )
        else:
            msg = 'Imported conjugation data for "%s".' % self._dst_lang
        qt.QMessageBox.information(self, self.windowTitle(), msg)

        self.accept()

    @classmethod
    def execute_modal(
        cls,
        dst_lang: str,
        mode: Mode,
    ) -> typing.Union[qt.QDialog.DialogCode, int]:
        index_data = webConfig.download_index()

        if index_data is None:
            qt.QMessageBox.information(
                None,
                "Migaku Dictionary",
                "The dictionary server is not reachable at the moment.\n\n"
                "Please try again later.",
            )

            return qt.QDialog.DialogCode.Rejected

        window = cls(dst_lang, index_data, mode)

        return window.exec()
