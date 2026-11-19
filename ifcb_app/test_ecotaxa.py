import csv
import io
import os
import tempfile
import zipfile

import ecotaxa
import project

B = "D20260802T010203_IFCB225"


def test_add_blobs():
    with tempfile.TemporaryDirectory() as root:
        blobs = project.blob_zip(root, B)
        os.makedirs(os.path.dirname(blobs))
        with zipfile.ZipFile(blobs, "w") as z:  # blobs of ROIs 2 and 3, not of ROI 4
            z.writestr(f"{B}_00002.png", b"blob2")
            z.writestr(f"{B}_00003.png", b"blob3")
        tsv = "object_id\timg_file_name\timg_rank\tobject_area\n[t]\t[t]\t[f]\t[f]\n" + "".join(
            f"{B}_{n:05d}\t{B}_{n:05d}.png\t0\t{n * 10}\n" for n in (2, 3, 4))
        out = os.path.join(root, "upload.zip")
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("upload_part1/ecotaxa_x.tsv", tsv)
            for n in (2, 3, 4):
                z.writestr(f"upload_part1/{B}_{n:05d}.png", b"image")

        assert ecotaxa.add_blobs(out, root) == 2
        with zipfile.ZipFile(out) as z:
            assert z.read(f"upload_part1/{B}_00002_blob.png") == b"blob2"
            rows = list(csv.reader(io.StringIO(z.read("upload_part1/ecotaxa_x.tsv").decode()), delimiter="\t"))
        assert rows[1] == ["[t]", "[t]", "[f]", "[f]"]
        assert rows[2:] == [[f"{B}_00002", f"{B}_00002.png", "0", "20"], [f"{B}_00002", f"{B}_00002_blob.png", "1", "20"],
                            [f"{B}_00003", f"{B}_00003.png", "0", "30"], [f"{B}_00003", f"{B}_00003_blob.png", "1", "30"],
                            [f"{B}_00004", f"{B}_00004.png", "0", "40"]], rows
        assert ecotaxa.add_blobs(out, root) == 0  # a second run adds nothing
        with zipfile.ZipFile(out) as z:
            assert len(z.read("upload_part1/ecotaxa_x.tsv").decode().splitlines()) == 7



def test_compare():
    with tempfile.TemporaryDirectory() as tmp:
        def table(project_dir, folder, name, header, types, in_zip=True):
            d = os.path.join(tmp, project_dir, folder)
            os.makedirs(d, exist_ok=True)
            text = "\t".join(header) + "\n" + "\t".join(types) + "\nx\n"
            if in_zip:
                with zipfile.ZipFile(os.path.join(d, name + ".zip"), "w") as z:
                    z.writestr(name + "/ecotaxa.tsv", text)
            else:
                open(os.path.join(d, name + ".tsv"), "w").write(text)
        table("a", "ecotaxa_import_zip_seastar", "b1", ["object_id", "object_lon", "acq_status"], ["[t]", "[f]", "[f]"])
        table("a", "ecotaxa_import_zip_seastar", "b2", ["object_id", "object_lon"], ["[t]", "[f]"], in_zip=False)
        table("a", "ecotaxa_import_zips_OLD", "old", ["ignored"], ["[t]"])
        table("b", "archives/ecotaxa_import_zips", "d1", ["object_id", "sample_long", "acq_status"], ["[t]", "[f]", "[t]"])
        heads = {n: ecotaxa.table_headers(os.path.join(tmp, n)) for n in ("a", "b")}
        assert len(heads["a"]) == 2 and len(heads["b"]) == 1  # _OLD left out, archives read
        text = ecotaxa.compare_report(heads)
        assert "a: 2 table(s), 2 set(s) of columns" in text, text
        assert "object_lon" in text and "sample_long" in text
        assert "acq_status" in text and "[f] in a; [t] in b" in text, text
        assert "2 in every project" in text, text  # object_id, acq_status


if __name__ == "__main__":
    test_add_blobs()
    test_compare()
    print("ok")
