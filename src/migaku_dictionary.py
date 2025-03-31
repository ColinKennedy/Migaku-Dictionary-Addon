import typing

from . import midict


_DICTIONARY: typing.Optional[midict.DictInterface] = None


def get() -> midict.DictInterface:
    if _DICTIONARY:
        return _DICTIONARY

    raise RuntimeError("No dictionary was initialized.")


def get_unsafe() -> typing.Optional[midict.DictInterface]:
    return _DICTIONARY


def get_visible_dictionary() -> typing.Optional[midict.DictInterface]:
    if dictionary := get_unsafe():
        if dictionary.isVisible():
            return dictionary

    return None


def clear() -> None:
    global _DICTIONARY

    _DICTIONARY = None


def set(dictionary: midict.DictInterface) -> None:
    global _DICTIONARY

    _DICTIONARY = dictionary
