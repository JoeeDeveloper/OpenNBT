#!/usr/bin/env bash
# Run tests, then publish tools to /home/jga/builds/OpenNBT/<short-hash>/ and latest/. Keeps the last 10 hashes.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover tests
hash=$(git rev-parse --short HEAD)
dest=/home/jga/builds/OpenNBT
mkdir -p "$dest/$hash" "$dest/latest"
rm -rf "$dest/latest"/* "$dest/$hash"/*
for d in "$dest/$hash" "$dest/latest"; do
  cp -r tools run_gui.bat README.md "$d"/
  mkdir -p "$d/docs" && cp docs/CAR_CHECKLIST.md "$d/docs/"
  find "$d" -name __pycache__ -type d -prune -exec rm -rf {} +
  # the [builds] share's create mask (0664) strips +x from every copied file; run_gui.bat needs it back or
  # Windows refuses to run it straight off the network share ("you do not have permission to access ...")
  chmod +x "$d/run_gui.bat"
done
ls -1dt "$dest"/*/ | grep -v '/latest/$' | tail -n +11 | xargs -r rm -rf
echo "published $hash -> N:\\OpenNBT\\latest\\"
