"""Publish: validation gate and the rows written to conditions_hourly."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from publish import run as publish

from conftest import SAMPLE_NOW, UTC


class FakeSupabase:
    """Records what publish would send. No network."""
    bucket = "fishing-data"

    def __init__(self):
        self.uploads, self.rows, self.flow = {}, {}, []

    def upload(self, remote, body, content_type):
        self.uploads[remote] = body

    def upsert_rows(self, rows):
        for row in rows:                       # same key replaces, like the table's primary key
            self.rows[(row["spot_id"], row["time_utc"])] = row

    def update_flow(self, update):
        self.flow.append(update)


def test_valid_output_is_uploaded_and_written(collected):
    out, _ = collected
    client = FakeSupabase()
    assert publish.push(out, client, SAMPLE_NOW) == 0
    assert {"conditions/new-brighton-pier.json", "conditions/southshore.json", "river_flow.json", "meta.json"} <= set(client.uploads)
    assert {"state/linz_tides.json", "state/ecan_flow.json"} <= set(client.uploads)
    assert len(client.rows) == 2 * 168
    row = client.rows[("new-brighton-pier", "2026-10-08T10:00:00Z")]
    assert set(row) == {"spot_id", "time_utc", "river_flow_m3s", "updated_at", *publish.CONDITION_COLUMNS}
    assert "score" not in row and "ruleset_version" not in row          # left alone for the scorer (M2)


def test_invalid_output_uploads_nothing(collected, capsys):
    """Acceptance item 7."""
    out, _ = collected
    path = out / "conditions" / "southshore.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["hourly"][5]["sea_temp_c"]
    path.write_text(json.dumps(doc), encoding="utf-8")
    client = FakeSupabase()
    assert publish.push(out, client, SAMPLE_NOW) == 1
    assert client.uploads == {} and client.rows == {} and client.flow == []
    assert "conditions/southshore.json: hourly/5" in capsys.readouterr().out


def test_broken_output_hook_is_caught(tmp_path, spots, monkeypatch):
    from collector import run
    from conftest import replay_fetchers
    monkeypatch.setenv("FISHING_BREAK_OUTPUT", "1")
    out = tmp_path / "out"
    run.collect(out, SAMPLE_NOW, replay_fetchers(spots, SAMPLE_NOW, out / "state"), spots)
    assert publish.push(out, None) == 1


def test_repeat_run_in_the_same_hour_adds_no_rows(collected):
    """Acceptance item 6."""
    out, _ = collected
    client = FakeSupabase()
    publish.push(out, client, SAMPLE_NOW)
    count = len(client.rows)
    publish.push(out, client, SAMPLE_NOW + timedelta(minutes=20))
    assert len(client.rows) == count


def test_past_hours_only_get_their_river_flow_refreshed(collected):
    out, _ = collected
    client = FakeSupabase()
    later = datetime(2026, 10, 8, 12, 5, tzinfo=UTC)                     # two hours after the files were made
    publish.push(out, client, later)
    assert ("new-brighton-pier", "2026-10-08T11:00:00Z") not in client.rows   # 10:00 and 11:00 are past: not rewritten
    assert ("new-brighton-pier", "2026-10-08T12:00:00Z") in client.rows
    assert all(set(u) == {"time_utc", "river_flow_m3s", "updated_at"} for u in client.flow)
    assert all(u["time_utc"] < "2026-10-08T12:00:00Z" for u in client.flow)


def test_hourly_flow_is_the_mean_of_the_readings_in_that_hour(collected):
    out, _ = collected
    series = json.loads((out / "river_flow.json").read_text())["series"]
    readings = [p["flow_m3s"] for p in series if p["time_utc"].startswith("2026-10-08T09:")]
    assert len(readings) == 12
    assert publish.hourly_flow_means(out)["2026-10-08T09:00:00Z"] == round(sum(readings) / 12, 3)
