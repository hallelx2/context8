# Plan 06 — Agent Integration

## Objective

Define exactly how coding agents discover, call, and benefit from Context8. This plan covers the integration patterns for different agents, the triggering logic (when should an agent search Context8?), and the feedback loop (when should it log solutions?).

## Integration Flow

### Phase 1: Agent Encounters an Error

```
Agent is working on task
        │
        ▼
Error occurs (build failure, runtime error, type error, etc.)
        │
        ▼
Agent's first instinct: try to fix it directly
        │
        ▼
┌─── Did the fix work? ───┐
│                          │
Yes                        No
│                          │
▼                          ▼
Done                 Agent calls context8_search
(maybe log it)       with the error message
                           │
                           ▼
                  ┌─── Results found? ──┐
                  │                     │
                 Yes                    No
                  │                     │
                  ▼                     ▼
            Agent uses             Agent tries
            past solution          other approaches
            as reference           (docs, reasoning)
                  │                     │
                  ▼                     ▼
            Problem solved         Eventually solved
                  │                     │
                  └──────────┬──────────┘
                             │
                             ▼
                    Agent calls context8_log
                    (if non-trivial solution)
```

### Phase 2: When to Search Context8

The agent should call `context8_search` when:

1. **After first fix attempt fails** — Don't search for every trivial error. If the agent's first attempt doesn't work, escalate to Context8.
2. **Error message looks uncommon** — Generic "syntax error" is not worth searching. "ECONNRESET when using prisma with pgbouncer in serverless" is.
3. **Agent has been stuck for multiple iterations** — If the agent has tried 3+ approaches without success, search Context8.
4. **Error involves specific library/framework interaction** — These are the "long tail" problems that docs don't cover.

### Phase 3: When to Log Solutions

The agent should call `context8_log` when:

1. **A non-trivial problem was solved** — Not typos, missing semicolons, or simple imports
2. **The solution required investigation** — Multiple attempts, reading source code, trial-and-error
3. **The problem is likely to recur** — Environment issues, version conflicts, undocumented behaviors
4. **The agent is confident in the solution** — Don't log guesses or partial fixes

### Phase 4: What NOT to Log

- Trivial syntax errors (missing comma, wrong indentation)
- Simple import fixes (just installing a package)
- Problems unique to a specific codebase (hardcoded paths, custom configs)
- Incomplete solutions (workarounds that don't fully fix the issue)
- Sensitive information (API keys, credentials, internal URLs)

## Agent-Specific Configuration

### Claude Code

**Configuration (`.claude/settings.json`):**

```json
{
  "mcpServers": {
    "context8": {
      "command": "python",
      "args": ["-m", "context8.server"],
      "env": {
        "CONTEXT8_DB_HOST": "localhost",
        "CONTEXT8_DB_PORT": "50051"
      }
    }
  }
}
```

**CLAUDE.md instructions (recommended):**

```markdown
## Context8 — Problem-Solving Memory

You have access to Context8, a collective problem-solving memory that stores past solutions from coding agents.

### When to use context8_search:
- After your first fix attempt for an error fails
- When encountering uncommon errors or library interaction issues
- When stuck on a problem for multiple iterations

### When to use context8_log:
- After solving a non-trivial problem (not typos or simple imports)
- When the solution required investigation or multiple attempts
- When the problem is likely to affect other projects

### When NOT to log:
- Trivial syntax fixes
- Project-specific configuration issues
- Incomplete or uncertain solutions
```

### Cursor

**Configuration (`.cursor/mcp.json`):**

```json
{
  "mcpServers": {
    "context8": {
      "command": "python",
      "args": ["-m", "context8.server"]
    }
  }
}
```

### Windsurf / Continue / Other MCP Agents

Any MCP-compatible agent uses the same pattern — configure the MCP server command and the agent discovers the tools automatically via the `list_tools()` protocol.

## How the Agent Actually Calls It

### Example 1: Agent Encounters TypeError

```
Agent: Building a React component with React Query v5

Error: TypeError: Cannot read properties of undefined (reading 'map')

Agent tries: Add optional chaining (data?.items.map)
Still fails: data is undefined during Suspense boundary transition

Agent calls context8_search:
  query: "TypeError Cannot read properties of undefined map React Query Suspense"
  code_context: "const items = data.items.map(item => <Item key={item.id} {...item} />)"
  language: "typescript"
  framework: "react"

Context8 returns:
  Solution 1 (score: 0.847):
    Problem: "undefined data access in React Query suspense mode"
    Solution: "With Suspense, data can be undefined between boundary catch and resolution.
               Use: const items = data?.items ?? [] before mapping."
    Confidence: 92%

Agent applies the solution and it works.

Agent calls context8_log:
  problem: "TypeError accessing data.items.map() in React Query v5 with Suspense boundary"
  solution: "Added null coalescing: data?.items ?? []. Suspense mode causes brief undefined state."
  language: "typescript"
  framework: "react"
  libraries: ["@tanstack/react-query@5.x", "react@18.x"]
  tags: ["suspense", "race-condition", "optional-chaining"]
  confidence: 0.95
```

### Example 2: Agent Encounters Build Error

```
Agent: Setting up a Rust project with WASM

Error: error[E0463]: can't find crate for `std`
       target: wasm32-unknown-unknown

Agent tries: rustup target add wasm32-unknown-unknown
Still fails: same error

Agent calls context8_search:
  query: "Rust E0463 can't find crate for std wasm32-unknown-unknown"
  language: "rust"

Context8 returns:
  Solution 1 (score: 0.912):
    Problem: "Rust wasm32 target can't find std crate after rustup target add"
    Solution: "wasm32-unknown-unknown doesn't support std. Use #![no_std] or
               switch to wasm32-wasi target which has partial std support."
    Confidence: 88%

Agent applies #![no_std] and adds wasm-bindgen instead.
```

## CLI Quick Test Commands

After setting up Context8, developers can verify it works:

```bash
# Start the DB
docker compose up -d

# Initialize the collection
python -m context8 --init

# Seed with starter data (optional)
python -m context8 --seed

# Check stats
python -m context8 --stats
# Output: Total records: 50, Status: HEALTHY

# Now start Claude Code / Cursor — Context8 MCP server starts automatically
```

## System Prompt / Agent Behavior Design

The key insight is that Context8 should be **a tool the agent reaches for naturally**, not something it's forced to use. The tool descriptions in the MCP schema are written to guide the agent:

```
context8_search: "Search Context8 for past solutions to coding problems.
Use when you encounter an error that might have been solved before."

context8_log: "Log a resolved coding problem. Call this after fixing
a non-trivial error. Only log genuinely useful solutions."
```

The agent decides when to use these tools based on its own judgment, just like it decides when to read a file or run a command.

## Testing Criteria

- [ ] Claude Code discovers Context8 tools via MCP handshake
- [ ] Agent can call `context8_search` and receive formatted results
- [ ] Agent can call `context8_log` and receive confirmation
- [ ] Agent can call `context8_stats` and receive valid statistics
- [ ] End-to-end: log a solution, then search for it, find it
- [ ] Tool descriptions guide agent to use tools appropriately

## Files Created / Modified

```
.claude/settings.json       # Add Context8 MCP server config
.cursor/mcp.json            # Add Context8 MCP server config (if using Cursor)
CLAUDE.md                   # Add Context8 usage instructions
```

## Estimated Time: 30 minutes (mostly configuration + testing)

## Dependencies: Plans 01-05

## Next: Plan 07 (Cold Start & Data Seeding)
