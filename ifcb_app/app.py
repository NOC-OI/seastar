"""IFCB -> EcoTaxa pipeline in the browser. Menu on the left, in three groups: Process (steps 1 to 5 and the comparison
of EcoTaxa tables), EcoTaxa API and BODC (to come).

Start it with start_ifcb_app.bat (Windows) or:  python -m streamlit run app.py
Everything runs on this computer; no data leaves it.
"""
from pathlib import Path

import streamlit as st
from PIL import Image

import common

REPO = Path(__file__).resolve().parent
st.set_page_config(page_title="IFCB pipeline", page_icon=Image.open(REPO / "ifcb_app.ico"), layout="wide")

# A widget's value is forgotten when its page is left: kept here, as this file runs before every page.
for key in ("project", "parent", "mode", "serial", "cruise_id", "cruise_name", "meta_file", "meta_project"):
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]

# The icon of each step tells where it stands for the project chosen (✅ done, ⚠️ to look at, ☐ to do, 🔄 running).
folder = common.chosen_project()
states = common.progress(folder) if folder else {}
steps = [st.Page(REPO / common.STEP_PAGES[n], title=title, default=n == 1,
                 icon=common.ICONS[states[n][0]] if n in states else None)
         for n, title in common.STEP_TITLES.items()]
st.navigation({
    "Process": steps + [st.Page(REPO / "compare.py", title="Compare EcoTaxa tables", icon="🔍")],
    "EcoTaxa API": [st.Page(REPO / "steps" / "ecotaxa_api.py", title="EcoTaxa API (to come)", icon="🌐")],
    "BODC": [st.Page(REPO / "steps" / "bodc.py", title="BODC tables (to come)", icon="🗂️")],
}).run()
