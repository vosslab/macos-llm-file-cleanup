#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

python -m macos_llm_file_cleanup -h >/dev/null

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "hello world" > "${TMP_DIR}/example.txt"
echo "col1,col2" > "${TMP_DIR}/data.csv"

python -m macos_llm_file_cleanup \
	--paths "${TMP_DIR}" \
	--max-files 2 \
	--one-by-one \
	--dry-run \
	>/dev/null

echo "Smoke OK"
