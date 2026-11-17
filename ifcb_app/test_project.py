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

        s = project.scan_project(root)
        assert s["days"]["D20260802"] == {"bins": 2, "complete_bins": 1, "features": 1, "ecotaxa_zips": 0}
        assert s["name_info"] == {"serial": "225", "cruise_id": "ce26008", "cruise_name": "ar7e"}
        assert all(s["present"].values())

        try:
            project.create_project(tmp, "ifcb_sn225_ce26008_ar7e")
            assert False, "must refuse to overwrite"
        except FileExistsError:
            pass


if __name__ == "__main__":
    test_create_and_scan()
    print("ok")
