#!/bin/bash
# Refresh the bundled TLE cache from Celestrak
# Run: ./scripts/refresh-tle-cache.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$(dirname "$SCRIPT_DIR")/data"
mkdir -p "$DATA_DIR"

echo "Fetching active TLEs from Celestrak..."
curl -s --max-time 60 "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle" \
  -o "$DATA_DIR/active.txt" || {
  echo "Celestrak unreachable, trying Space-Track..."
  if [ -n "$SPACETRACK_USER" ] && [ -n "$SPACETRACK_PASS" ]; then
    curl -s --max-time 30 -c /tmp/st-cookies \
      -d "identity=$SPACETRACK_USER&password=$SPACETRACK_PASS" \
      "https://www.space-track.org/ajaxauth/login" > /dev/null
    curl -s --max-time 60 -b /tmp/st-cookies \
      "https://www.space-track.org/basicspaceradar/query/class/tle_latest/ORDINAL/NORAD_CAT_ID/EPOCH/now/format/tle" \
      -o "$DATA_DIR/active.txt"
    rm -f /tmp/st-cookies
  else
    echo "No TLE source available. Set SPACETRACK_USER/SPACETRACK_PASS or wait for Celestrak."
    exit 1
  fi
}

COUNT=$(wc -l < "$DATA_DIR/active.txt")
echo "Saved $((COUNT / 3)) TLE entries to data/active.txt"
