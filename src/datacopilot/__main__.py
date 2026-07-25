"""Command-line interface.

    python -m datacopilot seed                 # (re)create + populate the database
    python -m datacopilot ask "how many students?"
    python -m datacopilot serve                # run the API (uvicorn)
    python -m datacopilot info                 # dataset + config summary
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import settings
from .data import summary as data_summary
from .logging_config import configure_logging


def _cmd_seed(_args: argparse.Namespace) -> int:
    from .seed import create

    create(settings.db_path)
    print(f"Seeded {settings.db_path}: {json.dumps(data_summary())}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    import os

    from .copilot import Copilot
    from .seed import create

    if not os.path.exists(settings.db_path):
        create(settings.db_path)
    result = Copilot().ask(args.question)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.status == "success" else 1


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required to serve: pip install 'uvicorn[standard]'", file=sys.stderr)
        return 1
    uvicorn.run("datacopilot.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_info(_args: argparse.Namespace) -> int:
    print(json.dumps({
        "version": "1.0.0",
        "llm_mode": settings.llm_mode,
        "db_path": settings.db_path,
        "max_retries": settings.max_retries,
        "row_limit": settings.row_limit,
        "dataset": data_summary(),
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging(settings.log_level, settings.log_json)
    parser = argparse.ArgumentParser(prog="datacopilot", description="AI Data Copilot")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="create and populate the database").set_defaults(func=_cmd_seed)

    p_ask = sub.add_parser("ask", help="ask a question")
    p_ask.add_argument("question")
    p_ask.set_defaults(func=_cmd_ask)

    p_serve = sub.add_parser("serve", help="run the API server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=_cmd_serve)

    sub.add_parser("info", help="print dataset + config summary").set_defaults(func=_cmd_info)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
