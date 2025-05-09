from __future__ import annotations

import typing


T = typing.TypeVar("T")

AddType = typing.Union[
    typing.Literal["add"],
    typing.Literal["no"],
    typing.Literal["overwrite"],
]

GroupName = typing.Union[typing.Literal["All"], typing.Literal["Google Images"], typing.Literal["Forvo"]]
SearchMode = typing.Union[typing.Literal["Forward"], typing.Literal["Backward"], typing.Literal["Exact"], typing.Literal["Anywhere"], typing.Literal["Definition"], typing.Literal["Example"], typing.Literal["Pronunciation"]]
SearchTerm = typing.Union[
    typing.Literal["Forward"],
    typing.Literal["Pronunciation"],
    typing.Literal["Backward"],
    typing.Literal["Anywhere"],
    typing.Literal["Exact"],
    typing.Literal["Definition"],
]


class _GenerationPreferences(typing.TypedDict):
    addType: str
    destination: str
    dict1: str
    dict2: str
    dict3: str
    limit: int
    origin: str


class Card(typing.TypedDict):
    # unknowns: list[str]
    audio: str
    bulk: bool
    image: typing.Optional[str]
    primary: str
    secondary: str
    total: int
    unknownWords: list[str]


# TODO: @ColinKennedy - Probably the Literal[False] is should be `| None`
class Configuration(typing.TypedDict):
    autoAddCards: bool
    autoAddDefinitions: bool
    autoDefinitionSettings: typing.Optional[list[DefinitionSetting]]
    backBracket: str
    condensedAudioDirectory: typing.Optional[str]
    currentDeck: typing.Optional[str]
    currentGroup: GroupName
    currentTemplate: typing.Optional[str]
    day: bool
    deinflect: bool
    dictAlwaysOnTop: bool
    dictOnStart: bool
    dictSearch: int
    dictSizePos: typing.Union[tuple[int, int, int, int], typing.Literal[False]]
    disableCondensed: bool
    displayAgain: bool
    exporterLastTags: str
    exporterSizePos: typing.Union[tuple[int, int, int, int], typing.Literal[False]]
    failedFFMPEGInstallation: bool
    fontSizes: tuple[int, int]
    frontBracket: str
    globalHotkeys: bool
    googleSearchRegion: str
    highlightSentences: bool
    highlightTarget: bool
    jReadingCards: bool
    jReadingEdit: bool
    massGenerationPreferences: _GenerationPreferences
    maxHeight: int
    maxSearch: int
    maxWidth: int
    mp3Convert: bool
    onetab: bool
    openOnGlobal: bool
    safeSearch: bool
    searchMode: SearchMode
    showTarget: bool
    tooltips: bool
    unknownsToSearch: int

    DictionaryGroups: dict[str, DictionaryGroup]
    ExportTemplates: dict[str, ExportTemplate]
    GoogleImageFields: list[str]
    ForvoFields: list[str]
    ForvoAddType: AddType
    ForvoLanguage: str  # typing.Literal["Japanese"]  # TODO: @ColinKennedy add more languages later
    GoogleImageAddType: AddType


class Conjugation(typing.TypedDict):
    dict: str
    inflected: str
    prefix: str


class DefinitionSetting(typing.TypedDict):
    name: str
    limit: int


class Dictionary(typing.NamedTuple):
    dictionary_index: int
    order: int
    text: str


class DictionaryConfiguration(typing.TypedDict):
    dictName: str
    field: str
    limit: int
    tableName: str


class DictionaryLanguagePair(typing.TypedDict):
    dict: str
    lang: str  # TODO: @ColinKennedy this type may not be right


class DictionaryGroup(typing.TypedDict):
    # TODO: @ColinKennedy - I think bool is actually str. Test that later.
    customFont: bool
    dictionaries: list[DictionaryLanguagePair]
    font: str


class DictionaryResult(typing.TypedDict):
    # TODO: @ColinKennedy - Check the types here, later
    term: str
    altterm: str
    pronunciation: str
    pos: int
    definition: str
    examples: str
    audio: str
    starCount: str


# TODO: @ColinKennedy - Rename this classes later
# TODO: @ColinKennedy - DictionaryFrequencyResult might actually be DictionaryResult
class DictionaryFrequencyResult(typing.TypedDict):
    term: str
    altterm: str
    pronunciation: str
    pos: int
    definition: str
    examples: str
    audio: str
    starCount: str
    frequency: int


class DictionaryLanguageIndex(typing.TypedDict):
    # TODO: @ColinKennedy - Check if these key / values work
    name_en: str
    name_native: str
    to_languages: typing.Optional[typing.Sequence[DictionaryLanguageIndex]]
    dictionaries: typing.Sequence[IndexDictionary]


class DictionaryLanguageIndex2Pack(typing.TypedDict):
    # TODO: @ColinKennedy - Check if these key / values work
    languages: typing.Optional[typing.Sequence[DictionaryLanguageIndex2Index]]


class DictionaryLanguageIndex2Index(typing.TypedDict):
    # TODO: @ColinKennedy - Can we merge this class with `DictionaryLanguageIndex`
    code: str
    frequency_url: str
    name_en: str
    name_native: str
    to_languages: typing.Optional[typing.Sequence[DictionaryLanguageIndex]]


class ExportTemplate(typing.TypedDict):
    audio: str
    image: str
    secondary: typing.Optional[str]
    sentence: str
    word: str

    # TODO: @ColinKennedy - Not sure if these keys/values are correct. It seemed as
    # though `src/cardExporter.py` needed them but still not sure.
    noteType: str
    notes: str
    separator: str

    # TODO: @ColinKennedy - Not sure if these keys/values are correct. It seemed as
    # though `src/cardExporter.py` needed them but still not sure.
    specific: dict[str, list[str]]
    unspecified: str


class IndexDictionary(typing.TypedDict):
    name: str
    description: str
    url: str


class InstallLanguage(DictionaryLanguageIndex):
    conjugation_url: str
    frequency_url: str


def check_t(item: typing.Optional[T]) -> T:
    if item is None:
        raise RuntimeError('Item was not defined as expected.')

    return item
