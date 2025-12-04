set -e
set -x
dir_name=$(basename "$(pwd)")
git branch $2
git worktree add ../$1 $2
cd ../$1
cp ../$dir_name/frontend/.env.local ./frontend/
cp ../$dir_name/reader_api/.env ./reader_api/
cd frontend
pnpm i
cd ../reader_api
make setup
