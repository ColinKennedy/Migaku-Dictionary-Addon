import typing

from aqt import mw

from . import typer


_NAMESPACE = __name__
_INSTANCE: typing.Optional[typer.Configuration] = None


def initialize_by_namespace() -> None:
    global _INSTANCE

    _INSTANCE = mw.addonManager.getConfig(_NAMESPACE)

    return _INSTANCE


def get() -> typer.Configuration:
    if not _INSTANCE:
        raise RuntimeError("No Migaku dictionary configuration was found.")

    return _INSTANCE


def override_configuration(configuration: typer.Configuration) -> None:
    global _INSTANCE

    _INSTANCE = configuration


def refresh_configuration(configuration: typing.Optional[typer.Configuration]) -> None:
    if configuration is None:
        initialize_by_namespace()

        return

    override_configuration(configuration)
