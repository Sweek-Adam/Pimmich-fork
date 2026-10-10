"""
Comparaison de l'installation avec le dépôt d'origine de Pimmich (upstream) et avec le dépôt suivi (origin).
"""
import subprocess
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
UPSTREAM_URL = "https://github.com/gotenash/pimmich.git"
BRANCH = "main"
MAX_COMMITS = 50


def _git(*args, timeout=60):
    result = subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} a échoué")
    return result.stdout.strip()


def _remote_url(name):
    try:
        return _git("remote", "get-url", name)
    except RuntimeError:
        return None


def _new_commits(ref):
    """Commits présents sur `ref` mais pas dans l'installation actuelle."""
    count = int(_git("rev-list", "--count", f"HEAD..{ref}") or 0)
    log = _git("log", f"--max-count={MAX_COMMITS}", "--date=short", "--format=%h%x09%ad%x09%an%x09%s", f"HEAD..{ref}")
    commits = []
    for line in filter(None, log.splitlines()):
        sha, date, author, subject = line.split("\t", 3)
        commits.append({"sha": sha, "date": date, "author": author, "subject": subject})
    return count, commits


def check_upstream():
    """
    Récupère le dépôt d'origine et le dépôt suivi, et retourne les nouveautés de chacun.
    Ne modifie pas le code installé (seulement les références distantes de git).
    """
    origin_url = _remote_url("origin")
    upstream_url = _remote_url("upstream")
    if upstream_url is None:
        if origin_url and origin_url.rstrip("/").removesuffix(".git").lower() == UPSTREAM_URL.removesuffix(".git").lower():
            upstream_name = "origin"  # Installation directe depuis le dépôt d'origine
        else:
            _git("remote", "add", "upstream", UPSTREAM_URL)
            upstream_name = "upstream"
    else:
        upstream_name = "upstream"

    _git("fetch", "--quiet", upstream_name, BRANCH, timeout=120)
    upstream_count, upstream_commits = _new_commits(f"{upstream_name}/{BRANCH}")

    result = {
        "upstream_url": _remote_url(upstream_name),
        "upstream_new_count": upstream_count,
        "upstream_commits": upstream_commits,
        "is_fork": upstream_name == "upstream",
    }
    if upstream_name == "upstream" and origin_url:
        _git("fetch", "--quiet", "origin", BRANCH, timeout=120)
        origin_count, origin_commits = _new_commits(f"origin/{BRANCH}")
        result.update({"origin_url": origin_url, "origin_new_count": origin_count, "origin_commits": origin_commits})
    return result
