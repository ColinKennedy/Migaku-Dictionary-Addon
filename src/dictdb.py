# -*- coding: utf-8 -*-

from __future__ import annotations

import typing

import sqlite3
import os.path
from aqt.utils import showInfo
from .miutils import miInfo
from . import typer
import re
import json
addon_path = os.path.dirname(__file__)
from aqt import mw


_DictionaryHeader = tuple[typing.Literal["term"], typing.Literal["altterm"], typing.Literal["pronunication"]]
_INSTANCE: typing.Optional[DictDB] = None


class _DictionaryResultTuple(typing.NamedTuple):
    # See Also: typing.DictionaryResult
    term: str
    altterm: str
    pronunciation: str
    pos: int
    definition: str
    examples: list
    audio: str
    starCount: str


@typing.final
class DictDB:
    def __init__(self) -> None:
        super().__init__()

        db_file = os.path.join(mw.pm.addonFolder(), addon_path, "user_files", "db", "dictionaries.sqlite")
        self.conn: sqlite3.Connection = sqlite3.connect(db_file, check_same_thread=False)
        cursor = self.conn.cursor()

        if not cursor:
            raise RuntimeError(f'Database "{db_file}" has no cursor. Cannot connect!')

        self.c = cursor
        self.c.execute("PRAGMA foreign_keys = ON")
        self.c.execute("PRAGMA case_sensitive_like=ON;")

    def connect(self) -> None:
        self.oldConnection = self.c
        db_file = os.path.join(mw.pm.addonFolder(), addon_path, "user_files", "db", "dictionaries.sqlite")
        self.conn=sqlite3.connect(db_file)

        cursor = self.conn.cursor()

        if not cursor:
            raise RuntimeError(f'Database "{db_file}" has no cursor. Cannot connect!')

        self.c = cursor
        self.c.execute("PRAGMA foreign_keys = ON")
        self.c.execute("PRAGMA case_sensitive_like=ON;")

    def reload(self) -> None:
        self.c.close()
        self.c = self.oldConnection

    def closeConnection(self) -> None:
        self.c.close()

    def getLangId(self, lang: str) -> typing.Optional[int]:
        self.c.execute('SELECT id FROM langnames WHERE langname = ?;',  (lang,))

        # TODO: Remove try/except
        try:
            (lid,) = self.c.fetchone()
            # TODO: @ColinKennedy - I think ``lid`` is an int or str but don't know
            lid = typing.cast(int, lid)

            return lid
        except:
            return None

    def deleteDict(self, d: str) -> None:
        self.dropTables(d)
        d_clean = self.cleanDictName(d)
        self.c.execute('DELETE FROM dictnames WHERE dictname = ?;', (d_clean,))
        self.commitChanges()
        self.c.execute("VACUUM;")

    def addDict(self, dictname: str, lang: str, termHeader: str) -> None:
        lid = self.getLangId(lang)
        self.c.execute('INSERT INTO dictnames (dictname, lid, fields, addtype, termHeader, duplicateHeader) VALUES (?, ?, "[]", "add", ?, 0);', (dictname, lid, termHeader))
        self.createDB(self.formatDictName(lid, dictname))
        self.commitChanges()

    def formatDictName(self, lid: typing.Any, name: str) -> str:
        return 'l' + str(lid) + 'name' + name

    def deleteLanguage(self, langname: str) -> None:
        self.dropTables('l' + str(self.getLangId(langname)) + 'name%')
        self.c.execute('DELETE FROM langnames WHERE langname = ?;', (langname,))
        self.commitChanges()
        self.c.execute("VACUUM;")

    def addLanguages(self, list: typing.Iterable[str]) -> None:
        for l in list:
            self.c.execute('INSERT INTO langnames (langname) VALUES (?);', (l,))

        self.commitChanges()

    def getCurrentDbLangs(self) -> list[str]:
        self.c.execute("SELECT langname FROM langnames;")

        langs: list[str] = []

        # TODO: @ColinKennedy add a better try / except or remove it
        try:
            allLs = self.c.fetchall()
        except:
            return []

        for l in allLs:
            langs.append(l[0])

        return langs

    def getUserGroups(self, dicts: list[str]) -> list[typer.DictionaryLanguagePair]:
        currentDicts = self.getDictToTable()
        foundDicts: list[typer.DictionaryLanguagePair] = []

        for d in dicts:
            if d in currentDicts or d in ['Google Images', 'Forvo']:
                if d == 'Google Images':
                    foundDicts.append({'dict' : 'Google Images', 'lang' : ''})
                elif d == 'Forvo':
                    foundDicts.append({'dict' : 'Forvo', 'lang' : ''})
                else:
                    foundDicts.append(currentDicts[d])

        return foundDicts

    def getDictToTable(self) -> dict[str, typer.DictionaryLanguagePair]:
        self.c.execute("SELECT dictname, lid, langname FROM dictnames INNER JOIN langnames ON langnames.id = dictnames.lid;")
        dicts: dict[str, typer.DictionaryLanguagePair] = {}

        try:
            allDs = self.c.fetchall()
        except:
            return {}

        for d in allDs:
            dicts[d[0]] = {'dict' : self.formatDictName(d[1], d[0]), 'lang' : d[2]}

        return dicts

    def fetchDefs(self):
        self.c.execute("SELECT definition FROM l64name大辞林 LIMIT 10;")
        langs = []

        try:
            allLs = self.c.fetchall()
        except:
            return []

        for l in allLs:
            langs.append(l[0])

        return langs

    def getAllDicts(self) -> list[str]:
        self.c.execute("SELECT dictname, lid FROM dictnames;")
        dicts: list[str] = []

        try:
            allDs = self.c.fetchall()
        except:
            return []

        for d in allDs:
            dicts.append(self.formatDictName(d[1], d[0]))

        return dicts

    def getAllDictsWithLang(self) -> list[typer.DictionaryLanguagePair]:
        self.c.execute("SELECT dictname, lid, langname FROM dictnames INNER JOIN langnames ON langnames.id = dictnames.lid;")
        dicts: list[typer.DictionaryLanguagePair] = []

        try:
            allDs = self.c.fetchall()
        except:
            return []

        for d in allDs:
            dicts.append({'dict' : self.formatDictName(d[1], d[0]), 'lang' : d[2]})

        return dicts

    def getDefaultGroups(self) -> dict[str, typer.DictionaryLanguagePair]:
        langs = self.getCurrentDbLangs()
        dictsByLang: dict[str, typer.DictionaryLanguagePair] = {}

        for lang in langs:
            self.c.execute("SELECT dictname, lid FROM dictnames INNER JOIN langnames ON langnames.id = dictnames.lid WHERE langname = ?;", (lang,))
            allDs = self.c.fetchall()
            dictionaries: list[typer.DictionaryLanguagePair] = []

            for d in allDs:
                dictionaries.append({'dict' : self.formatDictName(d[1], d[0]), 'lang' : lang})

            if dictionaries:
                dictsByLang[lang] = dictionaries

        return dictsByLang

    def cleanDictName(self, name: str) -> str:
        return re.sub(r'l\d+name', '', name)

    def getDuplicateSetting(self, name: str) -> typing.Optional[tuple[int, str]]:
        self.c.execute('SELECT duplicateHeader, termHeader  FROM dictnames WHERE dictname=?', (name, ))
        try:
            (duplicateHeader,termHeader) = self.c.fetchone()
            return duplicateHeader, json.loads(termHeader)
        except:
            return None

    def getDefEx(self, sT: str) -> bool:
        return sT in ['Definition', 'Example']

    def applySearchType(self,terms: list[str], sT: typer.SearchTerm) -> None:
        for idx, _ in enumerate(terms):
            if sT in  {'Forward','Pronunciation'}:
               terms[idx] = terms[idx] + '%';
            elif sT ==  'Backward':
                terms[idx] = '%_' + terms[idx]
            elif sT ==  'Anywhere':
                terms[idx] = '%' + terms[idx] + '%'
            elif sT ==  'Exact':
                terms[idx] = terms[idx]
            elif sT ==  'Definition':
                terms[idx] = '%' + terms[idx] + '%'
            else:
                terms[idx] = '%「%' + terms[idx] + '%」%'
        return terms;

    def deconjugate(
        self,
        terms: list[str],
        conjugations: typing.Sequence[typer.Conjugation],
    ) -> list[str]:
        deconjugations: list[str] = []

        for term in terms:
            for c in conjugations:
                if term.endswith(c['inflected']):
                    for x in c['dict']:
                        deinflected = self.rreplace(term, c['inflected'], x, 1)
                        if 'prefix' in c:
                            prefix = c['prefix']
                            if deinflected.startswith(prefix):
                                deprefixedDeinflected =  deinflected[len(prefix):]
                                if deprefixedDeinflected not in deconjugations:
                                    deconjugations.append(deprefixedDeinflected)
                        if deinflected not in deconjugations:
                            deconjugations.append(deinflected)
        deconjugations = list(filter(lambda x: len(x) > 1, deconjugations))
        deconjugations = list(set(deconjugations))
        return terms + deconjugations

    def rreplace(self, s: str, old: str, new: str, occurrence: int) -> str:
        li = s.rsplit(old, occurrence)
        return new.join(li)

    def searchTerm(
        self,
        term: str,
        selectedGroup,
        conjugations: typing.Sequence[typer.Conjugation],
        sT: typer.SearchTerm,
        deinflect: bool,
        dictLimit: str,
        maxDefs: int,
    ) -> dict[str, list[typer.DictionaryResult]]:
        alreadyConjTyped: dict[str, list[str]] = {}
        results: dict[str, list[typer.DictionaryResult]] = {}
        group = selectedGroup['dictionaries']
        totalDefs = 0
        defEx = self.getDefEx(sT)
        op = 'LIKE'
        if defEx:
            column = 'definition'
        elif sT == 'Pronunciation':
            column = 'pronunciation'
        else:
            column = 'term'
        if sT == 'Exact':
            op = '='
        terms = [term]
        terms.append(term.lower())
        terms.append(term.capitalize())
        terms = list(set(terms))
        for dic in group:
            if dic['dict'] == 'Google Images':
                results['Google Images'] = True
                continue
            elif dic['dict'] == 'Forvo':
                results['Forvo'] = True
                continue

            if deinflect:
                if dic['lang'] in alreadyConjTyped:
                    terms = alreadyConjTyped[dic['lang']]
                elif dic['lang'] in conjugations:
                    terms = self.deconjugate(terms, conjugations[dic['lang']])
                    self.applySearchType(terms, sT)
                    alreadyConjTyped[dic['lang']] = terms
                else:
                    self.applySearchType(terms, sT)
                    alreadyConjTyped[dic['lang']] = terms
            else:
                if term in alreadyConjTyped:
                    terms = alreadyConjTyped[term]
                else:
                    self.applySearchType(terms, sT)
                    alreadyConjTyped[term] = terms

            toQuery = self.getQueryCriteria(column, terms, op)
            termTuple = tuple(terms)
            allRs = self.executeSearch(dic['dict'], toQuery, dictLimit, termTuple)
            dictRes: list[typer.DictionaryResult] = []

            if len(allRs) > 0:
                for r in allRs:
                    totalDefs += 1
                    dictRes.append(self.resultToDict(r))
                    if totalDefs >= maxDefs:
                        results[self.cleanDictName(dic['dict'])] = dictRes
                        return results
                results[self.cleanDictName(dic['dict'])] = dictRes
            elif not defEx and not sT == 'Pronunciation':
                columns = ['altterm', 'pronunciation']
                for col in columns:
                    toQuery = self.getQueryCriteria(col, terms, op)
                    termTuple = tuple(terms)
                    allRs = self.executeSearch(dic['dict'], toQuery, dictLimit, termTuple)
                    if len(allRs) > 0:
                        for r in allRs:
                            totalDefs += 1
                            dictRes.append(self.resultToDict(r))
                            if totalDefs >= maxDefs:
                                results[self.cleanDictName(dic['dict'])] = dictRes
                                return results
                        results[self.cleanDictName(dic['dict'])] = dictRes
                        break
        return results

    def resultToDict(self, r: _DictionaryResultTuple) -> typer.DictionaryResult:
        return {
            'term' : r[0],
            'altterm' : r[1],
            'pronunciation' : r[2],
            'pos' : r[3],
            'definition' : r[4],
            'examples' : r[5],
            'audio' : r[6],
            'starCount' : r[7],
        }

    def executeSearch(
        self,
        dictName: str,
        toQuery: str,
        dictLimit: str,
        termTuple: tuple[str, ...],
    ) -> list[_DictionaryResultTuple]:
        try:
            self.c.execute(
                "SELECT term, altterm, pronunciation, pos, definition, examples, audio, starCount FROM " + dictName +" WHERE " + toQuery + " ORDER BY LENGTH(term) ASC, frequency ASC LIMIT "+dictLimit +" ;",
                termTuple,
            )
            return self.c.fetchall()
        except:
            return []

    def getQueryCriteria(self, col: str, terms: typing.Sequence[str], op: str = 'LIKE') -> str:

        toQuery = ''
        for idx, _ in enumerate(terms):
            if idx == 0:
                toQuery += ' ' + col + ' '+ op +' ? '
            else:
                toQuery += ' OR ' + col + ' '+ op +' ? '
        return toQuery

    def getDefForMassExp(
        self,
        term: str,
        dN: str,
        limit: str,
        rN: str,
    ) -> tuple[list[typer.DictionaryResult], int, str]:
        result = self.getDuplicateSetting(rN)

        if not result:
            raise RuntimeError(f'Cannot get duplicate settings from "{rN}" rN.')

        duplicateHeader, termHeader = result
        results: list[typer.DictionaryResult] = []
        columns = ['term','altterm', 'pronunciation']

        for col in columns:
            terms = [term]
            toQuery =  ' ' + col + ' = ? '
            termTuple = tuple(terms)
            allRs = self.executeSearch(dN, toQuery, limit, termTuple)

            if len(allRs) > 0:
                for r in allRs:
                    results.append(self.resultToDict(r))

                break

        return results,  duplicateHeader, termHeader;

    def cleanLT(self, text: str) -> str:
        return re.sub(r'<((?:[^b][^r])|(?:[b][^r]))', r'&lt;\1', str(text))

    def createDB(self, text: str) -> None:
        self.c.execute('CREATE TABLE  IF NOT EXISTS  ' + text +'(term CHAR(40) NOT NULL, altterm CHAR(40), pronunciation CHAR(100), pos CHAR(40), definition TEXT, examples TEXT, audio TEXT, frequency MEDIUMINT, starCount TEXT);')
        self.c.execute("CREATE INDEX IF NOT EXISTS it" + text +" ON " + text +" (term);")
        self.c.execute("CREATE INDEX IF NOT EXISTS itp" + text +" ON " + text +" ( term, pronunciation );")
        self.c.execute("CREATE INDEX IF NOT EXISTS ia" + text +" ON " + text +" (altterm);")
        self.c.execute("CREATE INDEX IF NOT EXISTS iap" + text +" ON " + text +" ( altterm, pronunciation );")
        self.c.execute("CREATE INDEX IF NOT EXISTS ia" + text +" ON " + text +" (pronunciation);")

    def importToDict(self, dictName: str, dictionaryData: typing.Iterable[list[str]]) -> None:
        self.c.executemany('INSERT INTO ' + dictName + ' (term, altterm, pronunciation, pos, definition, examples, audio, frequency, starCount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);', dictionaryData)

    def dropTables(self, text: str) -> None:
        self.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?;" , (text, ))
        dicts = self.c.fetchall()
        for name in dicts:
            self.c.execute("DROP TABLE " + name[0] + " ;")

    def setFieldsSetting(self, name: str, fields: str) -> None:
        self.c.execute('UPDATE dictnames SET fields = ? WHERE dictname=?', (fields, name))
        self.commitChanges()

    def setAddType(self, name: str, addType: str) -> None:
        self.c.execute('UPDATE dictnames SET addtype = ? WHERE dictname=?', (addType, name))
        self.commitChanges()

    def getFieldsSetting(self, name: str) -> typing.Optional[list[str]]:
        self.c.execute('SELECT fields FROM dictnames WHERE dictname=?', (name, ))

        # TODO: Remove try/except
        try:
            (fields,) = self.c.fetchone()
        except:
            return None

        return typing.cast(list[str], json.loads(fields))

    def getAddTypeAndFields(self, dictName: str) -> typing.Optional[tuple[list[str], str]]:
        self.c.execute('SELECT fields, addtype FROM dictnames WHERE dictname=?', (dictName, ))

        # TODO: Remove try/except
        try:
            (fields, addType) = self.c.fetchone()

            return json.loads(fields), addType;
        except:
            return None

    def getDupHeaders(self) -> typing.Optional[dict[str, int]]:
        # TODO: @ColinKennedy - the dict value might be int or bool. Not sure.
        self.c.execute('SELECT dictname, duplicateHeader FROM dictnames')
        # TODO: Remove try/except
        try:
            dictHeaders = self.c.fetchall()
            results: dict[str, int] = {}
            if len(dictHeaders) > 0:
                for r in dictHeaders:
                    results[r[0]] = r[1]
                return results
        except:
            return None

        return None

    def setDupHeader(self, duplicateHeader: str, name: str) -> None:
        self.c.execute('UPDATE dictnames SET duplicateHeader = ? WHERE dictname=?', (duplicateHeader, name))
        self.commitChanges()

    def getTermHeaders(self) -> typing.Optional[dict[str, _DictionaryHeader]]:
        self.c.execute('SELECT dictname, termHeader FROM dictnames')
        # TODO: Remove try/except
        try:
            dictHeaders = self.c.fetchall()
            # TODO: Make a more direct type for this type
            results: dict[str, _DictionaryHeader] = {}
            if len(dictHeaders) > 0:
                for r in dictHeaders:
                    results[r[0]] = typing.cast(_DictionaryHeader, tuple(*json.loads(r[1])))
                return results
        except:
            return None

        return None

    def getAddType(self, name: str) -> typing.Optional[typer.AddType]:
        self.c.execute('SELECT addtype FROM dictnames WHERE dictname=?', (name, ))
        # TODO: Remove try/except
        try:
            (addType,) = self.c.fetchone()

            return typing.cast(typer.AddType, addType)
        except:
            return None

    def getDictTermHeader(self, dictname: str) -> str:
        self.c.execute('SELECT termHeader FROM dictnames WHERE dictname=?', (dictname, ))

        return typing.cast(str, self.c.fetchone()[0])

    def setDictTermHeader(self, dictname: str, termheader: str) -> None:
        self.c.execute('UPDATE dictnames SET termHeader = ? WHERE dictname=?', (termheader, dictname))
        self.commitChanges()

    def commitChanges(self) -> None:
        self.conn.commit()


def get() -> DictDB:
    if _INSTANCE:
        return _INSTANCE

    raise RuntimeError("No database has been initialized yet.")


def clear() -> None:
    global _INSTANCE

    _INSTANCE = None


def initialize(database: DictDB) -> None:
    global _INSTANCE

    _INSTANCE = database
