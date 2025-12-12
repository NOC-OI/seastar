import os
import libifcb
from datetime import datetime, timezone
import csv
import json

class IFCBEntryProvider:
    def __init__(self, roi_readers, ifcb_ids, with_images = True, options = {}):
        self.roi_readers = roi_readers
        self.ifcb_ids = ifcb_ids
        self.with_images = with_images
        self.reader_index = 0
        self.index = 0
        self.options = options

        self.ecotaxa_table_header = {
                "object_id": "[t]",
                "object_lat": "[f]",
                "object_lon": "[f]",
                "object_date": "[t]",
                "object_time": "[t]",
                "object_area": "[f]",
                "object_convexarea": "[f]",
                "object_convexperimeter": "[f]",
                "object_roi_width": "[f]",
                "object_roi_height": "[f]",
                "process_id": "",
                "process_date": "[t]",
                "process_time": "[t]",
                "process_pixel_um": "[f]",
                "process_feature_extractor": "[t]",
                "process_min_thresh": "[f]",
                "process_max_thresh": "[f]",
                "acq_id": "[t]",
                "acq_operator": "[t]",
                "acq_instrument": "[t]",
                "acq_sn": "[t]",
                "acq_volimage": "[f]",
                "acq_min_esd": "[f]",
                "acq_max_esd": "[f]",
                "acq_run_time": "[f]",
                "acq_grab_time_start": "[f]",
                "acq_trigger_number": "[f]",
                "acq_peak_a": "[f]",
                "acq_pmt_a": "[f]",
                "acq_peak_b": "[f]",
                "acq_pmt_b": "[f]",
                "acq_grab_time_end": "[f]",
                "acq_adc_time": "[f]",
                "acq_signal_length": "[f]",
                "acq_inhibit_time": "[f]",
                "acq_status": "[f]",
                "acq_time_of_flight": "[f]",
                "acq_start_point": "[f]",
                "sample_id": "[t]",
            }

        self.static_additions = {
            }

        if "ship_name" in self.options.keys():
            self.static_additions["sample_ship"] = self.options["ship_name"]
            self.ecotaxa_table_header["sample_ship"] = "[t]"
        if "cruise_name" in self.options.keys():
            self.static_additions["sample_cruise"] = self.options["cruise_name"]
            self.ecotaxa_table_header["sample_cruise"] = "[t]"
        if "project_name" in self.options.keys():
            self.static_additions["sample_project"] = self.options["project_name"]
            self.ecotaxa_table_header["sample_project"] = "[t]"


        if "station_id" in self.options.keys():
            self.static_additions["sample_stationid"] = self.options["station_id"]
            self.ecotaxa_table_header["sample_stationid"] = "[t]"
        if "ctd_cast" in self.options.keys():
            self.static_additions["sample_ctdcast"] = self.options["ctd_cast"]
            self.ecotaxa_table_header["sample_ctdcast"] = "[t]"
        if "sample_barcode" in self.options.keys():
            self.static_additions["sample_barcode"] = self.options["sample_barcode"]
            self.ecotaxa_table_header["sample_barcode"] = "[t]"
        if "sample_comment" in self.options.keys():
            self.static_additions["sample_comment"] = self.options["sample_comment"]
            self.ecotaxa_table_header["sample_comment"] = "[t]"
        if "sampling_gear" in self.options.keys():
            self.static_additions["sample_samplinggear"] = self.options["sampling_gear"]
            self.ecotaxa_table_header["sample_samplinggear"] = "[t]"
        if "initial_collected_volume_m3" in self.options.keys():
            self.static_additions["sample_initial_col_vol_m3"] = self.options["initial_collected_volume_m3"]
            self.ecotaxa_table_header["sample_initial_col_vol_m3"] = "[f]"
        if "concentrated_sample_volume_m3" in self.options.keys():
            self.static_additions["sample_concentrated_sample_volume"] = self.options["concentrated_sample_volume_m3"]
            self.ecotaxa_table_header["sample_concentrated_sample_volume"] = "[f]"
        if "dilution_factor" in self.options.keys():
            self.static_additions["sample_dilution_factor"] = self.options["dilution_factor"]
            self.ecotaxa_table_header["sample_dilution_factor"] = "[f]"
        if "operator_name" in self.options.keys():
            self.static_additions["sample_operator"] = self.options["operator_name"]
            self.ecotaxa_table_header["sample_operator"] = "[t]"
        if "dilution_method" in self.options.keys():
            self.static_additions["sample_dilution_method"] = self.options["dilution_method"]
            self.ecotaxa_table_header["sample_dilution_method"] = "[t]"
        if "fixative" in self.options.keys():
            self.static_additions["sample_fixative"] = self.options["fixative"]
            self.ecotaxa_table_header["sample_fixative"] = "[t]"
        if "sieve_min_um" in self.options.keys():
            self.static_additions["sample_sieve_min_um"] = self.options["sieve_min_um"]
            self.ecotaxa_table_header["sample_sieve_min_um"] = "[f]"
        if "sieve_max_um" in self.options.keys():
            self.static_additions["sample_sieve_max_um"] = self.options["sieve_max_um"]
            self.ecotaxa_table_header["sample_sieve_max_um"] = "[f]"


        if self.with_images:
            print("With images!")
            self.ecotaxa_table_header["img_file_name"] = "[t]"
            self.ecotaxa_table_header["img_rank"] = "[f]"

    def __iter__(self):
        return self

    def __next__(self):
        if self.index < len(self.roi_readers[self.reader_index].rois):
            roi = self.roi_readers[self.reader_index].rois[self.index]
            self.index += 1
            if self.index >= len(self.roi_readers[self.reader_index].rois):
                if self.reader_index < (len(self.roi_readers) - 1):
                    self.reader_index += 1
                    self.index = 0
            dt = datetime.strptime(self.ifcb_ids[self.reader_index].split("_")[0], "D%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            observation_id = self.ifcb_ids[self.reader_index] + "_" + str(roi.index).zfill(5)

            extents = [(0, roi.array.shape[0]), (0, roi.array.shape[1])]
            origin_extents = roi.array.shape

            #print(roi.trigger.raw.keys())

            trigger_values = {}
            for key in roi.trigger.raw.keys():
                trigger_values[key] = float(roi.trigger.raw[key])

            #print(json.dumps(list(trigger_values.keys()), indent=4))

            #print(self.options)

            record = {
                "object_id": observation_id,
                "object_lat": None,
                "object_lon": None,
                "object_date": dt.strftime("%Y-%m-%d"),
                "object_time":  dt.strftime("%H:%M:%S"),
                "object_area": None,
                "object_convexarea": None,
                "object_convexperimeter": None,
                "object_roi_width": None,
                "object_roi_height": None,
                "process_id": None,
                "process_date": None,
                "process_time": None,
                "process_pixel_um": None,
                "process_feature_extractor": None,
                "process_min_thresh": None,
                "process_max_thresh": None,
                "acq_id": self.ifcb_ids[self.reader_index] + "_TN" + str(int(trigger_values["trigger_number"])),
                "acq_instrument": "IFCB",
                "acq_sn": self.ifcb_ids[self.reader_index].split("_")[1][4:],
                "acq_volimage": None,
                "acq_min_esd": None,
                "acq_max_esd": None,
                "acq_operator": self.options["operator_name"],
                "acq_run_time": trigger_values["run_time"],
                "acq_trigger_number": trigger_values["trigger_number"],
                "acq_peak_b": trigger_values["peak_b"],
                "acq_pmt_b": trigger_values["pmt_b"],
                "acq_peak_a": trigger_values["peak_a"],
                "acq_pmt_a": trigger_values["pmt_a"],
                "acq_grab_time_end": trigger_values["grab_time_end"],
                "acq_grab_time_start": trigger_values["grab_time_start"],
                "acq_adc_time": trigger_values["adc_time"],
                "acq_signal_length": trigger_values["signal_length"],
                "acq_inhibit_time": trigger_values["inhibit_time"],
                "acq_status": trigger_values["status"],
                "acq_time_of_flight": trigger_values["time_of_flight"],
                "acq_start_point": trigger_values["start_point"],
                "sample_id": self.ifcb_ids[self.reader_index],
            }

            # Add in denormalised data for the whole sample
            for key in self.static_additions.keys():
                record[key] = self.static_additions[key]

            if self.with_images:
                record["img_file_name"] = observation_id + ".png"
                record["img_rank"] = None
                return (record, roi.image)
            else:
                return (record, )
        raise StopIteration

class MainJob:
    def __init__(self, options):

        self.options = options
        print(options)
        input_files_list = []
        for input_file_path in options["input_files"]:
            input_files_list.append(os.path.realpath(input_file_path))

        print(input_files_list)

        ifcb_bins = []
        ifcb_files = []
        roi_readers = []

        intermediate_files_list = set()
        for file_name in input_files_list:
            intermediate_files_list.add(os.path.splitext(file_name)[0])

        for file_name in intermediate_files_list:
            ifcb_bins.append(os.path.basename(file_name))
            ifcb_files.append(file_name)


        for i in range(len(ifcb_files)):
            roi_readers.append(libifcb.ROIReader(ifcb_files[i] + ".hdr", ifcb_files[i] + ".adc", ifcb_files[i] + ".roi"))

        self.entry_provider = IFCBEntryProvider(roi_readers, ifcb_bins, False, options)

    def execute(self):
        with open(self.options["output_file"], "w") as ecotaxa_md:
            ecotaxa_md_writer = csv.DictWriter(ecotaxa_md, fieldnames=self.entry_provider.ecotaxa_table_header.keys(), quoting=csv.QUOTE_NONNUMERIC, delimiter='\t', lineterminator='\n')
            ecotaxa_md_writer.writeheader()
            ecotaxa_md_writer.writerow(self.entry_provider.ecotaxa_table_header)

            try:
                while True:
                    entry = next(self.entry_provider)
                    ecotaxa_md_writer.writerow(entry[0])
            except StopIteration:
                pass



