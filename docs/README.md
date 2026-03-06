# Apparatus development

## In this repo

### Next.js web client (`frontend`)

TK

### FastAPI + FastMCP Reader API (`reader_api`)

TK

### Go Publication API (`publication_api`)

TK

### Promptfoo eval suite (`evals`)

TK

### Bruno collections

TK

### Static publication files

TK

## Local development with tmuxp

This project uses `tmuxp` to manage multiple services for local development. tmux allows you to run multiple terminals in a single screen, and tmuxp provides a configuration layer for tmux that facilitates running multiple commands in a pre-defined layout.

To run the app:

1. Make sure you have [tmux](https://github.com/tmux/tmux) and [tmuxp](https://github.com/tmux-python/tmuxp) installed

1. Navigate to the project root directory (where `tmuxp.yaml` is located) and run `tmuxp load .`

This command will create or attach to a tmux session named `aie` with all services running in their respective windows and panes.
