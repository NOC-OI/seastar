"""EcoTaxa import zips of an IFCB project with SeaSTAR, one zip per bin, run in the background by the app.

    python make_ecotaxa.py <project folder> --operator "Full Name" [--qcdby "Full Name"] [--project-name NAME]
                           [--ship SHIP] [--cruise CRUISE] [--blobs] [--workers N]

Each zip has the images, the WHOI features, the metadata of section 3 (metadata/metadata_ecotaxa.csv) and the
feature extractor version; with --blobs, the blob of each image as a second image (img_rank 1).
Bins that already have their zip are skipped. Zips: ecotaxa_import_zip_seastar/<CRUISE NAME>_<bin>.zip.
Progress is written to log/ecotaxa_status.json (read by the app) and log/ecotaxa_<date>.log.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecotaxa
import metadata
import project

ZIP_DIR = "ecotaxa_import_zip_seastar"


def zip_path(root, bin_name):
    info = project.scan_name(root)
    prefix = info["cruise_name"].upper() + "_" if info else ""
    return os.path.join(root, ZIP_DIR, prefix + bin_name + ".zip")


def plan(root):
    """(bins to do, bins without features, bins already done)."""
    bins = project.complete_bins(root)
    without = set(project.bins_without_features(root))
    with_features = [b for b in bins if b not in without]
    zip_dir = os.path.join(root, ZIP_DIR)
    made = set(os.listdir(zip_dir)) if os.path.isdir(zip_dir) else set()  # one listing: a check per bin is slow on Y:
    done = [b for b in with_features if os.path.basename(zip_path(root, b)) in made]
    return [b for b in with_features if b not in set(done)], sorted(without), done


def one_row_csv(path, folder, name, bin_name, key="bin"):
    """The rows of `path` for this bin only, in a small CSV: SeaSTAR reads a whole metadata table for every image."""
    if not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r[key] == bin_name]
        fields = reader.fieldnames
    if not rows:
        return None
    out = os.path.join(folder, name)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows[-1:])  # the last row: a re-extracted bin has its latest version last
    return out


def make_one(root, bin_name, raw_path, args, bindcols):
    features_dir = os.path.join(root, project.FEATURES_DIR)
    out = zip_path(root, bin_name)
    with tempfile.TemporaryDirectory() as tmp:
        inputs = [raw_path + ext for ext in (".hdr", ".adc", ".roi")]
        inputs.append(project.feature_file(features_dir, bin_name))
        for p in (one_row_csv(os.path.join(root, "metadata", metadata.OUTPUT_CSV), tmp, "metadata.csv", bin_name),
                  one_row_csv(os.path.join(features_dir, project.VERSIONS_CSV), tmp, "versions.csv", bin_name)):
            if p:
                inputs.append(p)
        cmd = [sys.executable, "-m", "seastartool", "ifcb_to_ecotaxa", "-i", *inputs, "--operator", args.operator]
        for option, value in (("--qcdby", args.qcdby), ("--project", args.project_name), ("--ship", args.ship),
                              ("--cruise", args.cruise)):
            if value:
                cmd += [option, value]
        cmd += ["--bindcol", "feature_extractor_release:t:process_feature_extractor_release", *bindcols, "-o", out]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    errors = [l for l in run.stdout.splitlines() if l.startswith("[ERR]")]
    if run.returncode != 0 or not os.path.isfile(out):
        last = (run.stderr.strip().splitlines() or run.stdout.strip().splitlines() or ["no message"])[-1]
        if os.path.isfile(out):
            os.remove(out)  # never leave half a zip: the bin is done again next time
        raise RuntimeError(f"SeaSTAR failed: {last}")
    blobs = ecotaxa.add_blobs(out, root) if args.blobs else 0
    return f"{len(errors)} missing values" + (f", {blobs} blobs" if args.blobs else "")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--operator", required=True, help="Full name of the person who ran the IFCB")
    parser.add_argument("--qcdby", help="Full name of the person who checked the metadata")
    parser.add_argument("--project-name", help="sample_project, e.g. ce26008_AR7E")
    parser.add_argument("--ship")
    parser.add_argument("--cruise")
    parser.add_argument("--blobs", action="store_true", help="add the blob of each image as a second image (img_rank 1)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = parser.parse_args()

    root = os.path.abspath(args.project)
    log_dir = os.path.join(root, "log")
    os.makedirs(os.path.join(root, ZIP_DIR), exist_ok=True)
    todo, _, _ = plan(root)
    raw = project.raw_bin_paths(root, todo)
    columns = metadata.read_choices(os.path.join(root, "metadata")).get("columns", {})
    bindcols = metadata.bindcol_args(columns) if os.path.isfile(os.path.join(root, "metadata", metadata.OUTPUT_CSV)) else []
    status = {"pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds"), "workers": args.workers,
              "blobs": args.blobs, "total": len(todo), "done": 0, "errors": [], "finished": None}
    status_path = os.path.join(log_dir, "ecotaxa_status.json")
    log = open(os.path.join(log_dir, f"ecotaxa_{datetime.now():%Y%m%d_%H%M%S}.log"), "a", encoding="utf-8")

    def save():
        tmp = status_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status, f)
        os.replace(tmp, status_path)

    def say(text):  # the log file and the screen
        log.write(text)
        print(text, end="", flush=True)

    warnings = project.warnings(root, "ecotaxa")  # before save(): it reads the status of the last run
    save()
    for w in warnings:
        say(f"WARNING: {w}\n")
    say(f"SeaSTAR EcoTaxa zips, {len(todo)} bins, {args.workers} at a time, blobs: {args.blobs}, "
              f"metadata columns: {len(bindcols)}\n")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:  # threads: the work is in the SeaSTAR processes
        futures = {pool.submit(make_one, root, b, raw[b], args, bindcols): b for b in todo}
        for fut in as_completed(futures):
            b = futures[fut]
            try:
                say(f"[{status['done'] + 1}/{len(todo)}] {b} ok, {fut.result()}\n")
            except Exception as e:
                status["errors"].append(f"{b}: {e}")
                say(f"[{status['done'] + 1}/{len(todo)}] {b} ERROR {e}\n")
            status["done"] += 1
            log.flush()
            save()
    status["finished"] = datetime.now().isoformat(timespec="seconds")
    save()
    say(f"Finished in {time.time() - t0:.0f} s, {len(status['errors'])} errors\n")
    for e in status["errors"]:
        say(f"  failed: {e}\n")
    log.close()


if __name__ == "__main__":
    main()
