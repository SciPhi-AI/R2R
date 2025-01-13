#!/usr/bin/env bash
#
# rename_r2r_to_fuse.sh
#
# Recursively replaces:
#   - "R2R" -> "FUSE"
#   - "r2r" -> "fuse"
# in file contents and filenames, excluding .git directory.
#
# USAGE:
#   ./rename_r2r_to_fuse.sh <TARGET_DIRECTORY>
#
# EXAMPLE:
#   ./rename_r2r_to_fuse.sh /path/to/your/repo
#
# REQUIRES:
#   - bash
#   - find
#   - sed (GNU sed on Linux, BSD sed on macOS)
#
# NOTE:
#   Back up or commit your repo before running. These changes can't be undone easily!

set -euo pipefail

#######################################
# Print usage information.
#######################################
usage() {
  cat <<EOF
Usage: $0 <TARGET_DIRECTORY>

This script will recursively rename "R2R" -> "FUSE" and "r2r" -> "fuse" 
in file contents and filenames within <TARGET_DIRECTORY>, excluding .git.

Example:
    $0 /path/to/dir
EOF
}

#######################################
# Check for required argument (TARGET_DIR).
#######################################
if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

TARGET_DIR="$1"

# Make sure the directory exists
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Error: Directory '$TARGET_DIR' does not exist."
  exit 1
fi

echo "=== Step 1: Replacing 'R2R' -> 'FUSE' and 'r2r' -> 'fuse' in file contents ==="
if [[ "$(uname -s)" == "Darwin" ]]; then
  # macOS (BSD sed requires a backup extension with -i)
  find "$TARGET_DIR" -type f -not -path '*/.git/*' \
    -exec sed -i '' 's/R2R/FUSE/g; s/r2r/fuse/g' {} +
else
  # Linux (GNU sed typically)
  find "$TARGET_DIR" -type f -not -path '*/.git/*' \
    -exec sed -i 's/R2R/FUSE/g; s/r2r/fuse/g' {} +
fi

echo
echo "=== Step 2: Renaming filenames containing 'R2R' -> 'FUSE' ==="
find "$TARGET_DIR" -type f -not -path '*/.git/*' -name "*R2R*" \
  -exec bash -c '
    for f in "$@"; do
      new="${f//R2R/FUSE}"
      echo "Renaming: $f -> $new"
      mv "$f" "$new"
    done
  ' _ {} +

echo
echo "=== Step 3: Renaming filenames containing 'r2r' -> 'fuse' ==="
find "$TARGET_DIR" -type f -not -path '*/.git/*' -name "*r2r*" \
  -exec bash -c '
    for f in "$@"; do
      new="${f//r2r/fuse}"
      echo "Renaming: $f -> $new"
      mv "$f" "$new"
    done
  ' _ {} +

echo
echo "All done! Please review changes (e.g., 'git diff' if this is a Git repo) to ensure they look correct."

