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


def bins_without_features(root):
    """Complete bins (hdr+adc+roi) that have no feature file yet, sorted."""
    out = os.path.join(root, FEATURES_DIR)
    return sorted(b for b, exts in raw_bins(root).items() if len(exts) == 3 and not os.path.isfile(feature_file(out, b)))


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
