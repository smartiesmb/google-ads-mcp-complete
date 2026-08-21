# Project Instructions

## One CLI — Platform Integrations

The One CLI (`one`) is installed and configured on this machine. It is a command-line tool that
gives AI agents the ability to interact with 400+ third-party platforms (Gmail, Slack, Shopify,
HubSpot, Stripe, GitHub, Notion, Salesforce, etc.) through a single, unified interface.

**Whenever you need to interact with any third-party platform or external service, use the One
CLI.** This is the primary tool for all integrations. Always confirm with the user before running
anything destructive (deleting data, sending irreversible messages, charging payments, etc.).

### IMPORTANT: Always use the --agent flag
The `--agent` flag gives structured JSON output. Always include it right after `one`:
  one --agent <command>

### IMPORTANT: Learn before you use
Before using any feature (actions, flows, relay), you MUST read the corresponding skill
documentation first via `actions knowledge`. The skills teach the correct workflow, required
parameters, and common mistakes. Never guess — read the skill, then act.

### Quick reference:
- `one --agent list` — See connected platforms and connection keys
- `one --agent actions search <platform> "<query>"` — Find actions
- `one --agent actions knowledge <platform> <actionId>` — Read docs (REQUIRED before execute)
- `one --agent actions execute <platform> <actionId> <connectionKey>` — Execute action
- `one --agent flow create` — Build multi-step workflows
- `one --agent relay create` — Set up webhook relay (receive events, forward to other platforms)
- `one --agent guide` — Full documentation
- `one add <platform>` — Connect a new platform (interactive, no --agent)

### Workflow: search -> knowledge -> execute
Always read the knowledge before executing. It tells you required parameters, validation rules,
and platform-specific details.

### Webhook Relay
Use `one relay` to receive webhooks from platforms (Stripe, GitHub, etc.) and forward event data
to other platforms using passthrough actions with Handlebars templates. No middleware needed.
