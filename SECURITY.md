# Security

Mesosphere's guards exist to keep credentials out of mining extracts and archives (the scrubber) and to stop an agent passing off unfinished work as done (the ledger: `status`, `close` and the stop gate, which re-run every ticked check). The lock guard in front of the ledger folder is defence in depth, a set of command patterns rather than a sandbox, as the README's "What it does not stop" says.

## Reporting

Do not open a public issue. Open a private security advisory on this repository: the Security tab, then "Report a vulnerability". If that button is missing, open an issue that says only that you have a security report and asks for a private channel, with no details. Say which guard was bypassed, the exact input or steps, and what you expected to happen.

## What counts

- A credential shaped string that survives the scrubber into a mining extract or a closed ledger's archive.
- A way for an honest agent, one not trying to cheat, to end a turn or close a ledger as met while a ticked gate's real check fails: a bug in the re-run, the lock, the lookup or the stop gate.
- A stop gate that fails open: allows a turn it could not judge.
- Anything that sends vault content to a recipient the contract forbids.

Out of scope, because the README says so: an agent that sets out to forge a pass with its shell (rewriting a check and the lock, editing the harness or its tests, poisoning the environment or PATH, deleting the ledger folder, unwiring the hooks), and the deliberate exits the README names. A command that slips past the lock guard's patterns is not a security bug on its own; hardening the patterns is welcome as a normal issue.

Please do not include real credentials in a report; a made up value with the same shape is enough.
