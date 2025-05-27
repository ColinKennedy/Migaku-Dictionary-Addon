"""Any types that make reading Yomitan JSON dicts (or complex types) easier."""

import typing


class _DictionaryEntryContent(typing.TypedDict):
    content: str
    tag: str


class _DictionaryEntryData(typing.TypedDict):
    content: str


class _DictionaryEntryStyle(typing.TypedDict):
    listStyleType: str


class _DictionaryEntryDefinition(typing.TypedDict):
    content: typing.Union[list[_DictionaryEntryContent], _DictionaryEntryContent]
    data: _DictionaryEntryData
    lang: str
    style: _DictionaryEntryStyle
    tag: str


class DictionaryEntryWithExamples(typing.TypedDict):
    # Example:
    #
    # {
    #     'content': [
    #         {
    #             'content': {
    #                 'content': 'repetition mark in katakana',
    #                 'tag': 'li',
    #             },
    #             'data': {'content': 'glossary'},
    #             'lang': 'en',
    #             'style': {'listStyleType': 'circle'},
    #             'tag': 'ul'
    #         },
    #         {
    #             'content': {
    #                 'content': [
    #                     'see: ',
    #                     {
    #                         'content': 'Σ╕Çπü«σ¡ùτé╣',
    #                         'href': '?query=Σ╕Çπü«σ¡ùτé╣&wildcards=off',
    #                         'lang': 'ja',
    #                         'tag': 'a',
    #                     },
    #                     {
    #                         'content': ' kana iteration mark',
    #                         'data': {'content': 'refGlosses'},
    #                         'style': {'fontSize': '65%', 'verticalAlign': 'middle'},
    #                         'tag': 'span',
    #                     },
    #                 ],
    #                 'tag': 'li',
    #             },
    #             'data': {'content': 'references'},
    #             'lang': 'en',
    #             'style': {'listStyleType': "'Γ₧í∩╕Å '"},
    #             'tag': 'ul',
    #         },
    #     ],
    #     'type': 'structured-content',
    # },
    #
    content: list[_DictionaryEntryDefinition]
