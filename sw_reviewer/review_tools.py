"""Purpose-built review tools for the Shipwright review pipeline.

These replace the generic browser toolkit. Each tool does one specific thing
the review pipeline needs, with no room for the agent to go off-script.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import os

import httpx

logger = logging.getLogger(__name__)

_GITHUB_API = 'https://api.github.com'
_TIMEOUT = 20.0


def _github_headers() -> dict[str, str]:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'sw-reviewer'}
    token = os.getenv('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def _ok(data: Any) -> str:
    return json.dumps({'ok': True, **data} if isinstance(data, dict) else {'ok': True, 'data': data})


def _err(reason: str) -> str:
    return json.dumps({'ok': False, 'error': reason})


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL."""
    # Handle both https://github.com/owner/repo and github.com/owner/repo
    m = re.match(r'(?:https?://)?github\.com/([^/]+)/([^/\s#?]+)', url.strip())
    if not m:
        return None
    return m.group(1), m.group(2).removesuffix('.git')


async def review_get_github_repo_info(repo_url: str) -> str:
    """Check if a GitHub repository exists and is public.

    Returns repo visibility, default branch, language, description, and star/fork counts.
    Use this as the FIRST step when reviewing a project to verify the repo is accessible.
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_github_headers()) as client:
            r = await client.get(f'{_GITHUB_API}/repos/{owner}/{repo}')

        if r.status_code == 404:
            return _err('Repository not found (404) — may not exist or is private')
        if r.status_code != 200:
            return _err(f'GitHub API returned status {r.status_code}')

        data = r.json()
        return _ok({
            'owner': owner,
            'repo': repo,
            'exists': True,
            'private': data.get('private', False),
            'default_branch': data.get('default_branch', 'main'),
            'language': data.get('language'),
            'description': data.get('description'),
            'stars': data.get('stargazers_count', 0),
            'forks': data.get('forks_count', 0),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at'),
            'topics': data.get('topics', []),
        })
    except Exception as e:
        return _err(f'Failed to check repo: {e}')


async def review_get_github_readme(repo_url: str) -> str:
    """Fetch the README content of a GitHub repository.

    Returns the decoded README text. Use this to check README existence,
    detect boilerplate, evaluate substance, and check for AI-generated content.
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={**_github_headers(), 'Accept': 'application/vnd.github.raw+json'}) as client:
            r = await client.get(f'{_GITHUB_API}/repos/{owner}/{repo}/readme')

        if r.status_code == 404:
            return json.dumps({'ok': True, 'exists': False, 'content': None})
        if r.status_code != 200:
            return _err(f'GitHub API returned status {r.status_code}')

        content = r.text
        # Truncate very long READMEs
        if len(content) > 30000:
            content = content[:30000] + '\n\n... (truncated, original length: ' + str(len(r.text)) + ' chars)'

        return json.dumps({'ok': True, 'exists': True, 'content': content, 'length': len(r.text)})
    except Exception as e:
        return _err(f'Failed to fetch README: {e}')


async def review_get_github_commits(repo_url: str, per_page: int = 30) -> str:
    """Fetch recent commits from a GitHub repository.

    Returns commit authors, dates, and messages. Use this to check:
    - Pre-Flavortown activity (commits before Dec 25, 2024)
    - Commit authorship (who wrote the code)
    - Suspicious patterns (single huge commit, no commits, etc.)
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed
    if per_page < 1:
        per_page = 1
    if per_page > 100:
        per_page = 100

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_github_headers()) as client:
            r = await client.get(
                f'{_GITHUB_API}/repos/{owner}/{repo}/commits',
                params={'per_page': per_page},
            )

        if r.status_code != 200:
            return _err(f'GitHub API returned status {r.status_code}')

        commits = []
        for c in r.json():
            commit_data = c.get('commit', {})
            author_info = commit_data.get('author', {})
            committer_info = commit_data.get('committer', {})
            commits.append({
                'sha': c.get('sha', '')[:7],
                'message': commit_data.get('message', '')[:200],
                'author_name': author_info.get('name'),
                'author_email': author_info.get('email'),
                'author_date': author_info.get('date'),
                'committer_name': committer_info.get('name'),
                'committer_date': committer_info.get('date'),
                'github_author': (c.get('author') or {}).get('login'),
            })

        return _ok({'total_fetched': len(commits), 'commits': commits})
    except Exception as e:
        return _err(f'Failed to fetch commits: {e}')


async def review_get_github_languages(repo_url: str) -> str:
    """Get the programming languages used in a GitHub repository.

    Returns a dict of language -> bytes. Use this to detect the actual
    project type (web, desktop, mobile, etc.) independent of what the
    submitter claimed.
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_github_headers()) as client:
            r = await client.get(f'{_GITHUB_API}/repos/{owner}/{repo}/languages')

        if r.status_code != 200:
            return _err(f'GitHub API returned status {r.status_code}')

        return _ok({'languages': r.json()})
    except Exception as e:
        return _err(f'Failed to fetch languages: {e}')


async def review_get_github_repo_tree(repo_url: str) -> str:
    """Get the file/directory tree of a GitHub repository (top-level + key subdirs).

    Returns file names at the repo root. Use this to detect project type by
    looking for marker files (package.json, Cargo.toml, setup.py, etc.) and
    to check if specific files exist (like .env files committed).
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_github_headers()) as client:
            r = await client.get(
                f'{_GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD',
                params={'recursive': '1'},
            )

        if r.status_code != 200:
            return _err(f'GitHub API returned status {r.status_code}')

        data = r.json()
        tree = data.get('tree', [])
        # Return file paths only, truncate if huge repo
        files = [item['path'] for item in tree if item.get('type') in ('blob', 'tree')]
        truncated = False
        if len(files) > 500:
            files = files[:500]
            truncated = True

        return _ok({'file_count': len(tree), 'files': files, 'truncated': truncated})
    except Exception as e:
        return _err(f'Failed to fetch repo tree: {e}')


async def review_get_github_file_content(repo_url: str, file_path: str) -> str:
    """Fetch the content of a specific file from a GitHub repository.

    Use this to inspect source files for hardcoded API keys, check specific
    config files, or verify code claims. Returns raw file content.
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={**_github_headers(), 'Accept': 'application/vnd.github.raw+json'}) as client:
            r = await client.get(f'{_GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}')

        if r.status_code == 404:
            return _err(f'File not found: {file_path}')
        if r.status_code != 200:
            return _err(f'GitHub API returned status {r.status_code}')

        content = r.text
        if len(content) > 50000:
            content = content[:50000] + '\n\n... (truncated)'

        return json.dumps({'ok': True, 'path': file_path, 'content': content, 'length': len(r.text)})
    except Exception as e:
        return _err(f'Failed to fetch file: {e}')


async def review_check_url(url: str) -> str:
    """Check if a URL is reachable and what it returns.

    Makes an HTTP GET request and reports the status code, final URL (after
    redirects), and content type. Use this to verify demo URLs are live.
    Does NOT return page content — use review_fetch_page_text for that.
    """
    if not url or not url.startswith(('http://', 'https://')):
        return _err(f'Invalid URL: {url}')

    # Classify the URL for flagging
    flags = []
    lower = url.lower()
    if 'drive.google.com' in lower:
        flags.append('google_drive')
    if 'colab.research.google.com' in lower:
        flags.append('colab')
    if 'huggingface.co' in lower:
        flags.append('huggingface')
    if '.onrender.com' in lower:
        flags.append('render')
    if '.up.railway.app' in lower:
        flags.append('railway')
    if 'ngrok' in lower:
        flags.append('ngrok')
    if 'localhost' in lower or '127.0.0.1' in lower:
        flags.append('localhost')

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers={'User-Agent': 'sw-reviewer'}) as client:
            r = await client.get(url)

        return _ok({
            'url': url,
            'final_url': str(r.url),
            'status_code': r.status_code,
            'reachable': 200 <= r.status_code < 400,
            'content_type': r.headers.get('content-type', ''),
            'flags': flags if flags else None,
        })
    except Exception as e:
        return json.dumps({
            'ok': True,
            'url': url,
            'reachable': False,
            'error': str(e),
            'flags': flags if flags else None,
        })


async def review_fetch_page_text(url: str) -> str:
    """Fetch a web page and extract its visible text content.

    Returns the text content of the page (HTML tags stripped). Use this to
    read demo pages, check for AI-generated content on websites, or verify
    that a deployed app shows real content.
    Limited to first 20000 characters.
    """
    if not url or not url.startswith(('http://', 'https://')):
        return _err(f'Invalid URL: {url}')

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers={'User-Agent': 'sw-reviewer'}) as client:
            r = await client.get(url)

        if r.status_code >= 400:
            return _err(f'HTTP {r.status_code} fetching {url}')

        content_type = r.headers.get('content-type', '')
        if 'text/html' in content_type:
            # Basic HTML to text: strip tags
            import re as _re
            text = _re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=_re.S | _re.I)
            text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.S | _re.I)
            text = _re.sub(r'<[^>]+>', ' ', text)
            text = _re.sub(r'\s+', ' ', text).strip()
        else:
            text = r.text

        if len(text) > 20000:
            text = text[:20000] + '\n\n... (truncated)'

        return json.dumps({'ok': True, 'url': url, 'text': text, 'content_type': content_type})
    except Exception as e:
        return _err(f'Failed to fetch page: {e}')


async def review_fetch_flavortown_project(ft_url: str) -> str:
    """Fetch a Flavortown project page and extract key settings.

    Checks for AI disclosure checkbox status, "This is an update" flag,
    and project description. Pass the ftLink URL from the ship cert data.
    Returns the page text content for the agent to analyze.
    """
    if not ft_url or 'flavortown.hackclub.com' not in ft_url:
        return _err(f'Not a Flavortown URL: {ft_url}')

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers={'User-Agent': 'sw-reviewer'}) as client:
            r = await client.get(ft_url)

        if r.status_code >= 400:
            return _err(f'HTTP {r.status_code} fetching Flavortown project')

        # Extract text content
        import re as _re
        text = _re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=_re.S | _re.I)
        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.S | _re.I)
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = _re.sub(r'\s+', ' ', text).strip()

        if len(text) > 20000:
            text = text[:20000] + '\n\n... (truncated)'

        return json.dumps({'ok': True, 'url': ft_url, 'text': text})
    except Exception as e:
        return _err(f'Failed to fetch Flavortown project: {e}')


async def review_search_github_code(repo_url: str, query: str) -> str:
    """Search for code patterns in a GitHub repository.

    Use this to scan for hardcoded API keys, secrets, or specific code patterns.
    The query searches file contents. Limited to public repos.

    Note: GitHub code search API has rate limits. Use review_get_github_file_content
    for targeted file inspection instead when you know the file path.
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return _err(f'Could not parse GitHub URL: {repo_url}')
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_github_headers()) as client:
            r = await client.get(
                f'{_GITHUB_API}/search/code',
                params={'q': f'{query} repo:{owner}/{repo}'},
            )

        if r.status_code in (401, 403):
            return _err(
                f'GitHub search API returned {r.status_code} (auth required or rate limited). '
                'Use review_get_github_repo_tree to list files, then review_get_github_file_content to inspect suspicious files instead.'
            )
        if r.status_code != 200:
            return _err(f'GitHub search API returned status {r.status_code}')

        data = r.json()
        items = []
        for item in data.get('items', [])[:20]:
            items.append({
                'path': item.get('path'),
                'name': item.get('name'),
                'url': item.get('html_url'),
            })

        return _ok({'total_count': data.get('total_count', 0), 'matches': items})
    except Exception as e:
        return _err(f'Code search failed: {e}')
