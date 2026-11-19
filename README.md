![SeaSTAR Logo](seastar-logo-text.png)

SeaSTAR (Sea-faring System for Tagging, Attribution and Redistribution) is a CLI and GUI application for processing biodiversity data collected at sea.

## Use cases
Currently SeaSTAR focuses on processing data collected on the IFCB instrument. It has functionality for interactions with EcoTaxa and CRAB.

## How to install and basic use
```
$ pip install seastartool
Collecting seastartool
  Downloading seastartool-0.1-py3-none-any.whl.metadata (1.1 kB)
[...]
Successfully installed seastartool-0.1
```

SeaSTAR has in-built help which you can access using:
```
$ seastar --help
```

For more guides on how to use the software (such as to extract features or generate EcoTaxa tables), see the [wiki](https://github.com/NOC-OI/seastar/wiki).

## An example with the IFCB
Given an example data:
```
raw/
  D20250810/
    D20250810T164958_IFCB225.adc
    D20250810T164958_IFCB225.hdr
    D20250810T164958_IFCB225.roi
    D20250810T171346_IFCB225.adc
    D20250810T171346_IFCB225.hdr
    D20250810T171346_IFCB225.roi
    D20250810T173732_IFCB225.adc
```

### Extracting features (IFCB)
```
$ seastar ifcb_v4_features -i raw/D20250810/*.hdr -o features/D20250810/
```

### Creating EcoTaxa tables
```
$ seastar ifcb_to_ecotaxa -i raw/D20250810/*.hdr ./metadata/A16N_metadata_filtered.csv --operator "Sample Operator" --qcdby "Sample Supervisor" --project "Sample Project" --nonull --ship "Sample Ship" --depth 5 -o
```

## IFCB → EcoTaxa pipeline

Takes an IFCB cruise from the raw files to the EcoTaxa import files, in five steps. Every step runs **on the command line** (Python scripts) or **in a desktop app** (a [Streamlit](https://streamlit.io) page): both use the same code and write the same files, so a cruise can be started in one and finished in the other. Everything runs on your own computer, so no data leaves it, and the EcoTaxa tables are made by SeaSTAR. The code is in [`ifcb_app/`](ifcb_app).

**Go to:** [command line with Python](#command-line-with-python) · [the app](#the-app) · [the protocol](docs/PROTOCOL.md)

The pipeline follows the folder layout of the NOC IFCB projects:

```
ifcb_sn<serial>_<cruise ID>_<name>/          e.g. ifcb_sn225_ce26008_ar7e
    raw/D<yyyymmdd>/<bin>.hdr .adc .roi
    figures/                                  quality check figures (PNG), saved by step 4
    metadata/
    log/
    whoi_v4_V131_features/features/D<yyyymmdd>/<bin>_features_v4.csv
                          blobs/D<yyyymmdd>/<bin>_blobs_v4.zip
    ecotaxa_import_zip_seastar/
```

| Step | What it does | Status |
|---|---|---|
| 1 · Project | Opens a project with **Browse…** or creates one with the right folder names. Shows where each step stands, and, per day, the number of bins, complete bins (hdr + adc + roi), feature files and EcoTaxa zips, highlighting the days where they differ. | Done |
| 2 · Raw data check | Before the features, from the `.adc` and `.hdr` files only: images and volume analysed of each bin, particle concentration, and the instrument (images per trigger, position and width of the stream of particles in the camera field, images cut at its edge, humidity), against time. Lists the bins that look failed (few images, small volume, short run, few images per trigger, high humidity, stream shifted or wide, many cut images) and the gaps in the sampling, so that failed acquisitions are moved out before spending time on their features. One row per bin, one column per value, each with a flag of the IODE scale used by BODC (1 good, 3 probably bad, 4 bad, 9 missing). The result goes into the EcoTaxa tables as sample columns (each value and its flag, the worst flag `sample_qc_flag`, the reasons `sample_qc_flags`), so that doubtful bins are known before the classification and can be filtered in EcoTaxa. Shows the position of the images of a bin in the camera field (ROI x against ROI y, as the IFCB dashboard). | Done |
| 3 · Features | [WHOI ifcb-features](https://github.com/WHOIGit/ifcb-features) v1.3.1 (August 2026): the 30 features of the WHOI MATLAB code and the blob masks. Runs in the background on several cores, skips the bins already done (or does again the days and bins you choose), shows the progress and the time left. The WHOI version (tag and commit) is recorded for each bin and goes to EcoTaxa as `process_feature_extractor` and `process_feature_extractor_release`. Then shows 12 images of a bin above their blob, to check the segmentation. | Done |
| 4 · Sample metadata | Reads the spreadsheet of the samples (CSV or Excel) chosen with **Browse…**. For each EcoTaxa column of a shared list (latitude, longitude, depth, Niskin date and time, salinity, temperature, chlorophyll a, Niskin and CTD numbers, comment), you choose the spreadsheet column it comes from, or a value used when the spreadsheet has none (depth 5 m). Columns missing from the list can be added, and they stay available for the next projects, so every cruise gets the same column names. Depth goes to `sample_depth_*` and `object_depth_*`; dates and times are always text. Lists what to correct in the spreadsheet: probable typos in bin names (with the bin of `raw/` they most likely are), bins without metadata, values that are not numbers or outside the expected range, position jumps no ship could make, Niskin times after the IFCB analysis. **Save the metadata for the EcoTaxa tables** writes `metadata/metadata_ecotaxa.csv` and `log/metadata_check_<date>.txt`. Then the map and every environmental value against time and depth. | Done |
| 5 · EcoTaxa tables | First what is still to check (warnings and flagged bins of steps 2 and 4). Then one zip per bin (`<CRUISE NAME>_<bin>.zip`, as for CE26008), made by `seastar ifcb_to_ecotaxa` in the background with the images, the features, the metadata of step 4 and the feature extractor version. Operator, checker, project, ship and cruise are typed once and remembered. A box, checked by default, adds the blob of each image as a second image of the object (`img_rank` 1). Bins that already have their zip are skipped, or you choose days and bins to make again. Each feature file is checked first (one row per image), because SeaSTAR would make a zip without features ([issue #19](https://github.com/NOC-OI/seastar/issues/19)). Still to add: a check of the column names and types of every table before the upload. | Done |

In every figure of steps 2 and 4, only the bins flagged for a reason that figure shows are coloured, and the legend names the reason. The figures are saved as PNG in `figures/`.

**Compare EcoTaxa tables** compares the tables of several projects (row 1, the column names; row 2, the types `[f]`/`[t]`) and gives the differences as a text report you can download. It reads only the first two rows of each table and is run only when you ask.

The step-by-step protocol, for the app and for the command line, with diagrams of what the pipeline does: [docs/PROTOCOL.md](docs/PROTOCOL.md).

### Command line with Python

Every step runs in Python, on Windows, Linux or WSL. Install once, from the `ifcb_app` folder (needs [git](https://git-scm.com), for WHOI ifcb-features and SeaSTAR):

```
cd ifcb_app
pip install -r requirements.txt
```

Then, for a cruise, in this order (`<project>` is the project folder, e.g. `Y:\ifcb_sn225_ce26008_ar7e`):

| Step | Command | Options |
|---|---|---|
| 1 · Create the project | `python create_project.py <parent folder> --serial 225 --cruise-id ce26008 --name ar7e` | On an existing project, adds only its missing folders. Then copy the IFCB day folders (`DYYYYMMDD`) into `raw/` |
| Before each step | `python project_status.py <project>` | Bins, features and zips per day, and the warnings: incomplete bins, bins without features, no metadata, points to check, failed runs, WHOI version |
| 2 · Raw data check | `python make_figures.py <project>` | Before the features: failed bins and gaps in `log/bins_check_<date>.txt`, figures in `figures/`. Run it again after step 4 for the map and the environmental values |
| 2 · Image positions | `python show_positions.py <project> [<bin or day> ...]` | ROI x against ROI y of a bin; without a bin, the bins flagged for the flow or cut images |
| 3 · Features | `python extract_features.py <project> --workers 8` | Skips the bins already done, so it can be run again after a stop. `--bins BIN_OR_DAY …`: only those bins (or days), done again |
| 3 · Blobs | `python show_blobs.py <project> [<bin>]` | `--seed N` for other images, `--n 18` for more |
| 4 · Metadata: check | `python make_metadata.py <project> <spreadsheet> --check-only` | Prints the column used for each field and what to correct; writes nothing. Correct the spreadsheet and run it again |
| 4 · Metadata: write | `python make_metadata.py <project> <spreadsheet>` | `--map FIELD=COLUMN`, `--default FIELD=VALUE`, `--add-field oxygen:sample_oxygen:f:umol/kg:0:500`, `--sheet NAME`, `--bin-column COLUMN` |
| 5 · EcoTaxa tables | `python make_ecotaxa.py <project> --operator "Full Name" --blobs` | `--qcdby`, `--project-name`, `--ship`, `--cruise`, `--workers`; without `--blobs`, no blobs. `--bins BIN_OR_DAY …`: only those bins (or days), made again; a failure keeps the old zip |
| Blobs for zips made by `seastar ifcb_to_ecotaxa` | `python ecotaxa.py --blobs <project> <zip> [<zip> ...]` | Running it twice adds nothing |

Every script has `--help`. The protocol gives examples and what each check means: [docs/PROTOCOL.md](docs/PROTOCOL.md).

### The app

<img src="docs/ifcb_app_icon.png" alt="IFCB pipeline app icon: the IFCB instrument, an arrow, and a grid of plankton vignettes" width="128" align="right">

The same five steps, one page each, in the menu on the left: group **Process** (steps 1 to 5 and Compare EcoTaxa tables), then **EcoTaxa API** and **BODC** (to come). The icon of each step tells where it stands for the project chosen: ✅ done, ⚠️ something to look at, ☐ to do, ⏳ running. **Browse…** buttons for the folders and the spreadsheet, progress bars, the figures and the images shown on the page.

On Windows:

1. Double-click `ifcb_app/create_shortcut.bat` once: it puts an **IFCB pipeline** shortcut on the desktop.
2. Start the app from that shortcut. Keep the black window open while you use the app, and close it to stop the app.

The launcher (`start_ifcb_app.bat`) uses the conda environment `ifcb_app` when there is one, otherwise the Python of the computer. On the first start, it installs the requirements (Streamlit, pandas, Pillow, openpyxl, vl-convert, WHOI ifcb-features and SeaSTAR from the `all-fixes` branch of this fork, which gathers the SeaSTAR fixes of pull request #18 until they are merged). Installing WHOI ifcb-features needs [git](https://git-scm.com).

On any system, after the install of the command line section: `python -m streamlit run app.py` in `ifcb_app`.

The feature extraction and the EcoTaxa tables started from the app run as their own process. They go on if the browser tab is closed, as long as the computer stays on and awake. On one core, a bin of about 5,000 ROIs takes about 2 minutes to extract.

### Files

| File | Role |
|---|---|
| `create_project.py`, `project_status.py`, `make_figures.py`, `show_positions.py`, `extract_features.py`, `show_blobs.py`, `make_metadata.py`, `make_ecotaxa.py` | The command line, one script per step (table above). The app starts `extract_features.py` and `make_ecotaxa.py` itself |
| `app.py` | Starts the app: the menu on the left, in three groups, and the icon of each step |
| `steps/step1_project.py` … `steps/step5_ecotaxa.py` | The pages of steps 1 to 5 |
| `steps/ecotaxa_api.py`, `steps/bodc.py` | The EcoTaxa API and BODC pages (to come) |
| `common.py` | Pieces shared by the pages of the steps: the project chosen, the background runs, where each step stands |
| `compare.py` | Page **Compare EcoTaxa tables**: a text report comparing the column names and types of the EcoTaxa tables of several projects, run when you click Compare |
| `ui.py` | The folder field with **Browse…**, shared by the pages |
| `project.py` | Naming, creating and scanning a project folder (no interface code) |
| `metadata.py` | Builds `metadata_ecotaxa.csv` from the spreadsheet and the chosen columns, and the checks (no interface code) |
| `metadata_columns.csv` | The shared list of metadata fields: EcoTaxa column(s), type `f`/`t`, unit, value if empty, expected range. Columns added from the page are written here |
| `qc.py` | The quality check figures, used by the pages of steps 2 and 4 and by `make_figures.py` (no interface code) |
| `whoi/extract_slim_features.py` | Copied unchanged from WHOI ifcb-features v1.3.1 (MIT licence, `whoi/LICENSE`): this script is not part of the pip package |
| `ecotaxa.py` | Adds the blobs to the EcoTaxa zips made by SeaSTAR, as `img_rank` 1 rows (used by `make_ecotaxa.py --blobs`, or alone: table above) |
| `test_project.py`, `test_metadata.py`, `test_ecotaxa.py` | Tests: `python test_project.py`, `python test_metadata.py`, `python test_ecotaxa.py` |
| `make_icon.py` | Draws `ifcb_app.ico` and `docs/ifcb_app_icon.png` |
