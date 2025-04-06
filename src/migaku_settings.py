import typing

from . import addonSettings


_INSTANCE: typing.Optional[addonSettings.SettingsGui] = None


def clear() -> None:
    _INSTANCE = None


def initialize(settings: addonSettings.SettingsGui) -> None:
    global _INSTANCE

    _INSTANCE = settings

    return _INSTANCE


def get() -> addonSettings.SettingsGui:
    if _INSTANCE:
        return _INSTANCE

    raise RuntimeError("No settings GUI was initialized.")


def get_unsafe() -> typing.Optional[addonSettings.SettingsGui]:
    return _INSTANCE
