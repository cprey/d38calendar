# d38calendar

Fetches events from a Google Calendar and renders them as a static HTML table,
suitable for hosting on any website (including GitHub Pages via the included
GitHub Actions workflow).

## Project structure

Fetching and rendering are separate modules on purpose, so you can iterate on
the display template without touching the Google Calendar integration:

| File | Responsibility |
|---|---|
| `gcal_source.py` | Talks to the Google Calendar API, returns plain `Event` objects. No HTML/formatting logic. |
| `render.py` | Renders a list of `Event` objects to HTML via a Jinja2 template. No Google API knowledge. |
| `templates/table.html.j2` | The actual page template — edit this to change how the calendar looks. |
| `generate_page.py` | CLI entry point that wires the two together: fetch → render → write file. |

## Prerequisites

- Python 3.9+
- A Google account with a calendar you want to publish
- A Google Cloud project (free) to create a service account

## 1. Create or choose a Google Calendar

You can use an existing calendar (e.g. your primary calendar) or create a
dedicated one:

1. Go to [calendar.google.com](https://calendar.google.com).
2. In the left sidebar, click **+** next to "Other calendars" → **Create new calendar** (skip this if reusing an existing calendar).
3. Open the calendar's **Settings and sharing** page.
4. Under **Integrate calendar**, copy the **Calendar ID** (looks like
   `abc123@group.calendar.google.com`, or your email address if it's your
   primary calendar). You'll pass this as `calendar_id`.

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

## 4. Share the calendar with the service account

The service account can only read calendars explicitly shared with it:

1. Open the downloaded JSON key and copy the `client_email` value (looks like
   `calendar-reader@your-project.iam.gserviceaccount.com`).
2. Back in Google Calendar, open **Settings and sharing** for the calendar from step 1.
3. Under **Share with specific people**, click **Add people**, paste the service account email, and grant **See all event details**.

## 5. Install dependencies

```bash
pip install -r requirements.txt
```

## 6. Run it

Via CLI flags:

```bash
python generate_page.py \
  --start 2026-08-01 --end 2026-08-31 \
  --calendar-id your_calendar_id_or_email@group.calendar.google.com \
  --credentials service-account.json \
  --output calendar.html
```

Or via a config file for anything that doesn't change run-to-run (CLI flags
always override matching config values):

```bash
cp config.example.json config.json
# edit config.json: calendar_id, credentials, timezone, output, title
python generate_page.py --config config.json --start 2026-08-01 --end 2026-08-31
```

Config/CLI options:

| Setting | CLI flag | Config key | Required |
|---|---|---|---|
| Start date (`YYYY-MM-DD`, inclusive) | `--start` | `start` | yes |
| End date (`YYYY-MM-DD`, inclusive) | `--end` | `end` | yes |
| Calendar ID or email | `--calendar-id` | `calendar_id` | yes |
| Service account key path | `--credentials` | `credentials` | yes |
| IANA timezone for interpreting start/end | `--timezone` | `timezone` | no (default `UTC`) |
| Output HTML file path | `--output` | `output` | no (default `calendar.html`) |
| Page title | `--title` | `title` | no |
| Template filename (in `templates/`) | `--template` | `template` | no (default `table.html.j2`) |

## Customizing the display

Edit `templates/table.html.j2` (a Jinja2 template). Each event exposes:
`summary`, `location`, `description`, `all_day`, `start`, `end` (the latter
two are timezone-aware `datetime` objects), and `pdf_url` (the link to the
first PDF attached to the event, or empty if none), and `details`: any
`Key: value` lines in the event description, with lowercased keys. The default
template shows `details.club` and `details.format`, so put lines like these in
each event's description:

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
minutes (`32°54'N 115°46'W`). Two filters are available for
formatting: `|date` and `|time` (see `render.py` if you want to change their
default formats or add new filters). To use an entirely different layout,
add a new `.j2` file under `templates/` and pass `--template your_file.j2`.

### Attached PDFs (e.g. race flyers)

If an event has a PDF attached, the event name links to it. Each run checks
every attached PDF anonymously (as a signed-out visitor) and prints a
`Warning:` line if it can't be opened. The page is still generated. To fix it,
in Google Drive set the file's (or its folder's) **Share → General access** to
**Anyone with the link → Viewer**.

## Automating updates with GitHub Actions

`.github/workflows/update-calendar.yml` regenerates the page on a schedule
and publishes it to GitHub Pages.

Setup:

1. Push this project to a GitHub repository.
2. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
3. Go to **Settings → Secrets and variables → Actions**:
   - **Secrets** tab → add `GCAL_CREDENTIALS_B64`: the base64-encoded contents
     of `service-account.json`. Generate it with:
     ```bash
     base64 -w0 service-account.json   # macOS: base64 -i service-account.json
     ```
   - **Variables** tab → add `CALENDAR_ID` (your calendar ID/email) and,
     optionally, `PAGE_TITLE` and `TIMEZONE` (an IANA name such as
     `America/New_York`; defaults to `UTC`). `TIMEZONE` sets both how "today"
     is computed for the rolling window and how event times are displayed.
4. The workflow runs every 6 hours and on manual trigger (**Actions → Update
   calendar page → Run workflow**), regenerating a rolling 30-day window
   (today through today + 30 days) and publishing it to your repo's GitHub
   Pages URL.

To change the schedule, edit the `cron` line in the workflow file. To change
the date window, edit the `Compute date range` step (e.g. hardcode fixed
dates instead of a rolling window).
