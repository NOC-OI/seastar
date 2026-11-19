"""Step 3: extract the features with WHOI ifcb-features v1.3.1 (a background process), then look at the images and
their blobs."""
import os
import subprocess
import sys

import streamlit as st

import common
import project

st.header("3 · Extract the features")
folder = common.current_project()


def start_extraction(root, workers, names=None):
    (root / "log").mkdir(exist_ok=True)
    err = open(root / "log" / "features_errors_python.log", "a", encoding="utf-8")
    # Its own process: it goes on if the browser tab is closed (not if this computer sleeps); stdout: the log has it
    subprocess.Popen([sys.executable, str(common.REPO / "extract_features.py"), str(root), "--workers", str(workers)]
                     + (["--bins", *names] if names else []), cwd=common.REPO, stdout=subprocess.DEVNULL, stderr=err,
                     creationflags=common.NO_WINDOW)
    st.session_state["extraction_started"] = True


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
           "Bins that already have a feature file are skipped. Move the failed bins of step 2 out of `raw/` first.")

status = common.extraction_status(folder)


@st.fragment(run_every=5 if status and status["running"] else None)
def features_panel():
    status = common.extraction_status(folder)
    if status and status["running"]:
        st.session_state["extraction_started"] = True
        done, total = status["done"], status["total"]
        left = common.minutes(total - done, status["workers"])
        st.progress(done / total if total else 1.0,
                    text=f"Extracting the features with WHOI ifcb-features {status.get('whoi_version')}: "
                         f"{done} / {total} bins · about {common.duration(left)} left · "
                         f"{status['workers']} cores · started {status['started'].replace('T', ' ')}")
        if status["errors"]:
            st.warning(f"{len(status['errors'])} bin(s) failed so far, see the list when it ends.")
        st.caption("You can close this tab: the extraction goes on as long as this computer stays on and awake.")
        st.button("Stop the extraction", on_click=common.stop_extraction, args=(status["pid"],))
        return
    if st.session_state.pop("extraction_started", False):
        common.rescan()
        st.rerun()  # the extraction just ended or was stopped: read the project again

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

    todo = common.bins_without_features(str(folder))
    if not todo:
        st.success("Every complete bin has its feature file. To extract some bins again, choose them below.")
    names, n = common.bin_choice(folder, "feat", len(todo), "All bins, skipping those already extracted")
    if not n:
        if names is not None:
            st.caption("Choose days or bins: their features are extracted again and replace the old ones.")
        return
    cores = os.cpu_count() or 2
    c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
    workers = c1.number_input("Cores to use", 1, cores, max(1, cores - 2),
                              help=f"This computer has {cores}. Keep one or two free to go on working.")
    c2.markdown(f"**{n} bin{'s' if n > 1 else ''}** to process, about **{common.duration(common.minutes(n, workers))}**")
    st.button("Run the feature extraction", type="primary", on_click=start_extraction, args=(folder, workers, names))


if WHOI_VERSION:
    features_panel()

st.subheader("Images and their blobs")
st.caption("The blob is the outline WHOI ifcb-features found in the image: the features are measured on it. Check that "
           "it covers the particle, not the background or a bubble. Each image is shown above its blob.")
with_blobs = common.bins_with_blobs(str(folder))
if not with_blobs:
    st.info("No blob yet: they are made by the feature extraction above.")
else:
    flagged = common.flagged_bins(folder)
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
st.page_link(common.STEP_PAGES[4], label="Next: 4 · Metadata", icon="➡️")
