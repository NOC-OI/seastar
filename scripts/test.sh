#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
cd ..
bash scripts/get-test-data.sh
mkdir -p testout
python3 src/main.py ifcb_to_ecotaxa -i testdata/*.hdr --operator Testname --project "PAP" --ship "James Cook" --depth 5 --tableonly -o testout/ecotaxa_test.tsv
