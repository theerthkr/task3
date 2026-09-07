#!/usr/bin/env bash
# Run every dry run (zero SerpApi searches) and capture outputs.
set -u
cd "$(dirname "$0")/.."
mkdir -p dryruns/output
export PYTHONWARNINGS=ignore
for demo in key_store parse rank faces pipeline_dry; do
  .venv/bin/python -m "dryruns.${demo}_demo" 2>&1 | grep -v -E "UserWarning|warnings.warn|FutureWarning|tform.estimate|Applied providers|find model|set det-size" > "dryruns/output/${demo}.txt"
  echo "${demo}: exit ${PIPESTATUS[0]} -> dryruns/output/${demo}.txt"
done
