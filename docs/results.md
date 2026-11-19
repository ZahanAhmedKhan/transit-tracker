# Results

Every number here comes from a run of the code. Each entry says how it was measured.
The final report (Milestone 7) is written after the tracker has collected at least 7 days of data.

## Milestone 1: Database in the cloud (2026-11-19)

All loads ran from a laptop in Ontario to Supabase (PostgreSQL 17, Canada Central region),
timed with PowerShell `Measure-Command`. Sizes come from `measure_size.py`
(`pg_database_size`, `pg_table_size`, `pg_indexes_size`).

| Measurement | Value |
|---|---|
| Phase 1 feed loaded in full: database size | 284 MB |
| Phase 1 feed: `load_trips_times.py` run time (1,667,673 stop_times) | 146.6 s |
| Current feed, 18-day window: database size after indexes | 188 MB |
| Current feed: stop_times rows kept | 481,784 |
| Current feed: trips kept | 28,765 |
| Current feed: shape points kept | 832,375 (509 shapes) |
| `load_trips_times.py` run time with the window | 41.9 s |
| `load_shapes.py` run time (COPY) | 24.2 s |
| Departures query (Milton GO, 06:00–10:00) from the laptop to Supabase | 0.38 s |

The window cut the stored stop_times from 1,667,673 (60 days, Phase 1 feed) to 481,784
(17 days, current feed), and the database from 284 MB to 188 MB including shapes and indexes.
The two loads used different feeds, so the row counts are not an exact like-for-like comparison.

## Milestones 2–4: Pipeline checks (2026-11-19)

| Measurement | Value | How it was measured |
|---|---|---|
| Automated tests | 25 (all passing) | `python -m pytest` locally against Supabase (temporary tables), and in GitHub Actions CI against a PostgreSQL 17 container |
| Daily refresh run time | 88.8 s | Whole `daily.yml` sequence run from the laptop against Supabase, timed with `Measure-Command` |
| Database size after a daily reload | 192 MB | `measure_size.py` after the run above |

Live-data numbers (trips tracked, on-time rate, ingestion success rate, trip_id match rate) are
added once the Metrolinx API key arrives and the tracker has run for at least 7 days.
