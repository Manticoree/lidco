# Android Studio Plugin

The LIDCO IntelliJ plugin connects Android Studio (and any JetBrains IDE) to the LIDCO HTTP server, providing AI-powered chat, code review, explanations, refactoring, and inline completion.

## Prerequisites

1. Android Studio Koala (2024.1) or later / IntelliJ IDEA 2024.1+
2. LIDCO server running (`lidco serve`)
3. JDK 17+ (for building from source)

## Installation

### From Source

```bash
cd ide/android-studio-plugin

# Build the plugin
./gradlew buildPlugin

# The .zip will be at:
# build/distributions/lidco-intellij-plugin-0.1.0.zip
```

Install in Android Studio:
1. **Settings** > **Plugins** > gear icon > **Install Plugin from Disk...**
2. Select `build/distributions/lidco-intellij-plugin-0.1.0.zip`
3. Restart the IDE

### Run in Dev Mode

```bash
cd ide/android-studio-plugin
./gradlew runIde
```

This launches a sandboxed IDE instance with the plugin pre-installed.

## Configuration

Open **Settings** > **Tools** > **LIDCO**:

| Setting | Default | Description |
|---------|---------|-------------|
| Server URL | `http://127.0.0.1:8321` | LIDCO server address |
| API Token | _(empty)_ | Bearer token (must match `LIDCO_API_TOKEN` on server) |
| Default Agent | _(empty)_ | Pre-select an agent (empty = auto-route) |
| Enable SSE streaming | `true` | Stream responses chunk-by-chunk |

## Features

### 1. Chat Window

Open: **View** > **Tool Windows** > **LIDCO** (or click the LIDCO icon in the right sidebar)

- Type a message and press **Enter** to send
- Press **Shift+Enter** for a new line
- Select an agent from the dropdown (or leave on "auto")
- Responses render with Markdown formatting and code highlighting
- With streaming enabled, text appears progressively

### 2. Context Menu Actions

Select code in the editor, right-click, and find the **LIDCO** submenu:

| Action | What it does |
|--------|-------------|
| **Review Code** | Sends selected code to the `reviewer` agent. Shows findings in a notification. |
| **Explain Code** | Sends selected code to the `coder` agent for explanation. |
| **Refactor** | Sends selected code to the `refactor` agent for improvement suggestions. |
| **Send to Chat** | Copies selected code (with file path and line numbers) to clipboard and opens the LIDCO chat window. |

All actions are only enabled when text is selected.

### 3. Inline Completion (Alt+L)

Press **Alt+L** anywhere in the editor to trigger an AI completion:

1. The plugin sends the current file content and cursor position to `/api/complete`
2. The server generates a completion using the configured LLM
3. The completion text is inserted at the cursor position

You can also get AI suggestions in the normal autocomplete popup (Ctrl+Space). LIDCO suggestions appear with an "(LIDCO)" suffix and "AI" type text.

### 4. Status Bar Widget

In the bottom-right status bar, you'll see:

- **LIDCO: gpt-4o-mini** — connected, showing current model
- **LIDCO: offline** — server not reachable

Click the widget to refresh the connection status. The widget auto-refreshes every 30 seconds.

## Workflow Example

```
1. Start the server:        lidco serve
2. Open Android Studio
3. Open a Kotlin file
4. Select a function
5. Right-click > LIDCO > Review Code
6. Read the review in the notification
7. Open LIDCO chat (right sidebar)
8. Ask: "How can I optimize this function for coroutines?"
9. Apply suggestions
10. Press Alt+L to complete a new line with AI
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Alt+L** | Inline AI completion at cursor |

To customize, go to **Settings** > **Keymap** and search for "LIDCO".

## Plugin Structure

```
com.lidco.plugin/
├── LidcoPlugin.kt              # Startup: checks server connectivity
├── settings/
│   └── LidcoSettings.kt        # Persistent settings + settings UI
├── api/
│   ├── LidcoClient.kt          # HTTP client (OkHttp + SSE)
│   └── Models.kt               # Request/response data classes
├── chat/
│   ├── ChatToolWindowFactory.kt # Registers the tool window
│   ├── ChatToolWindow.kt        # Chat UI with input, agent selector, SSE
│   └── MessagePanel.kt          # Markdown rendering (CommonMark)
├── actions/
│   ├── ReviewAction.kt          # Context menu: Review
│   ├── ExplainAction.kt         # Context menu: Explain
│   ├── RefactorAction.kt        # Context menu: Refactor
│   ├── SendToChatAction.kt      # Context menu: Send to Chat
│   └── ActionUtils.kt           # Shared notification helpers
├── completion/
│   ├── LidcoCompletionProvider.kt  # Autocomplete contributor
│   └── InlineCompleteAction.kt     # Alt+L action
└── statusbar/
    └── LidcoStatusWidget.kt     # Connection status in status bar
```
