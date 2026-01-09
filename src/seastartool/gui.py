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
import os

class SeaSTARGUI():
    def __set_dynamic_reflow(self, widget):
        widget.master.bind("<Configure>", self.__get_reflow_closure(widget))

    def __get_reflow_closure(self, widget):
        def closure(event):
            widget.config(wraplength=widget.master.winfo_width())
        return closure

    def __create_scrollable_standard_label(self, parent, text):
        container = tkinter.Frame(parent)

        label = tkinter.Label(container, text=text, justify="left")
        label.pack(anchor="w")
        self.__set_dynamic_reflow(label)

        return (container, label)

    def __init__(self, python_file_loc="", module_io_defs={}):
        self.root = tkinter.Tk()

        self.root.title("SeaSTAR")
        self.root.geometry("600x400")
        self.root.iconphoto(False, tkinter.PhotoImage(file=os.path.join(python_file_loc, "icon.png")))
        self.root.columnconfigure(index=0, weight=1)
        #self.root.rowconfigure(index=1, weight=2)

        self.standard_xpad = 5
        self.standard_ypad = 5

        self.head_text = self.__create_scrollable_standard_label(self.root, "Welcome to SeaSTAR! Start by selecting a job.")
        self.head_text[0].grid(column=0, row=0, sticky="ew", padx=self.standard_xpad * 2, pady=self.standard_ypad)


        row_index = 0
        for io_def_key in module_io_defs.keys():
            print(io_def_key)
            io_def = module_io_defs[io_def_key]
            row_index += 1
            job_frame = tkinter.Frame(self.root, borderwidth=2, relief=tkinter.GROOVE)
            job_frame.grid(column=0, row=row_index, sticky="ew", padx=self.standard_xpad * 2, pady=self.standard_ypad)
            job_frame.columnconfigure(index=0, weight=1)
            job_frame.columnconfigure(index=1, weight=0)

            if "name" not in io_def.keys():
                io_def["name"] = io_def_key

            name_label = self.__create_scrollable_standard_label(job_frame, io_def["name"])
            name_label[0].grid(column=0, row=0, sticky="ew", padx=self.standard_xpad, pady=self.standard_ypad)

            if "description" not in io_def.keys():
                io_def["description"] = "This job is missing a description!"

            description_label = self.__create_scrollable_standard_label(job_frame, io_def["description"])
            description_label[0].grid(column=0, row=1, sticky="ew", padx=self.standard_xpad, pady=self.standard_ypad)




        #input_files_text = tkinter.scrolledtext.ScrolledText(self.root, width=8,  height=8)
        #input_files_text.grid(column=0, row=1, padx=standard_xpad, pady=standard_ypad, sticky="NSEW")
        #input_files_text.configure(state ='disabled')

        #def button_execute_onclick():
        #    label.configure(text="Choose files...")#

        #    valid_filetypes = (
        #        ('IFCB files', '*.roi *.adc *.hdr'),
        #        ('Image files', '*.png *.jpg *.jpeg *.tif *.tiff')
        #    )

        #    selected_files = tkinter.filedialog.askopenfilenames(
        #        title='Select input files for processing',
        #        filetypes=valid_filetypes)

            #tkinter.messagebox.showinfo(
            #    title='Selected files!',
            #    message="Test"
            #)

            #label.configure(text=", ".join(selected_files))
        #    input_files_text.configure(state="normal")
        #    input_files_text.insert(tkinter.INSERT, "\n".join(selected_files))
        #    input_files_text.configure(state="disabled")

        #fg="red",

        #button = tkinter.Button(self.root, text="Select files", command=button_execute_onclick)
        #button.grid(column=1, row=1, sticky="SEW", padx=standard_xpad, pady=standard_ypad)

    def enter_mainloop(self):
        self.root.mainloop()
