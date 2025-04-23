from __future__ import annotations

import json
import typing

from anki.httpclient import HttpClient

from . import typer


DEFAULT_SERVER = 'dicts.migaku.io'


def normalize_url(url: str) -> str:
    if not url.startswith('http'):
        url = 'http://' + url

    while url.endswith('/'):
        url = url[:-1]

    return url


def download_index(server_url: str=DEFAULT_SERVER) -> typing.Optional[typer.DictionaryLanguageIndex]:
    server_url = normalize_url(server_url)

    index_url = server_url + '/index.json'

    client = HttpClient()
    resp = client.get(index_url)

    if resp.status_code != 200:
        return None

    data = client.stream_content(resp)

    # TODO: @ColinKennedy - should check that the output works with DictionaryLanguageIndex
    return typing.cast(typer.DictionaryLanguageIndex, json.loads(data))
