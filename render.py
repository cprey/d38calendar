"""Renders a list of Events to HTML using a Jinja2 template.

Decoupled from Google Calendar fetching (see gcal_source.py) so the display
template can be edited independently of how events are retrieved. To change
what the page looks like, edit templates/table.html.j2 (or point
--template at a different file) — no changes needed here or in gcal_source.py.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from gcal_source import Event

DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"
DEFAULT_TEMPLATE = "table.html.j2"


def _format_date(value: datetime, fmt: str = "%a, %b %d %Y") -> str:
    return value.strftime(fmt)


def _format_time(value: datetime, fmt: str = "%I:%M %p") -> str:
    return value.strftime(fmt).lstrip("0")


def render_events(
    events: list[Event],
    *,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
    template_name: str = DEFAULT_TEMPLATE,
    **context,
) -> str:
    """Render `events` to an HTML string using the named Jinja2 template.

    Extra keyword arguments (title, calendar_id, start, end, ...) are passed
    through to the template as-is so custom templates can display them.
    """
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["date"] = _format_date
    env.filters["time"] = _format_time

    template = env.get_template(template_name)
    return template.render(events=events, generated_at=datetime.now(), **context)
