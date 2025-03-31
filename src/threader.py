import typing

from . import midict


_THREAD: typing.Optional[midict.ClipThread] = None


def initialize(thread: midict.ClipThread):
    global _THREAD

    _THREAD = thread

    return _THREAD


def get():
    if not _THREAD:
        raise RuntimeError('No clip thread was initialized.')

    return _THREAD
