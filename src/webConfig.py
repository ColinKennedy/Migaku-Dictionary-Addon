from __future__ import annotations

import json
import typing

from anki.httpclient import HttpClient


DEFAULT_SERVER = 'dicts.migaku.io'


class _Dictionary(typing.TypedDict):
    name: str
    description: str


class DictionaryLanguage(typing.TypedDict):
    # TODO: @ColinKennedy - Check if these key / values work
    name_en: str
    name_native: str
    to_languages: typing.Optional[typing.Sequence[DictionaryLanguage]]
    dictionaries: typing.Sequence[_Dictionary]


def normalize_url(url: str) -> str:
    if not url.startswith('http'):
        url = 'http://' + url

    while url.endswith('/'):
        url = url[:-1]

    return url


def download_index(server_url: str=DEFAULT_SERVER) -> typing.Optional[DictionaryLanguage]:
    server_url = normalize_url(server_url)

    index_url = server_url + '/index.json'

    client = HttpClient()
    resp = client.get(index_url)

    if resp.status_code != 200:
        return None

    data = client.stream_content(resp)

    # TODO: @ColinKennedy - should check that the output works with DictionaryLanguage
    return typing.cast(DictionaryLanguage, json.loads(data))
