/**
 * LidcoClient — HTTP client for the LIDCO server (default: localhost:7777).
 *
 * Mirrors the REST API exposed by `lidco serve`.
 */

export interface ChatResponse {
    result?: string;
    error?: string;
}

export interface CommandResponse {
    result?: string;
    error?: string;
}

export interface CompletionItem {
    label: string;
    kind: number;
    insertText: string;
}

export interface CompletionResponse {
    isIncomplete: boolean;
    items: CompletionItem[];
}

export class LidcoClient {
    public readonly baseUrl: string;
    private readonly timeout: number;

    constructor(baseUrl: string = 'http://localhost:7777', timeoutMs: number = 30000) {
        // Normalize: remove trailing slash
        this.baseUrl = baseUrl.replace(/\/+$/, '');
        this.timeout = timeoutMs;
    }

    /** Check if the LIDCO server is reachable. */
    async ping(): Promise<boolean> {
        try {
            const controller = new AbortController();
            const id = setTimeout(() => controller.abort(), 3000);
            const resp = await fetch(`${this.baseUrl}/health`, {
                signal: controller.signal,
            });
            clearTimeout(id);
            return resp.ok;
        } catch {
            return false;
        }
    }

    /** Send a chat message, optionally directing to a specific agent. */
    async chat(message: string, agent?: string): Promise<ChatResponse> {
        try {
            const body: Record<string, unknown> = { message };
            if (agent) {
                body.agent = agent;
            }
            const resp = await this._fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            return (await resp.json()) as ChatResponse;
        } catch (err) {
            return { error: String(err) };
        }
    }

    /** Execute a named LIDCO command (mirrors LSP workspace/executeCommand). */
    async executeCommand(command: string, args: unknown[] = []): Promise<CommandResponse> {
        try {
            const resp = await this._fetch('/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, arguments: args }),
            });
            return (await resp.json()) as CommandResponse;
        } catch (err) {
            return { error: String(err) };
        }
    }

    /** Request code completions at a file position. */
    async complete(
        fileUri: string,
        line: number,
        character: number
    ): Promise<CompletionResponse> {
        try {
            const resp = await this._fetch('/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    textDocument: { uri: fileUri },
                    position: { line, character },
                }),
            });
            return (await resp.json()) as CompletionResponse;
        } catch (err) {
            return { isIncomplete: false, items: [] };
        }
    }

    /** Get hover explanation for a file position. */
    async hover(fileUri: string, line: number, character: number): Promise<string | null> {
        try {
            const resp = await this._fetch('/hover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    textDocument: { uri: fileUri },
                    position: { line, character },
                }),
            });
            if (!resp.ok) { return null; }
            const data = (await resp.json()) as { contents?: { value: string } } | null;
            return data?.contents?.value ?? null;
        } catch {
            return null;
        }
    }

    private async _fetch(path: string, init: RequestInit): Promise<Response> {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), this.timeout);
        try {
            const resp = await fetch(`${this.baseUrl}${path}`, {
                ...init,
                signal: controller.signal,
            });
            return resp;
        } finally {
            clearTimeout(id);
        }
    }
}
