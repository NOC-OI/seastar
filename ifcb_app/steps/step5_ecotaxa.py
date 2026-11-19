"""Step 5: the EcoTaxa zips, made by SeaSTAR in a background process, after a last look at what is still to check."""
import json
import os
import subprocess
import sys

import pandas as pd
import streamlit as st

import common
import make_ecotaxa
import project

st.header("5 · EcoTaxa tables")
folder = common.current_project()


def start_ecotaxa(root, settings, names=None):
    (root / "log").mkdir(exist_ok=True)
    (root / "log" / "ecotaxa_settings.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")
    cmd = [sys.executable, str(common.REPO / "make_ecotaxa.py"), str(root), "--operator", settings["operator"],
           "--workers", str(settings["workers"])]
    for option, key in (("--qcdby", "qcdby"), ("--project-name", "project_name"), ("--ship", "ship"), ("--cruise", "cruise")):
        if settings[key].strip():
            cmd += [option, settings[key].strip()]
    if settings["blobs"]:
        cmd.append("--blobs")
    if names:
        cmd += ["--bins", *names]
    err = open(root / "log" / "ecotaxa_errors_python.log", "a", encoding="utf-8")
    subprocess.Popen(cmd, cwd=common.REPO, stdout=subprocess.DEVNULL, stderr=err,
                     creationflags=common.NO_WINDOW)  # stdout: the log has it
    st.session_state["ecotaxa_started"] = True


st.caption(f"One zip per bin, in `{make_ecotaxa.ZIP_DIR}/`, made by SeaSTAR with the images, the features of step 3, "
           "the metadata of step 4 and the feature extractor version. Each feature file is checked first (one row "
           "per image). Bins that already have their zip are skipped, unless chosen below.")

st.subheader("Before the tables")
warnings = project.warnings(str(folder), "ecotaxa")
flagged = common.flagged_bins(folder)
if not warnings and not flagged:
    st.success("Nothing left to check: no warning and no bin with a point to check.")
for w in warnings:
    st.warning(w)
if flagged:
    with st.expander(f"{len(flagged)} bin(s) with a point to check in steps 2 and 4: correct them first if you can"):
        st.dataframe(pd.DataFrame([{"bin": b, "to check": " | ".join(r)} for b, r in sorted(flagged.items())]),
                     width="stretch", hide_index=True)

st.subheader("Make the zips")
try:
    from importlib.metadata import version as package_version
    st.markdown(f"SeaSTAR: **seastartool {package_version('seastartool')}**")
except Exception:
    st.error("SeaSTAR is not installed. Close the app, then start it again with start_ifcb_app.bat: it installs it.")
    st.stop()

ecotaxa_status = common.extraction_status(folder, "ecotaxa")


@st.fragment(run_every=5 if ecotaxa_status and ecotaxa_status["running"] else None)
def ecotaxa_panel():
    status = common.extraction_status(folder, "ecotaxa")
    if status and status["running"]:
        st.session_state["ecotaxa_started"] = True
        done, total = status["done"], status["total"]
        from datetime import datetime
        elapsed = (datetime.now() - datetime.fromisoformat(status["started"])).total_seconds()
        left = project.time_left(done, total, elapsed)
        st.progress(done / total if total else 1.0,
                    text=f"Making the EcoTaxa zips: {done} / {total} bins · {left} · {status['workers']} at a time · "
                         f"blobs: {'yes' if status['blobs'] else 'no'} · started {status['started'].replace('T', ' ')}")
        if status["errors"]:
            st.warning(f"{len(status['errors'])} bin(s) failed so far, see the list when it ends.")
        st.caption("You can close this tab: it goes on as long as this computer stays on and awake.")
        st.button("Stop", key="stop_ecotaxa", on_click=common.stop_extraction, args=(status["pid"],))
        return
    if st.session_state.pop("ecotaxa_started", False):
        common.rescan()
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
    if not todo:
        st.success(f"Every bin with features has its EcoTaxa zip ({len(done)}). To make some zips again, choose them below.")
    names, n = common.bin_choice(folder, "eco", len(todo), "a zip")
    if not n:
        if names is not None:
            st.caption("Choose days or bins: their zips are made again and replace the old ones once complete.")
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
    st.markdown(f"**{n} bin{'s' if n > 1 else ''}** to make into EcoTaxa zips"
                + (f" ({len(done)} already made)" if done and names is None else "")
                + (" · bins without features are left out" if names is not None and without else ""))
    st.button("Make the EcoTaxa tables", type="primary", disabled=not ok_name, on_click=start_ecotaxa,
              args=(folder, {"operator": operator.strip(), "qcdby": qcdby, "project_name": project_name, "ship": ship,
                             "cruise": cruise, "workers": int(workers), "blobs": blobs}, names))


ecotaxa_panel()
