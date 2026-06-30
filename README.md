# inMotion MCP Server

A **Model Context Protocol (MCP) server** that exposes custom Python tools over three internal data sources — **Notion** (CRM / system-of-record), **n8n** (automation), and **Gmail** (outbound) — to an LLM agent layer (Claude Desktop, claude.ai, or any MCP client).

Built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk) (the official MCP Python SDK). Async throughout, Pydantic-validated inputs, centralised auth and error handling, env-based configuration (no secrets in source).

---

## Why this exists

The agent shouldn't get raw API access to the CRM, the automation instance, and the mailbox. It should get a small set of **purpose-built, safe tools**: read the pipeline, write a lead, kick off a workflow, draft an email for a human to send. This server is that boundary layer.

## Tools (10)

| Tool | Service | Read/Write | Purpose |
|------|---------|-----------|---------|
| `notion_query_leads` | Notion | read | Query a database (defaults to the Leads DB), filter by status, paginate. |
| `notion_get_page` | Notion | read | Fetch one page's properties and optional body text. |
| `notion_create_lead` | Notion | write (create) | Create a lead/company row. |
| `notion_update_lead` | Notion | write (update) | Update properties or archive a page. |
| `n8n_list_workflows` | n8n | read | List workflows (filter by active), with node counts. |
| `n8n_get_workflow` | n8n | read | Fetch one workflow's full node graph + connections. |
| `n8n_list_executions` | n8n | read | Recent run history / status. |
| `n8n_trigger_webhook` | n8n | write (create) | Fire a webhook-triggered workflow with an optional payload. |
| `gmail_search_messages` | Gmail | read | Search the mailbox (Gmail query syntax). |
| `gmail_create_draft` | Gmail | write (create) | Draft an email. **Never sends** — a human reviews and sends. |

Each tool carries MCP annotations (`readOnlyHint`, `destructiveHint`, etc.) so clients can reason about safety. The one intentionally-omitted capability is "send email": an irreversible action is kept out of the agent's hands by design.

## Architecture

```
src/inmotion_mcp/
├── server.py    FastMCP init, 10 tool definitions, formatting helpers, CLI entrypoint
├── clients.py   One async _ServiceClient base (shared request + auth + error
│                normalisation) → NotionClient, N8nClient, GmailClient
├── models.py    Pydantic v2 input model per tool (constraints + descriptions)
├── config.py    Env-based Settings; each service independently optional
└── __init__.py
```

Design choices worth noting:
- **DRY transport**: every HTTP call goes through one `_request` method; service clients only declare base URL + auth headers.
- **Actionable errors**: upstream failures are normalised to a single `ServiceError` with human-readable, fix-oriented messages (401 → "verify credentials", 404 → "check the id", 429 → "rate limited, retry").
- **Graceful degradation**: an unconfigured service doesn't break the server — its tools just return a clear "not configured" message. You can run with only the integrations you have.
- **Two output modes**: every read tool supports `response_format='markdown'` (agent-friendly summary) or `'json'` (full structured data).

## Setup

```bash
# 1. Install
pip install -r requirements.txt          # or: pip install -e .

# 2. Configure
cp .env.example .env                      # then fill in the tokens you have
#   Load it however you prefer, e.g.:  export $(grep -v '^#' .env | xargs)

# 3. Verify which integrations are live
python -m inmotion_mcp.server --check
```

`--check` prints a checklist of which of the three services are configured — handy before wiring it into a client.

## Running

```bash
# Local (stdio) — for Claude Desktop and most local MCP clients
python -m inmotion_mcp.server

# Remote (streamable HTTP) — for a hosted/shared deployment
python -m inmotion_mcp.server --http --port 8000
```

### Claude Desktop config

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "inmotion": {
      "command": "python",
      "args": ["-m", "inmotion_mcp.server"],
      "env": {
        "NOTION_TOKEN": "secret_...",
        "NOTION_LEADS_DATABASE_ID": "your-db-id",
        "N8N_BASE_URL": "https://your-n8n-host/api/v1",
        "N8N_API_KEY": "your-n8n-key",
        "N8N_WEBHOOK_BASE_URL": "https://your-n8n-host",
        "GMAIL_ACCESS_TOKEN": "ya29...."
      }
    }
  }
}
```

## Configuration reference

| Env var | Service | Required for that service | Notes |
|---------|---------|---------------------------|-------|
| `NOTION_TOKEN` | Notion | yes | Internal integration token. |
| `NOTION_LEADS_DATABASE_ID` | Notion | no | Default DB for lead tools. |
| `N8N_BASE_URL` | n8n | yes | API root, e.g. `https://host/api/v1`. |
| `N8N_API_KEY` | n8n | yes | Sent as `X-N8N-API-KEY`. |
| `N8N_WEBHOOK_BASE_URL` | n8n | only for `trigger_webhook` | Host serving `/webhook/<path>`. |
| `GMAIL_ACCESS_TOKEN` | Gmail | yes | Short-lived OAuth2 access token with Gmail scopes. |
| `GMAIL_SENDER` | Gmail | no | Default `From` for drafts. |
| `MCP_HTTP_TIMEOUT` | all | no | Per-request timeout, seconds (default 30). |

## Security

- **No secrets in source.** Everything is read from the environment; `.env` is git-ignored by convention.
- **Gmail tokens are not refreshed here** — token acquisition/refresh is left to the surrounding environment, keeping this a thin, auditable integration layer.
- **No send capability.** The agent can draft but not send email.

## Testing

```bash
python -m py_compile src/inmotion_mcp/*.py     # syntax
python -m inmotion_mcp.server --check          # config
python -m inmotion_mcp.server --help           # CLI
```

Tool registration and the request/format logic are exercised end-to-end against a mocked HTTP layer (see the smoke test in the build notes); all 10 tools register with correct schemas and annotations.
