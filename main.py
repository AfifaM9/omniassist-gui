"""
==============================================================================
 OMNIASSIST GUI ENTRY POINT SCRIPT (v2026.6 "Dirt Cake")
==============================================================================
 The browser GUI is the default interface. The legacy in-repo terminal CLI is
 DEPRECATED — the standalone OmniAssist project already provides the CLI
 (https://github.com/AfifaM9/omniassist, exposed via interfaces/cli.py there).
 It is retained here behind `--cli` only for backward compatibility and may be
 removed in a future release.

 THREE-PORT AUTH SYSTEM:
   :8000  (default)  no auth            python main.py
   :8001  --totp     6-digit TOTP code  python main.py --totp
   :8002  --token    GUI Omni token     python main.py --token
   The TOTP secret (OMNIASSIST_TOTP_SECRET) and the GUI Omni token
   (OMNIASSIST_API_TOKEN) live in .env. In --totp mode the UI stays on the
   6-digit box until a valid code is entered, even if no secret is configured.

 MODEL PRIORITY & FALLBACK HIERARCHY:
   Primary Model:  Gemini 3.6 Flash-Lite
   Fallback 1:     Gemini 3.5 Flash-Lite
   Fallback 2:     Gemini 3.1 Flash-Lite
   Fallback 3:     Gemini 3.5 Flash
   Fallback 4:     Gemini 3 Flash
   Fallback 5:     Gemini 2.5 Flash
   Fallback 6:     Gemini 3.8 Flash
   Fallback 7:     Gemma 4
   Rule:           Automatically skip deprecated or decommissioned models.
                   Try the primary model first, then move down the fallback
                   chain until a model succeeds.

 USAGE:
   python main.py                          # :8000 web UI, no auth
   python main.py --token                  # :8002 GUI Omni token gate
   python main.py --totp                   # :8001 TOTP gate
   python main.py --totp --port 9001       # explicit port still honoured
   python main.py --cli                    # DEPRECATED legacy terminal interface
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


def _resolve_auth(args):
    """Maps the launch flag to an (auth mode, default port) pair."""
    from core.auth import AuthMode

    if args.totp:
        return AuthMode.TOTP
    if args.token:
        return AuthMode.TOKEN
    return AuthMode.OPEN


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
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--token",
        action="store_true",
        help="Auth via the GUI Omni token (port 8002 by default)",
    )
    mode_group.add_argument(
        "--totp",
        action="store_true",
        help="Auth via a 6-digit TOTP code (port 8001 by default)",
    )
    parser.add_argument(
        "--host", default=os.environ.get("OMNIASSIST_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override the bind port (defaults to the auth mode's port)",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Auto-reload the web server on file changes"
    )
    args = parser.parse_args()

    if args.cli:
        run_legacy_cli()
        return

    mode = _resolve_auth(args)
    # The server reads the mode from the environment.
    os.environ["OMNIASSIST_AUTH_MODE"] = mode.value
    port = args.port if args.port is not None else mode.default_port

    if mode.value == "open" and args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"WARNING: binding the unauthenticated (:8000) UI to {args.host}. "
            "Use --token or --totp before exposing it beyond localhost.",
            file=sys.stderr,
        )

    run_web(args.host, port, args.reload)


if __name__ == "__main__":
    sys.exit(main())
