"""Position of the images of a bin in the camera field (ROI x against ROI y), as a PNG (step 2 of the app).

    python show_positions.py <project folder> [<bin> ...]

The same plot as the RoiXY graph of IFCBacquire and the IFCB dashboard: the images should form one compact band;
spread out or moved, they point to a bad flow (blocked needle, pump); images touching the left or right edge of the
camera field are cut (coloured). Without a bin, the bins flagged "Stream shifted", "Stream wide" or "Many cut images"
by make_figures.py are shown, or the first bin if none. Writes figures/positions_<bin>.png (needs vl-convert-python).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metadata
import project
import qc

FLOW_CHECKS = ("Stream shifted", "Stream wide", "Many cut images")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("bins", nargs="*", help="bin names or days DYYYYMMDD")
    args = parser.parse_args()

    root = os.path.abspath(args.project)
    bins = project.complete_bins(root)
    if not bins:
        sys.exit(f"No complete bin in {os.path.join(root, 'raw')}")
    stats = project.bin_stats(root, bins, progress=project.printer("Reading the raw data"))  # reads the .adc of the bins not counted yet
    reasons = {}
    for p in project.check_bins(stats, metadata.bin_time):
        if p["check"] in FLOW_CHECKS:
            reasons.setdefault(p["bin"], []).append(f"{p['check']}: {p['detail']}")
    if args.bins:
        shown, unknown = project.select_bins(root, args.bins)
        if unknown:
            sys.exit("Not a complete bin or day of raw/: " + "; ".join(unknown))
    else:
        shown = sorted(reasons) or bins[:1]
        print(f"{len(reasons)} bin(s) flagged for the flow or cut images" + (", showing them." if reasons else
                                                                                  f"; showing {shown[0]}."))
    frame_right = max(s.get("right_edge", 0) for s in stats.values())
    os.makedirs(os.path.join(root, "figures"), exist_ok=True)
    for b in shown:
        chart = qc.roi_chart(project.roi_positions(root, b), frame_right)
        path = os.path.join(root, "figures", f"positions_{b}.png")
        chart.properties(width=700, title=f"{os.path.basename(root)} · {b} · ROI positions").save(path, scale_factor=2)
        print(f"{b}: " + (" | ".join(reasons.get(b, [])) or "no flow problem found") + f"\n  Written: {path}")


if __name__ == "__main__":
    main()
