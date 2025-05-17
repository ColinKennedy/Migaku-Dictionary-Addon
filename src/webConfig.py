from __future__ import annotations

import json
import typing

from anki import httpclient

from . import typer

DEFAULT_SERVER = "dicts.migaku.io"


def normalize_url(url: str) -> str:
    if not url.startswith("http"):
        url = "http://" + url

    while url.endswith("/"):
        url = url[:-1]

    return url


def download_index(
    server_url: str = DEFAULT_SERVER,
) -> typing.Optional[typer.DictionaryLanguageIndex2Pack]:
    server_url = normalize_url(server_url)

    index_url = server_url + "/index.json"

    client = httpclient.HttpClient()
    resp = client.get(index_url)

    if resp.status_code != 200:
        return None

    data = client.stream_content(resp)

    return typing.cast(typer.DictionaryLanguageIndex2Pack, json.loads(data))
