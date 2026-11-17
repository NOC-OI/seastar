"""IFCB -> EcoTaxa pipeline in the browser.
Section 1: create a new IFCB project or open an existing one. Section 2: extract the features (WHOI v1.3.1).

Start it with start_ifcb_app.bat (Windows) or:  python -m streamlit run app.py
Everything runs on this computer; no data leaves it.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

import project

REPO = Path(__file__).resolve().parent
OPEN, CREATE = "Open an existing project", "Create a new project"
DEFAULT_PARENT = "Y:\\" if Path("Y:/").is_dir() else str(Path.home())

st.set_page_config(page_title="IFCB pipeline", page_icon=Image.open(REPO / "ifcb_app.ico"), layout="wide")


# ---------------------------------------------------------------- folders
def browse(key):
    """Folder dialog of this computer (the app runs locally)."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    path = filedialog.askdirectory(initialdir=st.session_state.get(key) or DEFAULT_PARENT, parent=root)
    root.destroy()
    if path:
        st.session_state[key] = str(Path(path))


def folder_input(label, key, help_, status=None):
    """Folder field; `status` = (ok, text) is shown in its title, green when ok, red otherwise."""
    if status is not None:
        ok, text = status
        label = f":green[✅ **{label}** · {text}]" if ok else f":red[⚠️ **{label}** · {text}]"
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    c1.text_input(label, key=key, help=help_)
    c2.button("Browse…", key=f"b_{key}", on_click=browse, args=(key,), width="stretch")
    return Path(st.session_state[key]) if st.session_state.get(key) else None


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

s = project.scan_project(str(folder))
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


def extraction_status(root):
    """Content of log/features_status.json, with 'running' added; None if never run."""
    try:
        status = json.loads((root / "log" / "features_status.json").read_text(encoding="utf-8"))
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
    st.stop()
st.markdown(f"Feature extractor: **WHOI ifcb-features {WHOI_VERSION}** "
            "([github.com/WHOIGit/ifcb-features](https://github.com/WHOIGit/ifcb-features))")
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
        st.rerun()  # the extraction just ended: refresh the counts of section 1

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

    todo = project.bins_without_features(str(folder))
    if not todo:
        st.success("Every complete bin has its feature file.")
        return
    cores = os.cpu_count() or 2
    c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
    workers = c1.number_input("Cores to use", 1, cores, max(1, cores - 2),
                              help=f"This computer has {cores}. Keep one or two free to go on working.")
    c2.markdown(f"**{len(todo)} bin{'s' if len(todo) > 1 else ''}** to process, about **{duration(minutes(len(todo), workers))}**")
    st.button("Run the feature extraction", type="primary", on_click=start_extraction, args=(folder, workers))


features_panel()
