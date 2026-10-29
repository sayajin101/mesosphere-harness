# Cursor: the weekly review job is NOT supported unattended on this engine.
# Cursor's only headless mode that can write the digest is `-p --force`, which allows
# any command unless explicitly denied, and the job reads untrusted mined chat text and
# can push. Until Cursor has an edit only headless mode, this file refuses, and the
# wrapper fails loudly instead of running. Every session vault loading on Cursor
# (adapters/cursor/hooks/session-start.py) is unaffected and proven.
print -u2 "REFUSED: Cursor's unattended review job is not supported (its headless write mode allows any command). Use another engine for the review job."
AGENT_CMD=()
