"""Step 1: create a new IFCB project or open an existing one; per-day table of the bins, and where each step stands."""
from pathlib import Path

import pandas as pd
import streamlit as st

import common
import project
from ui import DEFAULT_PARENT, folder_input

OPEN, CREATE = "Open an existing project", "Create a new project"


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
    st.session_state.update(project=root, mode=OPEN, create_error="", created_note=f"Project created: {root}")


def create_missing():
    created = project.create_missing_dirs(st.session_state["project"])
    st.session_state["created_note"] = "Folders created: " + ", ".join(created)
    common.rescan()


st.title("IFCB → EcoTaxa pipeline")
st.caption("Prepares the images and measurements of an Imaging FlowCytobot (IFCB) cruise for EcoTaxa, in five steps "
           "(menu on the left): project folders, a check of the raw data, features, metadata and EcoTaxa import "
           "files. Everything runs on this computer.")

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
        folder_input("Create the project in", "parent", "The folder that holds the IFCB projects, e.g. Y:\\",
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
                      status=common.project_status(Path(st.session_state["project"]) if st.session_state["project"] else None))
if st.session_state["created_note"]:
    st.success(st.session_state["created_note"])
    st.session_state["created_note"] = ""
if not folder or not folder.is_dir():
    st.stop()

st.button("Rescan the project", on_click=common.rescan, help="Read the folders again, e.g. after copying new data into raw/")
s = common.scan_project(str(folder))
missing = [d for d, ok in s["present"].items() if not ok]
if missing:
    st.warning("This project has no " + ", ".join(f"`{d}`" for d in missing) + " folder.")
    st.button("Create the missing folders", on_click=create_missing)

info = s["name_info"]
if info:
    st.caption(f"IFCB serial number **{info['serial']}** · cruise ID **{info['cruise_id']}** · name **{info['cruise_name']}**")
else:
    st.caption(":orange[The folder name does not follow ifcb_sn<serial>_<cruise ID>_<name>.]")

st.subheader("Where the project stands")
steps = common.states(folder)
for n, title in common.STEP_TITLES.items():
    if n in steps:
        state, text = steps[n]
        c1, c2 = st.columns([1, 3])
        c1.page_link(common.STEP_PAGES[n], label=title, icon=common.ICONS[state])
        c2.markdown(text)

st.subheader("Per day")
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
