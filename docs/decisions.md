# Decisions

## 1. Keep a rolling date window of the schedule in Supabase (2026-11-19)

**Problem.** Supabase's free tier allows 500 MB. Loading the Phase 1 schedule as it was
(60 service days, all columns) into Supabase measured:

| What was loaded | Database size | stop_times total (data + index) |
|---|---|---|
| Full Phase 1 feed, all 8 stop_times columns, no shapes | 284 MB | 255 MB (1,667,673 rows) |
| Same feed, stop_times trimmed to 6 columns | 277 MB | 248 MB |

Dropping the unused columns (`drop_off_type`, `stop_headsign`) saved only 7 MB, because
each row's fixed overhead is larger than those columns. The number of rows is what matters.

The same check showed a second problem: the feed in `data/` covered 2026-09-29 to 2026-11-27,
so 52 of its 60 days were already in the past, and after 2026-11-27 no live trip could match it.
GO's trip_ids start with the service date (for example `20261125-GT-3514`), so a stale
schedule cannot be matched to live data at all.

**Decision.**
- `download_gtfs.py` downloads GO's current public schedule
  (`GO-GTFS.zip`, no key needed) before each load.
- `load_trips_times.py` keeps only service dates from 3 days ago to 14 days ahead
  (`DAYS_BEFORE` and `DAYS_AFTER`). Three days back leaves time to match late live updates
  and trips that run past midnight; two weeks ahead keeps the Departures tab useful.
- `load_shapes.py` keeps only the shapes used by those trips.
- `stop_times` keeps `trip_id, stop_sequence, stop_id, arrival_time, departure_time` and
  `pickup_type` (the Departures tab filters on `pickup_type`).

**Result** (measured with `measure_size.py` on 2026-11-19, feed published 2026-11-17):

| Table | Rows | Total size |
|---|---|---|
| shapes | 832,375 | 92 MB |
| stop_times | 481,784 | 79 MB |
| trips | 28,765 | 5.5 MB |
| stops, routes, calendar_dates | 890 / 88 / 17 | < 1 MB |
| **Whole database** | | **188 MB** |

That leaves about 310 MB for live data. The schedule must be reloaded regularly (the daily
workflow in Milestone 4 will do this), otherwise the window runs out.

**Next lever if space gets tight.** `shapes` is now the largest table: GO's current feed has
much more detailed paths (832,375 points for 509 shapes, against 446,142 points for 296 shapes
in the Phase 1 feed). Storing fewer points per path would shrink it without changing the
reliability numbers.

## 2. Store each live prediction once, with first-seen and last-seen times (2026-11-19)

The TripUpdates feed repeats every upcoming stop of every running trip in every snapshot.
Storing every row of every 5-minute snapshot would mostly store copies of the same prediction
and would fill 500 MB quickly. Instead:

- `rt_trip_updates` has a unique key on the prediction itself (trip, service date, stop,
  predicted times, delays and relationships). A repeated prediction does not add a row.
- On a repeat, `last_seen_at` moves forward (`ON CONFLICT ... DO UPDATE SET last_seen_at =
  GREATEST(...)`). Re-running the same snapshot changes nothing, so ingestion is idempotent.
- The final observed arrival for a trip and stop is the row with the newest `last_seen_at`.
  Plain `ON CONFLICT DO NOTHING` would get this wrong when a prediction changes and then
  changes back (A, B, A would end on B).
- `rt_vehicle_positions` uses `ON CONFLICT DO NOTHING` on (vehicle, report time), since a
  vehicle's report for a given moment never changes.
- A cancelled trip with no stop-level updates is stored as one row with no stop, so it can be
  counted separately from delays.

## 3. The local PostgreSQL database is no longer required

`db.py` uses `DATABASE_URL` when it is set and falls back to the Phase 1 local settings
(`DB_HOST`, `DB_PORT`, …) when it is not. The loaders, `run_sql.py` and the dashboard
therefore work against either database by changing only `.env`.
