# Project: GO Transit Schedule Tracker

## About me
I'm a 3rd-year Data Engineering student at Sheridan College, on Windows (PowerShell, VS Code, Python 3.12, virtual environment `.venv`). I'm a beginner at Python, SQL and PostgreSQL. I need this project finished and on my resume by next Friday (college job search week), so speed matters more than deep teaching right now. I'll study Python properly after this project.

## The project (Phase 1 only)
Load the GO Transit GTFS static schedule from the `data/` folder into PostgreSQL, answer questions with SQL, and show the results in a Streamlit dashboard.
Flow: GTFS .txt files -> Python loader -> PostgreSQL -> SQL queries -> Streamlit.
Do NOT add real-time data, Docker, tests, AWS or anything not listed below.

## Setup facts
- Repo: `transit-tracker` on GitHub (I push myself).
- `data/` holds the GTFS files and is in `.gitignore`. Never commit data files, `.env` or passwords.
- Database credentials go in `.env` (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD), loaded with python-dotenv. Also create a `.env.example` without the real password.
- Use `psycopg` (version 3) and `pandas`.

## How to work with me
1. Start by looking at what's already in the repo so you don't redo finished work.
2. Work one milestone at a time. Write the full code for the milestone in large chunks, not tiny steps.
3. Explain each chunk briefly and in general terms: what it does and why, in a few sentences with a simple real-life analogy. Don't explain every line.
4. No quizzes and no questions unless you are truly blocked.
5. Run the code yourself and fix any errors before telling me it's done. Show me the important output.
6. At the end of each milestone, stop and give me:
   - the list of files you created or changed
   - the exact `git add` command and a short, clear commit message
   Do NOT commit or push. I will check everything and commit and push myself.
7. Never put "Claude", "AI", "Co-Authored-By" or any similar attribution in commit messages, code comments or the README.
8. Keep the code simple and beginner-friendly: clear names, short comments, no advanced tricks or extra features.
9. SQL alert: before starting any milestone that involves writing SQL (Milestone 2: creating tables in schema.sql, and Milestone 4: the queries in queries.py), STOP and tell me first with the line "SQL PART STARTING". Wait until I reply "go" before writing that code, because I want to find an SQL learning roadmap and study alongside it. For SQL code, explain the main SQL ideas used (like CREATE TABLE, SELECT, WHERE, JOIN, GROUP BY) a little more than the Python parts.

## Technical rules
- Store all IDs (stop_id, trip_id, route_id, service_id) as TEXT, because some have leading zeros like "00194".
- Store GTFS times as TEXT, because times can go past midnight like "25:10:00".
- Use `encoding="utf-8-sig"` when reading GTFS files.
- Only load the columns we need. If a file is missing (for example calendar.txt), skip it with a message and don't crash.
- Load large files (stop_times.txt) with PostgreSQL COPY through psycopg, not one INSERT per row. Add indexes on stop_times(stop_id), stop_times(trip_id), trips(route_id), calendar_dates(date).
- A trip runs on a date if its service_id is active that day: active in `calendar` for that weekday and date range, plus dates added in `calendar_dates` (exception_type 1), minus dates removed (exception_type 2).

## Milestones
1. Check that PostgreSQL is installed and the `transit` database exists. If not, tell me the simplest steps to install it on Windows. Create `requirements.txt`, `.env.example`, update `.gitignore`.
2. `schema.sql` with tables: stops, routes, calendar, calendar_dates, trips, stop_times. `db.py` with a `get_connection()` function using `.env`.
3. `load_data.py`: creates the tables, loads all GTFS files, adds indexes, prints row counts per table.
4. `queries.py` with these functions returning pandas DataFrames:
   - departures from a station (name search) on a chosen date between two times
   - routes serving a stop (name search, for example "Sheridan")
   - number of trips per route
   - all stops with latitude and longitude (for a map)
5. `app.py`: a Streamlit dashboard with four tabs (Departures with Milton GO 6–10 am as default, Routes at a stop, Trips per route with a bar chart, Map of all stops).
6. `README.md` for recruiters: one-line summary, the data flow, what questions it answers, a file table, design decisions (TEXT IDs, COPY bulk loading, indexes, service calendar logic), how to run it, and "Next: Phase 2 real-time delay tracking".

Start with Milestone 1.