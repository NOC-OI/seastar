"""Step 2: check the raw data before the features. From the .adc and .hdr of each bin: image counts and volume
analysed, failed bins and gaps, and the instrument (images per trigger, stream of particles, cut images, humidity)."""
import pandas as pd
import streamlit as st

import common
import metadata
import project
import qc

st.header("2 · Raw data check")
folder = common.current_project()
st.caption("Before extracting the features, look for the bins that failed: they can be moved out of `raw/` (e.g. to "
           "`Failed_acquisitions_rawdata`) so that no time is spent on them. Everything here comes from the `.adc` and "
           "`.hdr` files: particle concentration = images / volume analysed (0.25 mL/min × (runTime − inhibitTime)); "
           "the position of each image in the camera field gives the stream of particles and the cut images.")

bins = common.complete_bins(str(folder))
if not bins:
    st.info("No complete bin in `raw/` yet (step 1).")
    st.stop()
known = common.known_stats(folder)
todo = [b for b in bins if b not in known]
if todo and not st.session_state.get(f"count_{folder}"):
    st.info(f"{len(todo)} bin(s) are not read yet, or were read before the instrument values were added. This reads "
            "their `.adc` and `.hdr` files once (about 25 s per bin on a slow network drive), then the values are kept "
            "in `log/bin_stats.csv`. The feature extraction also reads them.")
    if st.button("Read the raw data", type="primary"):
        st.session_state[f"count_{folder}"] = True
        st.rerun()
    st.stop()
if todo:
    import time
    bar, t0 = st.progress(0.0, text=f"Reading the raw data of {len(todo)} bin(s)…"), time.time()

    def show(done, total):
        elapsed = time.time() - t0
        bar.progress(done / total, text=f"Reading the raw data: {done} / {total} bins · "
                                        f"{elapsed / 60:.0f} min so far · {project.time_left(done, total, elapsed)}. "
                                        "Saved every 20 bins: if you leave the page, it goes on from there next time.")
    stats = project.bin_stats(str(folder), bins, progress=show)
    bar.empty()
    common.progress.clear()
else:
    stats = project.bin_stats(str(folder), bins)

bin_problems = project.check_bins(stats, metadata.bin_time)
project.write_qc(str(folder), stats, bin_problems)  # for the EcoTaxa tables, step 5
if bin_problems:
    summary = pd.Series([p["check"] for p in bin_problems]).value_counts()
    st.warning(f"**{len(bin_problems)} bin(s) to look at**: " + " · ".join(f"{c} ({n})" for c, n in summary.items())
               + ". Failed acquisitions can be moved out of `raw/` before the features; then **Rescan**.")
    st.dataframe(pd.DataFrame(bin_problems).drop(columns="spreadsheet row"), width="stretch", hide_index=True,
                 column_config={"detail": st.column_config.TextColumn("Detail", width="large")})
else:
    st.success(f"No bin to look at among the {len(stats)} bins.")
st.caption(f"The result of these checks is saved in `metadata/{project.QC_CSV}` and goes into the EcoTaxa tables "
           "(step 5) as sample columns: the values measured (`sample_qc_images`, `sample_qc_cut_images_pct`, "
           "`sample_qc_humidity_pct`…), the reasons (`sample_qc_flags`, `ok` if none) and their number "
           "(`sample_qc_n_flags`), so that doubtful bins are known before the classification.")
with st.expander("What each check means"):
    st.markdown("""
- **Few images** (< 10 % of the cruise median), **Small volume analysed** (< 50 %), **Short run** (< 1000 s and
  < 2.5 mL): a failed acquisition, or a run stopped early.
- **Few images per trigger** (< 0.9): triggers without an image, images lost.
- **High humidity** (above the alarm threshold of the `.hdr`): water inside the IFCB.
- **Stream shifted**, **Stream wide**: the images are not in their usual band of the camera field; bad flow (blocked
  needle, pump).
- **Many cut images** (> 5 % and > 3 × the cruise median): images touching the left or right edge of the camera field.
- **Gap in the sampling**: no bin for a long time (instrument stopped, or bins missing from `raw/`).

Sources: the RoiXY graph of IFCBacquire and the IFCB field guide, the WHOI IFCB dashboard, the QC script of the
California IFCB network (see the protocol).""")

df, variables, _ = qc.frame(stats, None, bin_problems)
figures = qc.charts(df, variables, None)
st.subheader("Against time")
st.caption("In each figure, only the bins flagged for a reason that figure shows are coloured, and the legend names "
           "the reason. Hover a point: *to check* lists every reason of the bin. Drag to pan, Shift + mouse wheel to zoom, double-click to reset.")
names = [c for c, _, _ in variables]
for i in range(0, len(names), 2):
    for col, c in zip(st.columns(2), names[i:i + 2]):
        col.altair_chart(figures[f"qc_{c}_time.png"][1], width="stretch")

st.subheader("Position of the images in the camera field")
st.caption("ROI x against ROI y of every image of a bin, as the RoiXY graph of IFCBacquire and the plot of the IFCB "
           "dashboard. The images should form one compact band: spread out, or moved, they point to a bad flow. A point "
           "is the top left corner of an image; orange: the image touches the left or right edge, so it is cut (a long "
           "image starting in the middle can reach the right edge). The bins flagged *Stream shifted*, *Stream wide* "
           "or *Many cut images* come first.")
flow = {p["bin"]: p["check"] for p in bin_problems if p["check"] in ("Stream shifted", "Stream wide", "Many cut images")}
choices = sorted(flow) + [b for b in bins if b not in flow]
roi_bin = st.selectbox("Bin", choices, key=f"roi_bin_{folder}",
                       format_func=lambda b: b + (f"  ({flow[b]})" if b in flow else ""))
frame_right = max(s.get("right_edge", 0) for s in stats.values())
with st.spinner("Reading the .adc file…"):
    rois = project.roi_positions(str(folder), roi_bin)
if rois:
    st.altair_chart(qc.zoomable(qc.roi_chart(rois, frame_right)), width="stretch")
    s = stats[roi_bin]
    st.caption(f"{len(rois)} images · stream centred at y = {s.get('stream_y_median', float('nan')):.0f} px, "
               f"{s.get('stream_y_spread', float('nan')):.0f} px wide (10 to 90 %) · "
               f"{df.set_index('bin').at[roi_bin, 'cut_percent'] or 0:.1f} % of the images touch the edge "
               f"(camera field {frame_right:.0f} px wide, the largest x + width of the cruise)")
with st.expander("Table of the values"):
    st.dataframe(df, width="stretch", hide_index=True)
st.page_link(common.STEP_PAGES[3], label="Next: 3 · Features", icon="➡️")
