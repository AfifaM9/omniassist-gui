"""
==============================================================================
 OMNIASSIST GUI ENTRY POINT SCRIPT (v2026.4 Deprecation 1 \"Biscotti Deprecation 1\")
==============================================================================
 The browser GUI is the default interface. The legacy in-repo terminal CLI is
 DEPRECATED — the standalone OmniAssist project already provides the CLI
 (https://github.com/AfifaM9/omniassist, exposed via interfaces/cli.py there).
 It is retained here behind `--cli` only for backward compatibility and may be
 removed in a future release.

 MODEL PRIORITY & FALLBACK HIERARCHY:
   Primary Model:  Gemini 3.5 Flash-Lite
   Fallback 1:     Gemini 3.1 Flash-Lite
   Fallback 2:     Gemini 3 Flash
   Fallback 3:     Gemini 2.5 Flash
   Fallback 4:     Gemini 2.5 Flash-Lite
   Fallback 5:     Gemma 4
   Rule:           Automatically skip deprecated or decommissioned models.
                   Try the primary model first, then move down the fallback
                   chain until a model succeeds.

 USAGE:
   python main.py                 # web UI + API (default http://127.0.0.1:8000)
   python main.py --web           # same as default (kept for compatibility)
   python main.py --host 0.0.0.0 --port 12000
   python main.py --cli           # DEPRECATED legacy terminal interface
==============================================================================
"""

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    pass


def run_web(host: str, port: int, reload: bool):
    import uvicorn

    uvicorn.run(
        "interfaces.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def run_legacy_cli():
    """Launches the deprecated in-repo terminal interface.

    The standalone OmniAssist project owns the CLI; this in-repo copy is kept
    only for backward compatibility.
    """
    print(
        "WARNING: the in-repo terminal CLI (interfaces/cli.py) is deprecated and "
        "will be removed in a future release.\n"
        "         Use the browser GUI (python main.py) instead, or the standalone "
        "OmniAssist CLI:\n"
        "         https://github.com/AfifaM9/omniassist\n",
        file=sys.stderr,
    )
    from interfaces.cli import main as cli_main

    cli_main()


def main():
    parser = argparse.ArgumentParser(
        prog="omniassist-gui",
        description="OmniAssist GUI agent framework (browser GUI by default)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the web UI and REST/WebSocket API (this is the default)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="DEPRECATED: launch the legacy in-repo terminal interface",
    )
    parser.add_argument("--host", default=os.environ.get("OMNIASSIST_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OMNIASSIST_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="Auto-reload the web server on file changes")
    args = parser.parse_args()

    if args.cli:
        run_legacy_cli()
        return

    # Default interface is the browser GUI; --web is an explicit no-op alias.
    run_web(args.host, args.port, args.reload)


if __name__ == "__main__":
    sys.exit(main())
