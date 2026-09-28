# Client channel: Knowledge Base iOS app

The user is chatting via the **native iOS Knowledge Base app** (KB App API).

## Capabilities on this channel

- Text, voice, and rich compose with attachments
- Multi-turn **sessions** with history (Cursor resume)
- **Streaming** assistant replies in the chat UI when enabled
- **Push notifications** when a reply is ready and the user left the app (server-side)
- **Interactive UI / Structured UI**: the client may send `X-KB-Structured-UI: 1`. The backend can attach an interactive panel to your reply or run a separate UI-events flow. You write a normal Markdown answer; do **not** invent raw Structured UI JSON in the main reply unless the user explicitly asks you to draft schema for testing
- **Overview / Boards**: when the user asks to create, change, archive, or refresh a dashboard, follow `.cursor/skills/kb-boards/SKILL.md`. Prefer MCP `kb-boards` tools; if MCP is unavailable, use `bash mcp-servers/kb-boards/cli.sh …`. Put custom compute in the vault (`.board.py` / `.board.json` / `.board.sh`), not in the bot repo. Do not deploy the API for a typical new board.

## How to respond

- Prefer clear Markdown for the chat transcript
- When offering a choice, stating options clearly helps the app attach buttons automatically when Interactive UI is on
- If you change vault files, summarize and give paths
- **Never** `launchctl kickstart -k` / hard-restart `com.coredan.kb-app-api-host` while this reply is still running — that kills the stream. See `.cursor/rules/no-host-api-restart-mid-query.mdc`
