# AGENTS.md

Repository-specific knowledge for OmniAssist GUI (nickname: **GUI Omni**).

## Release versioning

CalVer, dessert-codenamed: `v<YYYY>.<minor> "<Codename>"`, changelog id `v<YYYY>.<minor>-<kebab-codename>`.
Codenames increment and are dessert-themed, so the next minor bumps the number and picks the
next dessert.

| Version | Codename | Date |
| :--- | :--- | :--- |
| v2026.4 | Biscotti | 2026-09-17 |
| v2026.5 | Cake | 2026-10-19 |
| v2026.6 | Dirt Cake | 2026-10-19 |
| v2026.7 | Eton Mess | 2026-10-21 |
| v2026.8 | French Macaron | 2026-11-05 |
| **v2026.9 (current)** | **Galette** | 2026-11-15 |
| v2026.10 (next) | *unnamed* | — |

The next update of GUI Omni uses the codename **Galette** (i.e. `v2026.9 "Galette"`,
changelog id `v2026.9-galette`).

## Model hierarchy

Primary model is **`gemini-4-hydrogen`** (Gemini 4 Hydrogen, released November 2026), set in
`config/config.yml` and mirrored by `DEFAULT_MODEL` in `core/agent.py`. The fallback chain
(`gemini-3.6-flash-lite` -> `gemini-3.5-flash-lite` -> `gemini-3.1-flash-lite` ->
`gemini-3.5-flash` -> `gemini-3-flash-preview` -> `gemini-2.5-flash` -> `gemini-3.8-flash` ->
`gemma-4-31b-it` -> `gemma-4-26b-a4b-it`) lives in `config/config.yml` only; `core/agent.py`
loads it. Tests asserting the model are `tests/test_core.py::test_config_is_loaded` and
`tests/test_api.py` (health).

### Bumping the version

The version string is hardcoded in seven files and asserted in a test, so a release touches
all of them:

- `config/config.yml` (`app.version`)
- `main.py` (module docstring header)
- `interfaces/cli.py` (banner panel)
- `interfaces/api/server.py` (`VERSION` constant)
- `interfaces/web/index.html` (`#version` sidebar fallback)
- `mcp_tools/search_tools.py` (`api_lookup` User-Agent)
- `README.md` (intro paragraph)
- `tests/test_api.py::test_health_reports_the_current_release` (asserts the exact string)

Also add a new `## [v<...>-<codename>] - <date>` section to `CHANGELOG.md` (Keep a Changelog
format) and a link reference at the bottom of that file. The `[Unreleased]` section holds
changes merged but not yet released.

## Conventions

- Entry point is `main.py`; the browser GUI is the default and the in-repo terminal CLI
  (`interfaces/cli.py`) is deprecated in favour of the sister project
  [OmniAssist](https://github.com/AfifaM9/omniassist).
- Three-port auth: `:8000` open, `:8001` `--totp`, `:8002` `--token`. In TOTP mode an unset
  secret means *locked*, never open.
- Lint: `python -m ruff check .` (config in `ruff.toml`). Tests: `python -m pytest tests/ -v`.
  OCR tests skip when `tesseract`/`poppler-utils` are absent.
