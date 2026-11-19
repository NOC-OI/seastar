import datetime
import os
import shutil
import tempfile

import metadata

B1, B2, B3 = "D20250610T081500_IFCB225", "D20250610T093000_IFCB225", "D20250611T120000_IFCB225"


def test_build():
    rows = [  # as read from an Excel sheet: dates, times and 21.0 for an integer
        {"File": B1 + ".roi", "Latitude": 48.97, "Depth min (m)": 30.0, "Niskin date": datetime.datetime(2025, 6, 10),
         "Niskin time": datetime.time(7, 5), "Niskin": 21.0, "Salinity": "35.4"},
        {"File": B2, "Latitude": 48.98, "Depth min (m)": None, "Niskin date": None, "Niskin time": None, "Niskin": None,
         "Salinity": "n/a"},
        {"File": "D20990101T000000_IFCB225", "Latitude": 1.0},
    ]
    cols = list(rows[0])
    assert metadata.guess_bin_column(cols, rows) == "File"
    fields = {f["field"]: f for f in metadata.load_fields()}
    assert metadata.guess_source(fields["lat"], cols) == "Latitude"
    assert metadata.guess_source(fields["depth_min"], cols) == "Depth min (m)"
    assert metadata.guess_source(fields["salinity"], cols) == "Salinity"
    assert metadata.guess_source(fields["niskin_id"], cols) == "Niskin"
    assert metadata.guess_source(fields["depth_max"], ["Depth (m)", "Temp"]) == "Depth (m)"
    assert metadata.guess_source(fields["chla"], cols) is None
    assert metadata.guess_source(fields["niskin_date"], ["niskin_id", "date", "niskin_salinity_pss"]) is None

    mapping = {"lat": {"source": "Latitude", "default": ""}, "depth_min": {"source": "Depth min (m)", "default": "5"},
               "niskin_date": {"source": "Niskin date", "default": ""}, "niskin_time": {"source": "Niskin time", "default": ""},
               "niskin_id": {"source": "Niskin", "default": ""}, "salinity": {"source": "Salinity", "default": ""}}
    columns, out, problems = metadata.build(rows, "File", mapping, [B1, B2, B3])
    assert columns["sample_depth_min"] == columns["object_depth_min"] == "f"
    assert columns["sample_date"] == columns["sample_time"] == columns["sample_niskin_time"] == "t"
    r1, r2, r3 = out
    assert (r1["sample_date"], r1["sample_time"]) == ("2025-06-10", "08:15:00")  # from the bin name
    assert (r1["sample_niskin_date"], r1["sample_niskin_time"]) == ("2025-06-10", "07:05:00")
    assert r1["sample_depth_min"] == r1["object_depth_min"] == "30"
    assert r2["sample_depth_min"] == "5"  # empty cell: the constant
    assert r3["object_depth_min"] == "5" and r3["object_lat"] == ""  # bin not in the spreadsheet
    assert r1["sample_niskin_id"] == "21"
    assert r2["sample_salinity_pss"] == ""
    checks = {p["check"] for p in problems}
    assert any("n/a" in p["detail"] for p in problems)
    assert "Bin without metadata" in checks and "Bin not in raw/" in checks
    assert "sample_niskin_date:t:sample_niskin_date" in metadata.bindcol_args(columns)


def test_add_field():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "fields.csv")
    shutil.copy(metadata.FIELDS_CSV, path)
    n = len(metadata.load_fields(path))
    fields = metadata.add_field("Oxygen", "sample_oxygen_umol_kg", "f", "umol kg-1", path=path)
    assert len(fields) == n + 1 and metadata.load_fields(path)[-1]["field"] == "oxygen"
    for bad in (("oxygen", "sample_oxygen2", "f"), ("o2", "Oxygen", "f"), ("o2", "sample_o2", "x"),
                ("o2", "object_lat", "f")):
        try:
            metadata.add_field(*bad, path=path)
            assert False, bad
        except ValueError:
            pass
    shutil.rmtree(tmp)


def test_checks():
    """Typo in a bin name, out of range, position jump, Niskin after analysis."""
    bins = [B1, B2, B3]
    rows = [{"bin": "D20250610T081200_IFCB225", "lat": "48.9", "lon": "-16.5", "sal": "35.4", "nd": "", "nt": ""},  # B1 typed 3 min early
            {"bin": B2, "lat": "48.9", "lon": "-16.5", "sal": "350", "nd": "20250610", "nt": "101500"},  # sal x10, Niskin after
            {"bin": B3, "lat": "84.9", "lon": "-16.5", "sal": "35.4", "nd": "2025-06-11", "nt": "06:00"}]  # lat typo: jump
    mapping = {"lat": {"source": "lat"}, "lon": {"source": "lon"}, "salinity": {"source": "sal"},
               "niskin_date": {"source": "nd"}, "niskin_time": {"source": "nt"}}
    columns, out, problems = metadata.build(rows, "bin", mapping, bins)
    by_check = {p["check"]: p for p in problems}
    assert "probably " + B1 in by_check["Bin name typo?"]["detail"] and "3 min" in by_check["Bin name typo?"]["detail"]
    assert "Bin without metadata" not in by_check  # B1 is explained by the typo, not reported twice
    assert by_check["Out of range"]["bin"] == B2
    assert by_check["Niskin after analysis"]["bin"] == B2
    assert by_check["Position jump"]["bin"] == B3
    assert metadata.parse_datetime("20250610", "070500") == datetime.datetime(2025, 6, 10, 7, 5)
    assert metadata.parse_datetime("", "07:05") is None
    tmp = tempfile.mkdtemp()
    path = metadata.write_report(tmp, problems, len(out), "test.xlsx")
    text = open(path, encoding="utf-8").read()
    assert "Bin name typo?" in text and "4 point(s)" in text, text
    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_build()
    test_checks()
    test_add_field()
    print("ok")
