import typing


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
    currentGroup: typing.Union[typing.Literal["All"], typing.Literal["Google Images"], typing.Literal["Forvo"]]
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
    ontab: bool
    openOnGlobal: bool
    safeSearch: bool
    searchMode: typing.Union[typing.Literal["Forward"], typing.Literal["Backward"], typing.Literal["Exact"], typing.Literal["Anywhere"], typing.Literal["Definition"], typing.Literal["Example"], typing.Literal["Pronunciation"]]
    showTarget: bool
    tooltips: bool
    unknownsToSearch: int

    DictionaryGroups: dict
    ExportTemplates: dict
    GoogleImageFields: list
    ForvoFields: list
    ForvoAddType: typing.Literal["add"]
    ForvoLanguage: str  # typing.Literal["Japanese"]  # TODO: @ColinKennedy add more languages later
    GoogleImageAddType: typing.Literal["add"]


class Dictionary(typing.NamedTuple):
    index: int
    order: int
    text: str


class DictionaryGroup(typing.TypedDict):
    customFont: bool
    dictionaries: typing.List[Dictionary]
    font: str


class HeaderTerm(typing.TypedDict):
    altterm: str
    pronunciation: str
    term: str
