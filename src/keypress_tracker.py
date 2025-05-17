from anki import utils

from . import threader

_CURRENTLY_PRESSED: list[str] = []


def clear() -> None:
    _CURRENTLY_PRESSED.clear()


def get() -> list[str]:
    return _CURRENTLY_PRESSED


def capture_key(keyList: list[str]) -> None:
    key = keyList[0]
    char = str(key)

    if char not in _CURRENTLY_PRESSED:
        _CURRENTLY_PRESSED.append(char)

    thread = threader.get()

    if utils.is_win:
        if (
            "Key.ctrl_l" in _CURRENTLY_PRESSED
            and "'c'" in _CURRENTLY_PRESSED
            and "Key.space" in _CURRENTLY_PRESSED
        ):
            thread.handleSystemSearch()
            clear()
        elif (
            "Key.ctrl_l" in _CURRENTLY_PRESSED
            and "'c'" in _CURRENTLY_PRESSED
            and "'b'" in _CURRENTLY_PRESSED
        ):
            thread.handleColSearch()
            clear()
        elif (
            "Key.ctrl_l" in _CURRENTLY_PRESSED
            and "'c'" in _CURRENTLY_PRESSED
            and "Key.alt_l" in _CURRENTLY_PRESSED
        ):
            thread.handleSentenceExport()
            clear()
        elif "Key.ctrl_l" in _CURRENTLY_PRESSED and "Key.enter" in _CURRENTLY_PRESSED:
            thread.attemptAddCard()
            clear()
        elif (
            "Key.ctrl_l" in _CURRENTLY_PRESSED
            and "Key.shift" in _CURRENTLY_PRESSED
            and "'v'" in _CURRENTLY_PRESSED
        ):
            thread.handleImageExport()
            clear()
    elif utils.is_lin:
        if (
            "Key.ctrl" in _CURRENTLY_PRESSED
            and "'c'" in _CURRENTLY_PRESSED
            and "Key.space" in _CURRENTLY_PRESSED
        ):
            thread.handleSystemSearch()
            clear()
        elif (
            "Key.ctrl" in _CURRENTLY_PRESSED
            and "'c'" in _CURRENTLY_PRESSED
            and "Key.alt" in _CURRENTLY_PRESSED
        ):
            thread.handleSentenceExport()
            clear()
        elif "Key.ctrl" in _CURRENTLY_PRESSED and "Key.enter" in _CURRENTLY_PRESSED:
            thread.attemptAddCard()
            clear()
        elif (
            "Key.ctrl" in _CURRENTLY_PRESSED
            and "Key.shift" in _CURRENTLY_PRESSED
            and "'v'" in _CURRENTLY_PRESSED
        ):
            thread.handleImageExport()
            clear()
    else:
        if (
            ("Key.cmd" in _CURRENTLY_PRESSED or "Key.cmd_r" in _CURRENTLY_PRESSED)
            and "'c'" in _CURRENTLY_PRESSED
            and "'b'" in _CURRENTLY_PRESSED
        ):
            thread.handleColSearch()
            clear()
        elif (
            ("Key.cmd" in _CURRENTLY_PRESSED or "Key.cmd_r" in _CURRENTLY_PRESSED)
            and "'c'" in _CURRENTLY_PRESSED
            and "Key.ctrl" in _CURRENTLY_PRESSED
        ):
            thread.handleSentenceExport()
            clear()
        elif (
            "Key.cmd" in _CURRENTLY_PRESSED or "Key.cmd_r" in _CURRENTLY_PRESSED
        ) and "Key.enter" in _CURRENTLY_PRESSED:
            thread.attemptAddCard()
            clear()
        elif (
            ("Key.cmd" in _CURRENTLY_PRESSED or "Key.cmd_r" in _CURRENTLY_PRESSED)
            and "Key.shift" in _CURRENTLY_PRESSED
            and "'v'" in _CURRENTLY_PRESSED
        ):
            thread.handleImageExport()
            clear()


def release_key(keyList: list[str]) -> None:
    key = keyList[0]

    try:
        _CURRENTLY_PRESSED.remove(str(key))
    except:
        # TODO: @ColinKennedy - docstring / logging
        return
