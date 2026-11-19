"""Where a project stands (step 1 of the app) and what the app would warn about. Writes nothing.

    python project_status.py <project folder>

Per day: bins in raw/, complete bins (hdr + adc + roi), feature files and EcoTaxa zips; days where they differ are
marked with <. Then the warnings: incomplete bins, bins without features, no metadata file, points still to check,
last runs that failed or stopped, WHOI version. Run it before each step.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    root = os.path.abspath(parser.parse_args().project)
    if not os.path.isdir(root):
        sys.exit(f"No folder {root}")

    s = project.scan_project(root)
    print(f"Project: {root}")
    if not s["name_info"]:
        print("  The folder name does not follow ifcb_sn<serial>_<cruise ID>_<name>.")
    missing = [d for d, ok in s["present"].items() if not ok]
    if missing:
        print("  Missing folders: " + ", ".join(missing))
    print("  Metadata files: " + (", ".join(s["metadata"]) or "none yet"))

    keys = ("bins", "complete_bins", "features", "ecotaxa_zips")
    print(f"\n{'Day':10s} {'Bins':>6s} {'Complete':>9s} {'Features':>9s} {'Zips':>6s}")
    total = dict.fromkeys(keys, 0)
    for day, d in s["days"].items():
        differ = len({d[k] for k in keys}) > 1
        print(f"{day:10s} {d['bins']:6d} {d['complete_bins']:9d} {d['features']:9d} {d['ecotaxa_zips']:6d}"
              + ("  <" if differ else ""))
        for k in keys:
            total[k] += d[k]
    print(f"{'Total':10s} {total['bins']:6d} {total['complete_bins']:9d} {total['features']:9d} {total['ecotaxa_zips']:6d}")

    warnings = project.warnings(root, "all")
    print(f"\n{len(warnings)} warning(s)" + (":" if warnings else "."))
    for w in warnings:
        print(f"  - {w}")


if __name__ == "__main__":
    main()
