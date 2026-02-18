# Troubleshooting

## Server Issues

### "Connection refused" when starting the server

**Symptom:** `lidco serve` exits immediately or curl returns "Connection refused".

**Fixes:**
1. Check if the port is already in use:
   ```bash
   # Linux/macOS
   lsof -i :8321
   # Windows
   netstat -ano | findstr :8321
   ```
2. Try a different port: `lidco serve --port 9000`
3. Check for import errors: `python -c "from lidco.server.app import create_app; print('OK')"`

### "No module named 'fastapi'" or "No module named 'uvicorn'"

**Fix:** Install server dependencies:
```bash
pip install -e ".[dev]"
# or just the server deps:
pip install fastapi uvicorn[standard] sse-starlette
```

### Server returns 401 Unauthorized

**Cause:** `LIDCO_API_TOKEN` is set on the server but client isn't sending the token.

**Fix:** Either:
- Unset the token: `unset LIDCO_API_TOKEN` and restart server
- Include the token in requests:
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" http://127.0.0.1:8321/api/status
  ```
- In the IntelliJ plugin: **Settings** > **Tools** > **LIDCO** > set API Token

### Server returns 500 Internal Server Error

**Fix:** Enable debug mode for verbose errors:
```bash
LIDCO_DEBUG=1 lidco serve
```

Check the server terminal for full tracebacks.

### "Could not build project context"

**Symptom:** Warning in server logs, context endpoints return empty.

**Cause:** The server couldn't analyze the project directory.

**Fix:** Ensure `lidco serve` is run from the project root, or use:
```bash
lidco serve --project-dir /path/to/your/project
```

---

## Plugin Issues

### Plugin not visible after installation

**Fixes:**
1. Restart the IDE after installing the .zip
2. Check **Settings** > **Plugins** > **Installed** tab — search for "LIDCO"
3. Verify IDE version: plugin requires IntelliJ 2024.1+ / Android Studio Koala+

### "LIDCO: offline" in status bar

**Cause:** Plugin can't reach the LIDCO server.

**Fixes:**
1. Verify server is running: `curl http://127.0.0.1:8321/health`
2. Check server URL in **Settings** > **Tools** > **LIDCO**
3. If using a custom port, update the URL: `http://127.0.0.1:9000`
4. Check firewall isn't blocking localhost connections

### Context menu actions don't appear

**Cause:** No text is selected. All LIDCO context menu actions require a selection.

**Fix:** Select code in the editor first, then right-click.

### Alt+L doesn't work

**Possible causes:**
1. Shortcut conflicts: **Settings** > **Keymap** > search "LIDCO" > check for conflicts
2. Server not running (completion requires the server)
3. Server timeout (default 5s) — check server logs for slow responses

### Chat window shows "Connection failed"

**Fixes:**
1. Check server is running
2. Verify URL in plugin settings
3. If using auth, verify token matches between server and plugin
4. Check IDE logs: **Help** > **Show Log in Explorer/Finder** > search for "LIDCO" or "LidcoClient"

### Plugin build fails

**Fixes:**
```bash
cd ide/android-studio-plugin

# Clean and rebuild
./gradlew clean buildPlugin

# Check JDK version (requires 17+)
java -version

# If Gradle wrapper missing, use system Gradle
gradle wrapper --gradle-version 8.5
```

---

## CLI Issues

### "No module named 'lidco'"

**Fix:** Install the package:
```bash
cd /path/to/lidco
pip install -e ".[dev]"
```

### LLM errors: "API key not found"

**Fix:** Set API keys in `.env`:
```bash
cp .env.example .env
# Edit .env and add your keys
```

Or export directly:
```bash
export OPENAI_API_KEY=sk-...
```

### Slow responses

**Causes & fixes:**
1. **Large model:** Switch to a faster model: `/model gpt-4o-mini`
2. **Many tool calls:** Agent is doing extensive file operations. Wait or press Ctrl+C
3. **Network:** Check internet connection, try a local model (Ollama)

### Memory not persisting

**Fixes:**
1. Check memory is enabled: `cat ~/.lidco/config.yaml` — `memory.enabled` should be `true`
2. Check directory permissions: `ls -la ~/.lidco/memory/`
3. Manually add: `/memory add test_key: test value`
4. Verify: `/memory list`

---

## Getting Help

1. Check server logs (terminal where `lidco serve` is running)
2. Check IDE logs: **Help** > **Show Log in Explorer/Finder**
3. Enable debug logging:
   ```bash
   LIDCO_LOG_LEVEL=DEBUG lidco serve
   ```
4. File an issue on GitHub with:
   - LIDCO version (`lidco --version` or check `/api/status`)
   - IDE version (for plugin issues)
   - Full error message or traceback
   - Steps to reproduce
