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

## Database connection

The local database settings live in `.env` (see `.env.example`). If PostgreSQL rejects the
password, the `postgres` password was changed in PostgreSQL; update `DB_PASSWORD` in `.env` to match.
