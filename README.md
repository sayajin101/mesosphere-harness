![Mesosphere: hallucinations burn up before they hit main.](.github/banner.jpg)

# Mesosphere

**Hallucinations burn up before they hit main.**

AI coding agents are fast, eager and overconfident. They skip the hard part, announce "done" over half finished work, and tidy things nobody asked them to touch. Mesosphere sits between the agent and your work. Before the work starts, it writes down what was actually asked. While the work runs, plain scripts, not the agent's word, decide whether each part is finished. And on Claude Code, the agent is not allowed to end its turn until they say so; on other agents the ledger still judges, and the agent is told to ask it.

It also does the larger job it was built for: a **persona vault** that carries how you think and decide into every session, on any AI model, and an **eval** that tests whether a new model really decides like you before you trust it.

Why the name: the mesosphere is the middle layer of Earth's atmosphere, where most meteors burn up before they reach the ground. Here the AI model is the weather, changing from one release to the next. Mesosphere is the layer that stays. It was extracted from a personal harness its author runs every day, with everything personal taken out; the machinery is what is left.

## Contents

- [What it is, in one minute](#what-it-is-in-one-minute)
- [Which path is yours](#which-path-is-yours)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Path A: ledger only](#path-a-ledger-only)
- [Path B: full persona harness](#path-b-full-persona-harness)
- [Path C: eval only](#path-c-eval-only)
- [Using the ledger day to day](#using-the-ledger-day-to-day)
- [Engine support](#engine-support)
- [Platforms](#platforms)
- [Privacy and your data](#privacy-and-your-data)
- [What it costs](#what-it-costs)
- [What it does not stop](#what-it-does-not-stop)
- [Troubleshooting](#troubleshooting)
- [Getting help](#getting-help)
- [Contributing](#contributing)
- [Updating and removing](#updating-and-removing)
- [What is in the repo](#what-is-in-the-repo)
- [Security](#security)
- [License](#license)

## What it is, in one minute

Three pieces, usable alone or together.

**The task ledger** (`harness/ledger.py`). Before the agent starts, your request is split into its separate asks. Each ask is mapped to a **gate**: an outcome plus the command that proves it, such as "the export button exists" checked by a test. A gate that claims to prove new work must **fail** when it is written, so it can never be a check that was always going to pass.

Then the gate list is frozen and **locked** with a hash, so any later edit to it shows. From there a plain Python script, with no AI in it, decides what passed. When the agent tries to end its turn, a stop hook asks the ledger, not the agent, whether it may. The ledger re-runs every ticked check before it says yes. A tick is only a claim; the re-run is what counts.

**The persona vault** (`vault-template/`). Plain markdown that captures how you think, decide and write: values, judgement rules, taste, voice, people, and past decisions with their reasons. It is loaded into every agent session, on whatever agent you use, so the agent works the way you would. You sign the core pages; agents may only draft. A linter (`harness/verify.py`) checks the vault's structure and sources and, given a git ref, refuses changes only you may make (to `SOUL.md`, `IDENTITY.md` or a page's signed status); a weekly job turns what happened that week into a short review for you to approve.

**The eval** (`eval-template/`). An exam built from your real past decisions, kept in its own private repo and never shown to the vault. `blind.py` strips the answers before a model sees the questions; `score.py` totals a separate judge's verdicts and refuses a run that skipped a question. You adopt a new model by passing your own exam, not a public benchmark.

What the ledger catches, in two examples you can reproduce with `harness/LEDGER.md` open beside you:

- The agent ticks every box, then quietly weakens the wording of one gate. Its turn is still refused: every box is green, but the lock no longer matches, so narrowing the job after the fact is caught even when everything looks done.
- The agent ticks a box by hand without doing the work. The stop hook re-runs that gate's check, sees it fail, and keeps the turn open.

## Which path is yours

| You want | Take | You end up with |
|---|---|---|
| Your agent to stop calling unfinished work done, in a repo you already have | **Path A: ledger only** | The ledger and its hooks in that repo, proven to refuse |
| An agent that carries your judgement into every session, and learns from each week | **Path B: full persona harness** | A private vault, a private eval, the ledger, and a weekly review job |
| To test whether a model decides like you, with a persona vault you already have | **Path C: eval only** | A private eval repo built from your real decisions, and a first score |

You do not have to choose up front: the bootstrap asks you.

## Requirements

- **git.** On Windows, Git for Windows, which also brings Git Bash: the ledger's checks run in it.
- **Python 3.9 or newer.** Standard library only, nothing to install with pip. On Windows, beware the Microsoft Store's `python` stub, which opens the Store instead of running.
- **An AI coding agent.** Claude Code gets the full enforcement; see [Engine support](#engine-support) for the rest.
- **For paths B and C:** a GitHub account (or another host) for the private repos. On path B, setup also uses its command line tool (`gh` for GitHub) to check those repos really are private; on path C, make the eval repo private yourself.
- **For the weekly job:** your agent's own command line tool, logged in.
- **For the job's self tests:** zsh on macOS, Windows PowerShell 5.1 on Windows, both built in.

**git and Python are needed before the quick start**, because you use them to clone and test. If you do not have them:

- **macOS:** `xcode-select --install` gives both (its Python 3.9 is enough).
- **Windows:** `winget install --id Python.Python.3.13 -e` and `winget install --id Git.Git -e`, then open a new terminal. Without winget, install from python.org and git-scm.com, and tick "Add python.exe to PATH" in the Python installer.
- **Linux:** `sudo apt install python3 git` (Debian, Ubuntu), `sudo dnf install python3 git` (Fedora) or `sudo pacman -S python git` (Arch).

Everything else can wait: the bootstrap checks your machine first, records the exact path of every tool it finds, and shows you how to install anything else that is missing, asking before it runs anything.

## Quick start

1. Clone the repo:

   ```bash
   git clone https://github.com/sayajin101/mesosphere-harness.git
   ```

2. Go into it and prove the machinery works on your machine:

   ```bash
   cd mesosphere-harness
   ```

   ```bash
   python3 harness/tests/run_all.py
   ```

   On Windows, use `python` or the full path to `python.exe` instead of `python3`. The suite takes about three minutes and must end `ALL <n> PASSED`. If it does not, stop there and see [Getting help](#getting-help).

3. Open your AI coding agent in that folder and say:

   > read BOOTSTRAP.md and follow it. i am <your name>.

4. Answer its questions. It starts by checking your machine, asks before installing anything, and shows you every command that changes your system.

`BOOTSTRAP.md` is written to the agent, not to you, but nothing in it is hidden: read it first if you want to know exactly what it will do. It installs the shipped code as it is rather than rewriting it, proves every enforcement hook actually refuses before calling anything done, keeps your vault and eval private, and never signs anything on your behalf.

## Path A: ledger only

For a repo you already work in. You start the agent in this clone, as in the quick start, and it asks you for the path to your repo. Then it:

1. copies `harness/ledger.py`, `harness/history.py`, `harness/LEDGER.md`, `harness/ENGINEERING.md` and your agent's hooks into that repo, with the folder layout kept;
2. adds the ledger rule (contract section 9) to the repo's agent instructions file, or to a local file kept out of git if that one is shared with colleagues;
3. wires the stop and write guard hooks into `.claude/settings.local.json` (Claude Code), with absolute paths in quotes;
4. proves the wall: it opens a small ledger with one gate that cannot pass yet, and asks you to start a fresh session that tries to edit the ledger and end its turn. Both must be refused. If either is not, it fixes the wiring and repeats the proof.

On an agent without stop or pre tool hooks, the ledger is advisory: the rule is in the instructions file, the agent pastes `ledger.py status` into every report, and nothing can force it to. The bootstrap tells you plainly when that is your case.

## Path B: full persona harness

The full build. It runs in phases under one setup ledger inside your new vault, with a gate for each phase, so nothing is skipped quietly:

| Phase | What happens |
|---|---|
| 0 · Setup | A private vault repo and a separate private eval repo, each checked for its real visibility, plus the linter |
| 1 · Mine | Your own chat history is copied into a working folder you choose, outside every repo, and scrubbed of credentials there. Mining agents then read it for how you decide. Real decisions are split: half may become vault pages, half go straight into the eval and never touch the vault |
| 2 · Verify | Separate reviewers, on the strongest model, delete any claim without a verbatim quote behind it and hunt for flattery |
| 3 · Interview | A live interview about what your chat history cannot show |
| 4 · Sign and load | You correct and sign `SOUL.md` (your values and how you decide) and `IDENTITY.md` (how you present), choose the contract's options, and the vault is wired to load in the agents you use. Each is called supported only after a fresh session answers a question only the vault can answer |
| 5 · Moons | Company and project knowledge is kept out of the vault ("moons" orbiting it): your own projects keep it in their repos, and an employer's work goes in a local folder on the employer's machine, so it leaves with the job |
| 6 · Eval baseline | The current model sits the eval blind, a separate judge scores it, and that score becomes the bar every later model must meet |
| 7 · Keep it alive | A weekly review job that commits and pushes a digest to your private vault, a reminder when one is waiting, and, if you choose it, a regular re-mining of your new chats on a schedule you set |

What lands where: the raw history and its scrubbed copy stay in the working folder outside every repo. Into the vault go only the scrubbed distillates, short claims with their supporting quotes, as drafts marked `mined-unverified`. Phase 2's reviewers strip what the quotes do not support, and a page only rises above unverified when you confirm it. Quotes behind the eval's questions go into the private eval repo.

It takes more than one sitting, because it waits on you to answer questions and sign pages. Your place is kept: the setup ledger stays open in the vault listing every phase still unmet, and a long mining run saves a checkpoint and gives you a prompt to resume it in a fresh session.

## Path C: eval only

For someone who already has a persona vault, in this shape or any other. The agent creates the eval repo from `eval-template/` as a separate private repo, removes the example scenarios, and harvests real decisions from your history by following the eval's `RUNBOOK.md`. Then it runs the first exam: your current model answers blind, a separate judge scores the answers against what you actually decided, and that score is the bar.

From then on, `RUNBOOK.md` says when to run it again: before switching to a new model (which must meet or beat the bar under the same protocol), after a big batch of vault changes, and every few months. The one rule that matters: a decision that is in your vault can never be an exam question, because a model wearing the vault has already seen the answer.

## Using the ledger day to day

**When a ledger opens.** Only for substantial work: a task with more than one deliverable, or long enough that its start has left the agent's memory by the end. Questions, chat and one line fixes never open one. **Your part:** give the request in your own words, read the gates when the agent shows them, and do the JUDGE gates only you can (a sign off, a read through). The agent drives the rest; you read the result.

Everything goes through `harness/ledger.py`, run from the repo root (`python` on Windows):

```bash
python3 harness/ledger.py open --title "<task>" --prompt-file <file>
```

The prompt file holds your actual request, in your words. The agent writes the gates into the new file under `.ledger/`, maps every ask to a gate or dismisses it with a reason, and freezes the list:

```bash
python3 harness/ledger.py declare
```

From then on the file is only changed through `ledger.py`:

| Command | What it does |
|---|---|
| `run` | Runs every check, ticks what passed, records the output as evidence |
| `status` | Re-runs every ticked check and says what is still unmet. Exit 0 means done |
| `evidence <gate> "<proof>"` | Records proof for a gate no command can check (a JUDGE gate), such as your sign off |
| `brief` | Prints what to hand a fresh reviewer, who checks the gates cover every ask |
| `audit subagent "<verdict>"` | Records that reviewer's verdict, which opens with COVERED or GAPS FOUND |
| `abandon <gate> "<reason>"` | Gives a gate up, out loud, with the reason on the record |
| `map <ask> "<gates>"` | Remaps an ask after the freeze |
| `close --archive-to episodic` | Re-runs the checks, then archives a scrubbed record and retires the ledger. `episodic` is the vault's folder for such records; in a project repo, archive to its own docs folder instead |

`harness/LEDGER.md` is the full manual: gate classes, the red first rule, what makes a good gate, the lock, and the refusals. Read section 4 before you write your first gate. The single most useful thing to know: a gate with an `EXPECT` line passes when the output matches, whatever the check exited with, so the `EXPECT` must match only what a full pass prints.

## Engine support

"Engine" here means the AI coding agent you run.

| Engine | Loads the vault every session | Ledger wall | Weekly review job | Status |
|---|---|---|---|---|
| Claude Code | SessionStart hook | Stop and PreToolUse hooks | Yes, macOS and Windows | Proven |
| Codex CLI | Global `AGENTS.md` loader | Advisory | Adapter ships, not yet proven in a live run. On Windows, set `MESOSPHERE_CODEX` to a real executable: the npm `codex.cmd` shim is refused | Vault loading proven (macOS) |
| Cursor | `sessionStart` hook | Advisory | Not supported unattended: its only headless write mode allows arbitrary commands | Vault loading proven (macOS) |
| Antigravity CLI | `GEMINI.md` loader, plus a read rule you add and `--add-dir` | Advisory | Adapter ships, not yet proven in a live run, nor on Windows | Vault loading proven (macOS) |
| Gemini CLI | Adapter ships | Advisory | Adapter ships | Not proven: personal sign-ins are refused (see below) |

Google stopped accepting personal sign-ins for Gemini CLI in 2026; API key and paid Code Assist users may still be able to use it; personal users should use Antigravity.

"Advisory" means the ledger still judges correctly, but nothing forces the agent to ask it; the rule in its instructions file is what makes it ask. Each engine's `harness/adapters/<engine>/CAPABILITIES.md` lists honestly what it can and cannot do, and what has been proven so far.

**Any other engine** (Grok Build, OpenCode, Cline, Aider, Goose and whatever comes next): BOOTSTRAP's "Other engines" section has the recipe. The agent builds the adapter on your machine from the engine's own `--help` and documentation, starting from `harness/adapters/_template/`, and calls it supported only after a fresh session proves it.

## Platforms

- **macOS.** Everything is tested here. The weekly job runs from launchd, and its self tests use the built in zsh.
- **Windows.** Native Windows is supported. The ledger's checks run in Git Bash, which comes with Git for Windows. The weekly job runs from Task Scheduler, and its self tests use the built in Windows PowerShell 5.1. Watch for the Microsoft Store's `python` stub: the bootstrap finds the real interpreter and records its path.
- **Linux.** The ledger, hooks, vault and eval are plain Python and git with nothing platform specific, but no Linux setup has been proven end to end yet. There is no weekly job wrapper: use cron or a systemd timer for the same steps (pull the vault, run `harness/history.py` if mining is set up, run the review prompt headless, commit the digest).
- **WSL.** Treated as Linux. Hooks then run inside WSL, not Windows.

## Privacy and your data

- **Nothing personal ships here.** This repo holds only machinery and empty templates. `examples/` shows filled pages for a made up person.
- **Your vault and your eval are private repos.** On path B each is checked for its real visibility, never assumed. Nothing from them is pushed anywhere public, though quotes from your chats do live in them on your git host.
- **Only your own data, only with your yes.** The bootstrap mines only your own chat history and files, and only after you agree in the chat. Re-mining new chats on a schedule is a separate choice, offered in phase 7, which you can turn down or stop at any time.
- **Your AI provider reads it.** Mining means your agent reads your history, so whatever you mine is sent to the model provider your agent uses, under that provider's terms. Mine only what you are content for them to process. The same goes for the vault itself: it is loaded into every session, so each agent you wire it into sends it to that agent's provider.
- **Scrubbed before mining.** History is copied into a working folder you choose (the bootstrap suggests `~/persona-mining`), outside every repo, and scrubbed of credential shapes (keys, tokens, passwords, private keys, card numbers, phone numbers) before any mining agent reads a line. The scrubber is a pattern list, not a guarantee, which is why that folder stays outside every repo. Once setup is done you can delete the extracts in it; if monthly mining is on, keep the folder itself, since its `state.json` is where mining remembers what it has read.
- **Only what you typed.** The agent writes a small extractor for each tool's history that keeps only your own messages, and shows it to you before running it. For the monthly re-mining of Claude Code history, `harness/history.py` also leaves out session summaries, pasted content, harness notices and prompts written by agents.
- **No telemetry.** The ledger, linter, scrubber and eval scripts make no network calls. The network is used by your agent itself, by git, by `gh` when setup checks repo visibility, and by the weekly job when it pulls and runs your agent.
- **The agent never signs for you** and never sends a message to anyone on your behalf during setup.

## What it costs

- **The ledger is free to run:** plain Python, no AI calls. Only the coverage review it asks for uses a model, once per task.
- **Setup costs tokens,** mostly in path B's mining. The bootstrap measures your history first and tells you the size, runs a small pilot, uses cheap models for mechanical work and strong ones only for judgement, and checks your usage between batches.
- **The weekly review job** is bounded by time (about two hours at most), not by tokens. The agent tells you the expected cost of one run before the first, and the monthly mining step has its own character cap, which you set.

## What it does not stop

It is built against the failure that actually happens: an agent drifting into calling partial work done. Against that it holds. The gates are written before the work, every ticked check is re-run before a turn may end, and a forged tick or an edited gate list is caught and named; every recorded audit verdict stays in the log, including any it replaced.

It is not built against an agent set on cheating, and it cannot be. Anything that can run shell commands as the owner can forge a pass: rewrite a check and recompute the lock, edit the harness itself or the tests a check runs, poison the environment or the tools a check calls, delete the ledger folder, or unwire the hooks in `.claude/settings.local.json`. The write guard is a list of patterns, not a sandbox.

A few exits are deliberate and visible rather than hidden. An agent can record `audit human` itself, and the log shows who and when. `--force close` ends a ledger over unmet work; the closed file says FORCED and the stop hook names it for a day. And the stop hook lets a turn end after six blocks in a row with nothing changed, saying so, because a stuck agent must be able to hand over. Whether Claude Code asks you before any of these depends on your permission settings.

What the harness guarantees is that a drifting agent is stopped and a cheating one has to do it on purpose, never that cheating is impossible. `harness/LEDGER.md` section 2 has the detail.

## Troubleshooting

**The wall did not refuse during the proof.** The hook could not start. Check that the interpreter is the absolute path from your machine profile (the `machine.local.json` the bootstrap wrote), that the hook path is absolute and in double quotes, and that the entries are in that repo's `.claude/settings.local.json`. Settings usually load only when a session starts, so test in a fresh session.

**Every tool call and every turn end is refused, even edits to settings.** A hook path with a space in it was left unquoted, so Python exits with code 2, which Claude Code reads as a block. Quote the path, editing the settings file from outside that session if you have to.

**My turn will not end.** The stop hook lists what is unmet: do the work, or `abandon` a gate that is genuinely impossible and say why. While a coverage review is still on its way, record `audit awaiting-subagent` or `audit awaiting-human` and the turn may end. After six blocks in a row with nothing changed, it lets the turn end anyway and says so.

**LOCK BROKEN.** The frozen gate list was edited after `declare`. Put the gate lines back exactly as they were declared. Before any work is done you may instead re-freeze on purpose with `declare --force`, which is logged; once a gate's work is done its check passes, and `declare --force` refuses it. To add gates to a frozen ledger, write them to a file outside `.ledger/` and run `--force declare --gates-file <file>`.

**`declare` refuses a gate.** Read the reason it prints: a provable gate that already passes proves nothing, a check that cannot fail is not a check, an `EXPECT` that is a bare success word matches failing runs too. `harness/LEDGER.md` section 4 covers the gate rules and most refusals; the message itself always says what to change.

**The suite looks hung.** It takes about three minutes. Many agents stop a command after two; give it ten, or run it in the background.

**Another task's ledger is holding my turn.** Every open ledger in `.ledger/` is enforced, whoever opened it. Open yours under its own name with `--session <id>`, and close the other one only when its own work is done.

**Windows: `python` opens the Microsoft Store.** That is the Store stub. Install Python as shown under [Requirements](#requirements), open a new terminal, and use the full path to the real `python.exe` if `python` still finds the stub.

## Getting help

Open an issue on this repository. Say which path you took, your OS and agent, the command you ran and what it printed. Never paste credentials, vault pages or chat history into an issue: a made up value of the same shape is enough. Security problems go to the [Security](#security) route instead.

## Contributing

Ideas, bug reports and improvements are welcome.

- **Ideas and problems:** open an issue. Say what you were trying to do, what you ran and what happened.
- **Changes:** open a pull request. Keep it to one change, add a test that fails without it, and make sure `python3 harness/tests/run_all.py` still ends `ALL <n> PASSED`.
- **Your contribution's license:** by opening a pull request, you agree it can be shipped under this repository's license, and under any license the project uses later.

## Updating and removing

**Updating.** Pull this repo, run `harness/tests/run_all.py`, then bring the changed files over to the copies you installed one at a time, comparing each first. Never copy over files that hold your own choices: `harness/CONTRACT.md` after setup, `harness/verify.py` and `harness/review-job/prompt.md` if you dropped the dash rule or changed the review, and the tests if setup added an engine to them. Merge those by hand. Run the suite again in the vault afterwards.

**Removing the ledger from a repo.**

1. Close or abandon any open ledger.
2. Delete the two hook entries from `.claude/settings.local.json`.
3. Delete the ledger rule from the instructions file, or delete `CLAUDE.local.md` and its line in `.git/info/exclude` if that is where it went.
4. Delete the copied `harness/` files, the `.ledger/` folder and `machine.local.json`, and their lines in `.gitignore`.

**Removing the persona harness.**

1. Remove the vault loader from each agent's global instructions file, and its session start hook from that agent's settings.
2. Remove the weekly job. On macOS, run `launchctl bootout gui/$(id -u)/local.mesosphere-review`, then delete `~/Library/LaunchAgents/local.mesosphere-review.plist`, or launchd loads it again at your next login. On Windows, run `Unregister-ScheduledTask -TaskName mesosphere-review` in PowerShell.
3. Delete the job's state folder (`~/schedules/mesosphere-review` unless you moved it) and the mining working folder (`~/persona-mining` unless you chose another).
4. On Antigravity, remove the vault read rule you added to its settings.
5. The vault and eval are your private repos: keep them or delete them.

## What is in the repo

| Part | What it does |
|---|---|
| `BOOTSTRAP.md` | The setup prompt, written to your agent |
| `harness/ledger.py`, `harness/LEDGER.md` | The task ledger and its manual |
| `harness/adapters/` | One folder per agent: hooks, the review job's command, and an honest `CAPABILITIES.md`. `_template/` is the starting point for any other agent; `mcp-server/` is a design note, not built |
| `harness/CONTRACT.md` | The protocol any model works under: load order, decision rules, write rules, the separation of work knowledge from your vault, the learning loop, the duty to raise contradictions |
| `harness/MATURITY.md` | The autonomy ladder: what the agent may do on its own, earned one rung at a time |
| `harness/ENGINEERING.md` | Rules for building enforcement that actually enforces, each paid for by a real incident |
| `harness/history.py` | The history miner and credential scrubber |
| `harness/session_context.py` | What every agent's session start hook loads, and the review reminder |
| `harness/verify.py` | The vault linter |
| `harness/review-job/` | The weekly review job for macOS and Windows, with self tests |
| `harness/tests/` | The test suite (`run_all.py`) |
| `vault-template/` | The empty persona vault |
| `eval-template/` | The empty eval, with `blind.py`, `score.py` and its runbook |
| `examples/` | Filled pages and a ledger, for a made up person |
| `SECURITY.md`, `CHANGELOG.md`, `LICENSE` | How to report a security problem, what changed, and the license |

## Security

Found a way an honest agent can end a turn over failing work, a credential that survives the scrubber, or anything that sends vault content somewhere it must not go? Report it privately through the repository's Security tab ("Report a vulnerability"). `SECURITY.md` says what counts and how to report.

## License

[PolyForm Shield 1.0.0](LICENSE).

In plain words: you may use, copy and change this software for anything except competing with it, at home or at work, and share it, as long as anyone you share it with also gets the license and the `Required Notice:` line at the top of `LICENSE`. What you may not do is use it to provide a product that competes with it, or with any product its author provides using it: selling it, offering it as a service, or shipping a substitute for it, even for free. This summary is not the license; `LICENSE` is.
