"""IFCB project folders: naming, creation and scanning (no UI code here)."""
import csv
import json
import os
import re

# Layout of Y:\ifcb_snXXX_IDcruise_namecruise, with the WHOI v1.3.1 features folder of the recent cruises
FEATURES_DIR = "whoi_v4_V131_features"
STANDARD_DIRS = ["raw", "metadata", "log", FEATURES_DIR, "ecotaxa_import_zip_seastar", "figures"]

DAY_RE = re.compile(r"D\d{8}")
BIN_RE = re.compile(r"D\d{8}T\d{6}_IFCB\d+")


def whoi_version():
    """Installed WHOI ifcb-features, e.g. "v1.3.1 (commit 1d0687e)"; None if not installed.
    The git tag pip recorded is used first: tag v1.3.1 still declares version 1.3.0 in its pyproject.toml."""
    from importlib import metadata
    try:
        dist = metadata.distribution("ifcb-features")
    except metadata.PackageNotFoundError:
        return None
    vcs = json.loads(dist.read_text("direct_url.json") or "{}").get("vcs_info", {})
    if vcs.get("requested_revision"):
        return f"{vcs['requested_revision']} (commit {vcs.get('commit_id', '')[:7]})"
    return dist.version


def latest_whoi_release():
    """(tag, date) of the latest WHOI ifcb-features release on GitHub, e.g. ("v1.3.1", "2026-08-12");
    None when GitHub cannot be reached (offline, proxy, rate limit)."""
    from urllib.request import urlopen
    try:
        with urlopen("https://api.github.com/repos/WHOIGit/ifcb-features/releases/latest", timeout=5) as r:
            release = json.load(r)
        return release["tag_name"], release["published_at"][:10]
    except Exception:
        return None


VERSIONS_CSV = "feature_extractor_versions.csv"


def record_extractor_version(features_dir, bin_name, version):
    """One row per extracted bin. SeaSTAR joins it on `bin`: feature_extractor -> process_feature_extractor,
    and with --bindcol "feature_extractor_release:t:process_feature_extractor_release". A re-extracted bin
    gets a new row; SeaSTAR keeps the last matching row."""
    path = os.path.join(features_dir, VERSIONS_CSV)
    new = not os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["bin", "feature_extractor", "feature_extractor_release"])
        w.writerow([bin_name, extractor_name(version), version])


def extractor_name(version):
    """Same value as the AR7E tables: "v1.3.1 (commit …)" -> "whoi_v4_release131"."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version or "")
    return "whoi_v4_release" + "".join(m.groups()) if m else "whoi_v4"


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "", text.strip().lower())


def project_name(serial, cruise_id, cruise_name):
    """ifcb_sn<serial>_<cruiseid>_<cruisename>, e.g. ifcb_sn225_ce26008_ar7e."""
    parts = [_slug(serial), _slug(cruise_id), _slug(cruise_name)]
    if not all(parts):
        raise ValueError("Serial number, cruise ID and cruise name are all required")
    return "ifcb_sn{}_{}_{}".format(*parts)


def create_project(parent_dir, name):
    """Create the project and its standard sub-folders. Never touches existing content."""
    if not os.path.isdir(parent_dir):
        raise FileNotFoundError("Parent folder does not exist: " + parent_dir)
    root = os.path.join(parent_dir, name)
    if os.path.exists(root):
        raise FileExistsError("A project with this name already exists: " + root)
    for d in STANDARD_DIRS:
        os.makedirs(os.path.join(root, d))
    return root


def create_missing_dirs(root):
    created = [d for d in STANDARD_DIRS if not os.path.isdir(os.path.join(root, d))]
    for d in created:
        os.makedirs(os.path.join(root, d))
    return created


def _day_of(path):
    m = DAY_RE.search(os.path.basename(path))
    return m.group() if m else None


def _files(folder):
    """All file names under folder (recursive), or [] if it does not exist."""
    out = []
    for r, _, files in os.walk(folder):
        out += [os.path.join(r, f) for f in files]
    return out


def raw_bins(root):
    """{bin name: set of extensions found in raw/}"""
    bins = {}
    for f in _files(os.path.join(root, "raw")):
        m = BIN_RE.search(os.path.basename(f))
        ext = os.path.splitext(f)[1].lower()
        if m and ext in (".hdr", ".adc", ".roi"):
            bins.setdefault(m.group(), set()).add(ext)
    return bins


def feature_file(features_dir, bin_name):
    """Where WHOI's batch layout puts the feature file of a bin."""
    return os.path.join(features_dir, "features", bin_name[:9], bin_name + "_features_v4.csv")


def complete_bins(root):
    """Bins with all three files (hdr, adc, roi), sorted."""
    return sorted(b for b, exts in raw_bins(root).items() if len(exts) == 3)


def bins_without_features(root):
    """Complete bins (hdr+adc+roi) that have no feature file yet, sorted.
    One listing of the features folder: a file check per bin took minutes on a network drive."""
    suffix = "_features_v4.csv"
    done = {os.path.basename(f)[:-len(suffix)] for f in _files(os.path.join(root, FEATURES_DIR, "features"))
            if f.endswith(suffix)}
    return [b for b in complete_bins(root) if b not in done]


FLOW_ML_PER_MIN = 0.25  # IFCB sample flow rate, as in WHOI's ml_analyzed
STATS_CSV = "bin_stats.csv"
# Per bin, from the .hdr and .adc. stream_*: ROI y (pixels) of the images, median and 10-90 % range; cut_left: images
# starting at x = 0; right_edge / cut_right: the largest x + width of the bin and how many images reach it.
STATS_FIELDS = ["rois", "ml_analyzed", "rois_per_ml", "triggers", "images_per_trigger", "run_time", "humidity",
                "humidity_alarm", "stream_y_median", "stream_y_spread", "cut_left", "right_edge", "cut_right"]


def bin_stats(root, bins):
    """{bin: STATS_FIELDS values} from the .adc and .hdr files. Kept in log/bin_stats.csv: each bin is read once
    (again only if it was counted before a field was added), the raw files of a bin do not change."""
    stats = load_stats(root)
    new = [b for b in bins if not stats_complete(stats.get(b))]
    raw = raw_bin_paths(root, new)
    for b in new:
        stats[b] = read_bin_stats(raw[b], b)
    if new:
        save_stats(root, stats)
    return {b: stats[b] for b in bins}


def stats_complete(s):
    return bool(s) and all(k in s for k in STATS_FIELDS)


def read_bin_stats(path, bin_name):
    """STATS_FIELDS of one bin; path = the bin's files without extension."""
    import statistics
    from ifcbkit.adc import parse_adc_file
    from ifcbkit.header import parse_hdr
    with open(path + ".hdr", encoding="utf-8", errors="replace") as f:
        hdr = parse_hdr(f.read().splitlines())

    def number(key, default=float("nan")):
        try:
            return float(hdr.get(key, default))
        except (TypeError, ValueError):
            return default

    run_time = number("runTime", 0)
    ml = FLOW_ML_PER_MIN * (run_time - number("inhibitTime", 0)) / 60
    rois = [r for r in parse_adc_file(bin_name, path + ".adc", extended=True).values() if r["width"] > 0]
    n = len(rois)
    triggers = number("triggerCount")
    ys = sorted(r["y"] for r in rois)
    right = max((r["x"] + r["width"] for r in rois), default=0)
    q = lambda p: ys[min(len(ys) - 1, int(p * len(ys)))] if ys else float("nan")
    return {"rois": n, "ml_analyzed": round(ml, 4), "rois_per_ml": round(n / ml, 2) if ml > 0 else float("nan"),
            "triggers": triggers, "images_per_trigger": round(n / triggers, 3) if triggers > 0 else float("nan"),
            "run_time": round(run_time, 1), "humidity": round(number("humidity"), 2),
            "humidity_alarm": number("HumidityAlarmThreshold(%)", 90.0),
            "stream_y_median": statistics.median(ys) if ys else float("nan"), "stream_y_spread": q(0.9) - q(0.1),
            "cut_left": sum(1 for r in rois if r["x"] <= 0), "right_edge": right,
            "cut_right": sum(1 for r in rois if r["x"] + r["width"] >= right)}


def load_stats(root):
    path = os.path.join(root, "log", STATS_CSV)
    stats = {}
    if os.path.isfile(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                stats[r["bin"]] = {k: float(v) for k, v in r.items() if k != "bin" and v not in ("", None)}
    return stats


def save_stats(root, stats):
    """Write every bin of `stats` (merge with load_stats() first to keep the others)."""
    path = os.path.join(root, "log", STATS_CSV)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bin"] + STATS_FIELDS)
        w.writerows([b] + [s.get(k, "") for k in STATS_FIELDS] for b, s in sorted(stats.items()))


def cut_percent(stats):
    """{bin: % of its images touching the left or right edge of the camera field}. The field width is the largest
    x + width of the cruise (it is not in the .hdr), so the right edge counts only for bins that reach it."""
    frame = max((s.get("right_edge", 0) for s in stats.values()), default=0)
    out = {}
    for b, s in stats.items():
        if "cut_left" in s and s.get("rois"):
            cut = s["cut_left"] + (s["cut_right"] if s["right_edge"] >= frame else 0)
            out[b] = round(100 * cut / s["rois"], 2)
    return out


# Which figure shows each check of the bins: qc.py colours a bin only in the figures of its reasons.
BIN_CHECKS = {"Few images": "rois_per_ml", "Small volume analysed": "rois_per_ml", "Short run": "rois_per_ml",
              "Gap in the sampling": "rois_per_ml", "Few images per trigger": "images_per_trigger",
              "High humidity": "humidity", "Stream shifted": "stream_y_median", "Stream wide": "stream_y_spread",
              "Many cut images": "cut_percent"}


def check_bins(stats, bin_time):
    """Bins that look failed, and gaps in the sampling, compared with the rest of the cruise.
    stats: {bin: bin_stats values}; bin_time: bin name -> datetime. Returns problems like metadata.build."""
    import math
    import statistics
    problems = []

    def add(check, b, detail):
        problems.append({"check": check, "bin": b, "spreadsheet row": "", "detail": detail})

    if len(stats) < 3:
        return problems

    def known(k):
        return [s[k] for s in stats.values() if not math.isnan(s.get(k, float("nan")))]

    def median(k):
        return statistics.median(known(k)) if known(k) else float("nan")

    rois, ml = median("rois"), median("ml_analyzed")
    y_med, spread = median("stream_y_median"), median("stream_y_spread")
    y_dev = statistics.median(abs(v - y_med) for v in known("stream_y_median")) if known("stream_y_median") else 0
    cut = cut_percent(stats)
    cut_med = statistics.median(cut.values()) if cut else 0
    for b, s in sorted(stats.items()):
        def v(k):
            return s.get(k, float("nan"))
        if s["rois"] < 0.1 * rois:
            add("Few images", b, f"{s['rois']:.0f} images, the cruise median is {rois:.0f}: failed acquisition?")
        if s["ml_analyzed"] < 0.5 * ml:
            add("Small volume analysed", b,
                f"{s['ml_analyzed']:.2f} mL, the cruise median is {ml:.2f} mL: run stopped early?")
        if v("run_time") < 1000 and s["ml_analyzed"] < 2.5:  # thresholds of the California IFCB network QC
            add("Short run", b, f"{v('run_time'):.0f} s and {s['ml_analyzed']:.2f} mL: incomplete sample?")
        if v("images_per_trigger") < 0.9:  # California IFCB network QC: images lost
            add("Few images per trigger", b, f"{s['rois']:.0f} images for {v('triggers'):.0f} triggers "
                f"({v('images_per_trigger'):.2f}): triggers without an image")
        if v("humidity") > v("humidity_alarm"):
            add("High humidity", b, f"{v('humidity'):.1f} % inside the IFCB, alarm above {v('humidity_alarm'):.0f} %")
        if abs(v("stream_y_median") - y_med) > max(50, 4 * y_dev):
            add("Stream shifted", b, f"images centred at y = {v('stream_y_median'):.0f} px, the cruise median is "
                f"{y_med:.0f} px: flow deviated?")
        if v("stream_y_spread") > 1.5 * spread:
            add("Stream wide", b, f"images spread over {v('stream_y_spread'):.0f} px in y, the cruise median is "
                f"{spread:.0f} px: bad flow?")
        if cut.get(b, 0) > max(5, 3 * cut_med):
            add("Many cut images", b, f"{cut[b]:.1f} % of the images touch the edge of the camera field, the cruise "
                f"median is {cut_med:.1f} %")
    times = sorted((bin_time(b), b) for b in stats)
    steps = [(t2 - t1).total_seconds() for (t1, _), (t2, _) in zip(times, times[1:])]
    gap = max(3600, 3 * statistics.median(steps))  # shortcut: one threshold for the cruise, not per station
    for ((t1, b1), (t2, b2)), s in zip(zip(times, times[1:]), steps):
        if s > gap:
            add("Gap in the sampling", b2, f"{s / 3600:.1f} h without a bin since {b1}")
    return problems


def roi_positions(root, bin_name):
    """[{roi, x, y, width, height}] of the images of a bin, from its .adc (ROI x, y: top left corner, pixels)."""
    from ifcbkit.adc import parse_adc_file
    path = raw_bin_paths(root, [bin_name])[bin_name]
    return [{"roi": t, "x": r["x"], "y": r["y"], "width": r["width"], "height": r["height"]}
            for t, r in sorted(parse_adc_file(bin_name, path + ".adc", extended=True).items()) if r["width"] > 0]


def blob_zip(root, bin_name):
    return os.path.join(root, FEATURES_DIR, "blobs", bin_name[:9], bin_name + "_blobs_v4.zip")


def bins_with_blobs(root):
    """Bins that have a WHOI blobs zip, sorted (one listing of the blobs folder)."""
    suffix = "_blobs_v4.zip"
    return sorted(os.path.basename(f)[:-len(suffix)] for f in _files(os.path.join(root, FEATURES_DIR, "blobs"))
                  if f.endswith(suffix))


def images_and_blobs(root, bin_name, n=12, seed=0):
    """[(roi number, image, blob or None)] for n images of a bin picked at random (seed), read one by one from the
    .roi file rather than the whole bin; the blobs come from the WHOI blobs zip."""
    import random
    import zipfile
    from PIL import Image
    from ifcbkit.adc import parse_adc_file
    from ifcbkit.roi import extract_roi_image
    path = raw_bin_paths(root, [bin_name])[bin_name]
    adc = parse_adc_file(bin_name, path + ".adc", extended=True)
    picked = sorted(random.Random(seed).sample(sorted(adc), min(n, len(adc))))
    blobs = zipfile.ZipFile(blob_zip(root, bin_name)) if os.path.isfile(blob_zip(root, bin_name)) else None
    out = []
    with open(path + ".roi", "rb") as roi:
        for t in picked:
            a = adc[t]
            image = extract_roi_image(roi, a["width"], a["height"], a["offset"]).copy()
            name = f"{bin_name}_{t:05d}.png"
            blob = Image.open(blobs.open(name)).copy() if blobs and name in blobs.namelist() else None
            out.append((t, image, blob))
    return out


def raw_bin_paths(root, bins):
    """{bin: path without extension} for the given bins, from one listing of raw/."""
    wanted, out = set(bins), {}
    for f in _files(os.path.join(root, "raw")):
        name = os.path.splitext(os.path.basename(f))[0]
        if name in wanted:
            out[name] = os.path.splitext(f)[0]
    return out


def scan_name(root):
    """{serial, cruise_id, cruise_name} from ifcb_sn<serial>_<cruise ID>_<name>, or None."""
    m = re.match(r"ifcb_sn([^_]+)_([^_]+)_(.+)$", os.path.basename(os.path.normpath(root)))
    return {"serial": m.group(1), "cruise_id": m.group(2), "cruise_name": m.group(3)} if m else None


def scan_project(root):
    """Summarise an existing project: which standard folders exist, and per day how many
    bins, feature files, EcoTaxa zips there are."""
    present = {d: os.path.isdir(os.path.join(root, d)) for d in STANDARD_DIRS}
    days = {}

    def day(d):
        return days.setdefault(d, {"bins": 0, "complete_bins": 0, "features": 0, "ecotaxa_zips": 0})

    for b, exts in raw_bins(root).items():
        d = day(b[:9])
        d["bins"] += 1
        d["complete_bins"] += len(exts) == 3

    for f in _files(os.path.join(root, FEATURES_DIR)):
        if f.endswith("_features_v4.csv") and _day_of(f):
            day(_day_of(f))["features"] += 1

    for f in _files(os.path.join(root, "ecotaxa_import_zip_seastar")):
        if f.lower().endswith(".zip") and _day_of(f):
            day(_day_of(f))["ecotaxa_zips"] += 1

    meta_dir = os.path.join(root, "metadata")
    metadata = sorted(os.path.relpath(f, meta_dir).replace("\\", "/") for f in _files(meta_dir) if f.lower().endswith(".csv"))
    info = scan_name(root)
    return {"root": root, "name_info": info, "present": present, "days": dict(sorted(days.items())), "metadata": metadata}


# ---------------------------------------------------------------- warnings, for the command line
def last_run(root, job):
    """log/<job>_status.json (job: features or ecotaxa), or None if never run."""
    try:
        with open(os.path.join(root, "log", f"{job}_status.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def last_report(root, name):
    """(path, summary line) of the newest log/<name>_<date>.txt (metadata_check or bins_check), or None."""
    log_dir = os.path.join(root, "log")
    files = sorted(f for f in os.listdir(log_dir) if f.startswith(name + "_") and f.endswith(".txt")) \
        if os.path.isdir(log_dir) else []
    if not files:
        return None
    path = os.path.join(log_dir, files[-1])
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    return path, lines[2] if len(lines) > 2 else ""


def _some(bins, n=5):
    return ", ".join(bins[:n]) + (f" … (+{len(bins) - n})" if len(bins) > n else "")


def warnings(root, step):
    """What the app warns about before a step, as lines of text: step "features", "ecotaxa" or "all"."""
    out = []
    bins = raw_bins(root)
    incomplete = sorted(b for b, exts in bins.items() if len(exts) < 3)
    if not bins:
        return [f"No IFCB bin in {os.path.join(root, 'raw')}: copy the day folders (DYYYYMMDD) of the IFCB into raw/."]
    if incomplete:
        out.append(f"{len(incomplete)} bin(s) miss a file (.hdr, .adc or .roi) and are left out: " + _some(
            [f"{b} (no {', '.join(e for e in ('.hdr', '.adc', '.roi') if e not in bins[b])})" for b in incomplete]))
    if step in ("features", "all"):
        installed, last = whoi_version(), last_run(root, "features")
        if not installed:
            out.append("WHOI ifcb-features is not installed: pip install -r requirements.txt")
        elif last and last.get("whoi_version") and last["whoi_version"] != installed:
            out.append(f"The installed WHOI ifcb-features ({installed}) is not the one of the last extraction "
                       f"({last['whoi_version']}): the project would mix two versions.")
        latest = latest_whoi_release()
        if installed and latest and not installed.startswith(latest[0]):
            out.append(f"WHOI published ifcb-features {latest[0]} on {latest[1]}; installed: {installed}.")
    for job, what in (("features", "feature extraction"), ("ecotaxa", "EcoTaxa run")):
        last = last_run(root, job)
        if step in (job, "all") and last:
            if not last.get("finished"):
                out.append(f"The last {what} did not finish ({last['done']} / {last['total']} bins), "
                           "or is still running.")
            elif last.get("errors"):
                out.append(f"The last {what} had {len(last['errors'])} failed bin(s): " + _some(last["errors"], 3))
    if step in ("ecotaxa", "all"):
        without = bins_without_features(root)
        if without:
            out.append(f"{len(without)} bin(s) without features are left out of the EcoTaxa tables: run "
                       "extract_features.py first. " + _some(without))
        if not os.path.isfile(os.path.join(root, "metadata", "metadata_ecotaxa.csv")):
            out.append("No metadata file yet (make_metadata.py): the zips would have no sample metadata.")
        for name, script in (("metadata_check", "make_metadata.py"), ("bins_check", "make_figures.py")):
            report = last_report(root, name)
            if report is None:
                out.append(f"No {name.replace('_', ' ')} yet: run {script}.")
            elif not report[1].endswith(", 0 point(s) to check"):
                out.append(f"Last {name.replace('_', ' ')}: {report[1]}, see {report[0]}. Correct them first if you can.")
    return out


def select_bins(root, names):
    """The complete bins of raw/ named in `names` (bin names, or days DYYYYMMDD for all the bins of a day), sorted,
    and the names that match none, each with the closest bins."""
    import difflib
    bins = complete_bins(root)
    chosen, unknown = set(), []
    for n in (n.strip() for n in names):
        hit = [b for b in bins if b == n or (DAY_RE.fullmatch(n) and b.startswith(n + "T"))]
        if hit:
            chosen.update(hit)
        else:
            close = difflib.get_close_matches(n, bins, 3, 0.6)
            unknown.append(f"{n} (closest: {', '.join(close) or 'none'})")
    return sorted(chosen), unknown


def feature_file_problem(root, bin_name, stats=None):
    """Why the feature file of a bin cannot go to EcoTaxa, or None if it looks right: it must have a roi_number
    column and one row per image (the image count of log/bin_stats.csv, when known). SeaSTAR skips a feature file
    without rows and makes the zip anyway, with no features at all."""
    path = feature_file(os.path.join(root, FEATURES_DIR), bin_name)
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = sum(1 for _ in reader)
            columns = reader.fieldnames or []
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        return f"feature file unreadable ({e})"
    if "roi_number" not in columns:
        return "feature file without a roi_number column"
    if not rows:
        return "feature file without any row"
    images = (stats or {}).get(bin_name, {}).get("rois")
    if images and rows != int(images):
        return f"feature file has {rows} rows for {int(images)} images"
    return None
