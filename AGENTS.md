# Development guide

Anki add-on. Code lives in `src/` (Anki loads `src/` as the add-on package).
`src/vendors/` is third-party code: never lint, format or type-check it, and
keep it compatible with every supported Python (see below).

## Supported versions

Both are supported explicitly and tested as separate CI matrix entries:

| Anki     | Python | PyQt6 | tox envs                            |
| -------- | ------ | ----- | ----------------------------------- |
| 24.04    | 3.9    | 6.6.1 | `mypy-anki2404`, `test-anki2404`    |
| 26.09.4  | 3.13   | 6.11.0 | `mypy-anki2609`, `test-anki2609`   |

Anki 26.x ships Python 3.13, so avoid removed stdlib APIs and keep vendored
packages current (an old vendored `six` once broke the add-on on Python 3.12+).

## One-liners

Setup (once): `python -m pip install tox`

| Task                      | Command                              |
| ------------------------- | ------------------------------------ |
| Check formatting (black)  | `tox -e check-black`                 |
| Check import order        | `tox -e check-isort`                 |
| Auto-format               | `tox -e black && tox -e isort`       |
| Type-check, Anki 24.04    | `tox -e mypy-anki2404`               |
| Type-check, Anki 26.09.4  | `tox -e mypy-anki2609`               |
| Tests, Anki 24.04         | `tox -e test-anki2404`               |
| Tests, Anki 26.09.4       | `tox -e test-anki2609`               |
| Everything CI runs        | `tox` (runs every env above)         |

CI (`.github/workflows/`) runs on every pull request and on pushes to `master`:
black, isort, mypy (`--strict`, once per Anki version above) and the tests
(once per Anki version above).

Notes:

- tox needs Python 3.9 and 3.13 installed (`py -3.9` / `py -3.13` on Windows).
- PyQt6 is pinned per env to what that Anki bundles. The newest PyQt6 type
  stubs are broken and give false mypy errors.
- `tests/test_gui.py` boots a whole Anki and blocks forever, so tox does not run it.
- Anki 26.x has two editors, `Editor` and `NewEditor`. Never touch an editor's
  note directly; go through `src/editor_compat.py`.

## Trying changes in Anki

Link `src/` into Anki's add-ons folder instead of copying it:

- Windows (PowerShell): `New-Item -ItemType Junction -Path "$env:APPDATA\Anki2\addons21\foobar" -Target (Resolve-Path src)`
- Linux/macOS: `ln -s "$PWD/src" ~/.local/share/Anki2/addons21/foobar` (macOS: `~/Library/Application Support/Anki2/addons21/foobar`)

Quick load check without opening Anki, using Anki's own Python environment:

`QT_QPA_PLATFORM=offscreen python -c "import sys; sys.path.insert(0, '<addons21 dir>'); from aqt.qt import QApplication; QApplication([]); import foobar"`

## Conventions

- Add type hints to everything; `mypy --strict` must stay clean for new code.
- Prefer explicit `typing` imports compatible with Python 3.9.
- Don't commit `src/user_files/` (local user data).
