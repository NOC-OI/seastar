"""IFCB project folders: naming, creation and scanning (no UI code here)."""
import csv
import json
import os
import re

# Layout of Y:\ifcb_snXXX_IDcruise_namecruise, with the WHOI v1.3.1 features folder of the recent cruises
FEATURES_DIR = "whoi_v4_V131_features"
STANDARD_DIRS = ["raw", "metadata", "log", FEATURES_DIR, "ecotaxa_import_zip_seastar"]

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


def bin_stats(root, bins):
    """{bin: {"rois": images, "ml_analyzed": mL, "rois_per_ml": concentration}} from the .adc and .hdr files.
    Kept in log/bin_stats.csv: each bin is read once, the raw files of a bin do not change."""
    stats = load_stats(root)
    new = [b for b in bins if b not in stats]
    raw = raw_bin_paths(root, new)
    for b in new:
        stats[b] = read_bin_stats(raw[b], b)
    if new:
        save_stats(root, stats)
    return {b: stats[b] for b in bins}


def read_bin_stats(path, bin_name):
    """Images, mL analysed and concentration of one bin; path = the bin's files without extension."""
    from ifcbkit.adc import parse_adc_file
    from ifcbkit.header import parse_hdr
    with open(path + ".hdr", encoding="utf-8", errors="replace") as f:
        hdr = parse_hdr(f.read().splitlines())
    ml = FLOW_ML_PER_MIN * (float(hdr.get("runTime", 0)) - float(hdr.get("inhibitTime", 0))) / 60
    n = len(parse_adc_file(bin_name, path + ".adc"))
    return {"rois": n, "ml_analyzed": round(ml, 4), "rois_per_ml": round(n / ml, 2) if ml > 0 else float("nan")}


def load_stats(root):
    path = os.path.join(root, "log", STATS_CSV)
    stats = {}
    if os.path.isfile(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                stats[r["bin"]] = {k: float(r[k]) for k in ("rois", "ml_analyzed", "rois_per_ml")}
    return stats


def save_stats(root, stats):
    """Write every bin of `stats` (merge with load_stats() first to keep the others)."""
    path = os.path.join(root, "log", STATS_CSV)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bin", "rois", "ml_analyzed", "rois_per_ml"])
        w.writerows([b, s["rois"], s["ml_analyzed"], s["rois_per_ml"]] for b, s in sorted(stats.items()))


def check_bins(stats, bin_time):
    """Bins that look failed, and gaps in the sampling, compared with the rest of the cruise.
    stats: {bin: bin_stats values}; bin_time: bin name -> datetime. Returns problems like metadata.build."""
    import statistics
    problems = []
    if len(stats) < 3:
        return problems
    rois = statistics.median(s["rois"] for s in stats.values())
    ml = statistics.median(s["ml_analyzed"] for s in stats.values())
    for b, s in sorted(stats.items()):
        if s["rois"] < 0.1 * rois:
            problems.append({"check": "Few images", "bin": b, "spreadsheet row": "",
                             "detail": f"{s['rois']:.0f} images, the cruise median is {rois:.0f}: failed acquisition?"})
        if s["ml_analyzed"] < 0.5 * ml:
            problems.append({"check": "Small volume analysed", "bin": b, "spreadsheet row": "",
                             "detail": f"{s['ml_analyzed']:.2f} mL, the cruise median is {ml:.2f} mL: run stopped early?"})
    times = sorted((bin_time(b), b) for b in stats)
    steps = [(t2 - t1).total_seconds() for (t1, _), (t2, _) in zip(times, times[1:])]
    gap = max(3600, 3 * statistics.median(steps))  # shortcut: one threshold for the cruise, not per station
    for ((t1, b1), (t2, b2)), s in zip(zip(times, times[1:]), steps):
        if s > gap:
            problems.append({"check": "Gap in the sampling", "bin": b2, "spreadsheet row": "",
                             "detail": f"{s / 3600:.1f} h without a bin since {b1}"})
    return problems


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
    m = re.match(r"ifcb_sn([^_]+)_([^_]+)_(.+)$", os.path.basename(os.path.normpath(root)))
    info = {"serial": m.group(1), "cruise_id": m.group(2), "cruise_name": m.group(3)} if m else None
    return {"root": root, "name_info": info, "present": present, "days": dict(sorted(days.items())), "metadata": metadata}
