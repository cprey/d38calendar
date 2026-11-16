#!/usr/bin/env python3
"""CLI entry point: fetch events from one or more Google Calendars and write
one HTML page per calendar, plus index.html (a copy of the first page).

Calendars, page names, site title and timezone come from a JSON config file
(default: calendars.json). See README.md for the format.

Ties together gcal_source.py (data) and render.py (display). To change how
events are fetched, edit gcal_source.py; to change how the pages look, edit
templates/table.html.j2. Neither needs to touch this file.

Usage:
    python generate_page.py --start 2026-01-01 --end 2026-12-31
    python generate_page.py --config calendars.json --start 2026-01-01 --end 2026-12-31 \
        --credentials service-account.json --output-dir public
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from gcal_source import CalendarFetchError, fetch_events
from pdf_check import check_public
from render import render_events


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path("calendars.json"), help="JSON config file (default: calendars.json)")
    parser.add_argument("--start", required=True, help="Start date, inclusive (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date, inclusive (YYYY-MM-DD)")
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("service-account.json"),
        help="Service account JSON key file (default: service-account.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Directory to write pages into (default: .)")
    parser.add_argument("--template", default="table.html.j2", help="Template filename in templates/ (default: table.html.j2)")
    return parser.parse_args()


def _slugify(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "calendar"


def load_config(path: Path) -> dict:
    """Load and validate the config file. Exits with a clear message on any problem."""
    if not path.exists():
        sys.exit(f"Config file not found: {path}")
    try:
        config = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"Config file is not valid JSON: {path} ({exc})")

    calendars = config.get("calendars")
    if not isinstance(calendars, list) or not calendars:
        sys.exit(f"{path}: 'calendars' must be a non-empty list")

    pages_seen = set()
    for i, cal in enumerate(calendars, start=1):
        if not isinstance(cal, dict) or not cal.get("label") or not cal.get("id"):
            sys.exit(f"{path}: calendar #{i} needs both 'label' and 'id'")
        cal.setdefault("page", _slugify(cal["label"]) + ".html")
        if cal["page"] == "index.html":
            sys.exit(f"{path}: calendar '{cal['label']}' can't use page 'index.html' (it's written automatically)")
        if cal["page"] in pages_seen:
            sys.exit(f"{path}: page '{cal['page']}' is used by more than one calendar")
        pages_seen.add(cal["page"])

    config.setdefault("title", "Calendar")
    config.setdefault("timezone", "UTC")
    return config


def warn_about_private_pdfs(events) -> None:
    """Print a warning for each attached PDF that visitors can't open without signing in."""
    for event in events:
        if not event.pdf_url:
            continue
        problem = check_public(event.pdf_url)
        if problem:
            print(
                f"Warning: PDF for '{event.summary.strip()}' on {event.start:%Y-%m-%d} {problem}. "
                f"In Google Drive, set Share -> General access -> 'Anyone with the link'. ({event.pdf_url})",
                file=sys.stderr,
            )


def main():
    args = parse_args()
    config = load_config(args.config)

    if not args.credentials.exists():
        sys.exit(f"Credentials file not found: {args.credentials}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    calendars = config["calendars"]
    failures = []
    first_page_html = None

    for cal in calendars:
        try:
            events = fetch_events(
                calendar_id=cal["id"],
                credentials_path=args.credentials,
                start_date=args.start,
                end_date=args.end,
                timezone=config["timezone"],
            )
        except ValueError as exc:
            # Bad dates/timezone affect every calendar; no point continuing.
            sys.exit(str(exc))
        except CalendarFetchError as exc:
            print(f"Error: '{cal['label']}': {exc}", file=sys.stderr)
            failures.append(cal["label"])
            continue

        warn_about_private_pdfs(events)

        nav = [{"label": c["label"], "page": c["page"], "current": c is cal} for c in calendars]
        html = render_events(
            events,
            template_name=args.template,
            title=f"{config['title']} – {cal['label']}" if len(calendars) > 1 else config["title"],
            calendar_id=cal["id"],
            start=args.start,
            end=args.end,
            nav=nav,
        )
        out_path = args.output_dir / cal["page"]
        out_path.write_text(html)
        print(f"Wrote {len(events)} event(s) to {out_path}")

        if cal is calendars[0]:
            first_page_html = html

    if first_page_html is not None:
        index_path = args.output_dir / "index.html"
        index_path.write_text(first_page_html)
        print(f"Wrote {index_path} (copy of {calendars[0]['page']})")

    if failures:
        sys.exit(f"Failed to fetch {len(failures)} calendar(s): {', '.join(failures)}")


if __name__ == "__main__":
    main()
