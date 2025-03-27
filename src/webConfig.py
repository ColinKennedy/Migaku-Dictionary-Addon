import json
from anki.httpclient import HttpClient


DEFAULT_SERVER = 'dicts.migaku.io'


class _Dictionary(typing.TypedDict):
    name: str
    description: str


class _DictionaryLanguage(typing.TypedDict):
    name_en: str
    name_native: str
    to_languages: typing.Sequence[_DictionaryLanguage] | None
    dictionaries: typing.Sequence[_Dictionary]


def normalize_url(url: str) -> str:
    if not url.startswith('http'):
        url = 'http://' + url

    while url.endswith('/'):
        url = url[:-1]

    return url


def download_index(server_url: str=DEFAULT_SERVER) -> _DictionaryLanguage:
    server_url = normalize_url(server_url)
    
    index_url = server_url + '/index.json'

    client = HttpClient()
    resp = client.get(index_url)

    if resp.status_code != 200:
        return None

    data = client.stream_content(resp)

    return json.loads(data)
