"""
TUI demo recorder.

Records a terminal session into asciinema v2 format, then agg converts to GIF.
This script spawns astrosis directly through a PTY, interacts with it,
and writes a recorded asciinema cast file.

Usage:
    python scripts/demo_tui.py                # writes assets/demo.cast
    agg --speed 1.5 assets/demo.cast assets/tui-demo.gif
"""

import json
import os
import time
import pty
import select
import signal
import sys


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    width, height = 100, 28
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["ASTROSIS_MOCK_GPU"] = "1"

    pid, fd = pty.fork()
    if pid == 0:
        # Child: run astrosis
        os.execve(
            ".venv/bin/python",
            [".venv/bin/python", "-m", "engine"],
            env,
        )
        sys.exit(1)

    # Parent: record session
    events = []
    t0 = time.monotonic()

    def now():
        return time.monotonic() - t0

    def record(t, typ, data):
        events.append([round(t, 3), typ, data])

    def write_input(data):
        os.write(fd, data.encode() if isinstance(data, str) else data)

    def read_output(timeout=0.05):
        r, _, _ = select.select([fd], [], [], timeout)
        if r:
            try:
                return os.read(fd, 4096).decode("utf-8", errors="replace")
            except OSError:
                return None
        return None

    # Drain initial output
    time.sleep(1.5)
    chunk = read_output(0.1)
    while chunk:
        record(now(), "o", chunk)
        chunk = read_output(0.1)

    # ── Helper: send a key sequence ───────────────────────────────────────
    def send(seq, pause=0.3):
        write_input(seq)
        time.sleep(pause)
        chunk = read_output(0.05)
        while chunk:
            record(now(), "o", chunk)
            chunk = read_output(0.05)

    def type_text(text, pause=0.3):
        for ch in text:
            write_input(ch)
            time.sleep(0.05)
            chunk = read_output(0.01)
            while chunk:
                record(now(), "o", chunk)
                chunk = read_output(0.01)
        time.sleep(pause)
        chunk = read_output(0.05)
        while chunk:
            record(now(), "o", chunk)
            chunk = read_output(0.05)

    # ── 1. Passes mode: ISS 25544, 240 h ──────────────────────────────────
    type_text("25544")

    for _ in range(3):
        send("\t", 0.15)

    type_text("240")
    send("\t", 0.2)
    send("\n", 0.5)

    # ── 2. Tour other modes ───────────────────────────────────────────────
    send("\x1b6", 1.5)  # backend
    send("\x1b2", 1.5)  # propagate
    send("\x1b4", 1.5)  # info
    send("\x1b3", 1.5)  # conjunction
    send("\x1b5", 1.5)  # ephemeris
    send("\x1b1", 2.0)  # back to passes

    # ── 3. Help overlay ───────────────────────────────────────────────────
    send("\x1bOP", 2.0)  # F1
    send("\x1b", 1.0)  # Escape

    # ── 4. Quit ───────────────────────────────────────────────────────────
    send("\x03", 0.3)   # Ctrl+C
    send("\x11", 1.0)   # Ctrl+Q

    # Drain remaining output
    chunk = read_output(0.2)
    while chunk:
        record(now(), "o", chunk)
        chunk = read_output(0.2)

    # Write cast file (newline-delimited JSON, compatible with agg)
    os.makedirs("assets", exist_ok=True)
    with open("assets/demo.cast", "w") as f:
        header = {
            "version": 2,
            "width": width,
            "height": height,
            "timestamp": int(time.time()),
            "env": {"TERM": env["TERM"]},
        }
        json.dump(header, f, separators=(",", ":"))
        f.write("\n")
        for t, typ, data in events:
            json.dump([round(t, 6), typ, data], f, separators=(",", ":"))
            f.write("\n")
    print(f"Recorded {len(events)} events → assets/demo.cast ({os.path.getsize('assets/demo.cast')} bytes)")


if __name__ == "__main__":
    main()
