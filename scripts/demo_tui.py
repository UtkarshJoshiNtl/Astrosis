"""
TUI demo recorder.

Records a terminal session into asciinema v2 format, then agg converts to GIF.
Drives `astrosis` through the passes tab (NORAD ID + hours), help overlay, quit.

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
    # Ensure clean state for demo
    state_path = os.path.expanduser("~/.cache/astrosis/tui_state.json")
    if os.path.exists(state_path):
        os.remove(state_path)

    pid, fd = pty.fork()
    if pid == 0:
        os.execve(
            ".venv/bin/python",
            [".venv/bin/python", "-m", "engine"],
            env,
        )
        sys.exit(1)

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

    # Drain initial output (wait for TUI to render)
    time.sleep(2.0)
    chunk = read_output(0.2)
    while chunk:
        record(now(), "o", chunk)
        chunk = read_output(0.2)

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
            time.sleep(0.04)
            chunk = read_output(0.01)
            while chunk:
                record(now(), "o", chunk)
                chunk = read_output(0.01)
        time.sleep(pause)
        chunk = read_output(0.05)
        while chunk:
            record(now(), "o", chunk)
            chunk = read_output(0.05)

    # ── Passes mode: ISS 25544, 240 h ─────────────────────────────────────
    type_text("25544")

    # Tab from NORAD ID to Hours (NORAD → City → Hours)
    send("\t", 0.15)
    send("\t", 0.15)

    type_text("240")

    # Tab to Run button and press Enter
    send("\t", 0.2)
    send("\n", 1.0)

    # Let computation run for a bit (shows loading spinner in header)
    time.sleep(5.0)
    chunk = read_output(0.2)
    while chunk:
        record(now(), "o", chunk)
        chunk = read_output(0.2)

    # Show help overlay (F1)
    send("\x1bOP", 2.5)

    # Dismiss help
    send("\x1b", 1.0)

    # Quit
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
