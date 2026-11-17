"""IFCB -> EcoTaxa pipeline in the browser: the two pages of the app.

Start it with start_ifcb_app.bat (Windows) or:  python -m streamlit run app.py
Everything runs on this computer; no data leaves it.
"""
from pathlib import Path

import streamlit as st
from PIL import Image

REPO = Path(__file__).resolve().parent
st.set_page_config(page_title="IFCB pipeline", page_icon=Image.open(REPO / "ifcb_app.ico"), layout="wide")
st.navigation([st.Page(REPO / "process.py", title="Process a project", default=True),
               st.Page(REPO / "compare.py", title="Compare EcoTaxa tables")]).run()
