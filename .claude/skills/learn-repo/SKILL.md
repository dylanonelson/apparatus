---
name: learn-repo
description: A set of steps to follow to understand this repo
user-invocable: true
---

# YOUR ROLE - CODING ASSISTANT

You a coding assistant for a full-stack e-reading application. You are working
in a git worktree on a branch and you are running in a Docker container.

## STEP 1: GET YOUR BEARINGS

```bash
# 1. See your working directory
pwd

# 2. List files to understand project structure
ls -la
```

## STEP 2: UNDERSTAND THE PROJECT

Make sure you understand the app's core features. Check if the development servers are running already.

```
# 1. Read the product and technical READMEs to understand the purpose and basic layout of the app.
cat README.md
cat docs/README.md

# 2. Read the tmuxp config to understand how to start the component services.
cat tmuxp.yaml

# 3. Check recent git history
git log --oneline -20
```

## STEP 3: RUN DEVELOPMENT SERVERS

If necessary, run the script in scripts/start-services.sh to start the
necessary component servers. If a dependency is missing, you can inspect how
this environment was set up by looking at claude.Dockerfile.
