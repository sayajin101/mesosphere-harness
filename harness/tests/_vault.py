"""Where the vault-shaped tests run.

Inside a real vault, the repo root IS the vault. In the public harness repo the
root is not a vault, so a throwaway one is assembled from vault-template/ plus
harness/, which also proves the template itself passes the gates.
"""
import atexit, pathlib, shutil, tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]


def vault_root():
    if (REPO / "SOUL.md").is_file():
        return REPO
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vault-"))
    atexit.register(shutil.rmtree, tmp, True)
    shutil.copytree(REPO / "vault-template", tmp, dirs_exist_ok=True)
    shutil.copytree(REPO / "harness", tmp / "harness", ignore=shutil.ignore_patterns("__pycache__"))
    return tmp
