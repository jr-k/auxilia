<div align="center">
  <img src="docs/public/logo.svg#gh-light-mode-only" alt="auxilia" height="72" />
  <img src="docs/public/logo-dark.svg#gh-dark-mode-only" alt="auxilia" height="72" />

  <h1>auxilia</h1>
  <h3>The open-source, self-hosted web client for MCP-powered AI agents — built for teams.</h3>

  <p>
    <a href="https://github.com/jr-k/auxilia/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/jr-k/auxilia?color=blue"></a>
    <a href="https://github.com/jr-k/auxilia/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/jr-k/auxilia?style=flat"></a>
    <a href="https://github.com/jr-k/auxilia/issues"><img alt="Issues" src="https://img.shields.io/github/issues/jr-k/auxilia"></a>
    <a href="https://github.com/jr-k/auxilia/pulls"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg"></a>
  </p>

  <p>
    <a href="#-quick-start"><b>Quick start</b></a> ·
    <a href="#-why-this-fork"><b>Why this fork</b></a> ·
    <a href="#-why-auxilia"><b>Why auxilia</b></a> ·
    <a href="#-what-this-fork-adds"><b>Fork additions</b></a> ·
    <a href="#-integrations"><b>Integrations</b></a> ·
    <a href="https://auxilia-docs.vercel.app/"><b>Docs</b></a>
  </p>
</div>

---

[https://github.com/user-attachments/assets/3236f9da-28c5-44c8-8c2c-4c68199f187c](https://github.com/user-attachments/assets/868f36cc-9c45-4003-9687-0494ca86d2a2
)

**auxilia is a web platform for running AI agents as a team.** An admin sets up [MCP](https://modelcontextprotocol.io/) servers and agents once, and the whole workspace shares them — no more everyone configuring their own assistant with their own prompts and credentials. Anyone can create an agent and experiment, zero technical skills required: agents chat in the browser or in Slack, use your internal tools, ask a human for approval before sensitive actions, and run on schedules or in the background. An agent is only as good as the environment you give it. That's where auxilia comes in: iterating quickly is how you find what's missing — a tool it needed, a doc that's outdated, data that isn't as clean as you thought. The more gaps you close, the more reliable your agents become; when one proves itself, plug it into your own products through the API. You pick the LLM provider (Anthropic, OpenAI, Google, DeepSeek) and can switch anytime — and because it's self-hosted, conversations, credentials, and usage data never leave your infrastructure. Everything that matters — the documentation, the data models, the MCP servers you build to make your agents work — is yours, and it follows you to any other agentic platform.

## 🍴 Why this fork

This fork builds on the [original auxilia project](https://github.com/keurcien/auxilia) with a shorter development cycle. The goal is to turn feedback from real agent deployments into small, production-ready releases quickly, then harden the capabilities that prove useful. That faster loop has expanded auxilia from a shared MCP client into a complete platform for building, operating, and governing agents as a team.

## ✨ What this fork adds

This list covers only capabilities introduced by this fork. Existing upstream features such as scheduled triggers, sandboxes, skills, subagents, and durable runs are intentionally not repeated.

**Workspace and administration**

- 🏷️ **White-label instances**: customize the application name and logo throughout the product, including authentication screens, invitations, browser metadata, and the generated PWA manifest.
- 🏢 **Multi-workspace administration**: create, switch, edit, and delete isolated workspaces, each with its own members, resources, branding, integrations, and credentials.
- ⚙️ **In-app instance configuration**: manage model provider credentials, Google authentication, Slack, Langfuse, OAuth callbacks, and other deployment settings without editing environment variables.
- 🗂️ **Resource organization and visibility**: hierarchical groups, personal or workspace visibility scopes, team filters, bulk actions, and clearer ownership across agents, skills, triggers, and MCP servers.
- 👤 **Richer user management**: profile pictures, password management, TOTP two-factor authentication, navigation and response preferences, a user grid, and detailed usage statistics.

**Chat and product experience**

- ⏭️ **Prompt queue**: send follow-up prompts while an agent is running, preserve pending submissions, and play an optional sound when the queue completes.
- 🎛️ **Conversation-level resources**: inspect and change the MCP servers and other resources enabled for an individual conversation.
- 📊 **Runtime and usage insights**: live run controls and statistics, per-conversation usage, user-level analytics, profile thread management, and bulk conversation deletion.
- 📱 **Responsive UX overhaul**: improved mobile layouts, resource pickers, related-resource navigation, OAuth and destructive flows, bulk management, and state preservation across the app.
- 🔄 **Realtime workspace sync**: propagate workspace and resource changes across tabs and active sessions over SSE without requiring a refresh.

**Automation and integrations**

- 🔗 **Webhook triggers**: start agents from external systems through a unique POST endpoint, with optional per-call agent, model, and instruction overrides.
- 🗄️ **Managed databases**: connect PostgreSQL, MySQL, MariaDB, SQL Server, and Oracle as managed MCP data sources, with encrypted credentials, read-only controls, query limits, and connection health.
- 📄 **SQLite file uploads**: upload SQLite databases directly, expose them as managed data sources, and safely maintain their files and sidecars.
- 💬 **Advanced Slack agents**: dedicated bots per agent, private messages, thread context, configurable tool callouts, multiple side channels, progress updates, and MCP error reporting.
- 📧 **Gmail and native web search**: give agents first-class Gmail tools and provider-native web search with relevant MCP context.

**MCP and models**

- 🔐 **Enterprise MCP authentication**: shared service identities, provider-specific credentials such as Google Compute service accounts, CIMD support, provider quirks, and workspace-managed OAuth configuration.
- 🧰 **Expanded MCP management**: server-level tool controls, instance-specific servers, a dedicated connection test dialog, richer deletion flows, and a much larger official catalog with hosted icons.
- 🔁 **Auxilia as an MCP server**: expose authenticated workspace administration tools through MCP and connect clients through auxilia's OAuth authorization server.
- 🧠 **More model control**: Ollama support, guided model onboarding, agent-level defaults, configurable tool discovery, and improved model-aware chat flows.

## 🤔 Why auxilia

Most MCP clients are desktop apps tied to a single user: every teammate reinvents the same agent, alone, in their own tool. auxilia is the middle ground between "everyone has their own ChatGPT tab" and building a custom AI platform:

- 🧪 **A playground for the whole company** — business users build and test agents themselves, no code. Not every experiment is a keeper — that's the point: everyone gets hands-on intuition for what agents can (and can't) do, cheaply.
- 👥 **One place, shared agents** — register MCP servers and agents once; the whole team reuses them, with workspace roles and per-agent permissions.
- 🏠 **Your infra, your data** — self-hosted; conversations, API keys (AES-GCM encrypted at rest) and per-user OAuth tokens stay in your own database and Redis.
- 🔓 **No provider lock-in** — swap Anthropic, OpenAI, Google, or DeepSeek per agent as pricing and quality shift.
- ✅ **Guardrails built in** — each tool can be always-allowed, require human approval (in chat or Slack), or be disabled.
- 🔌 **Remote MCP native** — any remote (Streamable HTTP) MCP server becomes a tool: internal services or one-click Notion, Linear, GitHub, HubSpot, BigQuery, Slack, Sentry.

## 🚀 Quick start

All you need is [Docker](https://docs.docker.com/get-docker/) and **one LLM API key** (Anthropic, OpenAI, Google, or DeepSeek).

```bash
git clone https://github.com/jr-k/auxilia.git
cd auxilia
cp .env.example .env      # paste at least one LLM API key
make build && make up
```

Open **http://localhost:3000** — the first account you create becomes the workspace **admin**. Add an MCP server, create an agent, and start chatting.

PostgreSQL and Redis are started and wired up by Docker Compose; every other setting has a working dev default. The `.env` at a glance:

| Variable(s)                                                                    | When you need it                                                                                                                                          |
| ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` / `XIAOMI_API_KEY` / `METAAI_API_KEY` | **At least one.** Each key unlocks that provider's models in the model picker.                                                                            |
| `BACKEND_ENCRYPTION_SALT`, `BACKEND_JWT_SECRET_KEY`, `BACKEND_COOKIE_SECURE`   | **Before production.** Encryption secret for stored credentials, session signing secret, and secure cookies behind HTTPS. Dev defaults work locally. |
| `RUN_*`                                                                        | Tuning for the background run worker (concurrency, timeouts). Defaults are fine.                                                                          |

Google OAuth, Slack and Langfuse are configured by workspace admins from
**Settings → Authentication**, **Notifications**, and **Observability**. Their
credentials are encrypted in PostgreSQL.

> Upgrading an existing deployment? Rename `SALT` or
> `MCP_API_KEY_ENCRYPTION_SALT` to `BACKEND_ENCRYPTION_SALT` without changing
> its value. Rotating it without re-encrypting stored secrets makes existing
> credentials and TOTP secrets unreadable.

Developing? `make dev` runs PostgreSQL, Redis, the FastAPI backend (migrations applied) and the Next.js frontend in parallel, all with hot reload. Full walkthrough in the [Get Started guide](https://auxilia-docs.vercel.app/get-started).

## 🤝 Integrations

**LLM providers**

| Provider  | Models                                       |
| --------- | -------------------------------------------- |
| Anthropic | Claude Haiku 4.5, Sonnet 4.6, Sonnet 5       |
| OpenAI    | GPT-4o mini                                  |
| Google    | Gemini 3 Flash Preview, Gemini 3 Pro Preview |
| DeepSeek  | DeepSeek v4 Flash, v4 Pro                    |
| Meta      | Muse Spark 1.2                               |
| Xiaomi    | MiMo-V2.5-Pro, MiMo-V2.5                     |
| OpenRouter | GLM 5.2 (Max), GLM 5.2 (High)              |

**MCP servers — one-click install**: Notion · Linear · GitHub · HubSpot · BigQuery · Slack · Sentry — or paste the URL of any custom remote MCP server with its OAuth credentials or API key.

**Workspace tools**: Slack, Langfuse, Google OAuth SSO.

## 💡 From playground to production

A few agents we run ourselves:

**📊 A data analyst that answers with dashboards, not spreadsheets.** Plugged into our BigQuery warehouse, with a custom MCP server that renders interactive charts and dashboards _inside the chat_. "How did sales move after the price change?" used to be a ticket for the data team; now it's a question anyone types and gets answered — with a graph — in seconds.

**🎧 A super agent behind our customer support.** One orchestrator dispatches specialized subagents — orders, refunds, logistics — and delivers ready-to-send suggestions straight into our support tool through the invoke API. It was built and tuned like any other workspace agent, then wired into the product without changing a line of it.

**💶 A pricing analyst that does the work nobody wants twice.** Hand it a spreadsheet with thousands of messy, wildly inconsistent rows, and it writes and runs its own code in an isolated sandbox to clean, cross-check, and price every one of them. The same sandbox trick stretches surprisingly far — we've used it to train and deploy small ML models.

## 📚 Documentation

Full docs at **[auxilia-docs.vercel.app](https://auxilia-docs.vercel.app/)**:

- [Get Started](https://auxilia-docs.vercel.app/get-started) — run auxilia locally
- [Agents](https://auxilia-docs.vercel.app/agents) — configuration, permissions, subagents
- [Skills](https://auxilia-docs.vercel.app/agents/skills) — reusable procedures, in-app or synced from a repository
- [Triggers](https://auxilia-docs.vercel.app/agents/triggers) — scheduled agent runs
- [MCP Servers](https://auxilia-docs.vercel.app/deploy/mcp-servers) — registration, auth, examples
- [Tools](https://auxilia-docs.vercel.app/agents/tools) — per-tool approval rules
- [Sandbox](https://auxilia-docs.vercel.app/agents/sandbox) — code execution for an agent
- [Deployment](https://auxilia-docs.vercel.app/deploy) — environment, Google Cloud Run, sandboxes
- [Integrations](https://auxilia-docs.vercel.app/deploy/slack) — Slack, [Langfuse](https://auxilia-docs.vercel.app/deploy/langfuse)
- [Tutorials](https://auxilia-docs.vercel.app/tutorials) — HTTP, Slack, n8n & schedulers, embedding
- [Case Studies](https://auxilia-docs.vercel.app/case-studies) — Google Sheets from a sandbox, slide decks from a GitHub skill

## 🗺 Roadmap

- [x] Scheduled triggers
- [x] Skills
- [x] Support for more sandboxes (Daytona, Cloud Run)
- [ ] Deployment guides
- [ ] More SSO providers (Okta, Entra ID)

Have an idea? [Open an issue](https://github.com/jr-k/auxilia/issues/new) or start a discussion.

## 🤝 Contributing

Contributions are very welcome — bug reports, agent ideas, MCP server recipes, UI fixes:

1. Fork the repo and create a branch (`git checkout -b feature/my-change`)
2. Enable the git hooks once per clone: `pre-commit install` — they run ruff on changed Python and a stricter type-aware ESLint config on changed `web/` files
3. Run `make dev` and make sure tests pass (`cd backend && uv run pytest`)
4. Open a pull request — **the PR title must follow [Conventional Commits](https://www.conventionalcommits.org/)** (e.g. `feat: …`, `fix: …`); PRs are squash-merged and release-please derives versions and changelogs from the titles

Please read [`CLAUDE.md`](./CLAUDE.md) first — it documents the backend's layered architecture (router → service → repository → model) and naming conventions.

## 📄 License

[AGPL-3.0](./LICENSE) — free to use, modify, and self-host.

---

<div align="center">
  <sub>Built with ❤️ using <a href="https://www.langchain.com/langgraph">LangGraph</a> and the <a href="https://modelcontextprotocol.io/">Model Context Protocol</a>.</sub>
</div>
