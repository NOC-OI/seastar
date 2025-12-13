import sys
import importlib
import os
import json
import math

if __name__ == "__main__":
    python_file_loc = os.path.dirname(os.path.realpath(__file__))

    job_dirs = os.scandir(os.path.join(python_file_loc, "jobs"))
    found_job_modules = {}
    module_io_defs = {}
    for job_dir in job_dirs:
        if job_dir.is_dir():
            full_job_dir = os.path.join(python_file_loc, "jobs", job_dir.name)
            with open(os.path.join(full_job_dir, "io.json"), "r") as io_json_fp:
                module_io_defs[job_dir.name] = json.loads(io_json_fp.read())
                found_job_modules[job_dir.name] = importlib.import_module("jobs." + job_dir.name)
                #options = {}
                #found_job_modules[job_dir.name].MainJob(options)



    #for
    #found_job_modules[module_name] = importlib.import_module(module_path)

    eargs = sys.argv[1:]
    help_flag = False
    ehelp_msg = "No command specified"

    mode = "command"
    mode_stack = []
    capture_heap = []
    command = None
    capture_option = None
    multiple_capture_switch = False
    options = {}
    io_def = None

    for arg in eargs:
        if arg.startswith("--"):
            if multiple_capture_switch:
                multiple_capture_switch = False
                mode = mode_stack.pop() # Break out of the current multiple capture
            if arg == "--help":
                command = "help"
                ehelp_msg = None
                help_flag = True
                break
            else:
                option_recognised = False
                if io_def is not None:
                    for io_def_key in io_def["inputs"].keys():
                        if "cli_arg" in io_def["inputs"][io_def_key].keys():
                            if io_def["inputs"][io_def_key]["cli_arg"] == arg[2:]:
                                capture_option = io_def_key
                                if "multiple" in io_def["inputs"][io_def_key].keys():
                                    multiple_capture_switch = io_def["inputs"][io_def_key]["multiple"]
                                if io_def["inputs"][io_def_key]["type"] == "BOOLEAN":
                                    options[io_def_key] = True
                                else:
                                    mode_stack.append(mode)
                                    if multiple_capture_switch:
                                        mode = "multi_capture"
                                    else:
                                        mode = "single_capture"
                                option_recognised = True
                                break

                if not option_recognised:
                    ehelp_msg = "Unrecognised option \"" + arg + "\""
                    help_flag = True
                    break
        elif arg.startswith("-"):
            if multiple_capture_switch:
                multiple_capture_switch = False
                mode = mode_stack.pop() # Break out of the current multiple capture
            if arg == "-h":
                command = "help"
                ehelp_msg = None
                help_flag = True
                break
            else:
                option_recognised = False
                if io_def is not None:
                    for io_def_key in io_def["inputs"].keys():
                        if "cli_short" in io_def["inputs"][io_def_key].keys():
                            if io_def["inputs"][io_def_key]["cli_short"] == arg[1:]:
                                capture_option = io_def_key
                                if "multiple" in io_def["inputs"][io_def_key].keys():
                                    multiple_capture_switch = io_def["inputs"][io_def_key]["multiple"]
                                if io_def["inputs"][io_def_key]["type"] == "BOOLEAN":
                                    options[io_def_key] = True
                                else:
                                    mode_stack.append(mode)
                                    if multiple_capture_switch:
                                        mode = "multi_capture"
                                    else:
                                        mode = "single_capture"
                                option_recognised = True
                                break

                if not option_recognised:
                    ehelp_msg = "Unrecognised option \"" + arg + "\""
                    help_flag = True
                    break
        else:
            if mode == "command":
                if arg == "help":
                    command = "help"
                    ehelp_msg = None
                    help_flag = True
                    break
                else:
                    if arg in found_job_modules.keys():
                        io_def = module_io_defs[arg]
                        command = arg
                        ehelp_msg = None
                    else:
                        ehelp_msg = "Unrecognised command \"" + arg + "\""
                        help_flag = True
                        break
            elif mode == "multi_capture":
                capture_heap.append(arg)
                options[capture_option] = capture_heap
            elif mode == "single_capture":
                options[capture_option] = arg
                mode = mode_stack.pop()

    if command is None:
        help_flag = True

    if help_flag:
        print("")
        print("SeaSTAR")
        print("Sea-faring System for Tagging, Attribution and Redistribution")
        print("")
        print("Copyright 2025, A Baldwin <alewin@noc.ac.uk>, National Oceanography Centre")
        print("This program comes with ABSOLUTELY NO WARRANTY. This is free software,")
        print("and you are welcome to redistribute it under the conditions of the")
        print("GPL version 3 license.")
        print("")
        if ehelp_msg is not None:
            print("ERROR")
            print(ehelp_msg)
            print("")
        #print("Common usage:")
        #print("    ifcbproc parquet <roi_file> [roi_file...] -o <output_path>")
        #print("    ifcbproc ecotaxa <roi_file> [roi_file...] -o <output_zip_file> [--table example_metadata.csv --join \"tables.example_metadata.filename = file.basename\" [--hide tables.example_metadata.filename]]")
        #print("    ifcbproc features <roi_file> [roi_file...] [-o <output_path>]")
        #print("")
    else:
        print("Preparing job...")

        def prf(prop, etr):
            bar_w = 32
            bar_x = round(bar_w * prop)
            bar_l = "#"*bar_x
            bar_r = "_"*(bar_w - bar_x)
            percent = f"{prop:.2%}"
            secs = round(etr)
            timestr = f"about {secs}s remaining..."
            if secs < 3:
                timestr = "only a few seconds remaining..."
            if secs > 60:
                mins = math.floor(secs / 60)
                secs = secs - (mins * 60)
                timestr = f"about {mins}min {secs}s remaining..."
            if secs > 3600:
                hrs = math.floor(mins / 60)
                mins = mins - (hrs * 60)
                timestr = f"about {hrs}hr {mins}min remaining..."

            print(f"\r[{bar_l}{bar_r}] {percent} done, {timestr}                ", end="")

        main_job_object = found_job_modules[command].MainJob(options, prf)
        print("Processing...")
        main_job_object.execute()
        print("Done!")
