#!/usr/bin/env python3
"""history.scrub redacts every credential and personal number shape a review leaked.

Each shape below got past the scrubber on 2026-10-28. One case per shape, so a
regression names the shape it lost. The near misses at the end must survive, or the
mined text stops reading like the owner. BOOTSTRAP's scrub gate regex had the JSON gap
too, so it is checked here when BOOTSTRAP.md exists.

  python3 harness/tests/test_scrub_shapes.py
    -> "ok: every shape scrubbed", exit 0
"""
import pathlib, re, sys

HARNESS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from history import scrub
from _ledgerkit import check, finish

LEAKS = {  # shape: (text, the secret that must vanish)
    "JSON key with quotes": ('{"password": "hunter2"}', "hunter2"),
    "YAML key with quotes": ("'api_key': 'abc123'", "abc123"),
    "mysql -p attached": ("mysql -u root -pS3cretPw db", "S3cretPw"),
    "--password X": ("run it with --password hunter2 please", "hunter2"),
    "--password=X": ("pgcli --password=hunter2", "hunter2"),
    "my password is X": ("fyi my password is tr0ub4dor", "tr0ub4dor"),
    "URL with an empty user": ("redis://:s3cretpw@cache:6379/0", "s3cretpw"),
    "Authorization: Basic": ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
    "Slack app token": ("xapp" + "-1-A0123456789-1234567890-abcdef", "A0123456789"),
    "Stripe webhook secret": ("whsec" + "_abcdefghijklmnop1234", "abcdefghijklmnop"),
    "Google OAuth token": ("ya29" + ".a0AfH6SMBx-yz_123456789", "a0AfH6SMBx"),
    "PGP private key block": ("-----BEGIN PGP PRIVATE KEY BLOCK-----\nlQOYBF\n"
                              "-----END PGP PRIVATE KEY BLOCK-----", "lQOYBF"),
    "card number (Luhn)": ("card 4111 1111 1111 1111 expires soon", "4111 1111"),
    "13 digit ID number (Luhn)": ("my id is 8001015009087 ok", "8001015009087"),
    "UK mobile": ("ring me on 07700 900123 later", "900123"),
    "short value": ("pin: 4821", "4821"),
    "short env value": ("DB_PASS=abc", "abc"),
}
SURVIVES = [
    "the meeting is on 2026-10-28 at 10:11",
    "order 1234567890123 shipped",           # 13 digits, fails Luhn
    "use mkdir -p build and ssh -p 2222 host",
    "a task-based, risk-free plan",
    "the key point is that it works",
    "the token is not in the archive",
]

for shape, (text, secret) in LEAKS.items():
    out = scrub(text)
    check(f"redacts {shape}", secret not in out and "[REDACTED]" in out, out)
for text in SURVIVES:
    check(f"leaves alone: {text}", scrub(text) == text, scrub(text))

boot = HARNESS.parent / "BOOTSTRAP.md"
if boot.exists():
    line = next((l for l in boot.read_text().split("\n") if "Scrub it there" in l), "")
    pats = [p for p in re.findall(r"`([^`]+)`", line) if "(password" in p]
    ok = bool(pats)
    for p in pats:
        try:
            ok = ok and re.search(p, '{"password": "hunter2"}') is not None
        except re.error:
            ok = False
    check("BOOTSTRAP's scrub gate regex catches a quoted JSON key", ok, pats)

finish("every shape scrubbed")
