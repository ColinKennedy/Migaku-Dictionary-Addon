# -*- coding: utf-8 -*-
#

import argparse
import json
import os
import re
import time
import typing
import urllib

import bs4
import requests
from aqt import qt

_COUNTRY_CODES = {
    "Afghanistan": "countryAF",
    "Albania": "countryAL",
    "Algeria": "countryDZ",
    "American Samoa": "countryAS",
    "Andorra": "countryAD",
    "Angola": "countryAO",
    "Anguilla": "countryAI",
    "Antarctica": "countryAQ",
    "Antigua and Barbuda": "countryAG",
    "Argentina": "countryAR",
    "Armenia": "countryAM",
    "Aruba": "countryAW",
    "Australia": "countryAU",
    "Austria": "countryAT",
    "Azerbaijan": "countryAZ",
    "Bahamas": "countryBS",
    "Bahrain": "countryBH",
    "Bangladesh": "countryBD",
    "Barbados": "countryBB",
    "Belarus": "countryBY",
    "Belgium": "countryBE",
    "Belize": "countryBZ",
    "Benin": "countryBJ",
    "Bermuda": "countryBM",
    "Bhutan": "countryBT",
    "Bolivia": "countryBO",
    "Bosnia and Herzegovina": "countryBA",
    "Botswana": "countryBW",
    "Bouvet Island": "countryBV",
    "Brazil": "countryBR",
    "British Indian Ocean Territory": "countryIO",
    "Brunei Darussalam": "countryBN",
    "Bulgaria": "countryBG",
    "Burkina Faso": "countryBF",
    "Burundi": "countryBI",
    "Cambodia": "countryKH",
    "Cameroon": "countryCM",
    "Canada": "countryCA",
    "Cape Verde": "countryCV",
    "Cayman Islands": "countryKY",
    "Central African Republic": "countryCF",
    "Chad": "countryTD",
    "Chile": "countryCL",
    "China": "countryCN",
    "Christmas Island": "countryCX",
    "Cocos (Keeling) Islands": "countryCC",
    "Colombia": "countryCO",
    "Comoros": "countryKM",
    "Congo": "countryCG",
    "Congo, the Democratic Republic of the": "countryCD",
    "Cook Islands": "countryCK",
    "Costa Rica": "countryCR",
    "Cote D'ivoire": "countryCI",
    "Croatia (Hrvatska)": "countryHR",
    "Cuba": "countryCU",
    "Cyprus": "countryCY",
    "Czech Republic": "countryCZ",
    "Denmark": "countryDK",
    "Djibouti": "countryDJ",
    "Dominica": "countryDM",
    "Dominican Republic": "countryDO",
    "East Timor": "countryTP",
    "Ecuador": "countryEC",
    "Egypt": "countryEG",
    "El Salvador": "countrySV",
    "Equatorial Guinea": "countryGQ",
    "Eritrea": "countryER",
    "Estonia": "countryEE",
    "Ethiopia": "countryET",
    "European Union": "countryEU",
    "Falkland Islands (Malvinas)": "countryFK",
    "Faroe Islands": "countryFO",
    "Fiji": "countryFJ",
    "Finland": "countryFI",
    "France": "countryFR",
    "France, Metropolitan": "countryFX",
    "French Guiana": "countryGF",
    "French Polynesia": "countryPF",
    "French Southern Territories": "countryTF",
    "Gabon": "countryGA",
    "Gambia": "countryGM",
    "Georgia": "countryGE",
    "Germany": "countryDE",
    "Ghana": "countryGH",
    "Gibraltar": "countryGI",
    "Greece": "countryGR",
    "Greenland": "countryGL",
    "Grenada": "countryGD",
    "Guadeloupe": "countryGP",
    "Guam": "countryGU",
    "Guatemala": "countryGT",
    "Guinea": "countryGN",
    "Guinea-Bissau": "countryGW",
    "Guyana": "countryGY",
    "Haiti": "countryHT",
    "Heard Island and Mcdonald Islands": "countryHM",
    "Holy See (Vatican City State)": "countryVA",
    "Honduras": "countryHN",
    "Hong Kong": "countryHK",
    "Hungary": "countryHU",
    "Iceland": "countryIS",
    "India": "countryIN",
    "Indonesia": "countryID",
    "Iran, Islamic Republic of": "countryIR",
    "Iraq": "countryIQ",
    "Ireland": "countryIE",
    "Israel": "countryIL",
    "Italy": "countryIT",
    "Jamaica": "countryJM",
    "Japan": "countryJP",
    "Jordan": "countryJO",
    "Kazakhstan": "countryKZ",
    "Kenya": "countryKE",
    "Kiribati": "countryKI",
    "Korea, Democratic People's Republic of": "countryKP",
    "Korea, Republic of": "countryKR",
    "Kuwait": "countryKW",
    "Kyrgyzstan": "countryKG",
    "Lao People's Democratic Republic": "countryLA",
    "Latvia": "countryLV",
    "Lebanon": "countryLB",
    "Lesotho": "countryLS",
    "Liberia": "countryLR",
    "Libyan Arab Jamahiriya": "countryLY",
    "Liechtenstein": "countryLI",
    "Lithuania": "countryLT",
    "Luxembourg": "countryLU",
    "Macao": "countryMO",
    "Macedonia, the Former Yugosalv Republic of": "countryMK",
    "Madagascar": "countryMG",
    "Malawi": "countryMW",
    "Malaysia": "countryMY",
    "Maldives": "countryMV",
    "Mali": "countryML",
    "Malta": "countryMT",
    "Marshall Islands": "countryMH",
    "Martinique": "countryMQ",
    "Mauritania": "countryMR",
    "Mauritius": "countryMU",
    "Mayotte": "countryYT",
    "Mexico": "countryMX",
    "Micronesia, Federated States of": "countryFM",
    "Moldova, Republic of": "countryMD",
    "Monaco": "countryMC",
    "Mongolia": "countryMN",
    "Montserrat": "countryMS",
    "Morocco": "countryMA",
    "Mozambique": "countryMZ",
    "Myanmar": "countryMM",
    "Namibia": "countryNA",
    "Nauru": "countryNR",
    "Nepal": "countryNP",
    "Netherlands": "countryNL",
    "Netherlands Antilles": "countryAN",
    "New Caledonia": "countryNC",
    "New Zealand": "countryNZ",
    "Nicaragua": "countryNI",
    "Niger": "countryNE",
    "Nigeria": "countryNG",
    "Niue": "countryNU",
    "Norfolk Island": "countryNF",
    "Northern Mariana Islands": "countryMP",
    "Norway": "countryNO",
    "Oman": "countryOM",
    "Pakistan": "countryPK",
    "Palau": "countryPW",
    "Palestinian Territory": "countryPS",
    "Panama": "countryPA",
    "Papua New Guinea": "countryPG",
    "Paraguay": "countryPY",
    "Peru": "countryPE",
    "Philippines": "countryPH",
    "Pitcairn": "countryPN",
    "Poland": "countryPL",
    "Portugal": "countryPT",
    "Puerto Rico": "countryPR",
    "Qatar": "countryQA",
    "Reunion": "countryRE",
    "Romania": "countryRO",
    "Russian Federation": "countryRU",
    "Rwanda": "countryRW",
    "Saint Helena": "countrySH",
    "Saint Kitts and Nevis": "countryKN",
    "Saint Lucia": "countryLC",
    "Saint Pierre and Miquelon": "countryPM",
    "Saint Vincent and the Grenadines": "countryVC",
    "Samoa": "countryWS",
    "San Marino": "countrySM",
    "Sao Tome and Principe": "countryST",
    "Saudi Arabia": "countrySA",
    "Senegal": "countrySN",
    "Serbia and Montenegro": "countryCS",
    "Seychelles": "countrySC",
    "Sierra Leone": "countrySL",
    "Singapore": "countrySG",
    "Slovakia": "countrySK",
    "Slovenia": "countrySI",
    "Solomon Islands": "countrySB",
    "Somalia": "countrySO",
    "South Africa": "countryZA",
    "South Georgia and the South Sandwich Islands": "countryGS",
    "Spain": "countryES",
    "Sri Lanka": "countryLK",
    "Sudan": "countrySD",
    "Suriname": "countrySR",
    "Svalbard and Jan Mayen": "countrySJ",
    "Swaziland": "countrySZ",
    "Sweden": "countrySE",
    "Switzerland": "countryCH",
    "Syrian Arab Republic": "countrySY",
    "Taiwan": "countryTW",
    "Tajikistan": "countryTJ",
    "Tanzania, United Republic of": "countryTZ",
    "Thailand": "countryTH",
    "Togo": "countryTG",
    "Tokelau": "countryTK",
    "Tonga": "countryTO",
    "Trinidad and Tobago": "countryTT",
    "Tunisia": "countryTN",
    "Turkey": "countryTR",
    "Turkmenistan": "countryTM",
    "Turks and Caicos Islands": "countryTC",
    "Tuvalu": "countryTV",
    "Uganda": "countryUG",
    "Ukraine": "countryUA",
    "United Arab Emirates": "countryAE",
    "United Kingdom": "countryUK",
    "United States": "countryUS",
    "United States Minor Outlying Islands": "countryUM",
    "Uruguay": "countryUY",
    "Uzbekistan": "countryUZ",
    "Vanuatu": "countryVU",
    "Venezuela": "countryVE",
    "Vietnam": "countryVN",
    "Virgin Islands, British": "countryVG",
    "Virgin Islands, U.S.": "countryVI",
    "Wallis and Futuna": "countryWF",
    "Western Sahara": "countryEH",
    "Yemen": "countryYE",
    "Yugoslavia": "countryYU",
    "Zambia": "countryZM",
    "Zimbabwe": "countryZW",
}


class _GoogleSignals(qt.QObject):
    resultsFound = qt.pyqtSignal(list)
    noResults = qt.pyqtSignal(str)
    finished = qt.pyqtSignal()


class Google(qt.QRunnable):

    # finished = qt.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._GOOGLE_SEARCH_URL = "https://www.google.com/search"
        self._term: typing.Optional[str] = None
        self._session = requests.session()
        self._safeSearch = False
        self.signals = _GoogleSignals()
        self._initSession()

    def _initSession(self) -> None:
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G960F "
                "Build/PPR1.180610.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Version/4.0 Chrome/74.0.3729.157 Mobile Safari/537.36"
            }
        )

    def _query_gen(self, keyword: str) -> typing.Generator[str, None, None]:
        page = 0
        while True:
            queryDict = {"q": keyword, "tbm": "isch"}
            if self._safeSearch:
                queryDict["safe"] = "active"
            params = urllib.parse.urlencode(queryDict)
            if self.region == "Japan":
                url = "https://www.google.co.jp/search"
            else:
                url = self._GOOGLE_SEARCH_URL
            yield url + "?" + params
            page += 1

    def _getResultsFromRawHtml(self, html: str) -> list[str]:
        pattern = r"AF_initDataCallback[\s\S]+AF_initDataCallback\({key: '[\s\S]+?',[\s\S]+?data:(\[[\s\S]+\])[\s\S]+?<\/script><script id="
        matches = re.findall(pattern, html)
        results: list[str] = []
        try:
            if len(matches) > 0:
                decoded = json.loads(matches[0])[31][0][12][2]
                for d in decoded:
                    d1 = d[1]
                    if d1:
                        results.append(str(d1[3][0]))
            return results
        except:
            # TODO: @ColinKennedy - Adjust try/except
            return []

    def _getHtml(self, term: str) -> str:
        images = self.search(term, 80)

        if not images or len(images) < 1:
            return "No Images Found. This is likely due to a connectivity error."

        firstImages: list[str] = []
        tempImages: list[str] = []
        for idx, image in enumerate(images):
            tempImages.append(image)
            if len(tempImages) > 2 and len(firstImages) < 1:
                firstImages.extend(tempImages)
                tempImages = []
            if len(tempImages) > 2 and len(firstImages) > 1:
                break
        html = '<div class="googleCont">'
        for img in firstImages:
            html += (
                '<div class="imgBox"><div onclick="toggleImageSelect(this)" data-url="'
                + img
                + '" class="googleHighlight"></div><img class="googleImage"  src="'
                + img
                + '"></div>'
            )
        html += '</div><div class="googleCont">'
        for img in tempImages:
            html += (
                '<div class="imgBox"><div onclick="toggleImageSelect(this)" data-url="'
                + img
                + '" class="googleHighlight"></div><img class="googleImage"  src="'
                + img
                + '"></div>'
            )
        html += (
            '</div><button class="imageLoader" onclick="loadMoreImages(this, \\\''
            + "\\' , \\'".join(_getCleanedUrls(images))
            + "\\')\">Load More</button>"
        )
        return html

    def _getPreparedResults(self, term: str, idName: str) -> list[str]:
        html = self._getHtml(term)

        return [html, idName]

    def _image_search(
        self,
        query_gen: typing.Iterator[str],
        maximum: int,
        region: str = "",
    ) -> typing.Optional[list[str]]:
        results: list[str] = []
        if not region:
            region = _COUNTRY_CODES[self.region]
        total = 0
        finished = False
        while True:
            try:
                count = 0
                while not finished:
                    count += 1
                    hr = self._session.get(next(query_gen) + "&ijn=0&cr=" + region)
                    html = hr.text
                    if not html and not "<!doctype html>" in html:
                        if count > 5:
                            finished = True
                            break
                        self._initSession()
                        time.sleep(0.1)
                    else:
                        finished = True
                        break
            except:
                self.signals.noResults.emit(
                    "The Google Image Dictionary could not establish a connection. Please ensure you are connected to the internet and try again. If you will be without internet for some time, consider using a template that does not include the Google Images Dictionary in order to prevent this message appearing everytime a search is performed. "
                )
                return None
            results = self._getResultsFromRawHtml(html)
            if len(results) == 0:
                soup = bs4.BeautifulSoup(html, "html.parser")
                elements = soup.select(".rg_meta.notranslate")
                jsons = [json.loads(e.get_text()) for e in elements]

                image_url_list = [js["ou"] for js in jsons]
                if not len(image_url_list):

                    break
                elif len(image_url_list) > maximum - total:
                    results += image_url_list[: maximum - total]
                    break
                else:
                    results += image_url_list
                    total += len(image_url_list)
            else:
                break
        return results

    def search(
        self, keyword: str, maximum: int, region: str = ""
    ) -> typing.Optional[list[str]]:
        query = self._query_gen(keyword)

        return self._image_search(query, maximum, region)

    def setSearchRegion(self, region: str) -> None:
        self.region = region

    def setSafeSearch(self, safe: bool) -> None:
        self._safeSearch = safe

    def setTermIdName(self, term: str, idName: str) -> None:
        self._term = term


def _getCleanedUrls(urls: typing.Iterable[str]) -> list[str]:
    return [x.replace("\\", "\\\\") for x in urls]


def search(target: str, number: int) -> list[str]:
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument("-t", "--target", help="target name", type=str, required=True)
    parser.add_argument(
        "-n", "--number", help="number of images", type=int, required=True
    )
    parser.add_argument(
        "-d", "--directory", help="download location", type=str, default="./data"
    )
    parser.add_argument(
        "-f",
        "--force",
        help="download overwrite existing file",
        type=bool,
        default=False,
    )

    args = parser.parse_args()

    data_dir = "./data"
    target_name = target

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, target_name), exist_ok=args.force)

    google = Google()

    results = google.search(target_name, maximum=number) or []
    return results
