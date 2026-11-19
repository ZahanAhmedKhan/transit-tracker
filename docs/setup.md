# Setup

## Metrolinx Open Data API key (needed for live GO Transit data)

GO Transit's real-time feeds come from the Metrolinx Open Data API. Access is free, but every call
needs an Access Key.

1. Fill in the registration form at
   https://api.openmetrolinx.com/OpenDataAPI/Help/Registration/en
   (company name, intended use, business contact name, email and phone). Submit it only once.
2. Wait for approval. Requests are processed by hand and can take up to 10 business days.
3. Put the key in `.env` (never commit it):
   ```
   METROLINX_API_KEY=your_key_here
   ```
4. For the scheduled GitHub Actions runs, add the same value as a repository secret named
   `METROLINX_API_KEY` (GitHub repo → Settings → Secrets and variables → Actions).

The key does not expire, but Metrolinx may disable it if it detects extensive API calls, so the
ingestion job polls no more than once every 5 minutes.

Status: registration submitted on 2026-11-18; waiting for the key.

### Real-time endpoints (from the API help page)

| Feed | Path |
|---|---|
| Trip updates | `api/V1/Gtfs/Feed/TripUpdates` |
| Vehicle positions | `api/V1/Gtfs/Feed/VehiclePosition` |
| Alerts | `api/V1/Gtfs/Feed/Alerts` |

The base URL is `https://api.openmetrolinx.com/OpenDataAPI/`. How the key is passed and which
formats each path returns are checked once the key arrives, and recorded in `docs/realtime-feed.md`.

## Database (Supabase)

1. Create a free project at https://supabase.com (region Canada (Central)). The Data API is not
   needed: every script connects straight to PostgreSQL.
2. Connect → Direct → **Session pooler**, copy the connection string, and put it in `.env` as
   `DATABASE_URL=...` with your database password in place of `[YOUR-PASSWORD]`. Use a password
   of letters and numbers only; `@`, `#`, `/` and `%` break the connection string.
3. Create the tables and load the schedule:
   ```
   python run_sql.py schema.sql
   python run_sql.py rt_schema.sql
   python run_sql.py metrics_schema.sql
   python download_gtfs.py
   python load_stops_routes.py
   python load_trips_times.py
   python load_shapes.py
   python run_sql.py indexes.sql
   ```
4. Create the read-only login for the dashboard:
   `python create_dashboard_role.py` (writes `DASHBOARD_DATABASE_URL` to `.env`).

Without `DATABASE_URL`, the scripts use the Phase 1 local settings (`DB_HOST`, `DB_PASSWORD`, …).

## GitHub Actions secrets

GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Name | Value |
|---|---|
| `DATABASE_URL` | the `DATABASE_URL` line from `.env` (admin login) |
| `METROLINX_API_KEY` | the Metrolinx key, once it arrives |

Until `METROLINX_API_KEY` is set, the ingestion workflow ends with a yellow warning instead of
running. The daily workflow needs only `DATABASE_URL`.

## Dashboard on Streamlit Community Cloud

1. Sign in at https://share.streamlit.io with GitHub and choose **Create app → Deploy a public
   app from GitHub**.
2. Repository `ZahanAhmedKhan/transit-tracker`, branch `main`, main file `app.py`.
   Under **Advanced settings** pick Python 3.12.
3. In **Secrets**, paste one line (the value of `DASHBOARD_DATABASE_URL` from `.env`, the
   read-only login, not the admin one):
   ```
   DATABASE_URL = "postgresql://dashboard_reader.xxxx:password@aws-1-ca-central-1.pooler.supabase.com:5432/postgres"
   ```
   Streamlit passes top-level secrets to the app as environment variables, so `db.py` reads it
   unchanged.
4. Deploy, then put the app URL in the README and in the GitHub repo's About → Website field.
