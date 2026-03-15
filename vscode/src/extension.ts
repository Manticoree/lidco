/**
 * LIDCO VS Code Extension — entry point.
 *
 * Provides:
 *   - Sidebar webview panel showing chat history
 *   - `lidco.chat` command — open chat panel
 *   - `lidco.runOnSelection` command — send selected code + prompt to lidco daemon
 *   - Status bar item showing lidco connection status
 */

import * as vscode from 'vscode';
import { LidcoClient } from './lidco_client';

let statusBarItem: vscode.StatusBarItem;
let client: LidcoClient;
let chatPanel: vscode.WebviewPanel | undefined;

export function activate(context: vscode.ExtensionContext): void {
    const config = vscode.workspace.getConfiguration('lidco');
    const serverUrl: string = config.get('serverUrl', 'http://localhost:7777');

    client = new LidcoClient(serverUrl);

    // Status bar
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.text = '$(loading~spin) LIDCO';
    statusBarItem.tooltip = 'LIDCO connection status';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Poll connection status
    checkConnection();
    const pollInterval = setInterval(() => checkConnection(), 10000);
    context.subscriptions.push({ dispose: () => clearInterval(pollInterval) });

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('lidco.chat', () => openChatPanel(context)),
        vscode.commands.registerCommand('lidco.runOnSelection', () => runOnSelection()),
        vscode.commands.registerCommand('lidco.openChat', () => openChatPanel(context)),
        vscode.commands.registerCommand('lidco.reviewFile', () => reviewCurrentFile()),
        vscode.commands.registerCommand('lidco.explainSelection', () => explainSelection()),
        vscode.commands.registerCommand('lidco.reviewSelection', () => reviewSelectionCmd()),
    );
}

export function deactivate(): void {
    if (chatPanel) {
        chatPanel.dispose();
    }
}

async function checkConnection(): Promise<void> {
    const alive = await client.ping();
    if (alive) {
        statusBarItem.text = '$(check) LIDCO';
        statusBarItem.tooltip = `LIDCO connected to ${client.baseUrl}`;
        statusBarItem.color = new vscode.ThemeColor('statusBarItem.prominentForeground');
    } else {
        statusBarItem.text = '$(circle-slash) LIDCO';
        statusBarItem.tooltip = `LIDCO disconnected (${client.baseUrl})`;
        statusBarItem.color = new vscode.ThemeColor('errorForeground');
    }
}

function openChatPanel(context: vscode.ExtensionContext): void {
    if (chatPanel) {
        chatPanel.reveal(vscode.ViewColumn.Beside);
        return;
    }

    chatPanel = vscode.window.createWebviewPanel(
        'lidcoChat',
        'LIDCO Chat',
        vscode.ViewColumn.Beside,
        {
            enableScripts: true,
            retainContextWhenHidden: true,
        }
    );

    chatPanel.webview.html = getChatWebviewHtml();

    chatPanel.webview.onDidReceiveMessage(
        async (message: { command: string; text?: string; agent?: string }) => {
            if (message.command === 'sendMessage' && message.text) {
                const response = await client.chat(message.text, message.agent);
                chatPanel?.webview.postMessage({
                    command: 'addMessage',
                    role: 'assistant',
                    content: response.result ?? response.error ?? 'No response',
                });
            }
        },
        undefined,
        context.subscriptions
    );

    chatPanel.onDidDispose(() => {
        chatPanel = undefined;
    });
}

async function runOnSelection(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    const selectedText = editor.document.getText(selection);
    if (!selectedText) {
        vscode.window.showWarningMessage('No text selected');
        return;
    }

    const prompt = await vscode.window.showInputBox({
        prompt: 'What should LIDCO do with the selected code?',
        placeHolder: 'e.g. Explain this, Add type hints, Write tests...',
    });

    if (!prompt) {
        return;
    }

    const fullPrompt = `${prompt}\n\n\`\`\`\n${selectedText}\n\`\`\``;

    try {
        vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: 'LIDCO thinking...' },
            async () => {
                const result = await client.chat(fullPrompt);
                const output = result.result ?? result.error ?? 'No response';
                vscode.window.showInformationMessage(output.slice(0, 200));
            }
        );
    } catch (err) {
        vscode.window.showErrorMessage(`LIDCO error: ${err}`);
    }
}

async function reviewCurrentFile(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }
    const fileUri = editor.document.uri.toString();
    const result = await client.executeCommand('lidco.review', [{ textDocument: { uri: fileUri } }]);
    vscode.window.showInformationMessage((result.result ?? '').slice(0, 300));
}

async function explainSelection(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) { return; }
    const text = editor.document.getText(editor.selection);
    if (!text) { return; }
    const result = await client.chat(`Explain this code:\n\`\`\`\n${text}\n\`\`\``);
    vscode.window.showInformationMessage((result.result ?? '').slice(0, 300));
}

async function reviewSelectionCmd(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) { return; }
    const text = editor.document.getText(editor.selection);
    if (!text) { return; }
    const result = await client.chat(`Review this code for quality, bugs, and security:\n\`\`\`\n${text}\n\`\`\``);
    vscode.window.showInformationMessage((result.result ?? '').slice(0, 300));
}

function getChatWebviewHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LIDCO Chat</title>
<style>
  body { font-family: var(--vscode-font-family); font-size: 13px; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
  #history { flex: 1; overflow-y: auto; padding: 8px; }
  .msg { margin: 6px 0; padding: 6px 10px; border-radius: 6px; }
  .user { background: var(--vscode-editor-selectionBackground); text-align: right; }
  .assistant { background: var(--vscode-editor-inactiveSelectionBackground); }
  #inputArea { display: flex; padding: 8px; border-top: 1px solid var(--vscode-panel-border); }
  #input { flex: 1; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 4px 8px; resize: none; }
  button { margin-left: 8px; padding: 4px 12px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; cursor: pointer; }
  button:hover { background: var(--vscode-button-hoverBackground); }
</style>
</head>
<body>
<div id="history"></div>
<div id="inputArea">
  <textarea id="input" rows="3" placeholder="Ask LIDCO anything..."></textarea>
  <button id="send">Send</button>
</div>
<script>
  const vscode = acquireVsCodeApi();
  const history = document.getElementById('history');
  const input = document.getElementById('input');

  document.getElementById('send').addEventListener('click', sendMessage);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    addMessage('user', text);
    vscode.postMessage({ command: 'sendMessage', text });
    input.value = '';
  }

  function addMessage(role, content) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = content;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
  }

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg.command === 'addMessage') {
      addMessage(msg.role, msg.content);
    }
  });
</script>
</body>
</html>`;
}
