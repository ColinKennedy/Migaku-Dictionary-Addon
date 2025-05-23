from __future__ import annotations

import typing

from aqt import qt

T = typing.TypeVar("T", bound="MiWizard", covariant=True)


# TODO: @ColinKennedy - What is all this? An abstract class without using ``abc``?
class MiWizardPage(typing.Generic[T], qt.QWidget):

    def __init__(self, parent: typing.Optional[qt.QWidget] = None) -> None:
        super().__init__(parent)

        self.wizard: typing.Optional[T] = None
        self.title: typing.Optional[str] = None
        self.subtitle: typing.Optional[str] = None
        self.pixmap: typing.Optional[qt.QPixmap] = None

        self.back_text = "< Back"
        self.back_enabled = True
        self.back_visible = True

        self.next_text = "Next >"
        self.next_enabled = True
        self.next_visible = True

        self.cancel_text = "Cancel"
        self.cancel_enabled = True
        self.cancel_visible = True

    def on_show(self, is_next: bool) -> None:
        pass

    def on_hide(self, is_next: bool, is_back: bool) -> None:
        pass

    def on_back(self) -> bool:
        return True

    def on_next(self) -> bool:
        return True

    def on_cancel(self) -> bool:
        return True

    def refresh_wizard_states(self) -> None:
        if self.wizard:
            self.wizard.refresh_states()


class MiWizard(qt.QDialog):

    def __init__(self, parent: typing.Optional[qt.QWidget] = None) -> None:
        super(MiWizard, self).__init__(parent)

        self._current_page: typing.Optional[MiWizardPage[MiWizard]] = None
        self._page_back: dict[
            MiWizardPage[MiWizard], typing.Optional[MiWizardPage[MiWizard]]
        ] = {}
        self._page_next: dict[
            MiWizardPage[MiWizard], typing.Optional[MiWizardPage[MiWizard]]
        ] = {}

        lyt = qt.QVBoxLayout()
        lyt.setContentsMargins(0, 0, 0, 0)
        self.setLayout(lyt)

        page_frame = qt.QFrame()
        page_frame.setSizePolicy(
            qt.QSizePolicy.Policy.Expanding, qt.QSizePolicy.Policy.Expanding
        )
        page_frame.setBackgroundRole(qt.QPalette.ColorRole.Base)
        page_frame.setAutoFillBackground(True)
        lyt.addWidget(page_frame)

        page_hlyt = qt.QHBoxLayout(page_frame)

        pixmap_lyt = qt.QVBoxLayout()
        page_hlyt.addLayout(pixmap_lyt)

        self._pixmap_lbl = qt.QLabel()
        self._pixmap_lbl.setSizePolicy(
            qt.QSizePolicy.Policy.Fixed, qt.QSizePolicy.Policy.Fixed
        )
        pixmap_lyt.addWidget(self._pixmap_lbl)
        pixmap_lyt.addStretch()

        page_vlyt = qt.QVBoxLayout()
        page_hlyt.addLayout(page_vlyt)

        self._header_lbl = qt.QLabel()
        page_vlyt.addWidget(self._header_lbl)

        self._pages_lyt = qt.QHBoxLayout()
        self._pages_lyt.setSizeConstraint(qt.QLayout.SizeConstraint.SetMaximumSize)
        page_vlyt.addLayout(self._pages_lyt)

        btn_lyt = qt.QHBoxLayout()
        lyt.addLayout(btn_lyt)
        style = self.style()

        if not style:
            raise RuntimeError("MiWizard has no style.")

        margins = (
            style.pixelMetric(qt.QStyle.PixelMetric.PM_LayoutLeftMargin),
            style.pixelMetric(qt.QStyle.PixelMetric.PM_LayoutTopMargin),
            style.pixelMetric(qt.QStyle.PixelMetric.PM_LayoutRightMargin),
            style.pixelMetric(qt.QStyle.PixelMetric.PM_LayoutBottomMargin),
        )
        btn_lyt.setContentsMargins(*margins)

        btn_lyt.addStretch()

        self._btn_back = qt.QPushButton()
        self._btn_back.setFocusPolicy(qt.Qt.FocusPolicy.NoFocus)
        self._btn_back.clicked.connect(self.back)
        btn_lyt.addWidget(self._btn_back)

        self._btn_next = qt.QPushButton()
        self._btn_next.setFocusPolicy(qt.Qt.FocusPolicy.NoFocus)
        self._btn_next.clicked.connect(self.next)
        btn_lyt.addWidget(self._btn_next)

        self._btn_cancel = qt.QPushButton()
        self._btn_cancel.setFocusPolicy(qt.Qt.FocusPolicy.NoFocus)
        self._btn_cancel.clicked.connect(self.cancel)
        btn_lyt.addWidget(self._btn_cancel)

    def add_page(
        self,
        page: MiWizardPage[MiWizard],
        back_page: typing.Optional[MiWizardPage[MiWizard]] = None,
        next_page: typing.Optional[MiWizardPage[MiWizard]] = None,
        back_populate: bool = True,
    ) -> MiWizardPage[MiWizard]:
        page.wizard = self
        page.hide()
        page_lyt = page.layout()
        if page_lyt:
            page_lyt.setContentsMargins(0, 0, 0, 0)
        page.setSizePolicy(
            qt.QSizePolicy.Policy.Expanding, qt.QSizePolicy.Policy.Expanding
        )
        self._pages_lyt.addWidget(page)
        self.set_page_back(page, back_page)
        self.set_page_next(page, next_page)

        if self._current_page is None:
            self.set_current_page(page, is_next=True)

        return page

    def set_page_back(
        self,
        page: MiWizardPage[MiWizard],
        back_page: typing.Optional[MiWizardPage[MiWizard]],
        back_populate: bool = True,
    ) -> None:
        self._page_back[page] = back_page
        if back_populate and back_page:
            self.set_page_next(back_page, page, back_populate=False)

    def set_page_next(
        self,
        page: MiWizardPage[MiWizard],
        next_page: typing.Optional[MiWizardPage[MiWizard]],
        back_populate: bool = True,
    ) -> None:
        self._page_next[page] = next_page
        if back_populate and next_page:
            self.set_page_back(next_page, page, back_populate=False)

    def set_current_page(
        self, page: MiWizardPage[MiWizard], is_next: bool = False, is_back: bool = False
    ) -> None:
        if self._current_page:
            self._current_page.on_hide(is_next, is_back)
            self._current_page.hide()
        self._current_page = page

        page.on_show(is_next)

        self.refresh_states()

        page.show()

    def back(self) -> None:
        if not self._current_page:
            return

        if not self._current_page.on_back():
            return

        back_page = self._page_back.get(self._current_page)

        if back_page:
            self.set_current_page(back_page, is_back=True)

    def next(self) -> None:
        if not self._current_page:
            return

        if not self._current_page.on_next():
            return

        next_page = self._page_next.get(self._current_page)

        if next_page:
            self.set_current_page(next_page, is_next=True)
        else:
            self.accept()

    def cancel(self) -> None:
        if self._current_page:
            if not self._current_page.on_cancel():
                return

        if not self.on_cancel():
            return

        self.reject()

    def on_cancel(self) -> bool:
        return True

    def refresh_states(self) -> None:
        if self._current_page:
            header_text = ""

            title = self._current_page.title
            if title:
                header_text += "<h2>%s</h2>" % title

            subtitle = self._current_page.subtitle
            if subtitle:
                header_text += "<h4>%s</h4>" % subtitle

            if header_text:
                self._header_lbl.setText(header_text)
                self._header_lbl.setVisible(True)
            else:
                self._header_lbl.clear()
                self._header_lbl.setVisible(False)

            pixmap = self._current_page.pixmap
            if pixmap:
                self._pixmap_lbl.setPixmap(pixmap)
            else:
                self._pixmap_lbl.clear()
            self._pixmap_lbl.setVisible(bool(pixmap))

            self._btn_back.setText(self._current_page.back_text)
            self._btn_back.setEnabled(self._current_page.back_enabled)
            self._btn_back.setVisible(self._current_page.back_visible)
            self._btn_next.setText(self._current_page.next_text)
            self._btn_next.setEnabled(self._current_page.next_enabled)
            self._btn_next.setVisible(self._current_page.next_visible)
            self._btn_cancel.setText(self._current_page.cancel_text)
            self._btn_cancel.setEnabled(self._current_page.cancel_enabled)
            self._btn_cancel.setVisible(self._current_page.cancel_visible)

    def closeEvent(self, event: typing.Optional[qt.QCloseEvent]) -> None:
        self.cancel()

        if event:
            event.ignore()
