set -e
set -x
set -u
echo "Worktree folder name: $1"
echo "Worktree branch name: $2"
dir_name=$(basename "$(pwd)")
git branch $2
git worktree add ../apparatus-worktrees/$1 $2
cd ../apparatus-worktrees/$1
cp ../$dir_name/frontend/.env.local ./frontend/
cp ../$dir_name/reader_api/.env.local ./reader_api/