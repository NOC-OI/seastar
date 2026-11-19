"""Step 3 on the command line: the sample spreadsheet -> metadata/metadata_ecotaxa.csv, with the checks.

    python make_metadata.py <project folder> [<spreadsheet>] [--sheet NAME] [--bin-column COLUMN]
                            [--map FIELD=COLUMN ...] [--default FIELD=VALUE ...] [--add-field ...] [--check-only]

Which spreadsheet column fills each field, in this order of priority:
  1. --map and --default given here;
  2. the choices saved by the app (or by an earlier run) for the same spreadsheet;
  3. the columns whose names look like the field, as the app proposes them, and the field's value if empty.
The columns used are printed, so check them. The points to check are printed and saved in
log/metadata_check_<date>.txt. With --check-only nothing is written.

A field that is not in the list yet: --add-field oxygen:sample_oxygen:f:umol/kg:0:500 --map oxygen="O2 (umol/kg)"
adds it to metadata_columns.csv for every project (and the QC figures plot it if it is a number).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metadata
import project


def pairs(values, option):
    out = {}
    for v in values or []:
        field, sep, value = v.partition("=")
        if not sep:
            sys.exit(f"{option} {v!r}: write it FIELD=VALUE, e.g. {option} depth_min=Depth")
        out[field.strip()] = value.strip()
    return out


FIELD_PARTS = ["field", "ecotaxa_column", "type_", "unit", "min_", "max_", "default", "description"]


def add_field(spec):
    """--add-field FIELD:COLUMN:TYPE[:UNIT[:MIN[:MAX[:DEFAULT[:DESCRIPTION]]]]] -> the shared list. Running the same
    command again is fine: a field already there with the same EcoTaxa column is left as it is."""
    parts = dict(zip(FIELD_PARTS, spec.split(":", len(FIELD_PARTS) - 1)))
    if len(parts) < 3:
        sys.exit(f"--add-field {spec!r}: write it FIELD:COLUMN:TYPE[:UNIT[:MIN[:MAX[:DEFAULT[:DESCRIPTION]]]]], "
                 "e.g. --add-field oxygen:sample_oxygen:f:umol/kg:0:500")
    old = {f["field"]: f for f in metadata.load_fields()}.get(parts["field"].strip().lower())
    if old and old["ecotaxa_columns"] == parts["ecotaxa_column"].strip().lower():
        return
    try:
        metadata.add_field(**parts)
    except ValueError as e:
        sys.exit(f"--add-field {spec!r}: " + (str(e) if "convert" not in str(e) else "MIN and MAX must be numbers"))
    print(f"Added the field {parts['field']} ({parts['ecotaxa_column']}) to {metadata.FIELDS_CSV}: "
          "it is now in the list of every project.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("spreadsheet", nargs="?", help="CSV or Excel file; default: the one used last time")
    parser.add_argument("--sheet", help="Excel sheet name; default: the first sheet")
    parser.add_argument("--bin-column", help="column with the bin names; default: found from the values")
    parser.add_argument("--map", action="append", metavar="FIELD=COLUMN", help="spreadsheet column of a field")
    parser.add_argument("--default", action="append", metavar="FIELD=VALUE", help="value used when the cell is empty")
    parser.add_argument("--add-field", action="append", metavar="FIELD:COLUMN:TYPE[:UNIT[:MIN[:MAX[:DEFAULT[:DESCRIPTION]]]]]",
                        help="add a field to the list shared by every project (TYPE f = number, t = text), "
                             "e.g. oxygen:sample_oxygen:f:umol/kg:0:500; then --map it")
    parser.add_argument("--check-only", action="store_true",
                        help="print the checks, write nothing (except the fields of --add-field)")
    args = parser.parse_args()

    root = os.path.abspath(args.project)
    meta_dir = os.path.join(root, "metadata")
    saved = metadata.read_choices(meta_dir)
    sheet_path = os.path.abspath(args.spreadsheet) if args.spreadsheet else saved.get("source_file")
    if not sheet_path or not os.path.isfile(sheet_path):
        sys.exit(f"No spreadsheet: give its path (not found: {sheet_path})")
    rows, columns = metadata.read_spreadsheet(sheet_path, args.sheet)
    same_file = saved.get("source_file") == sheet_path

    bin_column = args.bin_column or (saved.get("bin_column") if same_file else None) or metadata.guess_bin_column(columns, rows)
    if bin_column not in columns:
        sys.exit(f"No column {bin_column!r} with the bin names. Columns: {', '.join(columns)}")
    for spec in args.add_field or []:
        add_field(spec)
    fields = {f["field"]: f for f in metadata.load_fields()}
    maps, defaults = pairs(args.map, "--map"), pairs(args.default, "--default")
    for name in list(maps) + list(defaults):
        if name not in fields:
            sys.exit(f"No field {name!r}. Fields: {', '.join(fields)}")
    for name, column in maps.items():
        if column and column not in columns:
            sys.exit(f"--map {name}={column}: no such column. Columns: {', '.join(columns)}")
    old = saved.get("mapping", {}) if same_file else {}
    mapping = {}
    for name, f in fields.items():
        source = maps.get(name, old.get(name, {}).get("source") if name in old else metadata.guess_source(f, columns) or "")
        default = defaults.get(name, old.get(name, {}).get("default", f["default"]) if name in old else f["default"])
        mapping[name] = {"source": source or "", "default": default or ""}

    print(f"Spreadsheet: {sheet_path} ({len(rows)} rows), bin names in column {bin_column!r}")
    print(f"{'field':14s} {'EcoTaxa column(s)':40s} {'from column':24s} if empty")
    for name, m in mapping.items():
        if m["source"] or m["default"]:
            print(f"{name:14s} {fields[name]['ecotaxa_columns'].replace(';', ', '):40s} {m['source'] or '-':24s} {m['default'] or '-'}")

    out_columns, out, problems = metadata.build(rows, bin_column, mapping, project.complete_bins(root))
    counts = {}
    for p in problems:
        counts[p["check"]] = counts.get(p["check"], 0) + 1
    print(f"\n{len(out)} bins, {len(problems)} point(s) to check" + (":" if problems else "."))
    for check, n in counts.items():
        print(f"  {n:5d}  {check}")
    for p in problems[:50]:
        print(f"  {p['check']}: {p['bin'] or '-'} (row {p['spreadsheet row'] or '-'}) {p['detail']}")
    if len(problems) > 50:
        print(f"  … and {len(problems) - 50} more in the report")
    if args.check_only:
        return
    metadata.write(meta_dir, out_columns, out, mapping, sheet_path, bin_column)
    report = metadata.write_report(os.path.join(root, "log"), problems, len(out), sheet_path)
    print(f"\nWritten: {os.path.join(meta_dir, metadata.OUTPUT_CSV)}\nReport:  {report}")


if __name__ == "__main__":
    main()
