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
rows = project.qc_rows(stats, bin_problems)
LABELS = {"sample_qc_images": "Images", "sample_qc_ml_analyzed": "mL analysed", "sample_qc_run_time_s": "Run time (s)",
          "sample_qc_images_per_trigger": "Images per trigger", "sample_qc_humidity_pct": "Humidity (%)",
          "sample_qc_stream_y_median_px": "Stream position, y (px)", "sample_qc_stream_y_spread_px": "Stream width, y (px)",
          "sample_qc_cut_images_pct": "Cut images (%)"}
FLAG_COLOURS = {3: "background-color: rgba(235,104,52,.30)", 4: "background-color: rgba(200,40,40,.40)",
                9: "background-color: rgba(120,120,120,.15)"}
bad = [r for r in rows if r["sample_qc_flag"] in (3, 4)]
gaps = [p for p in bin_problems if p["check"] == "Gap in the sampling"]
if bad:
    n4 = sum(1 for r in bad if r["sample_qc_flag"] == 4)
    st.warning(f"**{len(bad)} bin(s) to look at** out of {len(rows)}: {n4} bad (flag 4), {len(bad) - n4} doubtful (flag 3). "
               "Failed acquisitions can be moved out of `raw/` before the features; then **Rescan**.")
else:
    st.success(f"No bin to look at among the {len(rows)} bins.")
show_all = st.toggle("Show every bin", value=not bad, key=f"qc_all_{folder}")
shown = rows if show_all else bad
if shown:
    table = pd.DataFrame([{"Bin": r["bin"], **{LABELS[c]: r[c] for _, c, _, _ in project.QC_COLUMNS},
                           "Flag": r["sample_qc_flag"], "Reasons": r["sample_qc_flags"]} for r in shown])
    flags = pd.DataFrame([{LABELS[c]: r[c + "_flag"] for _, c, _, _ in project.QC_COLUMNS} | {"Flag": r["sample_qc_flag"]}
                          for r in shown])
    styled = table.style.apply(lambda col: [FLAG_COLOURS.get(f, "") for f in flags[col.name]]
                               if col.name in flags.columns else [""] * len(col), axis=0)
    st.dataframe(styled, width="stretch", hide_index=True,
                 column_config={"Reasons": st.column_config.TextColumn(width="large")})
st.caption("One row per bin, one column per value measured: **orange** = probably bad (flag 3), **red** = bad "
           "(flag 4), grey = not measured (flag 9); *Flag* is the worst of the bin (1 = good). Flags of the IODE scale, "
           f"used by BODC. Saved in `metadata/{project.QC_CSV}` and put in the EcoTaxa tables (step 5) as sample "
           "columns: each value (`sample_qc_images`, `sample_qc_cut_images_pct`…) with its flag (`…_flag`), the worst "
           "flag (`sample_qc_flag`), the reasons (`sample_qc_flags`) and the procedure, so that doubtful bins are known "
           "before the classification and can be filtered in EcoTaxa.")
if bin_problems:
    with st.expander(f"Why each bin is flagged ({len(bin_problems)} points, with the values of the cruise)"
                     + (f", and {len(gaps)} gap(s) in the sampling" if gaps else "")):
        st.dataframe(pd.DataFrame(bin_problems).drop(columns="spreadsheet row"), width="stretch", hide_index=True,
                     column_config={"check": st.column_config.TextColumn("Check"), "bin": st.column_config.TextColumn("Bin"),
                                    "detail": st.column_config.TextColumn("Detail", width="large")})
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
