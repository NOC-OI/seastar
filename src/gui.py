#!/bin/python3

# Copyright 2025, A Baldwin <alewin@noc.ac.uk>, National Oceanography Centre.
#
# This file is part of SeaSTAR, a tool for processing IFCB data.
#
# SeaSTAR is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License (version 3 only)
# as published by the Free Software Foundation.
#
# SeaSTAR is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License v3
# along with SeaSTAR.  If not, see <http://www.gnu.org/licenses/>.

import tkinter
import tkinter.filedialog
import tkinter.messagebox
import tkinter.scrolledtext

root = tkinter.Tk()

root.title("SeaSTAR")
root.geometry("600x400")
root.columnconfigure(index=0, weight=6)
root.columnconfigure(index=1, weight=2)

standard_xpad = 5
standard_ypad = 5

label = tkinter.Label(root, text="Welcome to SeaSTAR! Start by selecting your input data.")
label.grid(column=0, columnspan=2, row=0, sticky="W", padx=standard_xpad, pady=standard_ypad)

input_files_text = tkinter.scrolledtext.ScrolledText(root, width=8,  height=8)
input_files_text.grid(column=0, row=1, padx=standard_xpad, pady=standard_ypad, sticky="NSEW")
input_files_text.configure(state ='disabled')

def button_execute_onclick():
    label.configure(text="Choose files...")

    valid_filetypes = (
        ('IFCB files', '*.roi *.adc *.hdr'),
        ('Image files', '*.png *.jpg *.jpeg *.tif *.tiff')
    )

    selected_files = tkinter.filedialog.askopenfilenames(
        title='Select input files for processing',
        filetypes=valid_filetypes)

    #tkinter.messagebox.showinfo(
    #    title='Selected files!',
    #    message="Test"
    #)

    #label.configure(text=", ".join(selected_files))
    input_files_text.configure(state="normal")
    input_files_text.insert(tkinter.INSERT, "\n".join(selected_files))
    input_files_text.configure(state="disabled")

#fg="red",

button = tkinter.Button(root, text="Select files", command=button_execute_onclick)
button.grid(column=1, row=1, sticky="SEW", padx=standard_xpad, pady=standard_ypad)

root.mainloop()
