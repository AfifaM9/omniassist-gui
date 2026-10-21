# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Calendar Versioning](https://calver.org/).

## [v2026.7-eton-mess] - 2026-10-21

*Release "v2026.7 \"Eton Mess\"".*

### Added
- **OCR tooling** (`mcp_tools/ocr_tool.py`): `ocr_image`, `ocr_pdf`, and `ocr_languages`, backed by the host Tesseract binary and invoked as a subprocess so no Python binding is required. Handles images, multi-page PDFs (via `pdftoppm`), language-pack validation, and blank/unreadable inputs. Ported from the sister CLI project's v2026.7 release.
- **Long-term semantic memory** (`memory/vector_store.py`): `vector_store.py` was a stub returning `"Mock semantic result for query: ..."`. It is now a persisted vector index with `add_document`, `search`, `get_document`, `recent`, `save`, `load`, and `clear`. Uses `sentence-transformers` when available and falls back to a deterministic hashing embedder otherwise; vectors are recomputed automatically when the backend changes.
- Agent memory integration: completed turns are stored and relevant notes are recalled into the system prompt. New `recall()` and `remember()` methods, `OMNIASSIST_MEMORY_DIR` to relocate storage, and `last_tool_log` exposing the tool calls a run made.
- `/memory` and `/tools` commands in the deprecated in-repo CLI.
- `GET /api/memory` endpoint reporting the memory backend, storage path, document count, and recent notes; `/api/health` now reports `memory_backend` and `memory_documents`.
- Test suites `tests/test_ocr_tool.py` and `tests/test_memory.py`, plus memory-integration and OCR-reachability coverage in `tests/test_agent_loop.py` (163 tests total, up from 115).

### Changed
- Version bumped to **v2026.7 "Eton Mess"** (changelog id `v2026.7-eton-mess`) across `config/config.yml`, `main.py`, `interfaces/cli.py`, `interfaces/api/server.py`, `mcp_tools/search_tools.py` (User-Agent), and `README.md`.
- `core/agent.py` now recalls relevant memory before the first model call and persists each completed turn, on both the plain-answer and iteration-cap exit paths.

## [v2026.6-dirt-cake] - 2026-10-19

*Release "v2026.6 \"Dirt Cake\"".*

### Changed
- **Model hierarchy refreshed.** The primary model is now `gemini-3.6-flash-lite`; `gemini-3.5-flash-lite` and the previous chain follow as fallbacks (`gemini-3.6-flash-lite` -> `gemini-3.5-flash-lite` -> `gemini-3.1-flash-lite` -> `gemini-3.5-flash` -> `gemini-3-flash-preview` -> `gemini-2.5-flash` -> `gemini-3.8-flash` -> `gemma-4-31b-it` -> `gemma-4-26b-a4b-it`).
- Version bumped to **v2026.6 "Dirt Cake"** (changelog id `v2026.6-dirt-cake`).

## [v2026.5-cake] - 2026-10-19

*Release "v2026.5 \"Cake\"".*

### Added
- **Three-port auth system.** The launch flag now selects the port and the credential gate: `:8000` (open, no credential), `:8001` (`--totp`, 6-digit TOTP), `:8002` (`--token`, GUI Omni token). `--host` / `--port` still override.
- `core/totp.py` — dependency-free RFC 6238 TOTP (HMAC-SHA1, 30 s step, 6 digits, ±1 window), verified against the RFC Appendix B vectors.
- `core/auth.py` — auth modes, in-memory session tokens (8 h TTL), and a per-IP failed-attempt throttle.
- `GET /api/auth`, `POST /api/auth/token`, `POST /api/auth/totp`; sessions are accepted as bearer credentials by every guarded endpoint and the WebSocket.
- Browser auth gate: a token textbox that auto-detects pasted tokens, and a 6-digit TOTP box that auto-verifies at 6 digits.
- `OMNIASSIST_TOTP_SECRET` documented in `.env.example`; `auth:` block added to `config/config.yml`.

### Changed
- Version bumped to **v2026.5 "Cake"** (changelog id `v2026.5-cake`).
- In **TOTP mode the absence of a secret means locked, not open**: the UI stays on the 6-digit box and no code is ever valid, so the gate cannot be bypassed by leaving `OMNIASSIST_TOTP_SECRET` empty.

## [v2026.4-deprecation] - 2026-10-19

*Deprecation release "v2026.4 Deprecation 1", codename "Biscotti Deprecation 1".*

### Changed
- The browser **web GUI is now the default interface**: `python main.py` starts the web server (`--web` remains an accepted alias). `--host` / `--port` configure the bind address.
- **Deprecated the in-repo terminal CLI.** The standalone [OmniAssist](https://github.com/AfifaM9/omniassist) project already provides the CLI, so `interfaces/cli.py` is retained only for backward compatibility and is reachable via the new `python main.py --cli` flag. It emits a `DeprecationWarning` and a visible notice, and may be removed in a future release.
- Updated `README.md` so the web UI is documented as the default and the terminal interface is flagged as deprecated.

## [v2026.4-rename] - 2026-09-19

*Nickname release "Biscotti Rename 1".*

### Added
- Added `docs/omni_personal/nickname_notice.md`, documenting that **OmniAssist** is nicknamed **Omni** and **OmniAssist GUI** is nicknamed **GUI Omni**.

### Changed
- Renamed the web-UI inspector labels: the execution panel formerly labelled **Trace** is now **Omni's Computer**, and the tool panel formerly labelled **Tools** is now **Omni's MCP Toolbox**. Both the header toggles and the inspector tabs are updated.
- Updated the README to document the new panel names, the nickname notice, and the `docs/omni_personal/` directory in the file tree.

## [v2026.4-post] - 2026-09-18

*Post release "Biscotti Post 1".*

### Changed
- Renamed the project to **OmniAssist GUI** across all documentation, and expanded the full name to *Operationalized Multi-Agent Networked Intelligence & Autonomous System Services Integration Toolkit Graphical User Interface*.
- Documented that the browser UI runs at `127.0.0.1:8000` (localhost) or `0.0.0.0:8000` (all interfaces).

## [v2026.4] - 2026-09-17

*Initial release. Version numbers 2026.1–2026.3 were skipped so the project version aligns with its sister repository: [OmniAssist](http://github.com/AfifaM9/omniassist), version 2026.4 "Biscotti".*

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

[v2026.7-eton-mess]: https://github.com/AfifaM9/omniassist-gui/tree/v2026.7-eton-mess
[v2026.6-dirt-cake]: https://github.com/AfifaM9/omniassist-gui/tree/v2026.6-dirt-cake
[v2026.5-cake]: https://github.com/AfifaM9/omniassist-gui/tree/v2026.5-cake
[v2026.4-deprecation]: https://github.com/AfifaM9/omniassist-gui/tree/v2026.4-deprecation
[v2026.4-rename]: https://github.com/AfifaM9/omniassist-gui/tree/v2026.4-rename
[v2026.4]: https://github.com/AfifaM9/omniassist/tree/v2026.4
