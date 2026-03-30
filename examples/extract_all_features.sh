#!/bin/bash

# This example script can be placed in a folder with the standard IFCB file structure for generating V4 features. It will automatically skip files already created, so is suitable for cron jobs.

mkdir -p logs

pattern="+([0123456789])"

for candidate_year in * ; do
    candidate_year=$(basename $candidate_year)
    if [[ $candidate_year == $pattern ]]; then
        for day_folder_full_path in $candidate_year/* ; do
            day_folder=$(basename $day_folder_full_path)
            if [[ $day_folder == "*" ]]; then
                echo "Skipping *"
            else
                for roi_file_full_path in $day_folder_full_path/* ; do
                    roi_file=$(basename $roi_file_full_path)
                    #echo $roi_file_full_path
                    if [[ $roi_file == *.roi ]]; then
                        #echo $roi_file_full_path
                        seastar ifcb_v4_features -i $roi_file_full_path -o $day_folder_full_path/ --ignore --logfile logs/$(echo $roi_file)_feature_extraction.log
                    fi

                done
            fi
        done
    fi
done

