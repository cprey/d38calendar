#!/usr/bin/env python3
"""CLI entry point: fetch events from a Google Calendar and write an HTML page.

Ties together gcal_source.py (data) and render.py (display). To change how
events are fetched, edit gcal_source.py; to change how the page looks, edit
templates/table.html.j2. Neither needs to touch this file.

Usage:
    python generate_page.py --start 2026-08-01 --end 2026-08-31 \
        --calendar-id your_calendar@group.calendar.google.com \
        --credentials service-account.json --output calendar.html

    # Or via config file (CLI args override config values):
    python generate_page.py --config config.json --start 2026-08-01 --end 2026-08-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gcal_source import CalendarFetchError, fetch_events
from pdf_check import check_public
from render import render_events


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="Path to a JSON config file with defaults")
    parser.add_argument("--start", help="Start date, inclusive (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date, inclusive (YYYY-MM-DD)")
    parser.add_argument("--calendar-id", help="Calendar ID or email to read events from")
    parser.add_argument("--credentials", type=Path, help="Path to service account JSON key file")
    parser.add_argument("--timezone", help="IANA timezone for interpreting --start/--end (default: UTC)")
    parser.add_argument("--output", type=Path, help="Path to write the HTML file (default: calendar.html)")
    parser.add_argument("--title", help="Page title")
    parser.add_argument("--template", help="Template filename in templates/ (default: table.html.j2)")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"Config file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"Config file is not valid JSON: {path} ({exc})")


def resolve_settings(args) -> dict:
    config = load_config(args.config) if args.config else {}

    settings = {
        "start": args.start or config.get("start"),
        "end": args.end or config.get("end"),
        "calendar_id": args.calendar_id or config.get("calendar_id"),
        "credentials": args.credentials or (Path(config["credentials"]) if config.get("credentials") else None),
        "timezone": args.timezone or config.get("timezone") or "UTC",
        "output": args.output or (Path(config["output"]) if config.get("output") else Path("calendar.html")),
        "title": args.title or config.get("title"),
        "template": args.template or config.get("template") or "table.html.j2",
    }

    missing = [key for key in ("start", "end", "calendar_id", "credentials") if not settings[key]]
    if missing:
        sys.exit("Missing required setting(s): " + ", ".join(missing) + ". Provide them via CLI flags or --config.")

    if not settings["credentials"].exists():
        sys.exit(f"Credentials file not found: {settings['credentials']}")

    return settings


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
    settings = resolve_settings(args)

    try:
        events = fetch_events(
            calendar_id=settings["calendar_id"],
            credentials_path=settings["credentials"],
            start_date=settings["start"],
            end_date=settings["end"],
            timezone=settings["timezone"],
        )
    except (CalendarFetchError, ValueError) as exc:
        sys.exit(str(exc))

    warn_about_private_pdfs(events)

    output_html = render_events(
        events,
        template_name=settings["template"],
        title=settings["title"],
        calendar_id=settings["calendar_id"],
        start=settings["start"],
        end=settings["end"],
    )

    settings["output"].write_text(output_html)
    print(f"Wrote {len(events)} event(s) to {settings['output']}")


if __name__ == "__main__":
    main()
