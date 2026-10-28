#!/usr/bin/env bash
# Run from the repository root after installing and signing into the official gh CLI.
# Creates a NEW public repo. It does not modify any existing remote repository.
set -euo pipefail
repo_name="${1:-indexlens}"
if [[ ! "$repo_name" =~ ^[a-zA-Z0-9._-]+$ ]]; then
  echo 'Repository name may contain only letters, numbers, dots, underscores, and hyphens.' >&2
  exit 1
fi
command -v gh >/dev/null || { echo 'Install GitHub CLI from https://cli.github.com first.' >&2; exit 1; }
gh auth status
owner="$(gh api user --jq .login)"
python -m pytest -q
node --check web/app.js
if [[ ! -d .git ]]; then
  git init -b main
  git add .
  git commit -m 'Build IndexLens sparse benchmark replication studio'
fi
gh repo create "$owner/$repo_name" --public --source=. --remote=origin --push --description 'Sparse S&P 500 replication: Python optimization, honest holdout tests, and an interactive portfolio explorer.'
gh api --method POST "repos/$owner/$repo_name/pages" -f build_type=workflow
gh workflow run pages.yml --repo "$owner/$repo_name"
gh repo view "$owner/$repo_name" --json url --jq .url
echo 'Repository created. View the Actions tab for the Pages deployment result.'

