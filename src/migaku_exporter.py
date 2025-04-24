import re
import typing

from anki import notes as notes_
from aqt import mw

from . import dictdb, google_imager, migaku_forvo, typer


def _getTermHeaderText(th: str, entry: typer.DictionaryResult, fb: str, bb: str) -> str:
    term = entry['term']
    altterm = entry['altterm']
    if altterm == term:
        altterm == ''
    pron = entry['pronunciation']
    if pron == term:
        pron = ''

    termHeader = ''
    for header in th:
        if header == 'term':
            termHeader += fb + term + bb
        elif header == 'altterm':
            if altterm != '':
                termHeader += fb + altterm + bb
        elif header == 'pronunciation':
            if pron != '':
                if termHeader != '':
                    termHeader += ' '
                termHeader  += pron + ' '
    termHeader += entry['starCount']
    return termHeader


def addDefinitionsToCardExporterNote(
    note: notes_.Note,
    term: str,
    dictionaryConfigurations: typing.Iterable[typer.DictionaryConfiguration],
) -> notes_.Note:
    config = mw.addonManager.getConfig(__name__)
    fb = config['frontBracket']
    bb = config['backBracket']
    lang = config['ForvoLanguage']
    fields = mw.col.models.field_names(note.model())
    database = dictdb.get()

    for dictionary in dictionaryConfigurations:
        tableName = dictionary["tableName"]
        dictName  = dictionary["dictName"]
        limit = dictionary["limit"]
        targetField = dictionary["field"]

        if targetField in fields:
            term = re.sub(r'<[^>]+>', '', term)
            term = re.sub(r'\[[^\]]+?\]', '', term)

            if not term:
                continue

            tresults: list[str] = []

            if tableName == 'Google Images':
                tresults.append(google_imager.export_images(term, limit))
            elif tableName == 'Forvo':
                tresults.append(migaku_forvo.export_audio(term, limit, lang))
            elif tableName != 'None':
                dresults, dh, th = database.getDefForMassExp(term, tableName, str(limit), dictName)
                tresults.append(formatDefinitions(dresults, th, dh, fb, bb))
            results = '<br><br>'.join([i for i in tresults if i != ''])
            if results != "":
                if note[targetField] == '' or note[targetField] == '<br>':
                    note[targetField] = results
                else:
                    note[targetField] += '<br><br>' + results
    return note


def formatDefinitions(
    results: typing.Iterable[typer.DictionaryResult],
    th: str,
    dh: int,
    fb: str,
    bb: str,
) -> str:
    definitions: list[str] = []

    for r in results:
        text = ''

        if dh == 0:
            text = _getTermHeaderText(th, r, fb, bb) + '<br>' + r['definition']
        else:
            stars = r['starCount']
            text =  r['definition']
            if '】' in text:
                text = text.replace('】',  '】' + stars + ' ', 1)
            elif '<br>' in text:
                text = text.replace('<br>', stars+ '<br>', 1);
            else:
                text = stars + '<br>' + text

        definitions.append(text)

    return '<br><br>'.join(definitions).replace('<br><br><br>', '<br><br>')
