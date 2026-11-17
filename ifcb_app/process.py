"""Page 1 of the app: process one IFCB project, from the raw files to the EcoTaxa zips.
Section 1: create a new IFCB project or open an existing one. Section 2: extract the features (WHOI v1.3.1).
Section 3: the sample metadata, with the EcoTaxa column names of metadata_columns.csv.
Section 4: quality check figures (map, particle concentration and environmental values against time and depth),
before the EcoTaxa tables, so that problems are corrected first; saved as PNG in figures/.
Section 5: the EcoTaxa zips, made by SeaSTAR.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import make_ecotaxa
import metadata
import project
from ui import DEFAULT_PARENT, folder_input

REPO = Path(__file__).resolve().parent
OPEN, CREATE = "Open an existing project", "Create a new project"


def project_status(folder):
    if not folder:
        return False, "not chosen yet"
    if not folder.is_dir():
        return False, "folder not found"
    missing = [d for d in project.STANDARD_DIRS if not (folder / d).is_dir()]
    if missing:
        return False, f"missing folder{'s' if len(missing) > 1 else ''}: {', '.join(missing)}"
    return True, "complete IFCB project"


def new_name():
    try:
        return project.project_name(st.session_state["serial"], st.session_state["cruise_id"], st.session_state["cruise_name"])
    except ValueError:
        return None


def create():
    try:
        root = project.create_project(st.session_state["parent"], new_name())
    except (ValueError, OSError) as e:
        st.session_state["create_error"] = str(e)
        return
    st.session_state.update(project=root, mode=OPEN, create_error="",
                            created_note=f"Project created: {root}")


def create_missing():
    created = project.create_missing_dirs(st.session_state["project"])
    st.session_state["created_note"] = "Folders created: " + ", ".join(created)
    rescan()


# Reading a project on the network drive can take a minute: kept in memory, read again by rescan() or after 10 min
scan_project = st.cache_data(ttl=600, show_spinner="Reading the project folder…")(project.scan_project)
bins_without_features = st.cache_data(ttl=600, show_spinner="Looking for the bins without features…")(
    project.bins_without_features)
complete_bins = st.cache_data(ttl=600, show_spinner="Listing the bins…")(project.complete_bins)
bins_with_blobs = st.cache_data(ttl=600, show_spinner="Listing the blobs…")(project.bins_with_blobs)


def rescan():
    scan_project.clear()
    bins_without_features.clear()
    complete_bins.clear()
    bins_with_blobs.clear()


# ---------------------------------------------------------------- page
st.title("IFCB → EcoTaxa pipeline")
st.caption("Prepares the images and measurements of an Imaging FlowCytobot (IFCB) cruise for EcoTaxa: "
           "project folders, features, metadata and import files. Everything runs on this computer.")

for k, v in (("mode", OPEN), ("project", ""), ("parent", DEFAULT_PARENT), ("serial", ""), ("cruise_id", ""),
             ("cruise_name", ""), ("create_error", ""), ("created_note", "")):
    st.session_state.setdefault(k, v)

st.header("1 · Choose the IFCB project")
st.radio("Project", (OPEN, CREATE), key="mode", horizontal=True, label_visibility="collapsed")

if st.session_state["mode"] == CREATE:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.text_input("IFCB serial number", key="serial", placeholder="225")
        c2.text_input("Cruise ID", key="cruise_id", placeholder="ce26008")
        c3.text_input("Cruise or project name", key="cruise_name", placeholder="ar7e")
        parent = folder_input("Create the project in", "parent", "The folder that holds the IFCB projects, e.g. Y:\\",
                              status=(True, "found") if Path(st.session_state["parent"]).is_dir() else (False, "folder not found"))
        name = new_name()
        if name:
            st.markdown(f"Will create **`{Path(st.session_state['parent']) / name}`** with the folders "
                        + ", ".join(f"`{d}`" for d in project.STANDARD_DIRS))
        else:
            st.caption("Fill in the serial number, cruise ID and name to see the project name.")
        st.button("Create project", type="primary", disabled=not name, on_click=create)
        if st.session_state["create_error"]:
            st.error(st.session_state["create_error"])
    st.stop()

folder = folder_input("IFCB project folder", "project",
                      "ifcb_sn<serial>_<cruise ID>_<name>, e.g. Y:\\ifcb_sn225_ce26008_ar7e",
                      status=project_status(Path(st.session_state["project"]) if st.session_state["project"] else None))
if st.session_state["created_note"]:
    st.success(st.session_state["created_note"])
    st.session_state["created_note"] = ""
if not folder or not folder.is_dir():
    st.stop()

st.button("Rescan the project", on_click=rescan, help="Read the folders again, e.g. after copying new data into raw/")
s = scan_project(str(folder))
missing = [d for d, ok in s["present"].items() if not ok]
if missing:
    st.warning("This project has no " + ", ".join(f"`{d}`" for d in missing) + " folder.")
    st.button("Create the missing folders", on_click=create_missing)

info = s["name_info"]
if info:
    st.caption(f"IFCB serial number **{info['serial']}** · cruise ID **{info['cruise_id']}** · name **{info['cruise_name']}**")
else:
    st.caption(":orange[The folder name does not follow ifcb_sn<serial>_<cruise ID>_<name>.]")

days = pd.DataFrame.from_dict(s["days"], orient="index")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Days", len(days))
for col, key, label in ((c2, "bins", "Bins"), (c3, "features", "Feature files"), (c4, "ecotaxa_zips", "EcoTaxa zips")):
    col.metric(label, int(days[key].sum()) if len(days) else 0)

if len(days):
    days.index.name = "Day"
    days = days.rename(columns={"bins": "Bins", "complete_bins": "Complete bins (hdr+adc+roi)",
                                "features": "Feature files", "ecotaxa_zips": "EcoTaxa zips"})
    todo = days[(days["Feature files"] != days["Bins"]) | (days["EcoTaxa zips"] != days["Bins"])
                | (days["Complete bins (hdr+adc+roi)"] != days["Bins"])]
    if len(todo):
        st.info(f"{len(todo)} day{'s' if len(todo) > 1 else ''} where the numbers of bins, feature files and "
                "EcoTaxa zips differ (highlighted).")
    st.dataframe(days.style.apply(lambda r: ["background-color: rgba(230,160,40,.18)" if r.name in todo.index else ""] * len(r),
                                  axis=1), width="stretch")
else:
    st.info("No IFCB bin found in raw/ yet. Copy the day folders (DYYYYMMDD) of the IFCB into raw/.")

st.markdown("**Metadata files:** " + (", ".join(f"`{m}`" for m in s["metadata"]) or "none yet"))


# ---------------------------------------------------------------- 2 · features
MINUTES_PER_BIN = 2  # measured: ~2 min for a bin of ~5000 ROIs on one core
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def extraction_status(root, job="features"):
    """Content of log/<job>_status.json (features or ecotaxa), with 'running' added; None if never run."""
    try:
        status = json.loads((root / "log" / f"{job}_status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    status["running"] = not status["finished"] and pid_alive(status["pid"])
    return status


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                         creationflags=NO_WINDOW).stdout
    return str(pid) in out


def start_extraction(root, workers):
    (root / "log").mkdir(exist_ok=True)
    err = open(root / "log" / "features_errors_python.log", "a", encoding="utf-8")
    # Its own process: it goes on if the browser tab is closed (not if this computer sleeps)
    subprocess.Popen([sys.executable, str(REPO / "extract_features.py"), str(root), "--workers", str(workers)],
                     cwd=REPO, stdout=err, stderr=err, creationflags=NO_WINDOW)
    st.session_state["extraction_started"] = True


def stop_extraction(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)


def minutes(n_bins, workers):
    """A bin runs on one core only: the cores work in rounds."""
    return -(-n_bins // workers) * MINUTES_PER_BIN


def duration(minutes):
    return f"{minutes / 60:.1f} h" if minutes >= 90 else f"{max(1, round(minutes))} min"


st.header("2 · Extract the features")
WHOI_VERSION = project.whoi_version()
if not WHOI_VERSION:
    st.error("WHOI ifcb-features is not installed. Close the app, then start it again with start_ifcb_app.bat: "
             "it installs it (git is needed).")
else:
    st.markdown(f"Feature extractor: **WHOI ifcb-features {WHOI_VERSION}** "
                "([github.com/WHOIGit/ifcb-features](https://github.com/WHOIGit/ifcb-features))")
latest = st.cache_data(ttl=24 * 3600, show_spinner=False)(project.latest_whoi_release)()  # GitHub asked once a day
if WHOI_VERSION and latest and WHOI_VERSION.split(" ")[0] != latest[0]:
    st.info(f"WHOI published ifcb-features **{latest[0]}** on {latest[1]} "
            f"([what changed](https://github.com/WHOIGit/ifcb-features/releases/tag/{latest[0]})); this app uses "
            f"{WHOI_VERSION}. To use it, change the tag in `requirements.txt` and copy the new "
            "`extract_slim_features.py` into `whoi/`. Keep one version for all the bins of a cruise.")
st.caption(f"The 30 morphological features of the WHOI MATLAB code, and the blob masks. "
           f"Written to `{project.FEATURES_DIR}/features/<day>/` and `blobs/<day>/`. "
           "Bins that already have a feature file are skipped.")

status = extraction_status(folder)


@st.fragment(run_every=5 if status and status["running"] else None)
def features_panel():
    status = extraction_status(folder)
    if status and status["running"]:
        st.session_state["extraction_started"] = True
        done, total = status["done"], status["total"]
        left = minutes(total - done, status["workers"])
        st.progress(done / total if total else 1.0,
                    text=f"Extracting the features with WHOI ifcb-features {status.get('whoi_version')}: "
                         f"{done} / {total} bins · about {duration(left)} left · "
                         f"{status['workers']} cores · started {status['started'].replace('T', ' ')}")
        if status["errors"]:
            st.warning(f"{len(status['errors'])} bin(s) failed so far, see the list when it ends.")
        st.caption("You can close this tab: the extraction goes on as long as this computer stays on and awake.")
        st.button("Stop the extraction", on_click=stop_extraction, args=(status["pid"],))
        return
    if st.session_state.pop("extraction_started", False):
        rescan()
        st.rerun()  # the extraction just ended or was stopped: read the project again for both sections

    if status and status["finished"] and status["total"]:
        msg = (f"Last extraction: {status['done']} bin{'s' if status['done'] > 1 else ''} with WHOI ifcb-features "
               f"{status.get('whoi_version') or '(version not recorded)'}, finished {status['finished'].replace('T', ' ')}")
        if status.get("whoi_version") != WHOI_VERSION:
            st.warning(f"The installed version ({WHOI_VERSION}) is not the one of the last extraction: "
                       "new bins would get features from another version than the bins already done.")
        if status["errors"]:
            st.warning(msg + f", {len(status['errors'])} failed:")
            st.code("\n".join(status["errors"]), language=None)
        else:
            st.success(msg + ", no error.")
    elif status and not status["finished"]:
        st.warning(f"The last extraction stopped before the end ({status['done']} / {status['total']} bins). "
                   "Run it again: the bins already done are skipped.")

    todo = bins_without_features(str(folder))
    if not todo:
        st.success("Every complete bin has its feature file.")
        return
    cores = os.cpu_count() or 2
    c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
    workers = c1.number_input("Cores to use", 1, cores, max(1, cores - 2),
                              help=f"This computer has {cores}. Keep one or two free to go on working.")
    c2.markdown(f"**{len(todo)} bin{'s' if len(todo) > 1 else ''}** to process, about **{duration(minutes(len(todo), workers))}**")
    st.button("Run the feature extraction", type="primary", on_click=start_extraction, args=(folder, workers))


if WHOI_VERSION:
    features_panel()


# ---------------------------------------------------------------- 3 · metadata
def browse_file(key):
    """File dialog for the spreadsheet of the sample metadata."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    start = st.session_state.get(key) or str(folder / "metadata")
    path = filedialog.askopenfilename(initialdir=str(Path(start).parent) if Path(start).is_file() else start,
                                      parent=root, title="Choose the spreadsheet of the sample metadata",
                                      filetypes=[("Spreadsheets", "*.csv *.xlsx *.xlsm"), ("All files", "*.*")])
    root.destroy()
    if path:
        st.session_state[key] = str(Path(path))


@st.cache_data(show_spinner="Reading the spreadsheet…")
def read_sheet(path, sheet, mtime):  # mtime: read again when the file changes
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", sep=None, engine="python")
    else:
        df = pd.read_excel(path, sheet_name=sheet, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    return df.to_dict("records"), list(df.columns)


@st.cache_data
def sheet_names(path, mtime):
    return pd.ExcelFile(path).sheet_names


def add_new_field():
    s = st.session_state
    try:
        metadata.add_field(s["nf_field"], s["nf_column"], "f" if s["nf_type"].startswith("Number") else "t",
                           s["nf_unit"], s["nf_default"], s["nf_description"], s["nf_min"], s["nf_max"])
    except ValueError as e:
        s["nf_message"] = ("error", str(e) if "convert" not in str(e) else "The expected values must be numbers")
        return
    s["nf_message"] = ("success", f"Added {s['nf_column']}: it is now in the list of every project.")
    for k in ("nf_field", "nf_column", "nf_unit", "nf_default", "nf_description", "nf_min", "nf_max"):
        s[k] = ""


st.header("3 · Sample metadata")
st.caption("Choose the spreadsheet of the samples (CSV or Excel), then which of its columns fills each EcoTaxa column. "
           "The EcoTaxa names come from one list shared by all the projects, so every cruise gets the same columns. "
           "A value in **If empty** is used when the spreadsheet has no value for a bin (e.g. depth 5 m). "
           "`sample_date` / `sample_time` (and `object_date` / `object_time`, written by SeaSTAR) are the time "
           "the IFCB analysed the sample, from the bin name.")

meta_dir = folder / "metadata"
saved = metadata.read_choices(meta_dir)
if st.session_state.get("meta_project") != str(folder):  # another project: show its own spreadsheet
    st.session_state["meta_project"] = str(folder)
    st.session_state["meta_file"] = saved.get("source_file", "")
sheet_path = Path(st.session_state["meta_file"]) if st.session_state["meta_file"] else None
c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
ok = bool(sheet_path and sheet_path.is_file())
c1.text_input(f":green[✅ **Metadata spreadsheet** · found]" if ok else ":red[⚠️ **Metadata spreadsheet** · "
              + ("file not found]" if sheet_path else "not chosen yet]"), key="meta_file",
              help="One row per bin, with a column holding the bin name (e.g. D20250810T164958_IFCB225)")
c2.button("Browse…", key="b_meta_file", on_click=browse_file, args=("meta_file",), width="stretch")
if saved:
    st.caption(f"Metadata file last written {saved['written'].replace('T', ' ')}: "
               f"`metadata/{metadata.OUTPUT_CSV}` ({len(saved['columns'])} columns).")

meta_rows, flagged = None, set()
if ok:
    mtime = sheet_path.stat().st_mtime
    sheet = None
    if sheet_path.suffix.lower() != ".csv":
        sheet = st.selectbox("Sheet", sheet_names(str(sheet_path), mtime))
    rows, columns = read_sheet(str(sheet_path), sheet, mtime)
    with st.expander(f"Spreadsheet: {len(rows)} rows, {len(columns)} columns"):
        st.dataframe(pd.DataFrame(rows[:50], columns=columns).astype(str), width="stretch", hide_index=True)

    same_file = saved.get("source_file") == str(sheet_path)  # the choices saved apply to that spreadsheet only
    bin_guess = saved.get("bin_column") if same_file else metadata.guess_bin_column(columns, rows)
    bin_column = st.selectbox("Column with the bin name", columns,
                              index=columns.index(bin_guess) if bin_guess in columns else 0,
                              help="Links each row to the images of that bin")

    fields = metadata.load_fields()
    old = saved.get("mapping", {}) if same_file else {}
    table = pd.DataFrame([{
        "Field": f["field"],
        "EcoTaxa columns": f["ecotaxa_columns"].replace(";", ", "),
        "Type": "number [f]" if f["type"] == "f" else "text [t]",
        "Unit": f["unit"],
        "From spreadsheet column": old.get(f["field"], {}).get("source", metadata.guess_source(f, columns) or "") or "",
        "If empty": old.get(f["field"], {}).get("default", f["default"]),
    } for f in fields])
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key=f"mapping_{sheet_path}_{sheet}",
        disabled=["Field", "EcoTaxa columns", "Type", "Unit"],
        column_config={"From spreadsheet column": st.column_config.SelectboxColumn(options=[""] + columns),
                       "If empty": st.column_config.TextColumn(help="Constant used when the spreadsheet has no value")})
    mapping = {r["Field"]: {"source": r["From spreadsheet column"] or "", "default": str(r["If empty"] or "")}
               for r in edited.to_dict("records")}

    bins = complete_bins(str(folder))
    out_columns, out, problems = metadata.build(rows, bin_column, mapping, bins)
    st.markdown(f"**{len(out)} bins** · EcoTaxa columns: " + ", ".join(f"`{c}`" for c in out_columns if c != "bin"))
    if problems:
        summary = pd.Series([p["check"] for p in problems]).value_counts()
        st.warning(f"**{len(problems)} point(s) to check** before the EcoTaxa tables: "
                   + " · ".join(f"{check} ({n})" for check, n in summary.items())
                   + ". Correct the spreadsheet, then choose it again.")
        st.dataframe(pd.DataFrame(problems), width="stretch", hide_index=True,
                     column_config={"check": st.column_config.TextColumn("Check", width="medium"),
                                    "detail": st.column_config.TextColumn("Detail", width="large")})
    else:
        st.success("No problem found in the spreadsheet.")
    with st.expander("Preview of the metadata file"):
        st.dataframe(pd.DataFrame(out[:200]), width="stretch", hide_index=True)
    if st.button("Write the metadata file", type="primary", disabled=not out):
        metadata.write(meta_dir, out_columns, out, mapping, str(sheet_path), bin_column)
        report = metadata.write_report(str(folder / "log"), problems, len(out), str(sheet_path))
        st.success(f"Written: `metadata/{metadata.OUTPUT_CSV}`, {len(out)} bins, {len(out_columns) - 1} columns. "
                   f"Check report: `log/{Path(report).name}`.")
    meta_rows, flagged = out, {p["bin"] for p in problems if p["bin"]}

with st.expander("Add an EcoTaxa column to the list"):
    st.caption("For a measurement that is not in the list yet. It is added for every future project "
               f"(file `{Path(metadata.FIELDS_CSV).name}` of the app).")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Field name", key="nf_field", placeholder="oxygen")
    c2.text_input("EcoTaxa column", key="nf_column", placeholder="sample_oxygen_umol_kg",
                  help="Starts with sample_ (or object_, acq_, process_); lower-case letters, digits and _")
    c3.radio("Type", ("Number [f]", "Text [t]"), key="nf_type", horizontal=True)
    c1, c2, c3 = st.columns(3)
    c1.text_input("Unit", key="nf_unit", placeholder="umol kg-1")
    c2.text_input("Value if empty (optional)", key="nf_default")
    c3.text_input("Description", key="nf_description", placeholder="Dissolved oxygen")
    c1, c2, _ = st.columns(3)
    c1.text_input("Lowest expected value (optional)", key="nf_min", placeholder="0",
                  help="Values outside the expected range are listed in the checks")
    c2.text_input("Highest expected value (optional)", key="nf_max", placeholder="400")
    st.button("Add the column", on_click=add_new_field)
    if st.session_state.get("nf_message"):
        kind, text = st.session_state.pop("nf_message")
        (st.error if kind == "error" else st.success)(text)


# ---------------------------------------------------------------- 4 · quality check figures
SERIES, TO_CHECK = "#2a78d6", "#eb6834"  # blue: bins; orange: bins with a point to check


def known_stats(root):
    """Bins already counted in log/bin_stats.csv (reading the others means reading their .adc files)."""
    path = Path(root) / "log" / project.STATS_CSV
    return set(pd.read_csv(path, usecols=["bin"])["bin"]) if path.is_file() else set()


st.header("4 · Quality check figures")
st.caption("Look at the data before making the EcoTaxa tables: a point far from the others is often a typo. "
           "Particle concentration = images of the bin / volume analysed (0.25 mL/min × (runTime − inhibitTime), "
           "from the .hdr). Environmental values and depth come from section 3.")
if meta_rows is None and (meta_dir / metadata.OUTPUT_CSV).is_file():
    meta_rows = pd.read_csv(meta_dir / metadata.OUTPUT_CSV, dtype=str, keep_default_na=False).to_dict("records")
bins = complete_bins(str(folder))
todo = sorted(set(bins) - known_stats(folder))
if todo and not st.session_state.get(f"count_{folder}"):
    st.info(f"The images of {len(todo)} bin(s) are not counted yet. The feature extraction (section 2) counts them; "
            "for bins extracted before, this button reads their .adc files once (up to an hour or more for a whole "
            "cruise on a slow network drive), then they are kept in `log/bin_stats.csv`.")
    if st.button("Count the images", type="primary"):
        st.session_state[f"count_{folder}"] = True
        st.rerun()
elif bins:
    with st.spinner(f"Counting the images of {len(todo)} bin(s)…" if todo else "Reading the image counts…"):
        stats = project.bin_stats(str(folder), bins)
    df = pd.DataFrame([{"bin": b, "time": metadata.bin_time(b), **s} for b, s in stats.items()])
    labels = {c: f"{f['field']} ({f['unit']})" if f["unit"] else f["field"]
              for f in metadata.load_fields() for c in f["ecotaxa_columns"].split(";")}
    numeric = [c for c, f in ((c, f) for f in metadata.load_fields() for c in f["ecotaxa_columns"].split(";"))
               if f["type"] == "f"]
    if meta_rows:
        meta = pd.DataFrame(meta_rows)
        keep = [c for c in meta.columns if c in numeric]
        meta[keep] = meta[keep].apply(pd.to_numeric, errors="coerce")
        df = df.merge(meta[["bin"] + keep], on="bin", how="left")
    bin_problems = project.check_bins(stats, metadata.bin_time)
    if bin_problems:
        summary = pd.Series([p["check"] for p in bin_problems]).value_counts()
        st.warning(f"**{len(bin_problems)} bin(s) to look at**: " + " · ".join(f"{c} ({n})" for c, n in summary.items())
                   + ". Failed acquisitions can be moved out of raw/ (e.g. to Failed_acquisitions_rawdata) "
                   "before the EcoTaxa tables.")
        st.dataframe(pd.DataFrame(bin_problems).drop(columns="spreadsheet row"), width="stretch", hide_index=True)
    flagged = flagged | {p["bin"] for p in bin_problems if p["check"] != "Gap in the sampling"}
    df["status"] = ["to check" if b in flagged else "ok" for b in df["bin"]]

    import altair as alt
    tooltip = ["bin", alt.Tooltip("time:T", format="%Y-%m-%d %H:%M"), alt.Tooltip("rois_per_ml:Q", format=".0f"),
               "rois", alt.Tooltip("ml_analyzed:Q", format=".2f"), "status"]
    color = alt.Color("status:N", scale=alt.Scale(domain=["ok", "to check"], range=[SERIES, TO_CHECK]),
                      legend=alt.Legend(title=None, orient="top"))

    def scatter(data, x, y, x_title, y_title, reverse_y=False):
        x_axis = (alt.X(x, title=x_title, axis=alt.Axis(format="%d %b %H:%M", labelAngle=-30)) if x.endswith(":T")
                  else alt.X(x, title=x_title, scale=alt.Scale(zero=False)))
        return (alt.Chart(data).mark_circle(size=60, opacity=0.8).encode(
            x=x_axis, y=alt.Y(y, title=y_title, scale=alt.Scale(reverse=reverse_y, zero=False)),
            color=color, tooltip=tooltip + [c for c in (y.split(":")[0], x.split(":")[0]) if c not in ("time", "rois_per_ml")])
            .properties(height=260).interactive())

    figures = {}  # file name in figures/ -> (title, chart), saved as PNG below
    if {"object_lat", "object_lon"} <= set(df.columns) and df["object_lat"].notna().any():
        st.subheader("Map")
        pos = df.dropna(subset=["object_lat", "object_lon"])
        st.map(pos.assign(color=[TO_CHECK if s == "to check" else SERIES for s in pos["status"]]),
               latitude="object_lat", longitude="object_lon", color="color", size=400)
        st.caption(f"{len(pos)} bin{'s' if len(pos) > 1 else ''} with a position · blue: no problem · orange: a point to check in section 3")
        figures["qc_map.png"] = ("Sample positions (longitude, latitude)", alt.Chart(pos).mark_circle(size=60, opacity=0.8).encode(
            x=alt.X("object_lon:Q", title="Longitude (degrees E)", scale=alt.Scale(zero=False)),
            y=alt.Y("object_lat:Q", title="Latitude (degrees N)", scale=alt.Scale(zero=False)),
            color=color, tooltip=tooltip).properties(height=450))

    depth = "sample_depth_min" if "sample_depth_min" in df.columns and df["sample_depth_min"].notna().any() else None
    variables = [("rois_per_ml", "Particle concentration (images mL-1)")] + [
        (c, labels[c]) for c in df.columns if c in numeric and c.startswith("sample_") and "depth" not in c
        and df[c].notna().any()]
    st.subheader("Against time and depth")
    st.caption("One row per variable: against the time the IFCB analysed the bin (left) and against depth (right). "
               "Hover a point to see its bin. Drag to pan, scroll to zoom.")
    for c, title in variables:
        left, right = st.columns(2)
        figures[f"qc_{c}_time.png"] = (f"{title} against time", scatter(df, "time:T", f"{c}:Q", "Time (UTC)", title))
        left.altair_chart(figures[f"qc_{c}_time.png"][1], width="stretch")
        if depth:
            figures[f"qc_{c}_depth.png"] = (f"{title} against depth",
                                            scatter(df, f"{c}:Q", f"{depth}:Q", title, "Depth (m)", reverse_y=True))
            right.altair_chart(figures[f"qc_{c}_depth.png"][1], width="stretch")
    if len(variables) == 1:
        st.caption("Salinity, temperature, chlorophyll a… appear here once they are chosen in section 3.")
    with st.expander("Table of the values plotted"):
        st.dataframe(df, width="stretch", hide_index=True)

    # The same figures as PNG in figures/, written again only when the data change
    import hashlib
    fig_dir = folder / "figures"
    signature = hashlib.sha1((df.to_csv() + ",".join(sorted(figures))).encode()).hexdigest()
    try:
        saved_figures = json.loads((fig_dir / "qc_figures.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved_figures = {}
    if saved_figures.get("signature") != signature:
        try:
            with st.spinner(f"Saving the {len(figures)} figures in figures/…"):
                fig_dir.mkdir(exist_ok=True)
                for name, (title, chart) in figures.items():
                    chart.properties(width=700, title=f"{folder.name} · {title}").save(str(fig_dir / name), scale_factor=2)
                saved_figures = {"signature": signature, "saved": datetime.now().isoformat(timespec="seconds"),
                                 "files": sorted(figures)}
                (fig_dir / "qc_figures.json").write_text(json.dumps(saved_figures, indent=1), encoding="utf-8")
        except Exception as e:  # e.g. vl-convert not installed yet: the page still works
            st.caption(f":orange[The figures could not be saved in figures/: {e}]")
    if saved_figures.get("signature") == signature:
        st.caption(f"These figures are saved as PNG in `figures/` ({len(saved_figures['files'])} files, "
                   f"{saved_figures['saved'].replace('T', ' ')}).")

st.subheader("Images and their blobs")
st.caption("The blob is the outline WHOI ifcb-features found in the image: the features are measured on it. Check that "
           "it covers the particle, not the background or a bubble. Each image is shown above its blob.")
with_blobs = bins_with_blobs(str(folder))
if not with_blobs:
    st.info("No blob yet: they are made by the feature extraction (section 2).")
else:
    first = next((b for b in with_blobs if b in flagged), with_blobs[0])  # a bin to check first, if any
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    shown = c1.selectbox("Bin", with_blobs, index=with_blobs.index(first), key=f"blob_bin_{folder}",
                         format_func=lambda b: b + ("  (to check)" if b in flagged else ""))
    if c2.button("Other images", width="stretch"):
        st.session_state["blob_seed"] = st.session_state.get("blob_seed", 0) + 1
    with st.spinner("Reading the images…"):
        pairs = project.images_and_blobs(str(folder), shown, n=12, seed=st.session_state.get("blob_seed", 0))
    for start in range(0, len(pairs), 6):
        for col, (n, image, blob) in zip(st.columns(6), pairs[start:start + 6]):
            col.image(image, caption=f"ROI {n} · {image.width}×{image.height} px", width="stretch")
            if blob is not None:
                col.image(blob, caption="blob", width="stretch")
            else:
                col.caption("no blob")


# ---------------------------------------------------------------- 5 · EcoTaxa tables
def start_ecotaxa(root, settings):
    (root / "log").mkdir(exist_ok=True)
    (root / "log" / "ecotaxa_settings.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")
    cmd = [sys.executable, str(REPO / "make_ecotaxa.py"), str(root), "--operator", settings["operator"],
           "--workers", str(settings["workers"])]
    for option, key in (("--qcdby", "qcdby"), ("--project-name", "project_name"), ("--ship", "ship"), ("--cruise", "cruise")):
        if settings[key].strip():
            cmd += [option, settings[key].strip()]
    if settings["blobs"]:
        cmd.append("--blobs")
    err = open(root / "log" / "ecotaxa_errors_python.log", "a", encoding="utf-8")
    subprocess.Popen(cmd, cwd=REPO, stdout=err, stderr=err, creationflags=NO_WINDOW)
    st.session_state["ecotaxa_started"] = True


st.header("5 · EcoTaxa tables")
st.caption(f"One zip per bin, in `{make_ecotaxa.ZIP_DIR}/`, made by SeaSTAR with the images, the features of section 2, "
           "the metadata of section 3 and the feature extractor version. Bins that already have their zip are skipped: "
           "delete a zip to make it again.")
try:
    from importlib.metadata import version as package_version
    st.markdown(f"SeaSTAR: **seastartool {package_version('seastartool')}**")
except Exception:
    st.error("SeaSTAR is not installed. Close the app, then start it again with start_ifcb_app.bat: it installs it.")
    st.stop()

ecotaxa_status = extraction_status(folder, "ecotaxa")


@st.fragment(run_every=5 if ecotaxa_status and ecotaxa_status["running"] else None)
def ecotaxa_panel():
    status = extraction_status(folder, "ecotaxa")
    if status and status["running"]:
        st.session_state["ecotaxa_started"] = True
        done, total = status["done"], status["total"]
        st.progress(done / total if total else 1.0,
                    text=f"Making the EcoTaxa zips: {done} / {total} bins · {status['workers']} at a time · "
                         f"blobs: {'yes' if status['blobs'] else 'no'} · started {status['started'].replace('T', ' ')}")
        if status["errors"]:
            st.warning(f"{len(status['errors'])} bin(s) failed so far, see the list when it ends.")
        st.caption("You can close this tab: it goes on as long as this computer stays on and awake.")
        st.button("Stop", key="stop_ecotaxa", on_click=stop_extraction, args=(status["pid"],))
        return
    if st.session_state.pop("ecotaxa_started", False):
        rescan()
        st.rerun()
    if status and status["finished"] and status["total"]:
        msg = f"Last run: {status['done']} zip(s), finished {status['finished'].replace('T', ' ')}"
        if status["errors"]:
            st.warning(msg + f", {len(status['errors'])} failed:")
            st.code("\n".join(status["errors"]), language=None)
        else:
            st.success(msg + ", no error. The log is in `log/ecotaxa_<date>.log`.")
    elif status and not status["finished"]:
        st.warning(f"The last run stopped before the end ({status['done']} / {status['total']} bins). "
                   "Run it again: the zips already made are kept.")

    todo, without, done = make_ecotaxa.plan(str(folder))
    if without:
        st.info(f"{len(without)} bin(s) without features are left out: run the feature extraction (section 2) first.")
    if not (folder / "metadata" / metadata.OUTPUT_CSV).is_file():
        st.warning("No metadata file yet (section 3): the zips would have no sample metadata.")
    if flagged:
        st.warning(f"{len(flagged)} bin(s) still have a point to check in sections 3 and 4. Correct them first if you can.")
    if not todo:
        st.success(f"Every bin with features has its EcoTaxa zip ({len(done)}).")
        return

    try:
        saved = json.loads((folder / "log" / "ecotaxa_settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = project.scan_name(str(folder)) or {}
        saved = {"project_name": f"{info.get('cruise_id', '')}_{info.get('cruise_name', '').upper()}".strip("_"),
                 "cruise": info.get("cruise_id", "")}
    c1, c2, c3 = st.columns(3)
    operator = c1.text_input("Operator (full name)", saved.get("operator", ""), key=f"op_{folder}",
                             help="The person who ran the IFCB: sample_operator and acq_operator")
    qcdby = c2.text_input("Metadata checked by (full name)", saved.get("qcdby", ""), key=f"qc_{folder}")
    project_name = c3.text_input("Project (sample_project)", saved.get("project_name", ""), key=f"pn_{folder}")
    c1, c2, c3 = st.columns(3)
    ship = c1.text_input("Ship (sample_ship)", saved.get("ship", ""), key=f"ship_{folder}")
    cruise = c2.text_input("Cruise (sample_cruise)", saved.get("cruise", ""), key=f"cr_{folder}")
    cores = os.cpu_count() or 2
    workers = c3.number_input("Bins at a time", 1, cores, saved.get("workers", max(1, cores - 2)), key=f"wk_{folder}")
    blobs = st.checkbox("Add the blob of each image as a second image (img_rank 1)", value=saved.get("blobs", True),
                        key=f"blobs_{folder}", help="Each object gets two rows in the EcoTaxa table: the image "
                        "(img_rank 0) and its blob (img_rank 1), with the same values")
    ok_name = len(operator.strip()) >= 5 and (not qcdby.strip() or len(qcdby.strip()) >= 5)
    if operator and not ok_name:
        st.caption(":red[SeaSTAR asks for full names, at least 5 characters.]")
    st.markdown(f"**{len(todo)} bin{'s' if len(todo) > 1 else ''}** to make into EcoTaxa zips"
                + (f" ({len(done)} already made)" if done else ""))
    st.button("Make the EcoTaxa tables", type="primary", disabled=not ok_name, on_click=start_ecotaxa,
              args=(folder, {"operator": operator.strip(), "qcdby": qcdby, "project_name": project_name, "ship": ship,
                             "cruise": cruise, "workers": int(workers), "blobs": blobs}))


ecotaxa_panel()
