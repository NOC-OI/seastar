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


if __name__ == "__main__":
    test_add_blobs()
    print("ok")
