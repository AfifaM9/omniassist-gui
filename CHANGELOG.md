# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Calendar Versioning](https://calver.org/).

## [v2026.4] - 2026-09-17

### Added
- Added a browser web UI (`interfaces/web/`) served directly by the API server — a single-page app with no build step. Includes streaming chat replies, a session sidebar, a live agent execution trace, and a tools inspector.
- Added a `POST /api/run` endpoint and a `WS /ws/run` WebSocket that streams every agent step as JSON (`session`, `plan`, `tool_call`, `tool_result`, `final`, `error`, `done`).
- Added `GET /api/health`, `GET /api/tools`, `GET /api/sessions`, `GET /api/sessions/{id}`, and `DELETE /api/sessions/{id}`.
- Added optional bearer-token authentication (`OMNIASSIST_API_TOKEN`) covering every endpoint that runs the agent or touches session storage. The UI accepts the token via `?token=`, stores it in `localStorage`, and strips it from the URL.
- Added `core/events.py` (`AgentEvent`) so the CLI and web UI share one streaming interface.
- Added `python main.py --web [--host] [--port]` to launch the web server, plus `OMNIASSIST_HOST` / `OMNIASSIST_PORT` env overrides.
- Added an offline mode: with no API key configured, the CLI, web UI, and test suite still run end-to-end against a deterministic `OfflineClient` stub.
- Added session persistence (`memory/session.py`) with listing, loading, and deletion, exposed over the API.
- Added `tests/test_agent_loop.py` (tool execution, result feedback, iteration limits) and `tests/test_api.py` (endpoints, WebSocket streaming, auth).
- Added `ruff` to the dev requirements so local linting matches CI.
- Added `__init__.py` files for `mcp_tools/`, `memory/`, `subagents/`, `interfaces/`, `interfaces/api/`, `interfaces/adapters/`, and `tests/`.

### Changed
- **Agent loop is now genuinely multi-step.** `OmniAssist.run()` and the new `run_stream()` execute tool calls and feed each result back to the model as structured `function_response` parts, repeating until the model answers in text or `agent.max_iterations` is reached. Previously a single model call was made and tool results were returned to the user without ever reaching the model.
- The final iteration now appends an instruction to stop calling tools, guaranteeing the loop terminates with a summary instead of spinning to the cap.
- Rewrote `core/router.py` to build SDK `FunctionDeclaration`s from registered tools and to expose a real `execute()` method. The agent previously called `router.execute` behind a `hasattr` guard against a class that only defined `route()`, silently skipping every tool call.
- Tool discovery is now fault-tolerant and type-accurate: a module that fails to import is recorded in `registry.load_errors` instead of aborting discovery, and only true module-level functions are registered (the `DDGS` class no longer leaks in as a "tool").
- `mcp_tools/ddgs_search.py` now imports `ddgs` rather than the deprecated `duckduckgo_search` package.
- Replaced the two placeholder model fallback lists with real, verified model IDs: `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-3.5-flash` → `gemini-3-flash-preview` → `gemini-2.5-flash` → `gemini-3.8-flash` → `gemma-4-31b-it` → `gemma-4-26b-a4b-it`.
- `interfaces/api/server.py` no longer instantiates an agent at import time, so the module can be imported without credentials. Agents are now created per session.
- `main.py` is now a real entry point with argument parsing instead of a bare `from interfaces.cli import main`.
- The CLI renders the plan and each tool call/result inline as the agent works, instead of only showing the final answer.
- Session IDs are validated against `^[A-Za-z0-9_-]{1,64}$` before any filesystem access.
- `requirements.txt` now declares the dependencies the code actually imports (`fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `ddgs`).
- CI and lint workflows now trigger on `main` (the default branch) as well as `master`; previously they only watched `master`, so they never ran.
- Rewrote the README with a Web UI & API section, the streaming protocol, an endpoint table, and an explicit Security section documenting the known limitations of the shell denylist and `eval`-based calculators.
- `.gitignore` now covers `data/` (session storage) and virtualenv directories; `.env.example` documents the new web and auth settings.

### Fixed
- Fixed `tests/test_core.py::test_agent_initialization`, which raised `ValueError` without an API key. It now asserts offline mode and uses an explicit key when one is needed.
- Fixed the `ruff` line-length failure risk in `interfaces/api/server.py` by following the Google function-calling guidance in the emitted system prompt.

### Removed
- Removed the duplicate `duckduckgo-search` dependency (superseded by `ddgs`).
- Removed `pytest` duplication across `requirements-dev.txt` and `requirements-dev-2.txt`.

### Security
- Documented that `mcp_tools/shell_tool.py` is a denylist and not a sandbox. It is bypassable via path traversal (`rm -rf /opt/../etc`), trailing slashes, unexpanded variables (`$HOME`), long flags (`--recursive --force`), command chaining, and `find / -delete`. The README and Security section now state this plainly rather than describing the tooling as sandboxed.
- Added optional token auth to the web API, which exposes shell-executing tools over HTTP for the first time.

## [v2026.4] - 2026-09-13

### Changed
- Bumped version to 2026.4 across `config/config.yml`, `main.py`, `interfaces/cli.py`, `interfaces/api/server.py`, `mcp_tools/search_tools.py` (User-Agent), `README.md`, and `SECURITY.md`
- Expanded the supported-version table in `SECURITY.md` from 2026.3 to 2026.4
- Reworked the model fallback chain to try the primary model first and automatically move on to the next fallback when a model call fails (primary: `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-3-flash` → `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemma-4-31B-it` → `gemma-4-26B-A4B-it`)

## [v2026.3]

### Added
- Added a slash-command framework to the CLI with a `/help` command that renders available commands in a Rich table
- Added an unknown-command handler that warns on unrecognized slash commands and points users to `/help`
- Added `tests/test_cli.py` covering slash-command matching, quit patterns, and edge cases
- Added GitHub Actions CI workflow (`.github/workflows/ci.yml`) running the pytest suite on Python 3.11
- Added GitHub Actions Lint workflow (`.github/workflows/lint.yml`) running `ruff check`
- Added status badges (CI, Lint, Python, License, Version) to the README
- Added a "Before vs. After" section and an "Other" checkbox to the PR template

### Changed
- Bumped version to 2026.3 across `config/config.yml`, `main.py`, `interfaces/cli.py`, `interfaces/api/server.py`, and `mcp_tools/search_tools.py` (User-Agent)
- Expanded the supported-version table in `SECURITY.md` from 2026.2 to 2026.3
- Reworked the README directory tree to reflect the full current structure (adapters, API server, `web_fetch.py`, requirements files) and dropped the stale `.env` / `venv` entries
- Documented `/help` in the README's usage section and linked `LICENSE.txt` in the License section

### Removed
- Removed redundant project scaffolding entries from the README tree (local `.env` and `venv/` directories)

## [v2026.2] - 2026-08-04

### Added
- Added `/help` command to display available slash commands

### Removed
- Removed catastrophic commands that could cause data loss or system damage

## [v2026.1]

### Added
- Initial Release

[v2026.4]: https://github.com/AfifaM9/omniassist/compare/v2026.3...v2026.4
[v2026.3]: https://github.com/AfifaM9/omniassist/compare/v2026.2...v2026.3
[v2026.2]: https://github.com/AfifaM9/omniassist/compare/v2026.1...v2026.2
[v2026.1]: https://github.com/AfifaM9/omniassist/tree/v2026.1
