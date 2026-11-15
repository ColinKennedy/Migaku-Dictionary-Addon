<h2 align="center">Migaku Dictionary Addon</h2>

<p align="center">
<a title="Rate on AnkiWeb" href="https://ankiweb.net/shared/info/1655992655"><img src="https://glutanimate.com/logos/ankiweb-rate.svg"></a>
<a title="License: GNU AGPLv3" href="https://github.com/migaku-official/Migaku-Dictionary-Addon/blob/master/README.md><img  src="https://img.shields.io/badge/license-GNU AGPLv3-green.svg"></a>
<br>
<a title="Support us on Patreon" href="https://www.patreon.com/Migaku"><img src="https://img.shields.io/badge/patreon-support-orange.svg"></a>
<br>
<a title="Subscribe to Immerse with Migaku" href="https://www.youtube.com/c/ImmerseWithYoga"><img src="https://img.shields.io/badge/YouTube-Immerse%20with%20Yoga-red"></a>
<br>
<a title="Follow us on Twitter" href="https://twitter.com/Migaku_Yoga"><img src="https://img.shields.io/badge/Twitter-Immerse%20with%20Yoga-blue"></a>
</p>

>Lookup word definitions, frequency, audio, and export that information to Anki cards in real-time

### Table of Contents

- [Installation](#installation)
- [Documentation](#documentation)
- [Development](#development)
- [Contributing](#contributing)
- [License and Credits](#license-and-credits)

### Installation

1. Install the version of Anki that is listed under the "Migaku Development Cycles" section of the AnkiWeb add-on [page](https://ankiweb.net/shared/info/1655992655)
2. Download the latest version of the addon from [AnkiWeb](https://ankiweb.net/shared/info/1655992655)

### Development

Supported: **Anki 24.04 (Python 3.9)** and **Anki 26.09.4 (Python 3.13)**. CI tests both.
See [AGENTS.md](./AGENTS.md) for full details.

```sh
python -m pip install tox      # one-time setup
tox -e check-black             # check formatting
tox -e check-isort             # check import order
tox -e black && tox -e isort   # auto-format
tox -e mypy-anki2404           # type-check against Anki 24.04
tox -e mypy-anki2609           # type-check against Anki 26.09.4
tox -e test-anki2404           # tests on Anki 24.04
tox -e test-anki2609           # tests on Anki 26.09.4
tox                            # everything CI runs
```

### Contributing

Contributions are welcome! Please review the [contribution guidelines](./.github/CONTRIBUTING.md) on how to:

- Report issues
- File pull requests
- Support the project as a non-developer

### License and Credits

*Migaku Dictionary Addon* is

*Copyright © 2020 Migaku ltd.

Migaku Dictionary Addon is free and open-source software. The add-on code that runs within Anki is released under the GNU AGPLv3 license, extended by a number of additional terms. For more information please see the [LICENSE](https://github.com/migaku-official/Migaku-Dictionary-Addon/blob/master/README.md) file that accompanied this program.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY.

----
