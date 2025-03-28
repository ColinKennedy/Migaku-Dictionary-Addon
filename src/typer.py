import typing


# TODO: @ColinKennedy - Probably the Literal[False] is should be `| None`
class Configuration(typing.TypedDict):
    autoAddCards: bool
    autoAddDefinitions: bool
    autoDefinitionSettings: bool
    backBracket: str
    condensedAudioDirectory: typing.Union[str, typing.Literal[False]]
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
    ForvoLanguage: typing.Literal["Japanese"]  # TODO: @ColinKennedy add more languages later
    GoogleImageAddType: typing.Literal["add"]
