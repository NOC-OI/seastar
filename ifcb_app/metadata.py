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
FIELD_KEYS = ["field", "ecotaxa_columns", "type", "unit", "default", "min", "max", "description"]
COLUMN_RE = re.compile(r"(sample|object|acq|process)_[a-z0-9_]+")
OUTPUT_CSV, OUTPUT_JSON = "metadata_ecotaxa.csv", "metadata_ecotaxa.json"
# From the bin name, as SeaSTAR writes object_date/object_time: the time the IFCB analysed the sample
BIN_COLUMNS = {"sample_date": "t", "sample_time": "t"}


def read_spreadsheet(path, sheet=None):
    """(rows as dicts, column names) of a CSV (any delimiter) or an Excel sheet (the first one if sheet is None)."""
    import pandas as pd
    if str(path).lower().endswith(".csv"):
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", sep=None, engine="python")
    else:
        df = pd.read_excel(path, sheet_name=sheet or 0, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    return df.to_dict("records"), list(df.columns)


def load_fields(path=FIELDS_CSV):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add_field(field, ecotaxa_column, type_, unit="", default="", description="", min_="", max_="", path=FIELDS_CSV):
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
    for bound in (min_, max_):
        if bound.strip():
            float(bound)  # ValueError if the bound is not a number
    fields.append(dict(zip(FIELD_KEYS, [field, ecotaxa_column, type_, unit.strip(), default.strip(),
                                        min_.strip(), max_.strip(), description.strip()])))
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

    def problem(check, bin_, detail, row=None):
        problems.append({"check": check, "bin": bin_, "spreadsheet row": row or "", "detail": detail})

    by_bin = {}
    for i, r in enumerate(rows, start=2):  # row 1 is the header in the spreadsheet
        m = project.BIN_RE.search(as_text(r.get(bin_column)))
        if not m:
            if any(as_text(v) for v in r.values()):
                problem("No bin name", "", f"{as_text(r.get(bin_column))!r} in column {bin_column}", i)
            continue
        if m.group() in by_bin:
            problem("Same bin in several rows", m.group(), f"also in row {by_bin[m.group()][0]}: the first row is used", i)
            continue
        by_bin[m.group()] = (i, r)

    # A bin name that is not in raw/ is most often a typo of a bin that has no row: pair them by time
    missing = set(bins) - set(by_bin)
    for b in sorted(set(by_bin) - set(bins)):
        near = nearest_bin(b, missing)
        if near:
            missing.discard(near[0])
            problem("Bin name typo?", b, f"not in raw/; probably {near[0]} ({near[1]} apart), which has no row. "
                    "Correct the spreadsheet", by_bin[b][0])
        else:
            problem("Bin not in raw/", b, "no bin of raw/ close in time: left out", by_bin[b][0])
    for b in sorted(missing):
        problem("Bin without metadata", b, "not in the spreadsheet: only the values 'If empty' are used")

    out = []
    for b in sorted(bins):
        dt = bin_time(b)
        row = {"bin": b, "sample_date": dt.strftime("%Y-%m-%d"), "sample_time": dt.strftime("%H:%M:%S")}
        line, r = by_bin.get(b, (None, {}))
        for f in fields:
            m = mapping[f["field"]]
            v = as_text(r.get(m["source"])) if m.get("source") else ""
            if v == "":
                v = m.get("default", "").strip()
            if v and f["type"] == "f":
                try:
                    x = float(v)
                    if not math.isfinite(x):
                        raise ValueError
                except ValueError:
                    problem("Not a number", b, f"{f['field']} = {v!r}: left empty", line)
                    v = ""
                else:
                    if (f.get("min") and x < float(f["min"])) or (f.get("max") and x > float(f["max"])):
                        problem("Out of range", b, f"{f['field']} = {v} {f['unit']}, expected {f['min']} to {f['max']}", line)
            for c in f["ecotaxa_columns"].split(";"):
                row[c] = v
        niskin = parse_datetime(row.get("sample_niskin_date", ""), row.get("sample_niskin_time", ""))
        if niskin and niskin > dt:
            problem("Niskin after analysis", b, f"Niskin {niskin:%Y-%m-%d %H:%M} is after the IFCB analysis {dt:%Y-%m-%d %H:%M}", line)
        out.append(row)
    check_track(out, problem)
    return columns, out, problems


MAX_SHIP_KNOTS = 20  # faster than any research ship: one of the two positions is wrong


def check_track(out, problem):
    """Position jumps between consecutive samples that no ship could make: a typo in lat or lon.
    Uses the Niskin time when there is one: Niskin samples are analysed later, often in batches, so the analysis
    times of two stations can be minutes apart."""
    fixes = []
    for r in out:
        try:
            t = parse_datetime(r.get("sample_niskin_date", ""), r.get("sample_niskin_time", "")) or bin_time(r["bin"])
            fixes.append((t, float(r["object_lat"]), float(r["object_lon"]), r["bin"]))
        except (KeyError, ValueError):
            pass
    fixes.sort()
    for (t1, la1, lo1, b1), (t2, la2, lo2, b2) in zip(fixes, fixes[1:]):
        nm = distance_nm(la1, lo1, la2, lo2)
        hours = max((t2 - t1).total_seconds() / 3600, 1 / 60)
        if nm > 1 and nm / hours > MAX_SHIP_KNOTS:
            problem("Position jump", b2, f"{nm:.0f} nautical miles from {b1} in {hours:.1f} h ({nm / hours:.0f} knots): "
                    "a typo in lat/lon, or Niskin samples without their Niskin date and time")


def distance_nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 3440.065 * math.asin(math.sqrt(min(1, a)))


def bin_time(bin_name):
    return datetime.datetime.strptime(bin_name.split("_")[0], "D%Y%m%dT%H%M%S")


def nearest_bin(bin_name, candidates, max_hours=24):
    """(candidate, 'time apart') of the same instrument closest in time, within max_hours; else None."""
    t, serial = bin_time(bin_name), bin_name.split("_")[1]
    same = [c for c in candidates if c.split("_")[1] == serial]
    if not same:
        return None
    best = min(same, key=lambda c: abs((bin_time(c) - t).total_seconds()))
    s = abs((bin_time(best) - t).total_seconds())
    if s > max_hours * 3600:
        return None
    apart = f"{s:.0f} s" if s < 60 else f"{s / 60:.0f} min" if s < 3600 else f"{s / 3600:.1f} h"
    return best, apart


def parse_datetime(date, time):
    """'2025-06-10' or '20250610' with '07:05', '07:05:00' or '070500'; None if absent or not readable."""
    d = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", date.strip())
    t = re.fullmatch(r"(\d{1,2}):?(\d{2})(?::?(\d{2}))?", time.strip())
    if not d or not t:
        return None
    try:
        return datetime.datetime(*map(int, d.groups()), int(t.group(1)), int(t.group(2)), int(t.group(3) or 0))
    except ValueError:
        return None


def write_report(log_dir, problems, n_bins, source_file, name="metadata_check"):
    """log/<name>_<date>.txt: a summary by check, then every problem. Returns its path."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"{name}_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt")
    counts = {}
    for p in problems:
        counts[p["check"]] = counts.get(p["check"], 0) + 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{name.replace('_', ' ').capitalize()}, {datetime.datetime.now():%Y-%m-%d %H:%M}\nFrom: {source_file}\n"
                f"{n_bins} bins, {len(problems)} point(s) to check\n\n")
        for check, n in counts.items():
            f.write(f"{n:6d}  {check}\n")
        f.write("\n")
        for p in problems:
            f.write(f"{p['check']}\t{p['bin'] or '-'}\trow {p['spreadsheet row'] or '-'}\t{p['detail']}\n")
    return path


def read_report(path):
    """The problems of a report written by write_report (for the figures of make_figures.py)."""
    problems = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 4 and parts[2].startswith("row "):
                row = parts[2][4:]
                problems.append({"check": parts[0], "bin": "" if parts[1] == "-" else parts[1],
                                 "spreadsheet row": "" if row == "-" else row, "detail": parts[3]})
    return problems


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
