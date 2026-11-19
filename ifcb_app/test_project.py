import os
import tempfile

import project


def test_create_and_scan():
    assert project.project_name(" 225", "CE26008", "AR7E") == "ifcb_sn225_ce26008_ar7e"
    assert project.extractor_name("v1.3.1 (commit 1d0687e)") == "whoi_v4_release131"
    assert project.extractor_name(None) == "whoi_v4"
    with tempfile.TemporaryDirectory() as tmp:
        root = project.create_project(tmp, "ifcb_sn225_ce26008_ar7e")
        day = os.path.join(root, "raw", "D20260802")
        os.makedirs(day)
        for ext in (".hdr", ".adc", ".roi"):
            open(os.path.join(day, "D20260802T010203_IFCB225" + ext), "w").close()
        open(os.path.join(day, "D20260802T020000_IFCB225.hdr"), "w").close()  # incomplete bin
        assert project.bins_without_features(root) == ["D20260802T010203_IFCB225"]  # the incomplete bin is left out
        feat = project.feature_file(os.path.join(root, project.FEATURES_DIR), "D20260802T010203_IFCB225")
        os.makedirs(os.path.dirname(feat))
        open(feat, "w").close()
        assert project.bins_without_features(root) == []
        b = "D20260802T010203_IFCB225"
        assert project.feature_file_problem(root, b) == "feature file without a roi_number column"  # empty file
        with open(feat, "w") as f:
            f.write("roi_number,Area\n")
        assert project.feature_file_problem(root, b) == "feature file without any row"
        with open(feat, "w") as f:
            f.write("roi_number,Area\n1,10\n2,12\n")
        assert project.feature_file_problem(root, b) is None
        assert project.feature_file_problem(root, b, {b: {"rois": 3.0}}) == "feature file has 2 rows for 3 images"
        assert project.feature_file_problem(root, b, {b: {"rois": 2.0}}) is None
        assert project.select_bins(root, ["D20260802T010203_IFCB225"]) == (["D20260802T010203_IFCB225"], [])
        assert project.select_bins(root, ["D20260802"]) == (["D20260802T010203_IFCB225"], [])  # a day: its complete bins
        chosen, unknown = project.select_bins(root, ["D20260802T010204_IFCB225", "D20260802T020000_IFCB225"])
        assert chosen == [] and len(unknown) == 2 and "closest: D20260802T010203_IFCB225" in unknown[0], unknown

        with open(os.path.join(day, "D20260802T010203_IFCB225.hdr"), "w") as f:
            f.write("softwareVersion: 1.0\nrunTime: 1260\ninhibitTime: 60\ntriggerCount: 3\nhumidity: 95.5\n"
                    "HumidityAlarmThreshold(%): 90\n")
        with open(os.path.join(day, "D20260802T010203_IFCB225.adc"), "w") as f:  # 2 images, 1 trigger without image
            f.write("\n".join(",".join(["1"] * 13 + [x, y, w, w] + ["0"] * 7) for x, y, w in
                              (("0", "5", "10"), ("1", "1", "0"), ("2", "9", "12"))))
        stats = project.bin_stats(root, ["D20260802T010203_IFCB225"])["D20260802T010203_IFCB225"]
        expected = {"rois": 2, "ml_analyzed": 5.0, "rois_per_ml": 0.4,  # 0.25 mL/min x 20 min
                    "triggers": 3, "images_per_trigger": 0.667, "run_time": 1260, "humidity": 95.5, "humidity_alarm": 90,
                    "stream_y_median": 7, "cut_left": 1, "right_edge": 14, "cut_right": 1}
        assert {k: stats[k] for k in expected} == expected, stats
        assert os.path.isfile(os.path.join(root, "log", project.STATS_CSV))
        assert project.load_stats(root)["D20260802T010203_IFCB225"] == stats  # saved and read back
        assert [r["x"] for r in project.roi_positions(root, "D20260802T010203_IFCB225")] == [0, 2]

        from datetime import datetime
        t = lambda b: datetime.strptime(b.split("_")[0], "D%Y%m%dT%H%M%S")
        cruise = {f"D20260802T{h:02d}0000_IFCB225": {"rois": 3000, "ml_analyzed": 4.5, "rois_per_ml": 666}
                  for h in range(0, 8)}
        cruise["D20260802T030000_IFCB225"] = {"rois": 12, "ml_analyzed": 1.0, "rois_per_ml": 12}  # failed
        cruise["D20260802T230000_IFCB225"] = {"rois": 3000, "ml_analyzed": 4.5, "rois_per_ml": 666}  # after 16 h
        checks = {(p["check"], p["bin"]) for p in project.check_bins(cruise, t)}
        assert checks == {("Small volume analysed", "D20260802T030000_IFCB225"),
                          ("Gap in the sampling", "D20260802T230000_IFCB225")}, checks

        ok = {"rois": 3000, "ml_analyzed": 4.5, "rois_per_ml": 666, "triggers": 2950, "images_per_trigger": 1.02,
              "run_time": 1200, "humidity": 22, "humidity_alarm": 90, "stream_y_median": 560, "stream_y_spread": 440,
              "cut_left": 6, "right_edge": 1358, "cut_right": 9}
        cruise = {f"D20260802T{h:02d}0000_IFCB225": dict(ok, stream_y_median=550 + h) for h in range(0, 8)}
        bad = {"D20260802T010000_IFCB225": {"images_per_trigger": 0.8},
               "D20260802T020000_IFCB225": {"humidity": 93},
               "D20260802T030000_IFCB225": {"stream_y_median": 700},
               "D20260802T040000_IFCB225": {"stream_y_spread": 800},
               "D20260802T050000_IFCB225": {"cut_right": 400},
               "D20260802T060000_IFCB225": {"run_time": 600, "ml_analyzed": 2.0}}
        for b, change in bad.items():
            cruise[b].update(change)
        found = {(p["bin"], p["check"]) for p in project.check_bins(cruise, t)}
        import csv
        qc_file = project.write_qc(root, cruise, project.check_bins(cruise, t))
        rows = {r["bin"]: r for r in csv.DictReader(open(qc_file, encoding="utf-8"))}
        assert rows["D20260802T060000_IFCB225"]["sample_qc_flags"] == "Small volume analysed; Short run", rows
        r6 = rows["D20260802T060000_IFCB225"]
        assert r6["sample_qc_run_time_s_flag"] == "4" and r6["sample_qc_ml_analyzed_flag"] == "3", r6
        assert r6["sample_qc_flag"] == "4" and "sample_qc_images_flag" not in r6 and "sample_qc_humidity_pct_flag" not in r6
        assert rows["D20260802T020000_IFCB225"]["sample_qc_flag"] == "1"  # humidity 93 %: no flag any more
        assert rows["D20260802T050000_IFCB225"]["sample_qc_flag"] == "3"  # many cut images: doubtful
        assert rows["D20260802T070000_IFCB225"]["sample_qc_flag"] == "1"
        assert 20 <= project.count_sample_columns(root) <= project.SAMPLE_COLUMNS_MAX
        assert rows["D20260802T070000_IFCB225"]["sample_qc_flags"] == "ok" and rows["D20260802T070000_IFCB225"]["sample_qc_images"] == "3000"
        binds = project.qc_bindcols(root)
        assert "sample_qc_flags:t:sample_qc_flags" in binds and "sample_qc_cut_images_pct:f:sample_qc_cut_images_pct" in binds
        assert found == {("D20260802T010000_IFCB225", "Few images per trigger"),
                         ("D20260802T030000_IFCB225", "Stream shifted"),
                         ("D20260802T040000_IFCB225", "Stream wide"),
                         ("D20260802T050000_IFCB225", "Many cut images"),
                         ("D20260802T060000_IFCB225", "Short run"),
                         ("D20260802T060000_IFCB225", "Small volume analysed")}, found

        s = project.scan_project(root)
        assert s["days"]["D20260802"] == {"bins": 2, "complete_bins": 1, "features": 1, "ecotaxa_zips": 0}
        assert s["name_info"] == {"serial": "225", "cruise_id": "ce26008", "cruise_name": "ar7e"}
        assert all(s["present"].values())

        try:
            project.create_project(tmp, "ifcb_sn225_ce26008_ar7e")
            assert False, "must refuse to overwrite"
        except FileExistsError:
            pass


def test_warnings():
    import json
    project.latest_whoi_release = lambda: ("v1.4.0", "2027-01-01")  # no network in tests
    project.whoi_version = lambda: "v1.3.1 (commit 1d0687e)"
    with tempfile.TemporaryDirectory() as tmp:
        root = project.create_project(tmp, "ifcb_sn225_ce26008_ar7e")
        assert project.warnings(root, "all")[0].startswith("No IFCB bin")
        day = os.path.join(root, "raw", "D20260802")
        os.makedirs(day)
        for ext in (".hdr", ".adc", ".roi"):
            open(os.path.join(day, "D20260802T010203_IFCB225" + ext), "w").close()
        open(os.path.join(day, "D20260802T020000_IFCB225.roi"), "w").close()
        with open(os.path.join(root, "log", "features_status.json"), "w") as f:
            json.dump({"whoi_version": "v1.3.0", "done": 3, "total": 9, "errors": [], "finished": None}, f)
        w = project.warnings(root, "features")
        assert "D20260802T020000_IFCB225 (no .hdr, .adc)" in w[0], w
        assert any("not the one of the last extraction" in x for x in w) and any("v1.4.0" in x for x in w)
        assert any("did not finish (3 / 9 bins)" in x for x in w)
        w = project.warnings(root, "ecotaxa")
        assert any("1 bin(s) without features" in x for x in w) and any("No metadata file" in x for x in w)
        assert any("No metadata check yet" in x for x in w), w
        with open(os.path.join(root, "log", "bins_check_20261119_100000.txt"), "w") as f:
            f.write("Bins check\nFrom: x\n9 bins, 0 point(s) to check\n")
        assert not any("bins check" in x for x in project.warnings(root, "ecotaxa"))


if __name__ == "__main__":
    test_create_and_scan()
    test_warnings()
    print("ok")
