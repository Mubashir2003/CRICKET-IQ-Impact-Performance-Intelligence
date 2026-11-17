#!/usr/bin/env python3
"""CRICKET IQ command-line entry point.

Usage:
    python run.py              Process the CSVs and build dashboard data
    python run.py serve        Start the local dashboard server (http://localhost:8000)
    python run.py all          Process the data, then start the server
    python run.py inspect      Show detected CSV schemas without processing
    python run.py test         Run the automated test suite
"""

from __future__ import annotations

import argparse
import functools
import http.server
import logging
import socketserver
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python"))


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")


def cmd_process() -> int:
    from cricketiq.config import ConfigError
    from cricketiq.ingestion.loader import IngestionError
    from cricketiq.pipeline import run

    try:
        summary = run()
    except (IngestionError, ConfigError) as exc:
        logging.error("Pipeline stopped: %s", exc)
        return 2
    print("\n=== CRICKET IQ pipeline complete ===")
    print(f"Time:              {summary['seconds']} s")
    print(f"Matches:           {summary['matches']}")
    print(f"Eligible players:  {summary['eligible']}")
    print(f"Validation checks: {summary['checks']}")
    if summary["failed_checks"]:
        print("FAILED checks (see data/processed/validation_report.md):")
        for name in summary["failed_checks"]:
            print("   -", name)
    print(f"Dashboard data:    data/dashboard ({summary['json_bytes'] / 1e6:.1f} MB)")
    print("Next: python run.py serve   then open http://localhost:8000/dashboard/")
    return 0


def cmd_inspect() -> int:
    from cricketiq.config import Paths, load_settings
    from cricketiq.ingestion.loader import load_raw

    paths = Paths()
    bundle = load_raw(paths, load_settings(paths))
    for rep in bundle.schema_report:
        print(f"\n[{rep['gender']}] {rep['file']}  rows={rep['rows']}")
        print("   columns :", ", ".join(rep["columns"]))
        print("   types   :", rep["detected_types"])
        if rep["renamed"]:
            print("   renamed :", rep["renamed"])
    for issue in bundle.issues:
        print("  !", issue.as_dict())
    return 0


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "application/javascript", ".json": "application/json", ".woff2": "font/woff2"}

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - quieter server
        pass


def cmd_serve(port: int, open_browser: bool) -> int:
    if not (ROOT / "data" / "dashboard" / "manifest.json").exists():
        print("Dashboard data not found - run `python run.py` first.")
        return 1
    handler = functools.partial(_Handler, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://localhost:{port}/dashboard/"
        print(f"CRICKET IQ dashboard running at {url}  (Ctrl+C to stop)")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
    return 0


def cmd_test() -> int:
    import pytest

    return pytest.main(["-q", str(ROOT / "tests")])


def main() -> int:
    ap = argparse.ArgumentParser(description="CRICKET IQ - T20 performance intelligence")
    ap.add_argument("command", nargs="?", default="process", choices=["process", "serve", "all", "inspect", "test"])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    _setup_logging(a.verbose)
    if a.command == "process":
        return cmd_process()
    if a.command == "inspect":
        return cmd_inspect()
    if a.command == "test":
        return cmd_test()
    if a.command == "serve":
        return cmd_serve(a.port, not a.no_browser)
    rc = cmd_process()
    return rc if rc else cmd_serve(a.port, not a.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
