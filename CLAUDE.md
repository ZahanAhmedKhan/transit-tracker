# Project: GTA Transit Tracker (GO Transit)

## About me
I'm a 3rd-year Data Engineering student at Sheridan College, on Windows with Python 3.12 and VS Code. I'm a beginner at Python, SQL and databases. I'm building this project to learn properly and to use in internship applications, so I must be able to explain every part of it myself.

## The project (Phase 1 only)
Load the GO Transit GTFS static schedule (stops.txt, routes.txt, trips.txt, calendar files, stop_times.txt) from the `data/` folder into PostgreSQL, answer questions with SQL, and show results in a simple Streamlit page.
Flow: GTFS files -> Python script -> PostgreSQL -> SQL queries -> Streamlit.
Real-time delays, Docker, tests and AWS are NOT part of Phase 1. Do not add them.

## Setup facts
- Virtual environment is `.venv`; the repo is `transit-tracker` on GitHub.
- `data/` is in .gitignore. Never commit data files, `.env` or API keys.
- IDs such as stop_id ("00194") must be stored as TEXT because of leading zeros.

## How you must teach me (most important)
1. Work on ONE milestone at a time. Never build ahead of the current milestone.
2. Split each milestone into small steps of at most about 15 lines of code.
3. For each step: first explain what it does in plain words with a real-life analogy, then show the code, then explain it line by line.
4. Before I run a script, ask me to predict what it will print.
5. After each step, give me a 3-question quiz using proper CS terms (no analogies in the quiz). Wait for my answers. If I get something wrong, re-explain it differently.
6. Do not continue to the next step until I say "next".
7. Keep code beginner-friendly: simple names, no advanced tricks, no extra features, no refactoring I didn't ask for.
8. Do not edit files outside the current milestone. Tell me which file you will change before you change it.
9. If I'm confused, make the step smaller, don't push ahead.
10. At the end of each milestone, ask me to explain the milestone in my own words, and tell me honestly what I'm missing. I'll write my notes in LEARNING.md myself; don't write them for me.

## Milestones
1. Read stops.txt and routes.txt with Python (csv.DictReader), filter stops by name.
2. Install PostgreSQL (propose the simplest way on Windows and ask me), create the database and the `stops` and `routes` tables.
3. Write a Python script that loads stops and routes into PostgreSQL (psycopg), IDs as text, credentials in .env.
4. Create and load `trips`, calendar tables and `stop_times` (large file, explain batch loading).
5. Write SQL queries for real questions: Milton line trains from Milton GO on weekday mornings; routes serving Sheridan College; trips per route.
6. A simple Streamlit page that shows those results.
7. README with an architecture diagram and a clear explanation of each part.

Start with Milestone 1, Step 1.