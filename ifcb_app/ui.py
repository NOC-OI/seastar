"""Page pieces shared by the two pages of the app."""
from pathlib import Path

import streamlit as st

DEFAULT_PARENT = "Y:\\" if Path("Y:/").is_dir() else str(Path.home())


def browse(key):
    """Folder dialog of this computer (the app runs locally)."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    path = filedialog.askdirectory(initialdir=st.session_state.get(key) or DEFAULT_PARENT, parent=root)
    root.destroy()
    if path:
        st.session_state[key] = str(Path(path))


def folder_input(label, key, help_, status=None):
    """Folder field; `status` = (ok, text) is shown in its title, green when ok, red otherwise."""
    if status is not None:
        ok, text = status
        label = f":green[✅ **{label}** · {text}]" if ok else f":red[⚠️ **{label}** · {text}]"
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    c1.text_input(label, key=key, help=help_)
    c2.button("Browse…", key=f"b_{key}", on_click=browse, args=(key,), width="stretch")
    return Path(st.session_state[key]) if st.session_state.get(key) else None
