"""Step 4: the sample metadata (spreadsheet → EcoTaxa columns of metadata_columns.csv), their checks, and the map and
figures of the environmental values, before the EcoTaxa tables. The figures are saved as PNG in figures/."""
from pathlib import Path

import pandas as pd
import streamlit as st

import common
import metadata
import project
import qc

st.header("4 · Sample metadata")
folder = common.current_project()


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
    return metadata.read_spreadsheet(path, sheet)


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
sheet_path = Path(st.session_state["meta_file"]) if st.session_state.get("meta_file") else None
c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
ok = bool(sheet_path and sheet_path.is_file())
c1.text_input(f":green[✅ **Metadata spreadsheet** · found]" if ok else ":red[⚠️ **Metadata spreadsheet** · "
              + ("file not found]" if sheet_path else "not chosen yet]"), key="meta_file",
              help="One row per bin, with a column holding the bin name (e.g. D20250810T164958_IFCB225)")
c2.button("Browse…", key="b_meta_file", on_click=browse_file, args=("meta_file",), width="stretch")
if saved:
    st.caption(f"Metadata last saved {saved['written'].replace('T', ' ')}: "
               f"`metadata/{metadata.OUTPUT_CSV}` ({len(saved['columns'])} columns).")

meta_rows, meta_problems = common.metadata_rows(folder), common.saved_metadata_problems(folder)
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

    bins = common.complete_bins(str(folder))
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
    with st.expander("Preview of the metadata"):
        st.dataframe(pd.DataFrame(out[:200]), width="stretch", hide_index=True)
    if st.button("Save the metadata for the EcoTaxa tables", type="primary", disabled=not out,
                 help=f"Writes metadata/{metadata.OUTPUT_CSV}, used by step 5. Nothing is saved before this click: "
                      "click again after correcting the spreadsheet, then make the zips of the corrected bins again."):
        metadata.write(meta_dir, out_columns, out, mapping, str(sheet_path), bin_column)
        report = metadata.write_report(str(folder / "log"), problems, len(out), str(sheet_path))
        common.progress.clear()
        st.success(f"Saved: `metadata/{metadata.OUTPUT_CSV}`, {len(out)} bins, {len(out_columns) - 1} columns, used by "
                   f"step 5. Check report: `log/{Path(report).name}`.")
    meta_rows, meta_problems = out, problems

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

# ---------------------------------------------------------------- figures of the metadata
st.subheader("Map and figures")
stats = common.known_stats(folder)
if not meta_rows:
    st.info("The map and the figures appear once a spreadsheet is chosen above.")
    st.stop()
if not stats:
    st.info("The figures need the image counts of each bin: read the raw data in step 2 first.")
    st.page_link(common.STEP_PAGES[2], label="Go to 2 · Raw data check", icon="➡️")
    st.stop()
bin_problems = project.check_bins(stats, metadata.bin_time)
df, variables, depth = qc.frame(stats, meta_rows, meta_problems + bin_problems)
figures = qc.charts(df, variables, depth)
st.caption("A point far from the others is often a typo. In each figure, only the bins flagged for a reason that "
           "figure shows are coloured, and the legend names the reason (e.g. *Out of range* in the salinity, "
           "*Position jump* on the map). Hover a point: *to check* lists every reason of the bin. Bin-name typos and "
           "bins without metadata are in the table above only.")
if "qc_map.png" in figures:
    pos = df.assign(why=qc.why(df, qc.MAP)).dropna(subset=["object_lat", "object_lon"])
    st.map(pos.assign(color=[qc.SERIES if w == "ok" else qc.TO_CHECK for w in pos["why"]]),
           latitude="object_lat", longitude="object_lon", color="color", size=400)
    st.caption(f"{len(pos)} bin{'s' if len(pos) > 1 else ''} with a position · blue: no problem · orange: a position "
               "to check (position jump, latitude or longitude out of range), named in the figure below")
    st.altair_chart(figures["qc_map.png"][1], width="stretch")
st.caption("One row per variable: against the time the IFCB analysed the bin (left) and against depth (right).")
for c, title, by_depth in variables:
    if not by_depth:
        continue  # the instrument values are in step 2
    left, right = st.columns(2)
    left.altair_chart(figures[f"qc_{c}_time.png"][1], width="stretch")
    if depth:
        right.altair_chart(figures[f"qc_{c}_depth.png"][1], width="stretch")
with st.expander("Table of the values plotted"):
    st.dataframe(df, width="stretch", hide_index=True)
try:  # every figure of steps 2 and 4 as PNG in figures/, written again only when the data change
    with st.spinner("Saving the figures in figures/…"):
        saved_figures = qc.save(folder, figures, df)
    st.caption(f"The figures of steps 2 and 4 are saved as PNG in `figures/` ({len(saved_figures['files'])} files, "
               f"{saved_figures['saved'].replace('T', ' ')}).")
except Exception as e:  # e.g. vl-convert not installed yet: the page still works
    st.caption(f":orange[The figures could not be saved in figures/: {e}]")
st.page_link(common.STEP_PAGES[5], label="Next: 5 · EcoTaxa tables", icon="➡️")
