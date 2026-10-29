# Adapter: vault MCP server (future, not built)

For surfaces that cannot read the vault from disk (phone apps, web chat, cloud agents). A small self-hosted MCP server exposing the vault: tools to fetch SOUL/IDENTITY/INDEX, fetch a page by name, search pages, and append to `episodic/` only, with the contract's write rules and secret policy enforced server-side.

Why this exists as a FUTURE adapter and not the primary hook: on-machine agents (Claude Code on a desktop machine) read the vault directly as files, which is fewer moving parts and works headless. MCP only provides tools the model may choose to call; it can never guarantee the always-loaded tier-1 injection the contract requires, so it supplements filesystem access for remote surfaces rather than replacing it. An Obsidian-specific MCP (via the Local REST API plugin) adds an Obsidian-must-be-running dependency for the same bytes on disk and is not the right shape; if this gets built, it serves the git repo directly.

Rule of thumb from the contract's spirit: identity is injected, knowledge is fetched, and the fewest moving parts wins.

## Sources

- `harness/CONTRACT.md` · section 3.4b, which is why any server built here may append to `episodic/` only and must refuse to hand vault content to anything outside the owner's machines
