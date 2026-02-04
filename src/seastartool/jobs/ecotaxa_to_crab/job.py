import os
import libifcb
from datetime import datetime, timezone
import csv
import json
import re
import zipfile
import io
import time

csv.field_size_limit(1024 * 1024 * 1024)

class EcoTaxaTSVReader:
    def __init__(self, tsv_fh):
        self.tsv_fh = tsv_fh
        self.tsv_fh.seek(0, os.SEEK_END)
        self.tsv_total_size = self.tsv_fh.tell()
        self.tsv_fh.seek(0)
        self.tsv_reader = csv.reader(self.tsv_fh, delimiter='\t', quotechar='"')
        self.column_names = next(self.tsv_reader)
        self.column_types = next(self.tsv_reader)
        self.last_row = next(self.tsv_reader)
        self.last_row_index = 0
        self.last_row_offset = self.tsv_fh.tell()

    def __iter__(self):
        return self

    def __next__(self):
        if self.last_row is None:
            raise StopIteration()

        parsed_row = self.last_row

        try:
            self.last_row_index += 1
            self.last_row = next(self.tsv_reader)
            self.last_row_offset = self.tsv_fh.tell()
        except StopIteration:
            self.last_row = None

        return parsed_row


class EcoTaxaDump:
    def __init__(self, tsv_list, other_files_list):
        self.tsvs = []
        self.other_files = {}
        for tsv_path in tsv_list:
            self.tsvs.append(EcoTaxaTSVReader(open(tsv_path, "r")))

        print(next(self.tsvs[0]))

class MainJob:
    def calc_progress_report(self):
        self.last_time = time.time()
        proportion = self.currently_processing/self.total_rois
        elapsed_time = self.last_time - self.first_time
        time_per_roi = elapsed_time / self.currently_processing
        remaining_rois = self.total_rois - self.currently_processing
        remaining_time = time_per_roi * remaining_rois
        self.report_progress(proportion, remaining_time)

    def __init__(self, options, progress_reporting_function = lambda prop, etr : print(str(int(prop*10000)/100) + "% done - ETR " + str(int(etr)) + "s"), log_function = lambda txt : print("[LOG] " + txt), error_function = lambda txt : print("[ERR] " + txt)):

        self.options = options
        self.report_progress = progress_reporting_function
        self.log_function = log_function
        self.error_function = error_function

        #print(options)

        if "data_file" in options.keys():
            self.with_images = True
        else:
            self.with_images = False

        input_files_list = []
        for input_file_path in options["input_files"]:
            input_files_list.append(os.path.abspath(input_file_path))



        #intermediate_files_list = set()
        tsv_files_list = set()
        other_files_list = set()
        for file_name in input_files_list:
            splitext = os.path.splitext(file_name)
            if (splitext[1] == ".tsv"):
                tsv_files_list.add(file_name)
            else:
                other_files_list.add(file_name)

        tsv_files_list = list(tsv_files_list)
        other_files_list = list(other_files_list)
        if len(tsv_files_list) == 0:
            raise RuntimeException("No TSV files supplied!")

        self.eco_taxa_dump_obj = EcoTaxaDump(tsv_files_list, other_files_list)

    def execute(self):
        self.first_time = time.time()
        self.currently_processing = 0
        self.last_time = time.time()




