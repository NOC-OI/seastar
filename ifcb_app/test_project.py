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
            f.write("softwareVersion: 1.0\nrunTime: 1260\ninhibitTime: 60\n")
        with open(os.path.join(day, "D20260802T010203_IFCB225.adc"), "w") as f:  # 2 images, 1 trigger without image
            f.write("\n".join(",".join(["1"] * 13 + [x, x, w, w] + ["0"] * 7) for x, w in
                              (("1", "10"), ("1", "0"), ("2", "12"))))
        stats = project.bin_stats(root, ["D20260802T010203_IFCB225"])["D20260802T010203_IFCB225"]
        assert stats == {"rois": 2, "ml_analyzed": 5.0, "rois_per_ml": 0.4}, stats  # 0.25 mL/min x 20 min
        assert os.path.isfile(os.path.join(root, "log", project.STATS_CSV))

        from datetime import datetime
        t = lambda b: datetime.strptime(b.split("_")[0], "D%Y%m%dT%H%M%S")
        cruise = {f"D20260802T{h:02d}0000_IFCB225": {"rois": 3000, "ml_analyzed": 4.5, "rois_per_ml": 666}
                  for h in range(0, 8)}
        cruise["D20260802T030000_IFCB225"] = {"rois": 12, "ml_analyzed": 1.0, "rois_per_ml": 12}  # failed
        cruise["D20260802T230000_IFCB225"] = {"rois": 3000, "ml_analyzed": 4.5, "rois_per_ml": 666}  # after 16 h
        checks = {(p["check"], p["bin"]) for p in project.check_bins(cruise, t)}
        assert checks == {("Few images", "D20260802T030000_IFCB225"),
                          ("Small volume analysed", "D20260802T030000_IFCB225"),
                          ("Gap in the sampling", "D20260802T230000_IFCB225")}, checks

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
