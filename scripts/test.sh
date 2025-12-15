#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
cd ..
bash scripts/get-test-data.sh
mkdir -p testout
#python3 src/main.py ifcb_v4_features -i testdata/*.hdr -o testout/
python3 src/main.py ifcb_to_ecotaxa -i testdata/*.hdr testout/*.csv testmetadata/static_metadata.csv --operator "Placeholder Name" --project "Test Project" --ship "Very Nice Ship" --depth 5 --tableonly -o testout/ecotaxa_test.tsv
#python3 src/main.py ifcb_to_ecotaxa -i testdata/*.hdr --operator "Unknown" --project "PAP" --ship "James Cook" --depth 5 -o testout/ecotaxa_pkg.zip
