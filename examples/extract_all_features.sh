#!/bin/bash

# This example script can be placed in a folder with the standard IFCB file structure for generating V4 features. It will automatically skip files already created, so is suitable for cron jobs.

# Move to directory specified on command input (if specified)
if [ -n "$1" ]; then
    cd $1
else
    echo "No directory to process specified, assuming data is in $(pwd)"
fi

# Make log directory if not existing
mkdir -p logs

# Pattern to match only numeric strings
pattern="+([0123456789])"

# Get all folders in data directory
for candidate_year in * ; do
    candidate_year=$(basename $candidate_year)

    # Select only folders with numeric names (e.g. "2025", but not "blobs")
    if [[ $candidate_year == $pattern ]]; then

        # Grab all day-folders in year folder
        for day_folder_full_path in $candidate_year/* ; do
            day_folder=$(basename $day_folder_full_path)

            # Skip any glob folders
            if [[ $day_folder == "*" ]]; then
                echo "Skipping *"
            else

                # Select all roi files as inputs
                for roi_file_full_path in $day_folder_full_path/*.roi ; do
                    roi_file=$(basename $roi_file_full_path)

                    # Run sea-star with a single roi file and the --ignore flag. The --ignore flag means any already processed files will be skipped. Logs will be saved per-day and will be appended, so no log file is overwritten.
                    seastar ifcb_v4_features -i $roi_file_full_path -o $day_folder_full_path/ --ignore --logfile logs/$(echo $roi_file)_feature_extraction.log
                done
            fi
        done
    fi
done

