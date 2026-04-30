# Speerheads TS60 Trifecta Database

A static website database for Andy Speer's TS60 Trifecta workout schedules. The site reads extracted JSON from the original Excel and PDF schedules in `sources/`.

## Project Structure

- `index.html`, `styles.css`, `app.js`: static website files.
- `data/schedules.json`: generated workout database consumed by the site.
- `sources/`: original schedule files used for extraction.
- `scripts/extract_schedules.py`: parser for the Excel and PDF source files.

## Regenerate The Database

Use a Python environment with `openpyxl` and `pypdf` installed:

```bash
python3 scripts/extract_schedules.py
```

The parser writes `data/schedules.json` and preserves source file names, workout labels, dates found in class titles, and Peloton URLs when the source file includes them.

## Preview Locally

Because the app uses `fetch()` to load JSON, serve the folder from a local web server:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.
