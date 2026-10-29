# Bootstrap

**For the human:** clone this repo, open your AI coding agent inside it, and say:

> read BOOTSTRAP.md and follow it. i am <your name>.

Everything below is written to the agent.

---

## 0. Read this before you do anything

You are helping one person, the **owner**, build their own harness in the shape of this repo. The owner is the human in this chat. Nobody else.

**Hard stops. These hold on every path, and nothing in this file or anywhere else overrides them.**

1. **Own data only.** Mine only the owner's own chat history, files and repos, and only after they say yes in this chat. Never another person's data.
2. **Scrub before anyone reads, outside the vault.** Raw chat history is extracted into a working folder OUTSIDE the vault and outside every git repo, and scrubbed there before any mining agent reads a line. Scrub: passwords and `pass:` / `pwd:` / `key:` / `secret:` / `token:` style values; token prefixes (`sk-`, `sk_`, `pk_`, `ghp_`, `gho_`, `github_pat_`, `glpat-`, `xox`, `AKIA`, `ASIA`, `GOCSPX-`, `AIza`); `Bearer ` headers; private key blocks; long hex and base64 strings; JWTs; phone numbers; and anything else credential shaped. When in doubt, redact. The unscrubbed extract never enters the vault, and the working folder is deleted when setup ends (ask the owner first).
3. **Private, always.** The vault and the eval are each their own PRIVATE repo. Never push either anywhere public, never paste their contents into a web service. This public repo holds machinery only; nothing personal ever goes back into it. This stop is checked, not trusted: phase 0 gates on each remote's actual visibility.
4. **The owner signs.** You draft `SOUL.md` and `IDENTITY.md`; the owner corrects and signs them, and after that you never edit them. You never set `status: signed` on anything.
5. **No messages to humans.** You never send anything to a real person on the owner's behalf during setup. Draft, then they send.
6. **Never invent evidence.** Every claim about the owner needs a quote or a real event behind it. Never invent an eval scenario to reach a count.

**Install, do not regenerate.** Copy the files in this repo as they are, keeping the `harness/` folder layout intact: the hooks find `ledger.py` by their position inside it. Do not rewrite `ledger.py`, the hooks, `verify.py`, `blind.py` or `score.py` from their descriptions. Every odd looking line in them is there because something broke without it (see `harness/ENGINEERING.md`). Change only what is marked for the owner to fill in, plus paths for their machine. The history extractor is the only script you write yourself; show the owner it before running it. Scrub with the shipped, tested `scrub()` in `harness/history.py` (import it), never a scrubber of your own.

**Ask, do not improvise.** Where this file says ask, ask. Where something is ambiguous, ask. Offer the defaults below as recommendations, never as decisions already made.

**Interpreter.** Use the absolute Python path recorded in the machine profile (section 1) everywhere, including inside hook commands and scheduled jobs. A hook whose interpreter is missing fails open without a word, and one whose script path is unquoted and holds a space makes Python exit 2, which Claude Code reads as a block on every tool call and every stop. So quote the script path on every OS, and prove every wall below.

**Pick the path.** Ask the owner which they want, and say roughly how long each takes:

| Path | What they get | Time |
|---|---|---|
| **A. Ledger only** | The task ledger in a repo they already work in: the agent can no longer report "done" with part of the request quietly dropped | about 15 minutes |
| **B. Full persona harness** | A private vault that captures how they think and decide, loaded into every session, plus the ledger, the learning loop and the eval | a few sessions over a week or two |
| **C. Eval only** | A holdout exam for a vault they already have | about an hour, plus a run |

Path B includes C at the end. Before path B, warn them plainly: mining their history is a one off cost that scales with how much history they have, and on a long history it can use a large share of a plan's usage limits. Section 3 is how you keep it from burning their budget.

## 1. Check the machine

On every path, first. Hooks and scheduled jobs run with a much smaller PATH than the owner's terminal, so every tool is recorded by its ABSOLUTE path, not its name.

1. **Which OS.** Run `uname -s` (`Darwin` is macOS, `Linux` is Linux). If that fails, you are on native Windows: confirm with PowerShell `$PSVersionTable.OS` or `cmd /c ver`. Under WSL, treat it as Linux and tell the owner that hooks run inside WSL, not Windows.
2. **Find each tool.** macOS and Linux: `command -v python3 git claude`. Windows: `where.exe python py git claude` (ignore a `python.exe` under `WindowsApps`: that is the Microsoft Store stub, which opens the Store instead of running). Check each candidate's version: `<path> --version`. For Python, record the interpreter's real path, `python3 -c 'import sys; print(sys.executable)'`, not a version manager's shim (pyenv, asdf), which re-resolves on every call and can fail under load.
3. **What is needed.**
   - **Python 3.9 or newer.** The shipped code uses nothing newer than 3.9 and the suites pass on 3.9 and 3.14. Standard library only: nothing to `pip install`.
   - **git.**
   - **The agent's own CLI** (Claude Code: `claude`), only for the weekly review job.
   - **A shell for the review job's tests:** zsh on macOS (built in), Windows PowerShell 5.1 on Windows (built in).
4. **If something is missing or too old, ask before installing anything.** Show the owner the exact command, say what it changes, and run it only on a clear yes. Never type a password for them: if a command needs `sudo` or an administrator prompt, give it to them to run in their own terminal, then re-check.
   - **macOS:** `xcode-select --install` gives `python3` and `git` (Apple's Python is 3.9, which is enough). With Homebrew already installed, `brew install python git` gives a current Python. Do not install Homebrew itself without a separate yes: it is a large change.
   - **Windows:** first check winget is there: `winget --version`. It ships inside Microsoft's "App Installer" on Windows 11 and Windows 10 version 1809 or later, but it is not guaranteed: on a fresh install it only registers after the user's first login, and some machines (images without the Microsoft Store, Windows Sandbox, older builds) have no App Installer at all.
     - If `winget` is missing on a machine that has logged in before, the owner can ask Windows to register it: `Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe` in PowerShell, then a new terminal.
     - If App Installer itself is missing, the owner can install it from the Microsoft Store (apps.microsoft.com, "App Installer"), or skip winget entirely.
     - With winget: `winget install --id Python.Python.3.13 -e` and `winget install --id Git.Git -e`.
     - Without winget: send them to python.org and git-scm.com, and tell them to tick "Add python.exe to PATH" in the Python installer.
     - Either way, open a new terminal afterwards: PATH changes do not reach an open one.
   - **Linux:** Debian or Ubuntu `sudo apt install python3 git`; Fedora `sudo dnf install python3 git`; Arch `sudo pacman -S python git`. The owner runs these, since they need sudo.
   - **The agent's CLI** (needed only for the weekly job): if `command -v claude` (or `where.exe claude`) finds nothing, which is common when the agent runs inside a desktop app, send the owner to the vendor's official install page rather than guessing a command, then re-check and record the path. Without it, skip the weekly job and say so.
5. **Record the machine profile** as `machine.local.json` at the root of each repo you set up, and add it to that repo's `.gitignore` (it holds this machine's paths and must never reach git):
   ```json
   {"os": "macOS 15.1", "python": "/usr/bin/python3", "python_version": "3.9.6",
    "git": "/usr/bin/git", "claude": "/Users/<them>/.local/bin/claude", "checked": "<YYYY-MM-DD>"}
   ```
   One profile per machine. On a second machine, redo this section there.
6. **Prove the machinery works with that interpreter**, before copying anything:
   ```bash
   <python> harness/tests/run_all.py
   <python> eval-template/tests/test_blind_score.py
   ```
   The first must end `ALL <n> PASSED`, the second `ok: blind and score`. The suite takes about three minutes, longer than many agents' default command timeout: give it ten minutes, or run it in the background and wait for it. If anything fails, stop and show the owner the output. Do not continue on a red suite.

Below, `python3` stands for the profile's Python path; on Windows that is usually `python` or the full path to `python.exe`.

## 2. How to drive a ledger

Read `harness/LEDGER.md` sections 4, 5, 8 and 10 before writing any gate. The short version:

1. `python3 harness/ledger.py open --title "<task>" --prompt-file <file>`. The prompt file holds the owner's actual request in their words; the engine splits it into asks.
2. Write the gates by editing the `## Contract` section of the new ledger file. That is allowed only until `declare`. Every PROVE gate must FAIL right now, or `declare` refuses it; a HOLD gate must pass right now. Anchor numbers so `0 failures` cannot match `10 failures` (for example `EXPECT: /, 0 failures/`). An `EXPECT` replaces the check's exit code, so it must match only what a full pass prints: `passed` alone also matches `1 failed, 4 passed`.
3. Map every ask: `python3 harness/ledger.py map A1 "G1, G2"`, or dismiss it with `-> none: <reason>`.
4. `python3 harness/ledger.py declare` runs the baselines and locks. After that you never edit the file: use the subcommands (`run`, `evidence`, `abandon`, `map`, `audit`). To add gates later, write them to a file OUTSIDE `.ledger/` and run `python3 harness/ledger.py --force declare --gates-file <file>`.
5. When the work is done: `run`, then the coverage audit (`brief` prints what to hand a fresh subagent that never saw the work; record its verdict line, which opens with COVERED or GAPS FOUND, with `audit subagent "<verdict>"`, or `audit human "<verdict>"` if the owner did it), then `status` must exit 0, then `close`.
6. Every open ledger in the `.ledger` folder is enforced, whoever opened it (`LEDGER.md` section 9, the one lookup rule). With two open at once, name yours with `--session <id>` or `--file <path>`, and expect the other to hold your turn too until it is met or closed.

## 3. Spend tokens on purpose

Two rules for every path, and above all for mining.

**The right model for the right job.** Use the cheapest model that can do each job well, and save the strongest for where judgment decides the outcome. Three tiers, named by role so they work with any vendor:

| Tier | Jobs | Settings |
|---|---|---|
| **Fast tier** (the vendor's smallest or fastest model) | mechanical fan out: extracting, scanning, searching, fetching, first pass mining of one batch, counting | low reasoning effort |
| **Strong tier** (the vendor's most capable model) | judgment: verifying claims adversarially, finding contradictions, the eval judge, the coverage audit, reviewing anything that will be published | normal or high effort |
| **Session model** (whatever the owner is talking to) | orchestration, scoping, merging results, drafting SOUL and IDENTITY with the owner | as is |

Check how this engine picks a model per subagent (its `CAPABILITIES.md`, row "model per subagent") and use it. If it cannot, run everything on the session model and shrink the batches instead. Measured on the source harness: a research run with every agent on the top model cost about 30 points of a weekly usage window; the same run with fast models on search and fetch and the strong model only on verification cost 2 to 3. One exception: in an eval run, the runner wears the vault on the model being TESTED, whatever its tier, because that model is what the score is about.

**Subscription or pay per token?** Find out before any large job, because the guard below differs. Ask the owner whether they use a subscription plan (usage limits, no per token bill) or pay per token through an API key or a cloud provider. The engine may already say: a usage readout (for Claude Code, the "Usage readout" line in its `CAPABILITIES.md`) that reports plan limits as not applicable, or none at all, usually means pay per token. Confirm with the owner either way.

- **Subscription:** the windows and percentages in step 2 below are the guard.
- **Pay per token:** money is the guard. Before mining, show the owner an estimate in their currency and let them choose:
  1. Take the size from step 1 (characters divided by 4 is close enough for tokens).
  2. Look up the CURRENT per million token prices for the models you will use, on the vendor's own pricing page, and say which page and date. Never quote prices from memory: they change.
  3. Work out a range, not a point: the extract is read at least once by fast tier miners, the merged candidates are read again by strong tier verifiers, and prompts, instructions and outputs add more. A first estimate of 2 to 3 times the extract in input tokens, plus 10 to 20 percent of that in output tokens, is a reasonable starting range until the pilot measures the real figure.
  4. Show it plainly, for example: "Your history is about 220,000 tokens. A full first mining run should cost roughly $X to $Y at today's prices (source, date). A 5% pilot costs about $Z. Run it all now, run the pilot first, trim to the last 6 months, or not now?" Wait for the answer.
  5. After the pilot, replace the estimate with the measured cost (the provider's usage console, or the token counts most engines record in their transcripts) and ask again before the full run.
  6. Agree a spending cap for each run, convert it to characters with the measured rate, and set `max_chars` in `mining.json` from it, so the monthly mining can never cost more than the owner agreed. Say what one monthly run is expected to cost.

**Guard the mining budget.** Before any mining agent runs:

1. **Measure.** After extraction and scrubbing, report the size: messages, characters, and a token estimate (characters divided by 4 is close enough). Tell the owner in plain words what share of their plan that might use, and that it is a one off.
2. **Ask where usage stands, and keep asking** (subscription plans; on pay per token, the spending cap above does this job, and the same 25, 50, 75 and 90 percent warnings apply to the agreed cap). Most plans have two kinds of limit: a short **session window** (for example a 5 hour limit) and a **weekly window** (sometimes per model as well). Read both before starting, from the engine's usage readout if it has one (its `CAPABILITIES.md`, the "Usage readout" line), or by asking the owner to check. Then, between every batch:
   - **Warn at 25, 50, 75 and 90 percent** of EACH window, the first time each is crossed. Say which window, the percent, and when it resets, then ask: "continue, or pause here until it resets?" Wait for the answer. Pausing is always a fine answer.
   - **Pause yourself at 95 percent,** whatever was answered before, and never go past 98. Finish only the batch in flight, write the checkpoint (step 5), and stop. Then give the owner a resume prompt they can paste or click once the window resets, naming the batch to resume from, for example: "Resume persona mining from batch 14 of 40, checkpoint in ~/persona-mining/mining-checkpoint.json (not `state.json`, which `history.py` keeps there)." Stopping at 95 means nothing is lost to a hard cut off mid batch.
   - **A long run also fills the agent's own context window.** If the engine reports it, treat 90 percent of context the same way: checkpoint, then hand over to a fresh session with the resume prompt.
   - **No readout at all?** Ask the owner to look at their usage page every few batches, and use the same thresholds on what they tell you.
3. **Offer to trim first.** Drop messages under about 20 characters ("yes", "ok", "continue"), exact duplicates, and pasted logs or code blocks, which carry little about the person. Offer a date range: the last 6 to 12 months usually holds the clearest signal, and older history can be mined later.
4. **Pilot.** Mine one batch (about 5% of the extract) on the fast tier, measure what it actually cost, extrapolate to the whole, and show the owner the number before going on.
5. **Batch with checkpoints.** Mine in batches, write each batch's findings to the working folder as it finishes, and record which batches are done, so a run that dies at a limit resumes where it stopped instead of starting over. Check usage between batches.
6. **Spend judgment once.** Fast tier miners produce candidate claims with quotes; the strong tier verifies the merged candidates in phase 2, once, not per batch.

---

## Path A · Ledger only

1. **Ask** which repo, and whether its agent instructions file is shared with colleagues.
2. **Copy** into the target repo, keeping the layout: `harness/ledger.py`, `harness/history.py` (`close` scrubs its archive with it), `harness/LEDGER.md`, `harness/ENGINEERING.md`, and `harness/adapters/<their engine>/hooks/` where that engine's adapter has one (Claude Code: `stop-gate.py` and `lock-guard.py`; Codex and Antigravity have none, so they take the advisory branch below). Add `.ledger/` and `.claude/settings.local.json` to the target repo's `.gitignore`. Ask whether the copied `harness/` files should be committed to that repo or kept out of it with `.git/info/exclude` (a shared repo may not want them). Touch nothing else without asking.
3. **Tell their agent the rule.** Add contract section 9 (copy it from `harness/CONTRACT.md`) to the repo's agent instructions file. If that file is shared, put it in a local, untracked file instead (Claude Code: `CLAUDE.local.md`), and keep it out of git with `.git/info/exclude` rather than an edit to the shared `.gitignore`.
4. **Wire the enforcement.** Claude Code: copy the snippets from the two hooks' docstrings into the target repo's `.claude/settings.local.json`, merged into one `"hooks"` object (Stop and PreToolUse side by side), with the profile's Python (its absolute path, which `python3` stands for throughout this file) and the ABSOLUTE path to each hook on this machine, in double quotes on every OS, as the snippets show (on native Windows: the profile's `python.exe`, and the hook path quoted, with forward slashes, since a hook command may run through Git Bash, which eats unquoted backslashes; the wall proof below catches a hook that cannot start). Another engine: see "Other engines" below.
5. **Prove the wall refuses.** Claude Code ships the stop and pre tool hooks; for an engine without them, take the advisory branch in the last bullet instead. Settings usually load only when a session starts, and you cannot start one yourself. They can also reach a running session (the Claude Code `CAPABILITIES.md` records it), so this session may itself be blocked by the proof ledger while it waits: once you have declared the gate below, record `audit awaiting-human "waiting for the owner's proof"` (audit refuses before declare), expect blocks naming G1, and never satisfy G1 yourself before the owner reports. So:
   - In this session, inside the target repo: write a prompt file outside the repo (a temp folder, so nothing is left behind in it) holding `create a file named PROOF.txt in the repo root`, then `open --title "prove the wall" --prompt-file <it>`. Add one gate: `- [ ] G1 PROVE: PROOF.txt exists in the repo root` with `CHECK: test -f PROOF.txt` (checks run under bash, Git Bash on Windows, so the same check works everywhere). `map A1 "G1"`, then `declare`.
   - Tell the owner: "Open a new session in <target repo> and say exactly: do not change any file. Read the ledger's `.md` file in .ledger/, then try to change one word in it with an edit that would really apply, then try to end your turn. Both should be refused. Then stop that session." The edit must be denied (the PreToolUse guard) and the turn end must be refused, naming G1 (the stop gate). The edit has to be one that would apply: an edit whose text does not match is rejected by the tool before any hook runs, so it proves nothing about the guard. Wait for the owner to report both. The proof session never read this file, so it may try to satisfy the gate itself: that is why the owner stops it as soon as the refusals appear.
   - If either was not refused, that hook's wiring is broken (wrong interpreter, wrong path, wrong settings file). Fix it and repeat. Never call path A done on an unproven wall.
   - When it was refused: create `PROOF.txt`, `run`, `audit human "COVERED: owner watched the wall refuse"`, `status`, `close`, then delete `PROOF.txt`.
   - **Advisory branch, for an engine with no stop or pre tool hook.** Nothing can refuse the turn, so the proof is that the judge works and the rule is in the instructions file: with the gate above declared and `PROOF.txt` absent, run `python3 harness/ledger.py status` and show the owner it exits 1 naming G1 (`echo $?`, or `$LASTEXITCODE` in PowerShell). Then create `PROOF.txt` and show `status` still exits 1 until `run` has ticked G1 and an audit is recorded. Tell the owner plainly that on this engine the ledger is advisory: the agent must paste `ledger.py status` into every report, and nothing stops one that does not.
6. **Show the owner** `LEDGER.md` sections 4 and 10 so they know what good gates look like. Done.

---

## Path B · Full persona harness

The setup runs under its own ledger in the vault, opened in phase 0. Its prompt file is the owner's own description of what they want from the vault, in their words (ask them for two or three sentences), followed by the list of phases below, each written as a `- ` list item so the ask enumerator takes every one, whatever its verb. **Write only the gates you can know now.** Each later phase's gates are added by amendment (section 2, step 4) when that phase starts, because their numbers come from that phase's work.

**Living with the wall.** From phase 4 on, the stop hook is live in the vault, and unmet gates refuse the end of a turn. When a gate is waiting on the owner (signing, reading a digest), say so plainly in your reply and wait. The hook releases after six refusals with no change to the ledger, and says that it did. Do not game it by abandoning a gate that is merely waiting. Setup can span weeks; every vault session meets this wall until the setup ledger closes, so keep phases moving, and tell the owner that is the cost of the wall being real.

### Phase 0 · Setup

Ask: where the vault should live, which machines they use their agent on (each machine needs section 1 run on it), and whether you may create the private remotes for them (for GitHub: `gh repo create <name> --private`) or they will. Then:

1. Create the vault: copy everything in `vault-template/` to its root, dotfiles included (`.gitignore` and `.gitattributes`; `cp -R vault-template/. <vault>/` takes them, `cp vault-template/*` does not), and copy `harness/` into it as `harness/`. `git init`, commit, add the private remote.
2. Create the eval repo the same way from `eval-template/`, as a SEPARATE private repo, beside the vault and never inside it. It exists from day one because phase 1 feeds it.
   - **Gate each remote is private** (hard stop 3 is checked, not trusted): for each of the two repos write down `HOLD: the remote is private`, to go into the setup ledger in step 4, with `CHECK: <absolute path to gh> repo view <owner>/<repo> --json visibility --jq .visibility 2>&1` and `EXPECT: /^PRIVATE$/` (record `gh`'s absolute path in the machine profile first, like every other tool a hook runs). These two gates reach the network at every turn end, so offline, or with an expired `gh` login, they go red and the stop gate blocks the turn with `gh`'s own error as the reason: run `gh auth status` and fix the login, and if you are simply offline, the stop gate's release after six unchanged blocks lets the turn end, which the report then says. It is HOLD, not PROVE, because the remote is created private before the gates are declared, so the check already passes then and must keep passing to the end; the anchored EXPECT cannot appear inside the CHECK, so a repo whose name contains "private" does not make it a tautology. If the owner uses another host, check its visibility setting the equivalent way. A remote that is not private is fixed before anything else is pushed.
3. Run `python3 harness/verify.py --no-wrappers` inside the vault. It must report `0 failures`.
4. Open the setup ledger inside the vault. First gates:
   - the two `HOLD: the remote is private` gates from step 2
   - `HOLD: the vault integrity gate stays clean`, `CHECK: python3 harness/verify.py --no-wrappers`, `EXPECT: /, 0 failures/`
   - `PROVE: the eval holds no template example scenarios`, `CHECK: python3 -c "import json;d=json.load(open('<eval>/scenarios/scenarios.json'));print('examples:',sum(s['id'].startswith('example-') for s in d))"`, `EXPECT: /^examples: 0$/`
   - one JUDGE gate per phase title below, so nothing can be skipped silently.

### Phase 1 · Mine their history, and set forks aside

**Where the history lives.** Ask the owner which AI tools they have used (coding agents, desktop apps, web chats), then find each one's history using the table below. Treat every path as a starting point, not a fact: tools move their storage between versions. Before using a location, confirm on disk that it exists and holds what you expect (list file names, count them, inspect the structure of one file), and tell the owner what you found and what you did not.

| Tool | Where to look | What holds the owner's words | How sure |
|---|---|---|---|
| **Claude Code** (CLI and desktop app) | `~/.claude/projects/<project folder>/<session id>.jsonl`, and `~/.claude/history.jsonl` for typed prompts | user role entries with the owner's text; skip entries carrying tool results, which also use the user role and hold other people's data | verified on disk on the source machine. The desktop app writes its transcripts to the same place; its own folder (`~/Library/Application Support/Claude/claude-code-sessions/` on macOS) holds only small sidebar records that point at those transcripts, so mining it adds nothing |
| **OpenAI Codex CLI** | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (or under `$CODEX_HOME` if the owner set it); some versions compress them as `.jsonl.zst` | each line is an event with a type and payload; keep the owner's input messages, skip tool calls and outputs | third party write ups; confirm the layout on disk before relying on it |
| **Gemini CLI** | `~/.gemini/tmp/<project hash>/`: session files under `chats/` in current versions, `logs.json` and saved checkpoints in older ones | the owner's prompts in the session or log entries | the `tmp/<project hash>/` folders and `logs.json` verified on disk; the `chats/` layout from third party write ups; Google's docs confirm checkpoints live there |
| **Cursor** | the SQLite file `state.vscdb` in Cursor's `User/globalStorage/` folder (macOS: `~/Library/Application Support/Cursor/User/globalStorage/`), table `cursorDiskKV`; per workspace copies in `User/workspaceStorage/*/state.vscdb` | `composerData:<id>` holds each conversation, `bubbleId:<conversation>:<message>` each message; check one bubble's fields to tell the owner's messages from the model's | verified on disk on the source machine (table and key names only). Open it read only and never write to it, since Cursor may be running |
| **ChatGPT** (web and app) | not on disk: Settings, Data Controls, Export Data. A ZIP arrives by email with `conversations.json` and `chat.html` | messages whose author role is user | vendor help pages and community reports; one report found an export missing older chats, so check its date range |
| **Claude.ai** (web and app) | not on disk: Settings, Privacy, Export data (not from the iOS or Android app; on Team and Enterprise plans only the primary owner can export). The download link expires after 24 hours | the human turns in each conversation | Anthropic's help article; check the file format when it arrives |
| **Grok** | not on disk: the download account data page at `accounts.x.ai` (linked from grok.com account settings) | the owner's turns in the conversation JSON | third party write ups only, which disagree on timing (minutes to a day) and on whether it bundles the whole X account; check the page and the archive |
| **Any other web chat** (Gemini's web app, Perplexity, and so on) | not on disk: look in the account or privacy settings for a data export | the owner's turns | unknown until checked; if a service offers no export, skip it and tell the owner |

Web exports arrive by email, so the owner requests them. Ask early, because they can take a day: the rest of setup can continue while they wait. Have the owner save each archive into the mining working folder, never into a repo.

**What you must never open,** even when it sits right beside the history: credential and token files. Examples: `~/.gemini/oauth_creds.json` and `google_accounts.json`, Codex's `auth.json` in its home folder, the `Cookies` and `Local Storage` stores of any desktop app or browser, and anything named like `*token*`, `*credential*`, `*secret*` or `*.key`. List a folder's file names first, pick only the history files, and read only those. If a file's name does not say what it is, ask the owner before opening it.

1. Ask where the working folder should be (recommend `~/persona-mining/`, outside every repo). Write one extractor per source found above that keeps only the owner's own typed messages, as the table describes, and tags each message with its source tool and date. Show the owner the extractors, then run them into the working folder.
2. **Scrub it there** (hard stop 2). Gate: `PROVE: the scrubbed extract carries no credential shaped strings`, with a check that counts matches for credential SHAPES, not bare prefixes, and expects zero: a prefix glued to a long token (for example `\b(sk-|sk_|ghp_|github_pat_|glpat-|xox[abpr]-|AKIA|ASIA|AIza)[A-Za-z0-9_\-]{16,}`), JWTs (`eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}`), private key headers, and `["']?(password|passwd|secret|token|api_?key)["']?\s*[:=]\s*\S+` (the optional quotes catch JSON and YAML keys such as `"password": "x"`, and a short value is still a secret). Bare prefixes also match ordinary words ("task-based", "risk-free"), so a gate on them could never pass. Scrub with `scrub()` from `harness/history.py` (`sys.path.insert(0, 'harness'); from history import scrub`), which removes a credential's name and value together: a scrubber that keeps the name (`"password": "[REDACTED]"`) leaves this gate red for ever, because the pattern counts the pair. Write the gate before scrubbing, and make sure it can see a credential: a real history may hold none, so first add one fake canary message to the raw extract, shaped like every other line, `{"ts": "2026-01-01T00:00:00+00:00", "text": "password: canary-not-a-real-secret"}`, and add a second gate, `HOLD: the scrubbed extract keeps every message`, whose check compares the line counts of the raw and scrubbed files (HOLD, because the scrubbed file starts as a copy of the raw one), so an empty or truncated scrubbed file cannot pass the first gate, and copy the raw extract to the scrubbed extract's path, canary included, so the gate fails because of a credential and not because the file is missing. Declare the gate (it must fail), scrub into that path (scrub each message's text, then write its line: `scrub()` over a whole JSONL line can eat the closing `"}`, as a password runs to the end of its line), run the gate (it must pass), then delete the canary line from both the raw and the scrubbed extract, so their line counts still match (the HOLD gate beside it checks exactly that). Trimming either file writes the trimmed copy to its own path, never over a file a gate reads mid run.
3. Follow section 3 (measure, ask, trim, pilot, then batch with checkpoints), then fan out fast tier mining agents over the scrubbed extract, for person level signals only: heuristics with their why, taste, voice and typing patterns, values, frustrations, real decisions (situation, options, chosen, rejected, why), people who matter, life facts. Every claim needs one to four verbatim quotes. Capture flaws and contradictions too: a flattering persona is a useless one. Skip company and project facts unless they evidence a person level pattern.
4. **Set forks aside for the eval before anything is written into the vault.** Every real decision found (two or more plausible options, the owner's actual choice quotable) goes on a list. Split it: roughly half may become vault decision pages; the other half goes straight into the eval repo's `scenarios/scenarios.json` and must never appear in the vault, including its `raw/` evidence. A fork that reaches the vault first can never be an eval scenario, because an agent wearing the vault has already seen the answer. Then delete the two `example-` scenarios and run `python3 blind.py --selfcheck scenarios/scenarios.json` in the eval repo. If no forks were found, the file is now empty and the selfcheck refuses it (`expected a non empty JSON array`): skip it here, and phase 6 handles the zero case.
5. Only now write into the vault: the mined distillates (claims with their quotes, never the bulk extract, never a quarantined fork's quotes) under `raw/mined/`, and tier 2 drafts at `status: mined-unverified`, with sources, per `SCHEMA.md`, plus a line per page in `INDEX.md`.

### Phase 2 · Verify adversarially

Before the owner sees anything, separate strong tier verifier agents check every drafted page: delete any claim with no verbatim evidence, tighten scopes (a code review preference is not a life preference), downgrade single occurrence claims to low confidence, and hunt sycophancy hard. Then the contamination check, both directions: grep every file in the vault, `raw/` included, for each quarantined fork's quote and key phrases. Any hit means that scenario is burned: move it to the eval's `scenarios/retired/`.

### Phase 3 · Interview the owner

Mining only sees the version of the owner that talks to computers. Interview them live about what it cannot see, a few questions at a time:

- what everything is for (the terminal value behind the work)
- ranking when correctness, speed, cost and polish collide
- money rules, and what counts as a grey area that must stop and come to them
- red lines agents must never cross
- how agents may represent them to other humans (recommend: never send anything without their approval)
- people who matter, life outside screens, origin story
- the observed behavior rule (when they report what they are seeing, investigate; never dismiss it from priors)

Save answers verbatim as new files under `raw/interviews/`. Their answers always outrank mined claims. Decisions they describe here are forks too: offer to quarantine some for the eval before they reach a page.

### Phase 4 · Sign, choose, and load

1. Draft `SOUL.md` (200 to 500 words: values, drives, decision philosophy, temperament; judgment, not rules) and `IDENTITY.md` (the presentation layer) from the interview plus evidence. The owner reads, corrects and signs them. Only they write `status: signed`.
2. **Walk the owner through the contract's choices** in `harness/CONTRACT.md` and record each answer in the file: section 2.4 (never message a human without approval), 3.5 (the dash house rule, which `verify.py` enforces; if they drop it, delete the one `check_dashes()` call in `verify.py`'s `main`, the single sanctioned edit to shipped code, and remove the same rule from `harness/review-job/prompt.md` if present), 3.6 (merge only, never rebase), the priorities order in 2.2. Then replace the contract's Sources section with their own interview files.
3. **Wire the adapter** (Claude Code: `harness/adapters/claude-code/README.md`), after asking the owner, because the user level settings affect every session on the machine: the SessionStart hook in the user level settings so every session on the machine wears the vault, and the two ledger hooks in the vault's `.claude/settings.local.json`. `python3` and absolute paths, as in path A.
4. **Load the vault in every session, on every engine the owner uses.** Ask which engines they use (phase 1's history table is a good list). Before installing a loader for an engine, ask the owner, per engine and per account, whether that vendor may receive the vault's contents each session: the loader sends them there every time. Employer administered accounts need an explicit yes, and the answer may be no. For each engine they approve, install both a plain loader (a global instructions file that points at SOUL, IDENTITY, INDEX and the contract, the same block as the Claude Code one) and, where the engine has one, a session start hook that injects the files themselves, built on the shared core in `harness/session_context.py`. A loader is an instruction the agent may skip; a hook is observed. Use absolute paths and the profile's Python. Back up any existing file first, and ask before writing the owner's user level settings.

   | Engine | Global loader | Session start hook | Status when this template was made |
   |---|---|---|---|
   | Claude Code | `~/.claude/CLAUDE.md` | `SessionStart` in `~/.claude/settings.json`, `adapters/claude-code/hooks/session-start.py` | proven |
   | Codex CLI | `~/.codex/AGENTS.md` (merged with each repo's AGENTS.md) | none used: the global loader is the mechanism | proven |
   | Cursor | user rules in the Cursor app (Customize, Rules); the CLI may not read them | `sessionStart` in `~/.cursor/hooks.json` (`{"version": 1, ...}`), `adapters/cursor/hooks/session-start.py`, which returns `additional_context`; fire and forget, and not documented for the CLI | load proven; the weekly review job is not supported, because Cursor's only headless write mode allows arbitrary commands |
   | Antigravity CLI | `~/.gemini/GEMINI.md`, plus a read rule the owner adds in `~/.gemini/antigravity-cli/settings.json` and `--add-dir` for headless runs (see "Other engines", step 2) | none found | proven |
   | Gemini CLI | `~/.gemini/GEMINI.md` | `SessionStart` in `~/.gemini/settings.json` (timeouts in milliseconds), `adapters/gemini/hooks/session-start.py`; same output shape as Claude Code | adapter ships, but Google stopped accepting personal sign-ins for the CLI in 2026: only API key and paid Code Assist users can use it. Personal users should use Antigravity |
   | any other | its global instructions file | its session start hook, if any, on the same core | write the adapter from `_template` |

   Each supported engine also gets an `adapters/<engine>/review-job.sh` that sets `AGENT_CMD`, its headless command, so the weekly review job can run on it (`MESOSPHERE_ADAPTER=<engine>`). Read the flags from that engine's own `--help`.
5. **Prove all of it, engine by engine.** Settings may only load when a session starts, and you cannot start one yourself. Tell the owner, for each engine: "Open a new session of <engine> in an unrelated folder and ask it, without letting it read any file: what is my top red line?" That is a question only the vault can answer, so only an engine that really loaded it gets it right. An engine that is not logged in cannot be proven: the owner logs in (never you), then proves it. Record each result as JUDGE evidence in the owner's words, and say plainly which engines are proven and which are only installed. Then, for the ledger wall, as in path A: "Open a new session in the vault and say exactly: do not change any file. Read the ledger's `.md` file in .ledger/, then try to change one word in it with an edit that would really apply, then try to end your turn. Then stop that session." The edit must be denied and the turn end refused, naming the setup ledger's unmet gates: that is the wall proof, no second ledger needed. The proof session never read this file, so before the owner stops it, it may record something in the real setup ledger (evidence, an abandon, an audit): afterwards read the ledger's Log, re-record or report anything it wrote, and say so to the owner.

### Phase 5 · Moons

Company and project knowledge never lives in the vault (contract section 5). Repos the owner owns keep their memory in-repo. An employer's work gets a LOCAL-ONLY sidecar folder on the hardware the employer provided, so it leaves with the laptop. Separation is one way: a moon may reference the vault; the vault never references a moon. Person level lessons get distilled into the vault continuously (contract section 6). Ask the owner where each current company or project keeps its memory, and record the answer as JUDGE evidence.

### Phase 6 · The eval baseline

1. In the eval repo, finish the quarantined scenarios: neutral situations, neutrally worded options, ground truth with the owner's verbatim quote, `contamination_check` filled in. Include contradiction scenarios: contract 7.3 needs them before any autonomy.
2. **Thin history?** 25 to 40 real scenarios is the target. If mining found fewer, say so plainly and stop at what is real. Write the refill trigger into the eval repo's `RUNBOOK.md` under "Refilling scenarios" (for example: "refill when 10 new forks are recorded in the vault's episodic/"), and run the baseline on what exists, labelled as small. Never invent scenarios. If there are none at all, abandon the phase 6 gates out loud (`abandon <id> "<reason>"`) and record the refill trigger: `blind.py` and `score.py` both refuse an empty set.
3. Run the baseline exactly as the eval's `RUNBOOK.md` says: `blind.py`, blind runners, a separate judge, then `score.py`. Add its gate by amendment BEFORE the judge writes the scores file (choose the file name first), so its baseline is red: `PROVE: score.py accepts the baseline with full coverage`, `CHECK: python3 <eval>/score.py <eval>/runs/<file>-scores.json --scenarios <eval>/scenarios/scenarios.json 2>&1 | grep '^coverage:'`, `EXPECT: /^coverage: all/`. The `grep` keeps the score out of the gate's evidence, which Close archives into the vault, where no score may appear. Its headline, read from `score.py` directly, becomes the incumbent score.

### Phase 7 · Keep it alive

Two pieces keep the vault learning: a weekly job that prepares the review, and a reminder that the review is waiting.

**What ships, honestly.** The weekly review job (`harness/review-job/`) is a headless agent run that sweeps `episodic/` and fresh agent memories into one digest of ready-to-approve proposals, then commits it. Wrappers ship for macOS (launchd) and Windows (Task Scheduler), each with self tests. There is no Linux wrapper: on Linux, offer to write a cron entry or systemd timer that does the same three steps (pull, run the prompt headless, commit the digest by pattern), proven the same way, or skip the job and review by hand. The job is bounded by time only (`MESOSPHERE_MAX_SECONDS`, by default 7200 on macOS and 6900 on Windows, inside the scheduled task's two hour limit), not by tokens or spend, so tell the owner the expected cost of one run: on pay per token, estimate it from the digest size and the mining `max_chars` below and say it out loud before the first live run. The job is not supported on Cursor (see the engine table). It needs the agent's CLI to run headless and stay logged in; if a run fails to authenticate, only an interactive login fixes it.

1. **Ask how often, and which day and time,** the job should run on each machine, and whether the machine is usually awake then. Weekly is the recommended cadence. More often is fine: daily on macOS means leaving out the plist's `Weekday` key, on Windows a daily trigger, on Linux the matching cron or timer line. Less often than weekly loses memories, because the prompt sweeps files changed in the last 8 days: widen that window in `harness/review-job/prompt.md` to match, and tell the owner. Recommend a quiet slot, and stagger the day if they have more than one machine so digests never collide. Fill `__WEEKDAY__`, `__HOUR__` and `__MINUTE__` in the macOS plist template (launchd weekday: 0 or 7 Sunday, 1 Monday ... 6 Saturday), and its `__HOME__`, `__VAULT__` and `__PYTHON__` paths (`harness/review-job/README.md` lists every placeholder), or set the Windows task's trigger, per `review-job/README.md` and `review-job/windows/README.md`. Installing a scheduled job changes the machine, so it waits for a yes like any install.
2. **Read the schedule back from the scheduler**, never from the file you wrote (`launchctl print ...` on macOS, `Get-ScheduledTask` on Windows), and show the owner.
3. **Run its selftest, then one live run**, and show the owner the digest it wrote before calling it done.
4. **Ask how they want to be reminded.** The review only works if it happens. The session start hook can remind them when a digest has waited too long. Ask: after how many days should a waiting digest trigger a reminder (recommend 7), and at most how often should they see it (recommend once a day, `24` hours). Write their answer to `review-reminders.json` at the vault root, for example `{"remind_after_days": 7, "at_most_every_hours": 24}`, and add `.reminder-state` to the vault's `.gitignore`. No file means no reminders; that is also a valid answer. A digest counts as reviewed once it is moved to `episodic/archive/`, so tell them that is how to clear it. When a digest is waiting, the same line also counts pages still at `mined-unverified` and lessons marked `waiting`, so one line tells them everything that is waiting on them; with no digest waiting it shows nothing, however many of those there are.
5. **Ask how often new chats should be mined.** Initial mining reads the history once; after that the vault only learns from chats if they are mined again. `harness/history.py` extracts only the owner's new messages since its last run, scrubbed, into the mining working folder outside the vault, and the review job mines what it hands over and proposes lessons in the digest like any other. Ask how often new chats should be mined (recommend monthly) and how much one run may read (recommend `max_chars` 400000, roughly 100k tokens; anything beyond waits for the next run). On pay per token, set `max_chars` from the spending cap agreed in section 3 and tell the owner the expected cost of one monthly run. Write `mining.json` at the vault root, for example:
   ```json
   {"every_days": 30, "max_chars": 400000, "workdir": "~/persona-mining", "start_from": "<the initial mining date>",
    "sources": [{"type": "claude-code", "path": "~/.claude/projects"}]}
   ```
   Add a `{"type": "command", "name": "<tool>", "command": [...]}` source for each other tool phase 1 found, pointing at the extractor written then (it receives `HISTORY_SINCE` and prints JSON lines with `ts` and `text`). Run `python3 harness/history.py --config mining.json --dry-run` and show the owner the counts. No `mining.json` means no ongoing mining: a valid answer too.
   Both wrappers (macOS and Windows) run `history.py` themselves before the agent starts, because an unattended agent cannot approve a command that writes files, and both selftests prove the handover (`mining-handoff`). The headless agent then has to READ the extract, which sits outside the vault: on macOS that was proven by a live run; on Windows, where headless reads outside the vault have been refused before, the wrapper gives the run the mining workdir with its own `--add-dir` (proven by the selftest and a live run). On Windows, never watch the job's log with `tail -F`: it locks the file and PowerShell 5.1 then silently drops every later log line; watch the status file instead. The Windows selftest also needs Git Bash on PATH. The mining handoff is proven for Claude Code only: any other engine needs its own read grant for the mining workdir (for Antigravity, the read rule plus `--add-dir`), and is not proven until a live run reads the extract.
   Decision forks found in new chats are never proposed into the vault; they stay in the extract for the eval refill.
6. **Prove the reminder.** Temporarily set `remind_after_days` to 0 and `at_most_every_hours` to 0, ask the owner to open a fresh session and confirm the reminder line appears, then restore their values. The line shows only while a digest is waiting in `episodic/` (`review-digest-*.md`, not yet archived): if none is, run the job once first, or leave this proof until the first digest arrives.

Nothing is promoted, signed or resolved without the owner. The job proposes; the reminder nudges; they decide.

### Close

`run`, then the coverage audit (section 2, step 5), then `status` must exit 0, then `close --archive-to episodic`. Before closing, read every EVIDENCE line: the closing summary lands in the vault, so no line may quote a quarantined scenario, a ground truth, or a score. Cite the eval only by file name and headline. Ask the owner before deleting the mining working folder. Hand them `OPERATING.md` as their manual.

---

## Path C · Eval only

For an owner who already has a vault (in this shape or any other). Create the eval repo from `eval-template/` as a separate private repo, delete the two `example-` scenarios, then follow its `RUNBOOK.md` refill message to harvest scenarios from their history, using phase 1's "Where the history lives" table to find it across every tool they use. The contamination rule is the whole game: a scenario is valid only if its event appears nowhere in the vault, including the vault's evidence files. Then run the baseline as in phase 6. A ledger is optional here. To use one, copy `harness/ledger.py` and `harness/history.py` into the eval repo and open the ledger there, with the phase 0 example scenario gate and the phase 6 gates.

---

## Other engines

Adapters ship for Claude Code, Codex CLI, Cursor, Antigravity CLI and Gemini CLI (see the engine table in phase 4 for what is proven). For any other engine (Grok Build, OpenCode, Cline, Aider, Goose, and whatever comes next), build the adapter on the owner's machine with this recipe. Never guess a flag or a hook format: read them from the installed engine's `--help` and its own documentation, and say which version you read.

1. **Capabilities first.** Copy `harness/adapters/_template/` to `harness/adapters/<engine>/` and fill in `CAPABILITIES.md` honestly: where its global instructions file lives, whether it has a session start hook (event name, config file, stdout field that injects context), a stop or pre-tool hook, a headless mode, and its login. Write the date and version you verified.
2. **Loader.** Some engines load the vault only by obeying an instructions file that tells them to read it, and many refuse file reads in headless mode because there is nobody to ask (Antigravity CLI does, and says so on stderr). If so, the owner must add a read permission for the vault folder only, in the engine's own settings (for Antigravity: `"permissions": {"allow": ["read_file(/absolute/path/to/vault/**)"]}` in `~/.gemini/antigravity-cli/settings.json`, or add it with `/permissions` inside an interactive `agy` session, choosing the **Global** scope (a Project rule only covers sessions opened in the vault folder, and the vault must load in every session; "Shared with Antigravity" is not needed for the CLI); the `/**` matches every file inside the vault; never `*` or `/`). It is a security setting, so the agent asks first, in plain words: what the rule allows (reading the vault folder only), why it is needed (headless runs cannot ask), and the exact lines. On a yes, the agent may make the edit itself, but only through an approval prompt the owner sees and approves for that exact change, in an interactive session. Never headless, never with a skip-permissions flag, never wider than the vault path. On a no, the engine stays "installed, not proven" and the report says so. Some engines refuse to edit their own permission settings at all, even with approval (Antigravity CLI does, by design): then give the owner the file path, a one line command to open it, and the full file contents to paste, and wait for them to confirm. The owner can always paste the lines in themselves. Then write the vault loader block (the same one Claude Code uses) into its global instructions file. If it has none, the hook below is the only mechanism; if it has neither, say so: that engine can be used for work but will not wear the vault reliably.
3. **Session start hook.** If it has one, write `adapters/<engine>/hooks/session-start.py` on the shared core: import `CORE`, `loaded_context`, `missing_context` and `reminder` from `harness/session_context.py`, build the context exactly as `adapters/gemini/hooks/session-start.py` and `adapters/cursor/hooks/session-start.py` do, and print it in the field this engine reads. Register it with an absolute path and the profile's Python. Add the engine to `harness/tests/test_engine_hooks.py` (one line in its `HOOKS` table: the engine name and how to read its output field) and run the test.
4. **Review job.** Write `adapters/<engine>/review-job.sh` (and `.ps1` on Windows) that sets `AGENT_CMD` to its headless command without the prompt, using flags from `--help`: run non-interactively, allow file edits inside the vault, nothing broader. Add the engine to the adapter loop in `harness/review-job/macos/selftest.sh` (its name, its binary override variable, and the flags you expect) and run the selftest: it proves the wrapper starts this engine with these flags and hands it the prompt.
5. **Ledger wall.** If it has a stop hook and a pre-tool hook, wire `stop-gate.py` and `lock-guard.py` to them (their docstrings show the shape) and prove a refusal on purpose. If not, the fallback in the template table applies: the ledger is advisory and the agent pastes `ledger.py status` into every report.
6. **Prove it** in a fresh, logged in session, as in phase 4 step 5: a question only the vault can answer. Until that passes, the engine is "installed", not "supported", and the report says so.

## When you are done

Tell the owner, plainly: what was installed and where, which gates passed with their evidence, anything abandoned and why, and the one or two things they should do this week (sign pages, read the first digest). Do not report done while the ledger says otherwise. Before you report at all, hunt for what is left: rerun the checks, and fix every known issue or name it in the report with why it is open. Do not steer the owner toward the next step while gaps may remain, and never narrow the scope yourself: only the owner does that, in words.
