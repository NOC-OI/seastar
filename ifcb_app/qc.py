"""Quality check figures of a project (no UI code here): used by the page (section 4) and by make_figures.py."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import metadata

SERIES, TO_CHECK = "#2a78d6", "#eb6834"  # blue: bins; orange: bins with a point to check


def frame(stats, meta_rows, flagged):
    """(table of the bins with their counts, metadata and status, [(column, title)] to plot, depth column or None)."""
    df = pd.DataFrame([{"bin": b, "time": metadata.bin_time(b), **s} for b, s in stats.items()])
    fields = metadata.load_fields()
    labels = {c: f"{f['field']} ({f['unit']})" if f["unit"] else f["field"]
              for f in fields for c in f["ecotaxa_columns"].split(";")}
    numeric = [c for f in fields for c in f["ecotaxa_columns"].split(";") if f["type"] == "f"]
    if meta_rows:
        meta = pd.DataFrame(meta_rows)
        keep = [c for c in meta.columns if c in numeric]
        meta[keep] = meta[keep].apply(pd.to_numeric, errors="coerce")
        df = df.merge(meta[["bin"] + keep], on="bin", how="left")
    df["status"] = ["to check" if b in flagged else "ok" for b in df["bin"]]
    depth = "sample_depth_min" if "sample_depth_min" in df.columns and df["sample_depth_min"].notna().any() else None
    variables = [("rois_per_ml", "Particle concentration (images mL-1)")] + [
        (c, labels[c]) for c in df.columns if c in numeric and c.startswith("sample_") and "depth" not in c
        and df[c].notna().any()]
    return df, variables, depth


def charts(df, variables, depth):
    """{file name in figures/: (title, Altair chart)}: the map, then each variable against time and depth."""
    import altair as alt
    tooltip = ["bin", alt.Tooltip("time:T", format="%Y-%m-%d %H:%M"), alt.Tooltip("rois_per_ml:Q", format=".0f"),
               "rois", alt.Tooltip("ml_analyzed:Q", format=".2f"), "status"]
    color = alt.Color("status:N", scale=alt.Scale(domain=["ok", "to check"], range=[SERIES, TO_CHECK]),
                      legend=alt.Legend(title=None, orient="top"))

    def scatter(x, y, x_title, y_title, reverse_y=False):
        x_axis = (alt.X(x, title=x_title, axis=alt.Axis(format="%d %b %H:%M", labelAngle=-30)) if x.endswith(":T")
                  else alt.X(x, title=x_title, scale=alt.Scale(zero=False)))
        return (alt.Chart(df).mark_circle(size=60, opacity=0.8).encode(
            x=x_axis, y=alt.Y(y, title=y_title, scale=alt.Scale(reverse=reverse_y, zero=False)),
            color=color, tooltip=tooltip + [c for c in (y.split(":")[0], x.split(":")[0]) if c not in ("time", "rois_per_ml")])
            .properties(height=260).interactive())

    figures = {}
    if {"object_lat", "object_lon"} <= set(df.columns) and df["object_lat"].notna().any():
        pos = df.dropna(subset=["object_lat", "object_lon"])
        figures["qc_map.png"] = ("Sample positions (longitude, latitude)", alt.Chart(pos).mark_circle(size=60, opacity=0.8).encode(
            x=alt.X("object_lon:Q", title="Longitude (degrees E)", scale=alt.Scale(zero=False)),
            y=alt.Y("object_lat:Q", title="Latitude (degrees N)", scale=alt.Scale(zero=False)),
            color=color, tooltip=tooltip).properties(height=450))
    for c, title in variables:
        figures[f"qc_{c}_time.png"] = (f"{title} against time", scatter("time:T", f"{c}:Q", "Time (UTC)", title))
        if depth:
            figures[f"qc_{c}_depth.png"] = (f"{title} against depth",
                                            scatter(f"{c}:Q", f"{depth}:Q", title, "Depth (m)", reverse_y=True))
    return figures


def save(folder, figures, df, force=False):
    """Save the figures as PNG in <folder>/figures/, unless the same data were already saved (force: always).
    Returns {"signature", "saved", "files"}. Needs vl-convert-python."""
    fig_dir = Path(folder) / "figures"
    signature = hashlib.sha1((df.to_csv() + ",".join(sorted(figures))).encode()).hexdigest()
    try:
        saved = json.loads((fig_dir / "qc_figures.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if force or saved.get("signature") != signature:
        fig_dir.mkdir(exist_ok=True)
        for name, (title, chart) in figures.items():
            chart.properties(width=700, title=f"{Path(folder).name} · {title}").save(str(fig_dir / name), scale_factor=2)
        saved = {"signature": signature, "saved": datetime.now().isoformat(timespec="seconds"), "files": sorted(figures)}
        (fig_dir / "qc_figures.json").write_text(json.dumps(saved, indent=1), encoding="utf-8")
    return saved
