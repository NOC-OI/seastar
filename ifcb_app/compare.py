"""Page 2 of the app: compare the EcoTaxa tables of several IFCB projects, when asked."""
from datetime import datetime
from pathlib import Path

import streamlit as st

import ecotaxa
from ui import DEFAULT_PARENT, folder_input

st.title("Compare EcoTaxa tables")
st.caption("Reads row 1 (column names) and row 2 (types [f] number / [t] text) of every EcoTaxa table of the projects: "
           "the .tsv files, alone or in zips, of their ecotaxa folders (archives too, not the _OLD ones). "
           "It lists, as text, the column names that differ between projects or inside a project, and the columns "
           "whose type differs. Nothing is written in the projects.")

st.session_state.setdefault("cmp_parent", DEFAULT_PARENT)
parent = folder_input("Folder of the IFCB projects", "cmp_parent", "The folder that holds the ifcb_sn… projects, e.g. Y:\\")
projects = sorted(d.name for d in parent.iterdir() if d.is_dir() and d.name.lower().startswith("ifcb_")) \
    if parent and parent.is_dir() else []
chosen = st.multiselect("Projects to compare", projects, default=projects, key=f"cmp_projects_{parent}")

if st.button("Compare", type="primary", disabled=not chosen):
    headers = {}
    bar = st.progress(0.0)
    for i, name in enumerate(chosen):
        bar.progress(i / len(chosen), text=f"Reading the tables of {name} ({i + 1} / {len(chosen)})…")
        headers[name] = ecotaxa.table_headers(str(parent / name))
    bar.empty()
    st.session_state["cmp_report"] = (f"EcoTaxa tables compared on {datetime.now():%Y-%m-%d %H:%M}, "
                                      f"{len(chosen)} project(s) in {parent}\n\n" + ecotaxa.compare_report(headers))

report = st.session_state.get("cmp_report")
if report:
    st.code(report, language=None)
    st.download_button("Download the report (.txt)", report, file_name=f"ecotaxa_tables_{datetime.now():%Y%m%d}.txt")
else:
    st.info("Choose the projects, then click Compare. Reading the tables of every project of Y:\\ can take several "
            "minutes on the network drive.")
