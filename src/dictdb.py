# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
import os.path
import re
import sqlite3
import typing
from collections import abc

from . import typer

addon_path = os.path.dirname(__file__)
from aqt import mw

_DictionaryHeader = tuple[str, ...]
_INSTANCE: typing.Optional[DictDB] = None
DictSearchResults = dict[str, list[typer.DictionaryResult]]
_LOGGER = logging.getLogger(__name__)


class _DictionaryResultTuple(typing.NamedTuple):
    # See Also: typing.DictionaryResult
    term: str
    altterm: str
    pronunciation: str
    pos: int
    definition: str
    examples: str
    audio: str
    starCount: str


@typing.final
class DictDB:
    def __init__(self) -> None:
        super().__init__()

        db_file = os.path.join(
            mw.pm.addonFolder(), addon_path, "user_files", "db", "dictionaries.sqlite"
        )
        self._conn: sqlite3.Connection = sqlite3.connect(
            db_file, check_same_thread=False
        )
        cursor = self._conn.cursor()

        if not cursor:
            raise RuntimeError(f'Database "{db_file}" has no cursor. Cannot connect!')

        self._c = cursor
        self._c.execute("PRAGMA foreign_keys = ON")
        self._c.execute("PRAGMA case_sensitive_like=ON;")

    def _getDuplicateSetting(self, name: str) -> typing.Optional[tuple[int, str]]:
        self._c.execute(
            "SELECT duplicateHeader, termHeader  FROM dictnames WHERE dictname=?",
            (name,),
        )
        try:
            (duplicateHeader, termHeader) = self._c.fetchone()
            return duplicateHeader, json.loads(termHeader)
        except:
            return None

    def _getDefEx(self, sT: str) -> bool:
        return sT in ["Definition", "Example"]

    def _getDictToTable(self) -> dict[str, typer.DictionaryLanguagePair]:
        self._c.execute(
            "SELECT dictname, lid, langname FROM dictnames INNER JOIN langnames ON langnames.id = dictnames.lid;"
        )
        dicts: dict[str, typer.DictionaryLanguagePair] = {}

        try:
            allDs = self._c.fetchall()
        except:
            return {}

        for d in allDs:
            dicts[d[0]] = {"dict": self._formatDictName(d[1], d[0]), "lang": d[2]}

        return dicts

    def _getQueryCriteria(
        self, col: str, terms: typing.Sequence[str], op: str = "LIKE"
    ) -> str:

        toQuery = ""
        for idx, _ in enumerate(terms):
            if idx == 0:
                toQuery += " " + col + " " + op + " ? "
            else:
                toQuery += " OR " + col + " " + op + " ? "
        return toQuery

    def _applySearchType(self, terms: list[str], sT: typer.SearchTerm) -> None:
        for idx, _ in enumerate(terms):
            if sT in {"Forward", "Pronunciation"}:
                terms[idx] = terms[idx] + "%"
            elif sT == "Backward":
                terms[idx] = "%_" + terms[idx]
            elif sT == "Anywhere":
                terms[idx] = "%" + terms[idx] + "%"
            elif sT == "Exact":
                terms[idx] = terms[idx]
            elif sT == "Definition":
                terms[idx] = "%" + terms[idx] + "%"
            else:
                terms[idx] = "%「%" + terms[idx] + "%」%"

    def _createDB(self, text: str) -> None:
        self._c.execute(
            "CREATE TABLE  IF NOT EXISTS  "
            + text
            + "(term CHAR(40) NOT NULL, altterm CHAR(40), pronunciation CHAR(100), pos CHAR(40), definition TEXT, examples TEXT, audio TEXT, frequency MEDIUMINT, starCount TEXT);"
        )
        self._c.execute(
            "CREATE INDEX IF NOT EXISTS it" + text + " ON " + text + " (term);"
        )
        self._c.execute(
            "CREATE INDEX IF NOT EXISTS itp"
            + text
            + " ON "
            + text
            + " ( term, pronunciation );"
        )
        self._c.execute(
            "CREATE INDEX IF NOT EXISTS ia" + text + " ON " + text + " (altterm);"
        )
        self._c.execute(
            "CREATE INDEX IF NOT EXISTS iap"
            + text
            + " ON "
            + text
            + " ( altterm, pronunciation );"
        )
        self._c.execute(
            "CREATE INDEX IF NOT EXISTS ia" + text + " ON " + text + " (pronunciation);"
        )

    def _deconjugate(
        self,
        terms: list[str],
        conjugations: typing.Sequence[typer.Conjugation],
    ) -> list[str]:
        deconjugations: list[str] = []

        for term in terms:
            for c in conjugations:
                if term.endswith(c["inflected"]):
                    for x in c["dict"]:
                        deinflected = self._rreplace(term, c["inflected"], x, 1)
                        if "prefix" in c:
                            prefix = c["prefix"]
                            if deinflected.startswith(prefix):
                                deprefixedDeinflected = deinflected[len(prefix) :]
                                if deprefixedDeinflected not in deconjugations:
                                    deconjugations.append(deprefixedDeinflected)
                        if deinflected not in deconjugations:
                            deconjugations.append(deinflected)
        deconjugations = list(filter(lambda x: len(x) > 1, deconjugations))
        deconjugations = list(set(deconjugations))
        return terms + deconjugations

    def _dropTables(self, text: str) -> None:
        self._c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?;",
            (text,),
        )
        dicts = self._c.fetchall()
        for name in dicts:
            self._c.execute("DROP TABLE " + name[0] + " ;")

    def _executeSearch(
        self,
        dictName: str,
        toQuery: str,
        dictLimit: str,
        termTuple: tuple[str, ...],
    ) -> list[_DictionaryResultTuple]:
        try:
            self._c.execute(
                "SELECT term, altterm, pronunciation, pos, definition, examples, audio, starCount FROM "
                + dictName
                + " WHERE "
                + toQuery
                + " ORDER BY LENGTH(term) ASC, frequency ASC LIMIT "
                + dictLimit
                + " ;",
                termTuple,
            )
            return self._c.fetchall()
        except:
            return []

    def _formatDictName(self, lid: typing.Any, name: str) -> str:
        return "l" + str(lid) + "name" + name

    def _rreplace(self, s: str, old: str, new: str, occurrence: int) -> str:
        li = s.rsplit(old, occurrence)
        return new.join(li)

    def _resultToDict(self, r: _DictionaryResultTuple) -> typer.DictionaryResult:
        return {
            "term": r[0],
            "altterm": r[1],
            "pronunciation": r[2],
            "pos": r[3],
            "definition": r[4],
            "examples": r[5],
            "audio": r[6],
            "starCount": r[7],
        }

    def closeConnection(self) -> None:
        self._c.close()

    def getLangId(self, lang: str) -> typing.Optional[int]:
        self._c.execute("SELECT id FROM langnames WHERE langname = ?;", (lang,))

        # TODO: Remove try/except
        try:
            # TODO: @ColinKennedy - I think ``lid`` is an int or str but don't know
            lid: int
            (lid,) = self._c.fetchone()

            return lid
        except:
            return None

    def deleteDict(self, d: str) -> None:
        self._dropTables(d)
        d_clean = self.cleanDictName(d)
        self._c.execute("DELETE FROM dictnames WHERE dictname = ?;", (d_clean,))
        self.commitChanges()
        self._c.execute("VACUUM;")

    def addDict(self, dictname: str, lang: str, termHeader: str) -> None:
        lid = self.getLangId(lang)
        self._c.execute(
            'INSERT INTO dictnames (dictname, lid, fields, addtype, termHeader, duplicateHeader) VALUES (?, ?, "[]", "add", ?, 0);',
            (dictname, lid, termHeader),
        )
        self._createDB(self._formatDictName(lid, dictname))
        self.commitChanges()

    def deleteLanguage(self, langname: str) -> None:
        self._dropTables("l" + str(self.getLangId(langname)) + "name%")
        self._c.execute("DELETE FROM langnames WHERE langname = ?;", (langname,))
        self.commitChanges()
        self._c.execute("VACUUM;")

    def addLanguages(self, list: typing.Iterable[str]) -> None:
        for l in list:
            self._c.execute("INSERT INTO langnames (langname) VALUES (?);", (l,))

        self.commitChanges()

    def getCurrentDbLangs(self) -> list[str]:
        self._c.execute("SELECT langname FROM langnames;")

        langs: list[str] = []

        # TODO: @ColinKennedy add a better try / except or remove it
        try:
            allLs = self._c.fetchall()
        except:
            return []

        for l in allLs:
            langs.append(l[0])

        return langs

    def getUserGroups(self, dicts: list[str]) -> list[typer.DictionaryLanguagePair]:
        currentDicts = self._getDictToTable()
        foundDicts: list[typer.DictionaryLanguagePair] = []

        for d in dicts:
            if d in currentDicts or d in ["Google Images", "Forvo"]:
                if d == "Google Images":
                    foundDicts.append({"dict": "Google Images", "lang": ""})
                elif d == "Forvo":
                    foundDicts.append({"dict": "Forvo", "lang": ""})
                else:
                    foundDicts.append(currentDicts[d])

        return foundDicts

    def getAllDicts(self) -> list[str]:
        self._c.execute("SELECT dictname, lid FROM dictnames;")
        dicts: list[str] = []

        try:
            allDs = self._c.fetchall()
        except:
            return []

        for d in allDs:
            dicts.append(self._formatDictName(d[1], d[0]))

        return dicts

    def getAllDictsWithLang(self) -> list[typer.DictionaryLanguagePair]:
        self._c.execute(
            "SELECT dictname, lid, langname FROM dictnames INNER JOIN langnames ON langnames.id = dictnames.lid;"
        )
        dicts: list[typer.DictionaryLanguagePair] = []

        try:
            allDs = self._c.fetchall()
        except:
            return []

        for d in allDs:
            dicts.append({"dict": self._formatDictName(d[1], d[0]), "lang": d[2]})

        return dicts

    def getDefaultGroups(self) -> dict[str, list[typer.DictionaryLanguagePair]]:
        langs = self.getCurrentDbLangs()
        dictsByLang: dict[str, list[typer.DictionaryLanguagePair]] = {}

        for lang in langs:
            self._c.execute(
                "SELECT dictname, lid FROM dictnames INNER JOIN langnames ON langnames.id = dictnames.lid WHERE langname = ?;",
                (lang,),
            )
            allDs = self._c.fetchall()
            dictionaries: list[typer.DictionaryLanguagePair] = []

            for d in allDs:
                dictionaries.append(
                    {"dict": self._formatDictName(d[1], d[0]), "lang": lang}
                )

            if dictionaries:
                dictsByLang[lang] = dictionaries

        return dictsByLang

    def cleanDictName(self, name: str) -> str:
        return re.sub(r"l\d+name", "", name)

    def searchTerm(
        self,
        term: str,
        selectedGroup: typer.DictionaryGroup2,
        conjugations: dict[str, list[typer.Conjugation]],
        sT: typer.SearchTerm,
        deinflect: bool,
        dictLimit: str,
        maxDefs: int,
    ) -> tuple[DictSearchResults, set[str]]:
        alreadyConjTyped: dict[str, list[str]] = {}
        results: dict[str, list[typer.DictionaryResult]] = {}
        group = selectedGroup["dictionaries"]
        totalDefs = 0
        defEx = self._getDefEx(sT)
        op = "LIKE"
        if defEx:
            column = "definition"
        elif sT == "Pronunciation":
            column = "pronunciation"
        else:
            column = "term"
        if sT == "Exact":
            op = "="
        terms = [term]
        terms.append(term.lower())
        terms.append(term.capitalize())
        terms = list(set(terms))
        known_dictionaries: set[str] = set()

        for dic in group:
            if dic["dict"] == "Google Images":
                known_dictionaries.add("Google Images")
                continue
            elif dic["dict"] == "Forvo":
                known_dictionaries.add("Forvo")
                continue

            if deinflect:
                if dic["lang"] in alreadyConjTyped:
                    terms = alreadyConjTyped[dic["lang"]]
                elif dic["lang"] in conjugations:
                    terms = self._deconjugate(terms, conjugations[dic["lang"]])
                    self._applySearchType(terms, sT)
                    alreadyConjTyped[dic["lang"]] = terms
                else:
                    self._applySearchType(terms, sT)
                    alreadyConjTyped[dic["lang"]] = terms
            else:
                if term in alreadyConjTyped:
                    terms = alreadyConjTyped[term]
                else:
                    self._applySearchType(terms, sT)
                    alreadyConjTyped[term] = terms

            toQuery = self._getQueryCriteria(column, terms, op)
            termTuple = tuple(terms)
            allRs = self._executeSearch(dic["dict"], toQuery, dictLimit, termTuple)
            dictRes: list[typer.DictionaryResult] = []

            if len(allRs) > 0:
                for r in allRs:
                    totalDefs += 1
                    dictRes.append(self._resultToDict(r))
                    if totalDefs >= maxDefs:
                        results[self.cleanDictName(dic["dict"])] = dictRes
                        return results, known_dictionaries
                results[self.cleanDictName(dic["dict"])] = dictRes
            elif not defEx and not sT == "Pronunciation":
                columns = ["altterm", "pronunciation"]
                for col in columns:
                    toQuery = self._getQueryCriteria(col, terms, op)
                    termTuple = tuple(terms)
                    allRs = self._executeSearch(
                        dic["dict"], toQuery, dictLimit, termTuple
                    )
                    if len(allRs) > 0:
                        for r in allRs:
                            totalDefs += 1
                            dictRes.append(self._resultToDict(r))
                            if totalDefs >= maxDefs:
                                results[self.cleanDictName(dic["dict"])] = dictRes
                                return results, known_dictionaries
                        results[self.cleanDictName(dic["dict"])] = dictRes
                        break
        return results, known_dictionaries

    def getDefForMassExp(
        self,
        term: str,
        dN: str,
        limit: str,
        rN: str,
    ) -> tuple[list[typer.DictionaryResult], int, str]:
        result = self._getDuplicateSetting(rN)

        if not result:
            raise RuntimeError(f'Cannot get duplicate settings from "{rN}" rN.')

        duplicateHeader, termHeader = result
        results: list[typer.DictionaryResult] = []
        columns = ["term", "altterm", "pronunciation"]

        for col in columns:
            terms = [term]
            toQuery = " " + col + " = ? "
            termTuple = tuple(terms)
            allRs = self._executeSearch(dN, toQuery, limit, termTuple)

            if len(allRs) > 0:
                for r in allRs:
                    results.append(self._resultToDict(r))

                break

        return results, duplicateHeader, termHeader

    def importToDict(
        self, dictName: str, dictionaryData: typing.Iterable[list[str]]
    ) -> None:
        self._c.executemany(
            "INSERT INTO "
            + dictName
            + " (term, altterm, pronunciation, pos, definition, examples, audio, frequency, starCount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            dictionaryData,
        )

    def setFieldsSetting(self, name: str, fields: str) -> None:
        self._c.execute(
            "UPDATE dictnames SET fields = ? WHERE dictname=?", (fields, name)
        )
        self.commitChanges()

    def setAddType(self, name: str, addType: str) -> None:
        self._c.execute(
            "UPDATE dictnames SET addtype = ? WHERE dictname=?", (addType, name)
        )
        self.commitChanges()

    def getFieldsSetting(self, name: str) -> typing.Optional[list[str]]:
        self._c.execute("SELECT fields FROM dictnames WHERE dictname=?", (name,))

        # TODO: Remove try/except
        try:
            (fields,) = self._c.fetchone()
        except:
            return None

        return typing.cast(list[str], json.loads(fields))

    def getAddTypeAndFields(
        self, dictName: str
    ) -> typing.Optional[tuple[list[str], str]]:
        self._c.execute(
            "SELECT fields, addtype FROM dictnames WHERE dictname=?", (dictName,)
        )

        # TODO: Remove try/except
        try:
            (fields, addType) = self._c.fetchone()

            return json.loads(fields), addType
        except:
            return None

    def getDupHeaders(self) -> typing.Optional[dict[str, int]]:
        # TODO: @ColinKennedy - the dict value might be int or bool. Not sure.
        self._c.execute("SELECT dictname, duplicateHeader FROM dictnames")
        # TODO: Remove try/except
        try:
            dictHeaders = self._c.fetchall()
            results: dict[str, int] = {}
            if len(dictHeaders) > 0:
                for r in dictHeaders:
                    results[r[0]] = r[1]
                return results
        except:
            return None

        return None

    def setDupHeader(self, duplicateHeader: str, name: str) -> None:
        self._c.execute(
            "UPDATE dictnames SET duplicateHeader = ? WHERE dictname=?",
            (duplicateHeader, name),
        )
        self.commitChanges()

    def getTermHeaders(self) -> typing.Optional[dict[str, _DictionaryHeader]]:
        self._c.execute("SELECT dictname, termHeader FROM dictnames")
        # TODO: Remove try/except
        try:
            dictHeaders = typing.cast(list[tuple[str, str]], self._c.fetchall())
            results: dict[str, _DictionaryHeader] = {}

            for entry in dictHeaders:
                dictionary_name = entry[0]
                headers = entry[1]
                results[dictionary_name] = typing.cast(
                    _DictionaryHeader,
                    tuple(json.loads(headers)),
                )

            return results
        except:
            _LOGGER.exception("Unable to get term headers.")

            return None

    def getAddType(self, name: str) -> typing.Optional[typer.AddType]:
        self._c.execute("SELECT addtype FROM dictnames WHERE dictname=?", (name,))
        # TODO: Remove try/except
        try:
            (addType,) = self._c.fetchone()

            return typing.cast(typer.AddType, addType)
        except:
            return None

    def getDictTermHeader(self, dictname: str) -> str:
        self._c.execute(
            "SELECT termHeader FROM dictnames WHERE dictname=?", (dictname,)
        )

        return typing.cast(str, self._c.fetchone()[0])

    def setDictTermHeader(self, dictname: str, termheader: str) -> None:
        self._c.execute(
            "UPDATE dictnames SET termHeader = ? WHERE dictname=?",
            (termheader, dictname),
        )
        self.commitChanges()

    def commitChanges(self) -> None:
        self._conn.commit()


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
