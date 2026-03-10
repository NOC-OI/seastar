#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
cd ..
bash scripts/build-install.sh

#seastar ifcb_to_ecotaxa -i "testdata/*.hdr" testdata/*.csv testmetadata/static_metadata.csv --operator "Placeholder" --qcdby "AB" --project "Test Project" --ship "Very Nice Ship" --depth 5 --tableonly --nonull -o testout/ecotaxa_test.tsv
seastar ifcb_to_ecotaxa -i "testdata/*.hdr" testdata/*.csv testmetadata/static_metadata.csv --operator "Lee" --reallyignoreshortnames --qcdby "Placeholder Name" --project "Test Project" --ship "Very Nice Ship" --depth 5 --tableonly --nonull -o testout/ecotaxa_test.tsv --logfile testout/seastar.log
#seastar ecotaxa_to_crab -i testout/ecotaxa_test.tsv --dataout testout/data.parquet --annotout testout/annot.parquet
