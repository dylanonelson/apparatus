set -e
set -x
set -u
echo "Worktree folder name: $1"
echo "Worktree branch name: $2"
dir_name=$(basename "$(pwd)")
# Create or checkout the branch
if git rev-parse --verify "$2" >/dev/null 2>&1; then
  echo "Found existing branch $2"
else
  git branch "$2"
  echo "Created and checked out new branch $branch_name"
fi
git worktree add ../apparatus-worktrees/$1 $2
cd ../apparatus-worktrees/$1
cp ../../$dir_name/frontend/.env.local ./frontend/
cp ../../$dir_name/reader_api/.env.local ./reader_api/
