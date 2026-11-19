"""EcoTaxa import files (no UI code here).

From the command line, after `seastar ifcb_to_ecotaxa`, to add the blobs to the zips it made:
    python ecotaxa.py --blobs <project folder> <zip> [<zip> ...]
"""
import argparse
import csv
import glob
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project


def table_headers(root):
    """Row 1 (names) and row 2 (types) of every EcoTaxa table of a project: the .tsv files, loose or in zips, of the
    folders with 'ecotaxa' in their name (also archives/ecotaxa_*), not the _OLD ones. Only these two rows are read.
    Returns [{"file": path relative to root, "columns": [...], "types": [...]}]."""
    out = []
    for folder, dirs, files in os.walk(root):
        rel = os.path.relpath(folder, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = [d for d in dirs if "_old" not in d.lower()
                   and ("ecotaxa" in rel.lower() or (depth < 2 and ("ecotaxa" in d.lower() or d == "archives")))]
        if "ecotaxa" not in rel.lower():
            continue
        for f in sorted(files):
            path = os.path.join(folder, f)
            try:
                if f.lower().endswith(".zip"):
                    with zipfile.ZipFile(path) as z:
                        for t in (n for n in z.namelist() if n.lower().endswith(".tsv")):
                            with z.open(t) as fh:
                                out.append(_header(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
                                                   os.path.relpath(path, root) + "!" + t))
                elif f.lower().endswith(".tsv"):
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        out.append(_header(fh, os.path.relpath(path, root)))
            except (OSError, zipfile.BadZipFile) as e:
                out.append({"file": os.path.relpath(path, root), "columns": [], "types": [], "error": str(e)})
    return out


def _header(fh, name):
    rows = []
    for row in csv.reader(fh, delimiter="\t"):
        rows.append(row)
        if len(rows) == 2:
            break
    rows += [[]] * (2 - len(rows))
    return {"file": name.replace("\\", "/"), "columns": rows[0], "types": rows[1]}


def compare_report(headers):
    """Text comparing the EcoTaxa tables of several projects. headers: {project name: table_headers(...)}."""
    lines, sets, types = [], {}, {}
    for name, tables in headers.items():
        good = [t for t in tables if t["columns"]]
        sets[name] = {}
        for t in good:
            sets[name].setdefault(frozenset(t["columns"]), []).append(t["file"])
            for c, ty in zip(t["columns"], t["types"]):
                types.setdefault(c, {}).setdefault(ty, set()).add(name)
        orders = {tuple(t["columns"]) for t in good}
        lines.append(f"{name}: {len(good)} table(s), {len(sets[name])} set(s) of columns, {len(orders)} column order(s)"
                     + (f", {len(tables) - len(good)} unreadable" if len(tables) > len(good) else ""))
        if len(sets[name]) > 1:  # differences inside one project
            base = max(sets[name], key=lambda s: len(sets[name][s]))
            for s, files in sets[name].items():
                if s != base:
                    lines.append(f"    {len(files)} table(s) differ from the {len(sets[name][base])} others "
                                 f"(e.g. {files[0]}): extra columns {sorted(s - base) or 'none'}, "
                                 f"missing columns {sorted(base - s) or 'none'}")
    every = {n: frozenset().union(*s) for n, s in sets.items() if s}  # all the columns of each project
    if not every:
        return "\n".join(lines + ["", "No EcoTaxa table found."])
    union, common = frozenset().union(*every.values()), frozenset.intersection(*every.values())
    lines += ["", f"{len(union)} column names in all, {len(common)} in every project."]
    lines += ["", "Columns not in every project (project: type):"]
    for c in sorted(union - common):
        where = [f"{n}: {'/'.join(sorted(ty for ty, ns in types.get(c, {}).items() if n in ns))}"
                 for n, cols in every.items() if c in cols]
        lines.append(f"    {c:42s} {'; '.join(where)}")
    conflicts = {c: t for c, t in types.items() if len(t) > 1}
    lines += ["", f"Columns with different types ([f] number / [t] text): {len(conflicts) or 'none'}"]
    for c, t in sorted(conflicts.items()):
        lines.append(f"    {c:42s} " + "; ".join(f"{ty} in {', '.join(sorted(ns))}" for ty, ns in sorted(t.items())))
    return "\n".join(lines)


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
            if any(r[rank_col] == "1" for r in body):  # blobs already added: run twice, nothing to do
                dst.writestr(item, data)
                continue
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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blobs", action="store_true", required=True,
                        help="add the WHOI blob of each image as a second image of the object (img_rank 1)")
    parser.add_argument("project", help="IFCB project folder, where whoi_v4_V131_features/blobs/ is")
    parser.add_argument("zips", nargs="+", help="EcoTaxa zips made by SeaSTAR (wildcards allowed)")
    args = parser.parse_args()
    zips = sorted({z for pattern in args.zips for z in (glob.glob(pattern) or [pattern])})
    for z in zips:
        if not os.path.isfile(z):
            print(f"[ERR] No file {z}")
            continue
        print(f"{z}: {add_blobs(z, args.project)} blobs added")


if __name__ == "__main__":
    main()
