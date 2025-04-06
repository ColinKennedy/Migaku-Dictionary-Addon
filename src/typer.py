import typing


T = typing.TypeVar("T")

GroupName = typing.Union[typing.Literal["All"], typing.Literal["Google Images"], typing.Literal["Forvo"]]
SearchMode = typing.Union[typing.Literal["Forward"], typing.Literal["Backward"], typing.Literal["Exact"], typing.Literal["Anywhere"], typing.Literal["Definition"], typing.Literal["Example"], typing.Literal["Pronunciation"]]


class Card(typing.TypedDict):
    # unknowns: list[str]
    audio: str
    bulk: bool
    image: str
    primary: str
    secondary: str
    total: int
    unknownWords: list[str]


# TODO: @ColinKennedy - Probably the Literal[False] is should be `| None`
class Configuration(typing.TypedDict):
    autoAddCards: bool
    autoAddDefinitions: bool
    autoDefinitionSettings: bool
    backBracket: str
    condensedAudioDirectory: typing.Optional[str]
    currentDeck: typing.Union[str, typing.Literal[False]]
    currentGroup: GroupName
    currentTemplate: typing.Union[str, typing.Literal[False]]
    day: bool
    deinflect: bool
    dictAlwaysOnTop: bool
    dictOnStart: bool
    dictSearch: int
    dictSizePos: typing.Union[tuple[int, int, int, int], typing.Literal[False]]
    disableCondensed: bool
    displayAgain: bool
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
    massGenerationPreferences: bool
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

    DictionaryGroups: dict
    ExportTemplates: dict
    GoogleImageFields: list[str]
    ForvoFields: list[str]
    ForvoAddType: typing.Literal["add"]
    ForvoLanguage: str  # typing.Literal["Japanese"]  # TODO: @ColinKennedy add more languages later
    GoogleImageAddType: typing.Literal["add"]


class Dictionary(typing.NamedTuple):
    index: int
    order: int
    text: str


class DictionaryLanguagePair(typing.TypedDict):
    dict: str
    lang: str  # TODO: @ColinKennedy this type may not be right


class DictionaryGroup(typing.TypedDict):
    # TODO: @ColinKennedy - I think bool is actually str. Test that later.
    customFont: bool
    dictionaries: typing.List[DictionaryLanguagePair]
    font: str


class DictionaryResult(typing.TypedDict):
    # TODO: @ColinKennedy - Check the types here, later
    term: str
    altterm: str
    pronunciation: str
    pos: int
    definition: str
    examples: list
    audio: str
    starCount: str


# TODO: @ColinKennedy - DictionaryFrequencyResult might actually be DictionaryResult
class DictionaryFrequencyResult(typing.TypedDict):
    term: str
    altterm: str
    pronunciation: str
    pos: int
    definition: str
    examples: list
    audio: str
    starCount: str
    frequency: int


def check_t(item: typing.Optional[T]) -> T:
    if item is None:
        raise RuntimeError('Item was not defined as expected.')

    return item
