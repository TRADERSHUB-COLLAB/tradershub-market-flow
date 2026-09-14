from validation.cli import main


def test_cli_run_day_and_report(tmp_path, capsys):
    db = tmp_path / "pulses.sqlite"

    rc = main(["--db", str(db), "run-day", "--date", "2026-09-14"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[us 2026-09-14]" in out
    assert "[asia 2026-09-14]" in out
    assert "[europe 2026-09-14]" in out

    rc = main(["--db", str(db), "report", "--limit", "10"])
    assert rc == 0
    assert "Market Pulse validation report" in capsys.readouterr().out

    rc = main(["--db", str(db), "list", "--limit", "10"])
    assert rc == 0
    assert "2026-09-14" in capsys.readouterr().out

    rc = main(["--db", str(db), "replay", "--limit", "10"])
    # No changes since we just recorded, so replay must be a clean exit.
    assert rc == 0
    assert "0 changed" in capsys.readouterr().out


def test_cli_run_day_specific_session(tmp_path, capsys):
    db = tmp_path / "pulses.sqlite"
    rc = main(["--db", str(db), "run-day", "--date", "2026-09-14", "--sessions", "us"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[us 2026-09-14]" in out
    assert "[asia" not in out
