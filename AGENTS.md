# This repo

This repo is an AI-powered ereading application that includes a frontend and backend. The frontend is a fork of https://github.com/edrlab/thorium-web and so this app uses the Readium Architecture for serving and navigating ebooks.

There are multiple code workspaces and each one is largely configured in its own folder. When using Cursor or VSCode, the config files are in the _.code-workspace file in the root folder and in _/.vscode/settings.json.

## Architecture

The frontend is a next.js app. The next.js backend serves as a backend-for-frontend for this web app. It converts the cookie auth into an api token to submit to the reader api.

The http api in reader_api is the sole public facing api. It exposes endpoints for retrieving user data and making LLM queries at /api; streaming epubs on the to the web client at /read; and an mcp server that exposes reading and publication data at /mcp.

The go service in publication_api is responsible for manipulating epub content and uses readium libraries (available esclusively in go) to do so.

Authentication is handled through Auth0.

## Dependencies

Dependencies are managed using pip and pip-tools. Dependencies are listed in both requirements.in (for production) and dev.in (for development), then compiled with pinned hashes into requirements.txt and dev.txt. To find which dependencies are included in the project or to add a new dependency, see the .in files.

Node & npm version inside frontend is managed by nvm.

Python version inside reader_api is managed by pyenv.

Go version inside publication_api is managed by goenv.

# Instructions

Make changes based only on the instructions in my prompt. If you think other actions are necessary or would be helpful, ask before adding them to the plan or doing them. When the prompt is vague or doesn't include specific instructions, create a more concrete set of steps and ask for confirmation before carrying them out.

If the prompt is a question that doesn't explicitly ask for you to take action but you think an action would be appropriate, create a plan for me to approve before doing anything. When I ask for an explanation of something, you don't have to make a plan; just give me an explanation.

After making changes, do a pass through the affected files to clean up any unused or redundant code.
