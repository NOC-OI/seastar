"""Feature extraction of an IFCB project with WHOI ifcb-features v1.3.1, run in the background by the app.

    python extract_features.py <project folder> [--workers N] [--bins BIN_OR_DAY ...]

Bins that already have a feature file are skipped. With --bins, only those bins (or all the bins of a day,
e.g. D20260729) are done, even if they have a feature file: its new version replaces it. Outputs, as WHOI's extract_features_batch.py:
    whoi_v4_V131_features/features/<day>/<bin>_features_v4.csv  (+ multiblob/)
    whoi_v4_V131_features/blobs/<day>/<bin>_blobs_v4.zip
    whoi_v4_V131_features/feature_extractor_versions.csv  (bin, extractor, release: joined by SeaSTAR per bin)
    log/bin_stats.csv  (images and mL analysed of each bin, for the quality check figures)
Progress is written to log/features_status.json (read by the app) and log/features_<date>.log.
"""
import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project


def extract_one(raw_dir, out_dir, bin_name, raw_path):
    from whoi.extract_slim_features import configure_output, extract_and_save_all_features
    configure_output(False)
    day = bin_name[:9]
    feature_file = project.feature_file(out_dir, bin_name)
    before = os.path.getmtime(feature_file) if os.path.isfile(feature_file) else None  # a bin done again (--bins)
    extract_and_save_all_features(raw_dir, os.path.join(out_dir, "features", day), bins=[bin_name],
                                  blobs_directory=os.path.join(out_dir, "blobs", day))
    if not os.path.isfile(feature_file) or os.path.getmtime(feature_file) == before:
        raise RuntimeError("no feature file written (bin unreadable or without images)")
    return project.read_bin_stats(raw_path, bin_name)  # images and mL analysed, for the QC figures


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--bins", nargs="+", metavar="BIN_OR_DAY",
                        help="only these bins (names, or days DYYYYMMDD), done again even if they have features")
    args = parser.parse_args()

    root = os.path.abspath(args.project)
    raw_dir, out_dir, log_dir = (os.path.join(root, d) for d in ("raw", project.FEATURES_DIR, "log"))
    if args.bins:
        todo, unknown = project.select_bins(root, args.bins)
        if unknown:
            sys.exit("Not a complete bin or day of raw/: " + "; ".join(unknown))
    else:
        todo = project.bins_without_features(root)
    os.makedirs(log_dir, exist_ok=True)
    raw_paths = project.raw_bin_paths(root, todo)
    stats = project.load_stats(root)
    version = project.whoi_version()
    status = {"pid": os.getpid(), "whoi_version": version,
              "started": datetime.now().isoformat(timespec="seconds"), "workers": args.workers,
              "total": len(todo), "done": 0, "errors": [], "finished": None}
    status_path = os.path.join(log_dir, "features_status.json")
    log = open(os.path.join(log_dir, f"features_{datetime.now():%Y%m%d_%H%M%S}.log"), "a", encoding="utf-8")

    def save():
        tmp = status_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status, f)
        os.replace(tmp, status_path)  # the app never reads a half-written file

    def say(text):  # the log file and the screen
        log.write(text)
        print(text, end="", flush=True)

    warnings = project.warnings(root, "features")  # before save(): it reads the status of the last run
    save()
    for w in warnings:
        say(f"WARNING: {w}\n")
    say(f"WHOI ifcb-features {version}, {len(todo)} bins to process with {args.workers} workers\n")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(extract_one, raw_dir, out_dir, b, raw_paths[b]): b for b in todo}
        for fut in as_completed(futures):
            b = futures[fut]
            try:
                stats[b] = fut.result()
                project.record_extractor_version(out_dir, b, version)
                say(f"[{status['done'] + 1}/{len(todo)}] {b} ok\n")
            except Exception as e:
                status["errors"].append(f"{b}: {e}")
                say(f"[{status['done'] + 1}/{len(todo)}] {b} ERROR {e}\n")
            status["done"] += 1
            log.flush()
            save()
            if status["done"] % 20 == 0:
                project.save_stats(root, stats)
    project.save_stats(root, stats)
    status["finished"] = datetime.now().isoformat(timespec="seconds")
    save()
    say(f"Finished in {time.time() - t0:.0f} s, {len(status['errors'])} errors\n")
    for e in status["errors"]:
        say(f"  failed: {e}\n")
    log.close()


if __name__ == "__main__":
    main()
