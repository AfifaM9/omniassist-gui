"""
==============================================================================
 OMNIASSIST ENTRY POINT SCRIPT (2026.4 "Biscotti")
==============================================================================
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
   python main.py                 # interactive terminal interface
   python main.py --web           # web UI + API (default http://127.0.0.1:8000)
   python main.py --web --port 12000 --host 0.0.0.0
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


def main():
    parser = argparse.ArgumentParser(prog="omniassist", description="OmniAssist agent framework")
    parser.add_argument("--web", action="store_true", help="Launch the web UI and REST/WebSocket API")
    parser.add_argument("--host", default=os.environ.get("OMNIASSIST_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OMNIASSIST_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="Auto-reload the web server on file changes")
    args = parser.parse_args()

    if args.web:
        run_web(args.host, args.port, args.reload)
        return

    from interfaces.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    sys.exit(main())
