# d38calendar

Fetches events from one or more Google Calendars and renders each one as a
static HTML page (a table), with links to switch between calendars. Suitable
for hosting on any website, including GitHub Pages via the included GitHub
Actions workflow.

## Project structure

Fetching and rendering are separate modules on purpose, so you can iterate on
the display template without touching the Google Calendar integration:

| File | Responsibility |
|---|---|
| `calendars.json` | Which calendars to publish, their page names, the site title and timezone. |
| `gcal_source.py` | Talks to the Google Calendar API, returns plain `Event` objects. No HTML/formatting logic. |
| `render.py` | Renders a list of `Event` objects to HTML via a Jinja2 template. No Google API knowledge. |
| `templates/table.html.j2` | The actual page template — edit this to change how the calendar looks. |
| `pdf_check.py` | Checks that attached PDF flyers can be opened without signing in. |
| `generate_page.py` | CLI entry point that wires it together: for each calendar, fetch → render → write page. |

## Prerequisites

- Python 3.9+
- A Google account with the calendar(s) you want to publish
- A Google Cloud project (free) to create a service account

## 1. Create or choose your Google Calendars

Use one calendar per page you want to publish (e.g. one for motorcycle races,
one for side-by-side races):

1. Go to [calendar.google.com](https://calendar.google.com).
2. In the left sidebar, click **+** next to "Other calendars" → **Create new calendar** (skip this if reusing an existing calendar).
3. Open the calendar's **Settings and sharing** page.
4. Under **Integrate calendar**, copy the **Calendar ID** (looks like
   `abc123@group.calendar.google.com`, or your email address if it's your
   primary calendar). It goes in `calendars.json` (see step 6).

## 2. Create a Google Cloud project and enable the Calendar API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Go to **APIs & Services → Library**, search for **Google Calendar API**, and click **Enable**.

## 3. Create a service account and key

1. Go to **APIs & Services → Credentials → Create Credentials → Service account**.
2. Give it any name (e.g. `calendar-reader`) and finish the wizard — no project roles are needed.
3. Open the new service account → **Keys** tab → **Add Key → Create new key → JSON**.
4. Save the downloaded file as `service-account.json` in this project directory.
   **Do not commit this file** — it's already covered by `.gitignore`.

## 4. Share each calendar with the service account

The service account can only read calendars explicitly shared with it. Do
this for **every** calendar listed in `calendars.json`:

1. Open the downloaded JSON key and copy the `client_email` value (looks like
   `calendar-reader@your-project.iam.gserviceaccount.com`).
2. Back in Google Calendar, open **Settings and sharing** for the calendar.
3. Under **Share with specific people**, click **Add people**, paste the service account email, and grant **See all event details**.

## 5. Install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 6. Configure `calendars.json`

```json
{
  "title": "D38 Race Calendar",
  "timezone": "America/Los_Angeles",
  "calendars": [
    {"label": "Motorcycle",   "id": "abc123@group.calendar.google.com", "page": "motorcycle.html"},
    {"label": "Side-by-Side", "id": "def456@group.calendar.google.com", "page": "sxs.html"}
  ]
}
```

| Key | Meaning |
|---|---|
| `title` | Site title. With more than one calendar, each page is titled "`title` – `label`". |
| `timezone` | IANA timezone for event times and for the date range (default `UTC`). |
| `calendars[].label` | Name shown in the page title and in the links between pages. |
| `calendars[].id` | The Google Calendar ID from step 1. |
| `calendars[].page` | Output filename. Optional; defaults to the label as a slug, e.g. `side-by-side.html`. |

Each calendar gets its own page, with links at the top to the other pages.
`index.html` is also written as a copy of the **first** calendar's page, so
the site's root URL works.

This file contains no secrets (a calendar ID alone doesn't grant access), so
it's committed to the repo and used by the GitHub Actions workflow too.

**To add a calendar:** create it (step 1), share it with the service account
(step 4), add an entry to `calendars.json`, and push.

## 7. Run it

```bash
.venv/bin/python generate_page.py --start 2026-01-01 --end 2026-12-31
```

| Option | Meaning | Default |
|---|---|---|
| `--start`, `--end` | Date range, `YYYY-MM-DD`, inclusive | required |
| `--config` | Config file | `calendars.json` |
| `--credentials` | Service account key file | `service-account.json` |
| `--output-dir` | Directory to write the pages into | `.` |
| `--template` | Template filename in `templates/` | `table.html.j2` |

If one calendar can't be fetched (e.g. it isn't shared with the service
account yet), its error is printed, the other pages are still written, and the
command exits with an error status.

## Customizing the display

Edit `templates/table.html.j2` (a Jinja2 template). Each event exposes:
`summary`, `location`, `description`, `all_day`, `start`, `end` (the latter
two are timezone-aware `datetime` objects), `pdf_url` (the link to the
first PDF attached to the event, or empty if none), and `details`: any
`Key: value` lines in the event description, with lowercased keys. The default
template uses `details.club`, `details.format`, `details.venue` and
`details.gps`, so put lines like these in each event's description:

```
Club: OTB
Format: Hare & Hound
Venue: Superstition OHV
GPS: 32.90197, -115.78046
```

Detail names are case-insensitive (`venue:` works too) and can go anywhere in
the description; other description text is ignored.

The Location column combines `Venue:` and `GPS:`:

| Event has | Location shows | Map link goes to |
|---|---|---|
| `Venue:` + `GPS:` | the venue name | the GPS point |
| `GPS:` only | the coordinates | the GPS point |
| Neither, but the event's location field is filled in | the location field | a map search for that text |
| Nothing | (blank) | no link |

`GPS:` accepts decimal coordinates (`32.90197, -115.78046`) or degrees and
minutes (`32°54'N 115°46'W`).

The template also receives `title`, `nav` (the list of calendar pages, each
with `label`, `page` and `current`), `start` and `end`. Two filters are
available for formatting: `|date` and `|time` (see `render.py` to change their
default formats or add new filters). To use an entirely different layout, add
a new `.j2` file under `templates/` and pass `--template your_file.j2`.

### Attached PDFs (e.g. race flyers)

If an event has a PDF attached, the event name links to it. Each run checks
every attached PDF anonymously (as a signed-out visitor) and prints a
`Warning:` line if it can't be opened. The page is still generated. To fix it,
in Google Drive set the file's (or its folder's) **Share → General access** to
**Anyone with the link → Viewer**.

## Automating updates with GitHub Actions

`.github/workflows/update-calendar.yml` regenerates the pages on a schedule
and publishes them to GitHub Pages.

Setup:

1. Push this project (including `calendars.json`) to a GitHub repository.
2. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
3. Go to **Settings → Secrets and variables → Actions → Secrets** and add
   `GCAL_CREDENTIALS_B64`: the base64-encoded contents of
   `service-account.json`. Generate it with:
   ```bash
   base64 -w0 service-account.json   # macOS: base64 -i service-account.json
   ```
   No repository variables are needed; everything else comes from
   `calendars.json`. (Older setups used `CALENDAR_ID`, `PAGE_TITLE` and
   `TIMEZONE` variables — these are no longer read and can be deleted.)
4. The workflow runs every 6 hours and on manual trigger (**Actions → Update
   calendar page → Run workflow**), regenerating every calendar's page with
   all events in the current year (Jan 1 through Dec 31, in the
   `calendars.json` timezone, including past events) and publishing them to
   your repo's GitHub Pages URL, e.g. `https://<user>.github.io/<repo>/sxs.html`.

To change the schedule, edit the `cron` line in the workflow file. To change
the date window, edit the `Compute date range` step (e.g. a rolling window
such as `$(date +%Y-%m-%d)` to `$(date -d '+30 days' +%Y-%m-%d)`).
