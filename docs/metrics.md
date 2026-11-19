# Reliability metrics

How live GO Transit data becomes the on-time numbers on the dashboard.
The SQL is in `refresh_metrics.py` (matching) and `metrics_schema.sql` (views), and
`tests/test_metrics_database.py` checks it on small known examples.

## From raw updates to one arrival per stop

1. **Raw layer.** `ingest.py` stores every distinct prediction from the TripUpdates feed in
   `rt_trip_updates`, with the snapshot it was first seen in (`snapshot_time`) and the last
   snapshot that still contained it (`last_seen_at`).
2. **Final observed arrival.** For each trip, service date and stop, the update with the newest
   `last_seen_at` is the final one. Its arrival time (or departure time at the first stop) is the
   observed arrival. If the feed gives only a delay, observed = scheduled + delay.
3. **Observed, not forecast.** A final update only counts if the arrival it predicts was no more
   than `max_prediction_gap_minutes` (15) after it was last seen. A trip that drops out of the
   feed hours before its last stops leaves forecasts, not arrivals, and those are not counted.
4. **Matching to the schedule.** The update is joined to `stop_times` on `trip_id` and
   `stop_sequence`. GO's trip_ids include the date, and `service_date` comes from the feed's
   `start_date` (or the first 8 characters of the trip_id).
5. **Times past midnight.** GTFS times are intervals counted from "noon minus 12 hours" on the
   service date in Toronto time. The scheduled arrival is that moment plus the `stop_times`
   interval, so `24:35:00` on Nov 25 becomes 00:35 on Nov 26. This also stays right on the two
   days a year the clocks change.
6. **Kept after cleanup.** The result goes into `stop_arrivals`, one row per trip and stop.
   `refresh_metrics.py` rebuilds the last 3 service dates every day while they are still inside
   the schedule window. Re-running it replaces rows instead of adding duplicates.

## Definitions

| Term | Definition |
|---|---|
| Delay | Observed arrival minus scheduled arrival, in minutes. Negative means early. |
| On time | Delay is between −1 and +5 minutes (inclusive). |
| On-time rate | On-time arrivals ÷ observed arrivals. |
| Average delay | Mean delay of observed arrivals. |
| 90th-percentile delay | 90% of observed arrivals were this late or less. |
| Skipped stop | The feed marked the stop `SKIPPED`. Counted separately and excluded from delays. |
| Cancelled trip | The trip's newest update says `CANCELED`. Counted separately and excluded from delays. |
| Trips tracked | Distinct (service date, trip) pairs with at least one row in `stop_arrivals`. |
| Hour of day | Hour of the scheduled arrival in Toronto time. |

The thresholds live in the one-row table `reliability_settings`, so they can be changed
without editing code:

```sql
UPDATE reliability_settings SET late_minutes = 3, early_minutes = 0;
```

## Views

| View | One row per |
|---|---|
| `arrival_results` | trip and stop, with delay in minutes, on-time flag, hour and day |
| `reliability_overall` | the whole data set (also the first and last service date) |
| `reliability_by_route` | route |
| `reliability_by_hour` | hour of day |
| `reliability_by_day_of_week` | day of week (1 = Monday) |
| `reliability_by_stop` | stop, with its name and coordinates for the map |

Each summary view has: observed arrivals, on-time rate, average delay, 90th-percentile delay,
skipped stops and cancelled trips.

## Cleanup

Every day `refresh_metrics.py` deletes raw `rt_trip_updates` rows for service dates more than
30 days old, but only if `stop_arrivals` already covers those dates. Vehicle positions older
than 30 days are deleted too. `stop_arrivals` itself is kept.

## To check once the API key arrives

- Whether GO's feed keeps a stop in TripUpdates after the train has left it, or drops it.
  This decides whether 15 minutes is the right `max_prediction_gap_minutes`.
- Whether the feed sends `stop_sequence` for every update. Matching uses it, so an update with
  only a `stop_id` would not be matched.
