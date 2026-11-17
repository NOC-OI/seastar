"""Sample metadata of an IFCB project, with the same EcoTaxa column names for every cruise (no UI code here).

The fields come from metadata_columns.csv: each field fills one or more EcoTaxa columns (depth goes to
sample_depth_* and object_depth_*) with one type. A spreadsheet column is chosen for each field; a field's
value can also be a constant, used when the spreadsheet has no value for a bin (e.g. depth 5 m).
The result, metadata/metadata_ecotaxa.csv, has one row per bin and already the EcoTaxa names and types:
SeaSTAR only has to bind each column to itself.
"""
import csv
import datetime
import json
import math
import os
import re

import project

FIELDS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata_columns.csv")
FIELD_KEYS = ["field", "ecotaxa_columns", "type", "unit", "default", "description"]
COLUMN_RE = re.compile(r"(sample|object|acq|process)_[a-z0-9_]+")
OUTPUT_CSV, OUTPUT_JSON = "metadata_ecotaxa.csv", "metadata_ecotaxa.json"
# From the bin name, as SeaSTAR writes object_date/object_time: the time the IFCB analysed the sample
BIN_COLUMNS = {"sample_date": "t", "sample_time": "t"}


def load_fields(path=FIELDS_CSV):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add_field(field, ecotaxa_column, type_, unit="", default="", description="", path=FIELDS_CSV):
    """Add a field to the list kept for every future project. Returns the new list."""
    fields = load_fields(path)
    field, ecotaxa_column = field.strip().lower(), ecotaxa_column.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]+", field):
        raise ValueError("The field name may only have lower-case letters, digits and _")
    if not COLUMN_RE.fullmatch(ecotaxa_column):
        raise ValueError("The EcoTaxa column must start with sample_, object_, acq_ or process_, "
                         "followed by lower-case letters, digits and _ (e.g. sample_oxygen_umol_kg)")
    if type_ not in ("f", "t"):
        raise ValueError("The type must be f (number) or t (text)")
    if any(f["field"] == field for f in fields):
        raise ValueError(f"The field {field} already exists")
    used = {c for f in fields for c in f["ecotaxa_columns"].split(";")} | set(BIN_COLUMNS)
    if ecotaxa_column in used:
        raise ValueError(f"The EcoTaxa column {ecotaxa_column} is already used")
    fields.append(dict(zip(FIELD_KEYS, [field, ecotaxa_column, type_, unit.strip(), default.strip(), description.strip()])))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELD_KEYS)
        w.writeheader()
        w.writerows(fields)
    return fields


def as_text(v):
    """A spreadsheet cell as text: Excel dates and times in ISO form, 21.0 as 21, empty for NaN/None."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d") if v.time() == datetime.time(0) else v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def guess_bin_column(columns, rows):
    """The column whose values are most often IFCB bin names."""
    def hits(c):
        return sum(bool(project.BIN_RE.search(as_text(r.get(c)))) for r in rows)
    best = max(columns, key=hits, default=None)
    return best if best is not None and hits(best) else None


def guess_source(field, columns):
    """A spreadsheet column whose name looks like the field, e.g. 'Latitude' for lat, 'Depth min (m)' for depth_min."""
    norm = {c: re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_") for c in columns}
    f = field["field"]
    for c, n in norm.items():
        if n == f or n in [col.split("_", 1)[1] for col in field["ecotaxa_columns"].split(";")]:
            return c
    for c, n in norm.items():
        if n.startswith(f) or f in n.split("_"):
            return c
    # The field's first word alone or with a short unit: 'Depth (m)' for depth_min, 'Niskin' for niskin_id;
    # never a column named after another field ('niskin_id' is not a niskin_date)
    taken = {g["field"] for g in load_fields()} - {f}
    same_word = [c for c, n in norm.items() if n.split("_")[0] == f.split("_")[0] and n not in taken
                 and all(len(t) <= 3 for t in n.split("_")[1:])]
    return min(same_word, key=lambda c: len(norm[c]), default=None)


def build(rows, bin_column, mapping, bins):
    """One output row per bin of `bins`.
    rows: spreadsheet rows (dicts); mapping: {field name: {"source": column or "", "default": text}}.
    Returns (columns {name: type}, output rows, problems)."""
    fields = [f for f in load_fields() if mapping.get(f["field"], {}).get("source") or mapping.get(f["field"], {}).get("default")]
    columns = {"bin": "t", **BIN_COLUMNS}
    for f in fields:
        for c in f["ecotaxa_columns"].split(";"):
            columns[c] = f["type"]
    problems = []
    by_bin = {}
    for i, r in enumerate(rows, start=2):  # row 1 is the header in the spreadsheet
        m = project.BIN_RE.search(as_text(r.get(bin_column)))
        if not m:
            continue
        if m.group() in by_bin:
            problems.append(f"{m.group()}: in several rows of the spreadsheet (rows {by_bin[m.group()][0]} and {i}), the first is used")
            continue
        by_bin[m.group()] = (i, r)
    missing = sorted(set(bins) - set(by_bin))
    if missing:
        problems.append(f"{len(missing)} bin(s) of raw/ are not in the spreadsheet: only the constant values are used "
                        f"for them (e.g. {', '.join(missing[:3])})")
    unknown = sorted(set(by_bin) - set(bins))
    if unknown:
        problems.append(f"{len(unknown)} bin(s) of the spreadsheet are not in raw/ and are left out (e.g. {', '.join(unknown[:3])})")

    out = []
    for b in sorted(bins):
        dt = datetime.datetime.strptime(b.split("_")[0], "D%Y%m%dT%H%M%S")
        row = {"bin": b, "sample_date": dt.strftime("%Y-%m-%d"), "sample_time": dt.strftime("%H:%M:%S")}
        line, r = by_bin.get(b, (None, {}))
        for f in fields:
            m = mapping[f["field"]]
            v = as_text(r.get(m["source"])) if m.get("source") else ""
            if v == "":
                v = m.get("default", "").strip()
            if v and f["type"] == "f":
                try:
                    if not math.isfinite(float(v)):
                        raise ValueError
                except ValueError:
                    problems.append(f"{b}: {f['field']} = {v!r} is not a number (spreadsheet row {line}), left empty")
                    v = ""
            for c in f["ecotaxa_columns"].split(";"):
                row[c] = v
        out.append(row)
    return columns, out, problems


def write(metadata_dir, columns, out, mapping, source_file, bin_column):
    """metadata_ecotaxa.csv, and metadata_ecotaxa.json with the column types (for SeaSTAR's --bindcol) and the
    choices made, so that the page can show them again."""
    with open(os.path.join(metadata_dir, OUTPUT_CSV), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(columns))
        w.writeheader()
        w.writerows(out)
    with open(os.path.join(metadata_dir, OUTPUT_JSON), "w", encoding="utf-8") as f:
        json.dump({"columns": columns, "mapping": mapping, "source_file": source_file, "bin_column": bin_column,
                   "written": datetime.datetime.now().isoformat(timespec="seconds")}, f, indent=1)


def read_choices(metadata_dir):
    try:
        with open(os.path.join(metadata_dir, OUTPUT_JSON), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def bindcol_args(columns):
    """--bindcol of each column to itself, except the bin column used for the join."""
    return [f"{c}:{t}:{c}" for c, t in columns.items() if c != "bin"]
