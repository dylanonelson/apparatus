#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: start-work-branch <work-name>" >&2
  exit 1
fi

work_name="$1"
date_prefix="$(date +%Y-%m-%d)"
branch_name="${date_prefix}_${work_name}"
spec_file="specs/${branch_name}.md"

# Create the spec file if it doesn't exist
if [ ! -f "$spec_file" ]; then
  touch "$spec_file"
  echo "Created $spec_file"
else
  echo "$spec_file already exists"
fi

# Create or checkout the branch
if git rev-parse --verify "$branch_name" >/dev/null 2>&1; then
  git checkout "$branch_name"
  echo "Checked out existing branch $branch_name"
else
  git checkout -b "$branch_name"
  echo "Created and checked out new branch $branch_name"
fi

git push origin "$branch_name"

