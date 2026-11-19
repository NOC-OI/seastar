"""Step 4 on the command line: the quality check figures and the bin checks of a project.

    python make_figures.py <project folder>

Saves the map and the figures against time and depth as PNG in figures/ (needs vl-convert-python), and the bins
that look failed and the gaps in the sampling in log/bins_check_<date>.txt. In each figure, only the bins flagged for
a reason shown by that figure are coloured, and the legend names the reason (the metadata points come from the last
log/metadata_check_<date>.txt). The instrument values (images per trigger, stream position and width, cut images,
humidity) are plotted against time; python show_positions.py <project> <bin> shows the ROI positions of one bin. Uses the image counts of
log/bin_stats.csv, made during the feature extraction; the bins not counted yet are counted first (their .adc files
are read once: slow on a network drive). The metadata come from metadata/metadata_ecotaxa.csv (step 3).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metadata
import project
import qc


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    root = os.path.abspath(parser.parse_args().project)

    bins = project.complete_bins(root)
    if not bins:
        sys.exit(f"No complete bin in {os.path.join(root, 'raw')}")
    known = project.load_stats(root)
    missing = sum(1 for b in bins if not project.stats_complete(known.get(b)))
    if missing:
        print(f"Counting the images of {missing} bin(s)…", flush=True)
    stats = project.bin_stats(root, bins)

    meta_csv = os.path.join(root, "metadata", metadata.OUTPUT_CSV)
    meta_rows = None
    if os.path.isfile(meta_csv):
        with open(meta_csv, newline="", encoding="utf-8") as f:
            meta_rows = list(csv.DictReader(f))
    else:
        print("No metadata file (step 3): only the particle concentration is plotted.")

    problems = project.check_bins(stats, metadata.bin_time)
    last_metadata = project.last_report(root, "metadata_check")  # its points are coloured in the figures too
    meta_problems = metadata.read_report(last_metadata[0]) if last_metadata and meta_rows else []
    df, variables, depth = qc.frame(stats, meta_rows, meta_problems + problems)
    saved = qc.save(root, qc.charts(df, variables, depth), df, force=True)
    report = metadata.write_report(os.path.join(root, "log"), problems, len(bins), "log/bin_stats.csv", "bins_check")

    print(f"{len(bins)} bins, {len(problems)} to look at:")
    for p in problems:
        print(f"  {p['check']}: {p['bin']} {p['detail']}")
    print(f"\n{len(saved['files'])} figures in {os.path.join(root, 'figures')}: {', '.join(saved['files'])}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
