## Local Development with tmuxp

This project uses `tmuxp` to manage multiple services for local development.

### 1. Install tmuxp

If you don't have `tmuxp` installed, you can do so using pip:

```bash
pip install --user tmuxp
```

(Ensure `~/.local/bin` is in your PATH, or install globally if preferred.)

### 2. Launch Development Environment

Navigate to the project root directory (where `tmuxp.yaml` is located) and run:

```bash
tmuxp load .
```

This command will create or attach to a tmux session named `aie` with all services running in their respective windows and panes.
