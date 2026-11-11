#!/usr/bin/env bash
# Refuse commits that would put match data, submissions or big files into git history.
# Run as a pre-commit hook (scripts/install_hooks.sh) and in CI on every push.
set -euo pipefail

mode="${1:-staged}"
if [ "$mode" = "staged" ]; then
  files=$(git diff --cached --name-only --diff-filter=ACMR)
else
  files=$(git ls-files)
fi

bad=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    vendor/*) continue ;;
    data/README.md) ;;
    data/*|submissions/*|devdata/*|*.mp4|*_atd.txt|*_atd.xml|*_homography.csv|*_smart_tagging.xml|*.npz|*.parquet)
      echo "BLOCKED: $f is data or a submission -- it must never be committed"; bad=1 ;;
  esac
  if [ -f "$f" ]; then
    size=$(wc -c < "$f" | tr -d ' ')
    if [ "$size" -gt 1000000 ]; then
      echo "BLOCKED: $f is ${size} bytes (>1 MB). Code only in this repo."; bad=1
    fi
    # A frame,label CSV with ~199k rows is a submission whatever it is called.
    case "$f" in *.csv)
      if head -1 "$f" | grep -qi '^frame,label'; then
        echo "BLOCKED: $f looks like a submission (frame,label header)"; bad=1
      fi ;;
    esac
  fi
done <<< "$files"

exit $bad
