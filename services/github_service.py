# services/github_service.py
"""Pure GitHub URL/repo helpers used by ingestion (pages/dashboard.py).
No Streamlit imports."""
import urllib.error
import urllib.request


def parse_github_url(repo_url: str):
    url = (repo_url or "").strip()
    if not url:
        return None
    if url.endswith(".git"):
        url = url[:-4]

    if "git@github.com:" in url:
        path = url.split("git@github.com:")[-1]
    elif "github.com/" in url:
        path = url.split("github.com/")[-1]
    else:
        path = url

    parts = path.strip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None


def check_repo_private(repo_url: str) -> bool:
    repo_path = parse_github_url(repo_url)
    if not repo_path:
        return False

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo_path}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        import json as _json

        with urllib.request.urlopen(req) as response:
            return bool(_json.loads(response.read().decode()).get("private", False))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            if e.headers.get("X-RateLimit-Remaining") == "0":
                return False
            try:
                if "rate limit" in e.read().decode("utf-8", errors="ignore").lower():
                    return False
            except Exception:
                pass
            return True
        if e.code in (401, 404):
            return True
        return False
    except Exception:
        return False


def fetch_branch_zip_bytes(repo_path: str, branch: str) -> bytes:
    """Download a branch/tag archive ZIP for `owner/repo`, falling back from
    main -> master. Raises the underlying urllib error if both fail."""

    def _fetch(ref):
        req = urllib.request.Request(
            f"https://github.com/{repo_path}/archive/refs/heads/{ref}.zip",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req) as response:
            return response.read()

    try:
        return _fetch(branch)
    except Exception:
        if branch == "main":
            return _fetch("master")
        raise
