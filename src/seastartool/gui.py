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
import tkinter.font
import os

class ScrollableFrame(tkinter.Frame):
    def _on_mousewheel(self, event):
        # Linux uses Button-4 and Button-5, Windows/Mac use MouseWheel
        if event.num == 4: # Linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux scroll down
            self.canvas.yview_scroll(1, "units")
        else: # Windows and MacOS
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def bind_mouse_wheel(self, widget):
        """Recursively bind mouse wheel to a widget and all its children."""
        # Support for Windows/MacOS
        widget.bind("<MouseWheel>", self._on_mousewheel)
        # Support for Linux
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)

        for child in widget.winfo_children():
            self.bind_mouse_wheel(child)

    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        # 1. Create a canvas object and a vertical scrollbar
        self.canvas = tkinter.Canvas(self)
        self.scrollbar = tkinter.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        # 2. Create the frame that will hold the actual content
        self.scrollable_content = tkinter.Frame(self.canvas)

        # 3. Bind the configuration of the internal frame to the canvas scroll region
        self.scrollable_content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 4. Create a window inside the canvas to house the internal frame
        self.canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")

        # 5. Link the canvas to the scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 6. Pack everything
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        #self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

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

    def render_job_form(self, job_name):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.columnconfigure(index=0, weight=1)
        self.root.rowconfigure(index=1, weight=1)
        self.head_text = self.__create_scrollable_standard_label(self.root, job_name)
        self.head_text[0].grid(column=0, row=0, sticky="ew", padx=self.standard_xpad * 2, pady=self.standard_ypad)

        self.main_scrollable_frame = ScrollableFrame(self.root)
        self.main_scrollable_frame.grid(column=0, row=1, sticky="nsew", padx=0, pady=0)

        for i in range(50):
            tkinter.Label(self.main_scrollable_frame.scrollable_content, text=f"This is item number {i}").pack(pady=5)

        self.main_scrollable_frame.bind_mouse_wheel(self.main_scrollable_frame.scrollable_content)

        #testtext = self.__create_scrollable_standard_label(self.main_scrollable_frame.scrollable_content, "Lorem ipsum dolor sit amet consectetur adipiscing elit. Quisque faucibus ex sapien vitae pellentesque sem placerat. In id cursus mi pretium tellus duis convallis. Tempus leo eu aenean sed diam urna tempor. Pulvinar vivamus fringilla lacus nec metus bibendum egestas. Iaculis massa nisl malesuada lacinia integer nunc posuere. Ut hendrerit semper vel class aptent taciti sociosqu. Ad litora torquent per conubia nostra inceptos himenaeos.")



    def render_start_page(self):
        self.root.columnconfigure(index=0, weight=1)
        self.head_text = self.__create_scrollable_standard_label(self.root, "Welcome to SeaSTAR! Start by selecting a job.")
        self.head_text[0].grid(column=0, row=0, sticky="ew", padx=self.standard_xpad * 2, pady=self.standard_ypad)


        def create_job_onclick_function(hlframe,io_def):
            def closure(event):
                print("Clicked! " + io_def["name"])
                self.render_job_form(io_def_key)
                #hlframe.config(relief=tkinter.SUNKEN)
            return closure

        def create_job_onenter_function(hlframe):
            def closure(event):
                hlframe.config(relief=tkinter.RAISED)
            return closure

        def create_job_onleave_function(hlframe):
            def closure(event):
                hlframe.config(relief=tkinter.GROOVE)
            return closure

        row_index = 0
        for io_def_key in self.module_io_defs.keys():
            print(io_def_key)
            io_def = self.module_io_defs[io_def_key]

            row_index += 1
            job_frame = tkinter.Frame(self.root, borderwidth=2, relief=tkinter.GROOVE)
            job_frame.grid(column=0, row=row_index, sticky="ew", padx=self.standard_xpad * 2, pady=self.standard_ypad)
            job_frame.columnconfigure(index=0, weight=1)
            job_frame.columnconfigure(index=1, weight=0)

            onclick_function = create_job_onclick_function(job_frame,io_def)
            onenter_function = create_job_onenter_function(job_frame)
            onleave_function = create_job_onleave_function(job_frame)
            job_frame.bind("<Button-1>", onclick_function)
            job_frame.bind("<Enter>", onenter_function)
            job_frame.bind("<Leave>", onleave_function)

            if "name" not in io_def.keys():
                io_def["name"] = io_def_key

            name_label = self.__create_scrollable_standard_label(job_frame, io_def["name"])
            name_label[0].grid(column=0, row=0, sticky="ew", padx=self.standard_xpad, pady=self.standard_ypad)
            name_label[0].bind("<Button-1>", onclick_function)
            name_label[0].bind("<Enter>", onenter_function)
            name_label[0].bind("<Leave>", onleave_function)
            name_label[1].bind("<Button-1>", onclick_function)
            name_label[1].bind("<Enter>", onenter_function)
            name_label[1].bind("<Leave>", onleave_function)
            name_label[1].config(font=(self.default_font["family"], self.default_font["size"], "bold"))

            if "description" not in io_def.keys():
                io_def["description"] = "This job is missing a description!"

            description_label = self.__create_scrollable_standard_label(job_frame, io_def["description"])
            description_label[0].grid(column=0, row=1, sticky="ew", padx=self.standard_xpad, pady=self.standard_ypad)
            description_label[0].bind("<Button-1>", onclick_function)
            description_label[0].bind("<Enter>", onenter_function)
            description_label[0].bind("<Leave>", onleave_function)
            description_label[1].bind("<Button-1>", onclick_function)
            description_label[1].bind("<Enter>", onenter_function)
            description_label[1].bind("<Leave>", onleave_function)

    def __init__(self, python_file_loc="", module_io_defs={}):
        self.root = tkinter.Tk()

        self.root.title("SeaSTAR")
        self.root.geometry("600x400")
        self.root.iconphoto(False, tkinter.PhotoImage(file=os.path.join(python_file_loc, "icon.png")))
        self.default_font = tkinter.font.nametofont("TkDefaultFont").actual()
        self.standard_xpad = 5
        self.standard_ypad = 5
        self.module_io_defs = module_io_defs
        self.python_file_loc = python_file_loc



        #button = tkinter.Button(self.root, text="Select files", command=button_execute_onclick)
        #button.grid(column=1, row=1, sticky="SEW", padx=standard_xpad, pady=standard_ypad)

    def enter_mainloop(self):
        self.root.mainloop()
