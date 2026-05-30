# Configuration

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CELESTRAK_API_URL` | `https://celestrak.org/NORAD/elements/gp.php` | TLE source URL |
| `TLE_REFRESH_INTERVAL_HOURS` | `6` | Cache refresh period |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SPACETRACK_USER` | — | Space-Track.org username |
| `SPACETRACK_PASS` | — | Space-Track.org password |

## Runtime Flags

| Variable | Description |
|----------|-------------|
| `ASTROSIS_MOCK_GPU=1` | Force CPU backend; skip CUDA even if GPU is available |
| `OMP_NUM_THREADS=N` | Set OpenMP thread count (default: all available cores) |

Set these via environment or `.env` file (copy `.env.example` → `.env`).

`ASTROSIS_MOCK_GPU` can also be passed as `--mock-gpu` to any CLI command.
