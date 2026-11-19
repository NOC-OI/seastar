"""Pieces shared by the pages of the Process group (steps 1 to 5): the project chosen, cached scans of the network
drive, the background jobs and the progress of each step. The calculations are in project.py, metadata.py, qc.py."""
import json
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

import metadata
import project

REPO = Path(__file__).resolve().parent
MINUTES_PER_BIN = 2  # measured: ~2 min for a bin of ~5000 ROIs on one core
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
STEP_PAGES = {1: "steps/step1_project.py", 2: "steps/step2_raw_check.py", 3: "steps/step3_features.py",
              4: "steps/step4_metadata.py", 5: "steps/step5_ecotaxa.py"}
STEP_TITLES = {1: "1 · Project", 2: "2 · Raw data check", 3: "3 · Features", 4: "4 · Metadata", 5: "5 · EcoTaxa tables"}
ICONS = {"done": "✅", "check": "⚠️", "todo": ":material/check_box_outline_blank:", "running": "🔄"}


def plural_bins(n):
    return f"{n} bin{'s' if n != 1 else ''}"

# Reading a project on the network drive can take a minute: kept in memory, read again by rescan() or after 10 min
scan_project = st.cache_data(ttl=600, show_spinner="Reading the project folder…")(project.scan_project)
bins_without_features = st.cache_data(ttl=600, show_spinner="Looking for the bins without features…")(
    project.bins_without_features)
complete_bins = st.cache_data(ttl=600, show_spinner="Listing the bins…")(project.complete_bins)
bins_with_blobs = st.cache_data(ttl=600, show_spinner="Listing the blobs…")(project.bins_with_blobs)


def rescan():
    st.session_state["rescanned"] = True  # app.py shows a message once the project is read again
    scan_project.clear()
    bins_without_features.clear()
    complete_bins.clear()
    bins_with_blobs.clear()
    progress.clear()


def project_status(folder):
    if not folder:
        return False, "not chosen yet"
    if not folder.is_dir():
        return False, "folder not found"
    missing = [d for d in project.STANDARD_DIRS if not (folder / d).is_dir()]
    if missing:
        return False, f"missing folder{'s' if len(missing) > 1 else ''}: {', '.join(missing)}"
    return True, "complete IFCB project"


def chosen_project():
    """The project chosen in step 1 (Path), or None."""
    p = st.session_state.get("project")
    return Path(p) if p and Path(p).is_dir() else None


def current_project():
    """Top of the pages of steps 2 to 5: the project chosen in step 1, or a link to step 1 and stop."""
    folder = chosen_project()
    if not folder:
        st.info("Choose or create the IFCB project first.")
        st.page_link(STEP_PAGES[1], label="Go to 1 · Project", icon="➡️")
        st.stop()
    c1, c2 = st.columns([5, 1], vertical_alignment="center")
    c1.caption(f"Project: **{folder.name}** · `{folder}`")
    c2.button("Rescan", on_click=rescan, width="stretch", help="Read the folders again, e.g. after copying new data")
    return folder


# ---------------------------------------------------------------- background jobs (features, EcoTaxa zips)
def extraction_status(root, job="features"):
    """Content of log/<job>_status.json (features or ecotaxa), with 'running' added; None if never run."""
    try:
        status = json.loads((Path(root) / "log" / f"{job}_status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    status["running"] = not status["finished"] and pid_alive(status["pid"])
    return status


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                         creationflags=NO_WINDOW).stdout
    return str(pid) in out


def stop_extraction(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)


def minutes(n_bins, workers):
    """A bin runs on one core only: the cores work in rounds."""
    return -(-n_bins // workers) * MINUTES_PER_BIN


def duration(minutes):
    return f"{minutes / 60:.1f} h" if minutes >= 90 else f"{max(1, round(minutes))} min"


def bin_choice(folder, key, n_new, new_label):
    """Which bins to run (steps 3 and 5): (None, n_new) for the bins not done yet (`new_label`), or (the days and
    bins picked, their number of bins) for --bins: those are done again even if already done."""
    mode = st.radio("Bins", ["new", "chosen"], horizontal=True, key=f"{key}_mode_{folder}", label_visibility="collapsed",
                    format_func=lambda m: f"{new_label} ({n_new})" if m == "new" else "Chosen days or bins, done again")
    if mode == "new":
        return None, n_new
    bins = complete_bins(str(folder))
    per_day = {}
    for b in bins:
        per_day[b[:9]] = per_day.get(b[:9], 0) + 1
    c1, c2 = st.columns(2)
    days = c1.multiselect("Days", list(per_day), key=f"{key}_days_{folder}",
                          format_func=lambda d: f"{d} ({per_day[d]} bins)")
    picked = c2.multiselect("Bins", [b for b in bins if b[:9] not in days], key=f"{key}_bins_{folder}")
    return days + picked, sum(per_day[d] for d in days) + len(picked)


# ---------------------------------------------------------------- what the steps know of each other
def known_stats(root):
    """Bins counted in log/bin_stats.csv with every value (the others need their .adc read, step 2)."""
    return {b: s for b, s in project.load_stats(str(root)).items() if project.stats_complete(s)}


def metadata_rows(root):
    path = Path(root) / "metadata" / metadata.OUTPUT_CSV
    return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records") if path.is_file() else None


def saved_metadata_problems(root):
    """The points of the last metadata check (the report written with the metadata file of step 4)."""
    report = project.last_report(str(root), "metadata_check")
    return metadata.read_report(report[0]) if report and metadata_rows(root) is not None else []


def flagged_bins(root):
    """{bin: [reasons]} of the last metadata check and of the bin checks: what is still to check before EcoTaxa."""
    stats = known_stats(root)
    problems = saved_metadata_problems(root) + (project.check_bins(stats, metadata.bin_time) if stats else [])
    out = {}
    for p in problems:
        if p["bin"] and p["check"] != "Gap in the sampling":
            out.setdefault(p["bin"], []).append(f"{p['check']}: {p['detail']}")
    return out


def _progress(folder):
    """{step: (state, text)} with state in ICONS: shown in the menu and on the page of step 1. From the cached scan
    of the project (one listing of each folder): the menu is drawn on every page."""
    s = scan_project(str(folder))
    days = list(s["days"].values())
    n_bins = sum(d["complete_bins"] for d in days)
    n_all = sum(d["bins"] for d in days)
    n_feat = sum(d["features"] for d in days)
    n_zip = sum(d["ecotaxa_zips"] for d in days)
    out = {1: ("done", f"{plural_bins(n_bins).replace('bin', 'complete bin')} in raw/" + (f", {n_all - n_bins} incomplete" if n_all > n_bins else ""))
           if n_bins else ("todo", "no IFCB bin in raw/ yet")}
    if not n_bins:
        return out
    stats = known_stats(folder)
    counted = sum(1 for b in complete_bins(str(folder)) if b in stats)
    if counted < n_bins:
        out[2] = ("todo", f"{plural_bins(n_bins - counted)} not checked yet")
    else:
        n = len({p["bin"] for p in project.check_bins(stats, metadata.bin_time) if p["check"] != "Gap in the sampling"})
        out[2] = ("check", f"{plural_bins(n)} to look at") if n else ("done", "no bin to look at")
    feat = extraction_status(folder)
    left = max(0, n_bins - n_feat)
    if feat and feat.get("running"):
        out[3] = ("running", f"running: {feat['done']} / {plural_bins(feat['total'])}")
    elif left:
        out[3] = ("todo", f"{plural_bins(left)} without features")
    elif feat and feat.get("errors"):
        out[3] = ("check", f"{plural_bins(len(feat['errors']))} failed in the last run")
    else:
        out[3] = ("done", "every bin has its features")
    if metadata_rows(folder) is None:
        out[4] = ("todo", "no metadata saved yet")
    else:
        n = len({p["bin"] for p in saved_metadata_problems(folder) if p["bin"]})
        out[4] = ("check", f"{plural_bins(n)} with a point to check") if n else ("done", "metadata saved, no point to check")
    eco = extraction_status(folder, "ecotaxa")
    if eco and eco.get("running"):
        out[5] = ("running", f"running: {eco['done']} / {plural_bins(eco['total'])}")
    elif n_zip < n_bins:  # done only when every complete bin has its zip
        out[5] = ("todo", f"{plural_bins(n_bins - n_zip)} without a zip"
                  + (f" ({n_feat - n_zip} ready: features done)" if n_feat > n_zip else ""))
    elif eco and eco.get("errors"):
        out[5] = ("check", f"{plural_bins(len(eco['errors']))} failed in the last run")
    else:
        out[5] = ("done", f"{n_zip} zip{'s' if n_zip != 1 else ''}")
    return out


progress = st.cache_data(ttl=20, show_spinner=False)(_progress)
