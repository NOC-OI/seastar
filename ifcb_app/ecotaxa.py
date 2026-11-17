"""EcoTaxa import files (no UI code here)."""
import csv
import io
import os
import zipfile

import project


def add_blobs(zip_path, root):
    """Add the WHOI blob of each image to an EcoTaxa zip made by SeaSTAR, as a second image of the object.

    EcoTaxa takes several images per object as several rows with the same object_id: the image (img_rank 0) and
    here its blob (img_rank 1), with the same measurements. The zip is rewritten in place.
    Returns the number of blobs added."""
    tmp = zip_path + ".tmp"
    added = 0
    blob_zips = {}
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item)
            if not item.filename.endswith(".tsv"):
                dst.writestr(item, data)
                continue
            folder = os.path.dirname(item.filename)
            rows = list(csv.reader(io.StringIO(data.decode("utf-8")), delimiter="\t"))
            header, types, body = rows[0], rows[1], rows[2:]
            name_col, rank_col, id_col = (header.index(c) for c in ("img_file_name", "img_rank", "object_id"))
            out = [header, types]
            for r in body:
                out.append(r)
                if r[rank_col] not in ("0", "0.0"):
                    continue
                bin_name = r[id_col].rsplit("_", 1)[0]
                if bin_name not in blob_zips:
                    path = project.blob_zip(root, bin_name)
                    blob_zips[bin_name] = zipfile.ZipFile(path) if os.path.isfile(path) else None
                blobs, blob_name = blob_zips[bin_name], r[id_col] + ".png"
                if blobs is None or blob_name not in blobs.namelist():
                    continue
                file_name = r[id_col] + "_blob.png"
                dst.writestr(f"{folder}/{file_name}" if folder else file_name, blobs.read(blob_name))
                blob_row = list(r)
                blob_row[name_col], blob_row[rank_col] = file_name, "1"
                out.append(blob_row)
                added += 1
            text = io.StringIO()
            csv.writer(text, delimiter="\t", lineterminator="\n").writerows(out)
            dst.writestr(item, text.getvalue())
    for z in blob_zips.values():
        if z:
            z.close()
    os.replace(tmp, zip_path)
    return added
