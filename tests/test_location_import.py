"""Lieux des photos sans GPS : chronologie Google Maps et Google Takeout."""
import io
import json
import time
import zipfile
from datetime import datetime

from utils import location_import as li


def local(text):
    return time.mktime(datetime.fromisoformat(text).timetuple())


def iso_utc(ts):
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def test_new_timeline_format_matches_photos_by_time(tmp_path, monkeypatch):
    monkeypatch.setattr(li, "LOCATIONS_FILE", tmp_path / "places.json")
    t = local("2026-07-16T14:30:00")
    timeline = {"semanticSegments": [
        {"startTime": iso_utc(t - 3600), "endTime": iso_utc(t + 3600), "visit": {"topCandidate": {"placeLocation": {"latLng": "43.4832°, -1.5586°"}}}},
        {"startTime": iso_utc(t + 7200), "endTime": iso_utc(t + 9000), "timelinePath": [{"point": "48.8566°, 2.3522°", "time": iso_utc(t + 8000)}]},
    ]}
    index = {"gdrive/20260716_143851.jpg": {"date": "2026-07-16T14:38:51"},
             "gdrive/20260716_165000.jpg": {"date": "2026-07-16T16:43:00"},
             "gdrive/20260101_120000.jpg": {"date": "2026-01-01T12:00:00"},   # rien ce jour-là
             "gdrive/deja.jpg": {"date": "2026-07-16T14:38:51", "lat": 1.0, "lon": 2.0}}
    result = li.import_files([("Timeline.json", json.dumps(timeline).encode())], index)
    found = li.load_locations()
    assert found["gdrive/20260716_143851.jpg"] == {"lat": 43.4832, "lon": -1.5586, "how": "timeline"}
    assert found["gdrive/20260716_165000.jpg"]["lat"] == 48.8566
    assert "gdrive/20260101_120000.jpg" not in found and "gdrive/deja.jpg" not in found
    assert result["added"] == 2 and result["without"] == 1
    merged = li.merge_into({k: dict(v) for k, v in index.items()})
    assert merged["gdrive/20260716_143851.jpg"]["lat"] == 43.4832 and merged["gdrive/deja.jpg"]["lat"] == 1.0


def test_records_and_semantic_history_formats():
    records = {"locations": [{"latitudeE7": 485000000, "longitudeE7": 23000000, "timestamp": "2020-05-01T10:00:00Z"},
                             {"latitudeE7": 0, "longitudeE7": 0, "timestampMs": "1588327200000"}]}
    assert li.timeline_points(records) == [(li._ts("2020-05-01T10:00:00Z"), 48.5, 2.3)]
    semantic = {"timelineObjects": [{"placeVisit": {"location": {"latitudeE7": 450000000, "longitudeE7": 50000000},
                                                    "duration": {"startTimestamp": "2020-06-01T08:00:00Z", "endTimestamp": "2020-06-01T09:00:00Z"}}}]}
    assert len(li.timeline_points(semantic)) == 2


def test_takeout_zip_matches_by_file_name(tmp_path, monkeypatch):
    monkeypatch.setattr(li, "LOCATIONS_FILE", tmp_path / "places.json")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Takeout/Google Photos/Vacances/20260716_143851.jpg.json",
                         json.dumps({"title": "20260716_143851.jpg", "photoTakenTime": {"timestamp": "1784205531"},
                                     "geoData": {"latitude": 43.48, "longitude": -1.55}}))
        archive.writestr("Takeout/Google Photos/Vacances/sans_lieu.jpg.json",
                         json.dumps({"title": "sans_lieu.jpg", "geoData": {"latitude": 0.0, "longitude": 0.0}}))
        archive.writestr("Takeout/Google Photos/Vacances/20260716_143851.jpg", b"photo")
    index = {"invités/20260716_143851_1786286364_19c8.jpg": {"date": "2026-07-16T14:38:51"},
             "gdrive/sans_lieu.jpg": {}}
    result = li.import_files([("takeout.zip", buffer.getvalue())], index)
    assert li.load_locations() == {"invités/20260716_143851_1786286364_19c8.jpg": {"lat": 43.48, "lon": -1.55, "how": "takeout"}}
    assert result["takeout"] == 1


def test_locations_api(admin_client, monkeypatch, tmp_path):
    from utils import photo_index
    monkeypatch.setattr(li, "LOCATIONS_FILE", tmp_path / "places.json")
    monkeypatch.setattr(photo_index, "load", lambda: {"gdrive/a.jpg": {"date": "2026-07-16T14:38:51"}})
    same = {"Sec-Fetch-Site": "same-origin"}
    assert admin_client.get("/api/locations").get_json()["with_place"] == 0
    bad = admin_client.post("/api/locations/import", data={"files": (io.BytesIO(b"{}"), "vide.json")}, content_type="multipart/form-data", headers=same)
    assert bad.status_code == 400
    t = local("2026-07-16T14:40:00")
    timeline = {"semanticSegments": [{"timelinePath": [{"point": "43.5°, -1.5°", "time": iso_utc(t)}]}]}
    r = admin_client.post("/api/locations/import", data={"files": (io.BytesIO(json.dumps(timeline).encode()), "Timeline.json")},
                          content_type="multipart/form-data", headers=same).get_json()
    assert r["success"] and r["added"] == 1
    assert admin_client.delete("/api/locations", headers=same).get_json()["success"] and li.load_locations() == {}
