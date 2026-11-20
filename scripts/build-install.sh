#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"
cd ..
bash scripts/get-test-data.sh
mkdir -p dist
mkdir -p testout
rm dist/*
rm testout/*

VERSION_STRING=$(git describe --tags)
cat > src/seastartool/version_string.py << EOF
# NOTE: This file is auto-generated at build time to allow reference to the version without requiring manual updates
version_string = "$VERSION_STRING"
EOF

python3 -m build
pip install --force-reinstall --no-deps dist/seastartool*.whl
