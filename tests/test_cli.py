import csv
import os
import subprocess
import sys


def run_astrosis(*args):
    env = os.environ.copy()
    env["ASTROSIS_MOCK_GPU"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "astrosis", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def assert_cli_success(result):
    assert result.returncode == 0, result.stderr + result.stdout


def write_states_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def test_backend_command_reports_active_backend():
    result = run_astrosis("backend")

    assert_cli_success(result)
    assert "Active backend" in result.stdout


def test_ephemeris_command_reports_sun_and_moon_positions():
    result = run_astrosis("ephemeris", "--mjd", "60000")

    assert_cli_success(result)
    assert "Sun" in result.stdout
    assert "Moon" in result.stdout


def test_propagate_command_runs_state_vector():
    result = run_astrosis(
        "propagate",
        "7000,0,0,0,7.5,0",
        "--dt",
        "60",
        "--steps",
        "1",
    )

    assert_cli_success(result)
    assert "Propagated after 1 steps" in result.stdout
    assert "Position X" in result.stdout


def test_batch_command_runs_csv_state_file(tmp_path):
    states_path = tmp_path / "states.csv"
    write_states_csv(states_path, [["sat-a", 7000, 0, 0, 0, 7.5, 0]])

    result = run_astrosis("batch", str(states_path), "--dt", "60", "--steps", "1")

    assert_cli_success(result)
    assert "Batch propagated 1 states" in result.stdout
    assert "sat-a" in result.stdout


def test_conjunction_command_runs_primary_secondary_csvs(tmp_path):
    primary_path = tmp_path / "primary.csv"
    secondary_path = tmp_path / "secondary.csv"
    write_states_csv(primary_path, [["sat-a", 7000, 0, 0, 0, 7.5, 0]])
    write_states_csv(secondary_path, [["deb-a", 7000.05, 0, 0, 0, 7.5, 0]])

    result = run_astrosis(
        "conjunction",
        "--primary",
        str(primary_path),
        "--secondary",
        str(secondary_path),
        "--lookahead",
        "60",
        "--step",
        "60",
    )

    assert_cli_success(result)
    assert "conjunction warning" in result.stdout
