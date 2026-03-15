# LIDCO VS Code Extension

AI-powered coding assistant for VS Code, powered by the LIDCO daemon.

## Requirements

- A running LIDCO server: `lidco serve` (default port: 7777)

## Features

- **Chat panel** — sidebar webview for conversational AI assistance
- **Run on selection** — send selected code with a prompt to LIDCO
- **Status bar** — live connection indicator
- **Context menu** — Explain / Review selected code

## Commands

| Command | Keybinding | Description |
|---------|-----------|-------------|
| `LIDCO: Open Chat` | `Ctrl+Shift+L` | Open the chat panel |
| `LIDCO: Run on Selection` | — | Send selection + prompt to LIDCO |
| `LIDCO: Review Current File` | — | Code review of active file |
| `LIDCO: Explain Selection` | — | Explain selected code |
| `LIDCO: Review Selection` | — | Review selected code |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `lidco.serverUrl` | `http://localhost:7777` | URL of the LIDCO server |
| `lidco.apiToken` | `""` | Optional API token |
| `lidco.defaultAgent` | `""` | Default agent (leave empty for auto-routing) |
| `lidco.enableInlineCompletions` | `true` | Enable AI completions |
| `lidco.enableHover` | `true` | Enable hover explanations |

## Development

```bash
npm install
npm run compile
```

Press `F5` in VS Code to launch the extension in a new Extension Development Host window.
