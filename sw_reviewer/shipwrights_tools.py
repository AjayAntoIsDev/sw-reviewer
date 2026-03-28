"""Shipwrights API tools for the Pydantic AI agent."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

SW_DASH_BASE_URL = 'https://review.hackclub.com'


def _get_auth() -> tuple[dict[str, str], dict[str, str]]:
    """Load headers and cookies from environment variables."""
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}

    raw_headers = os.getenv('SHIPWRIGHTS_HEADERS', '')
    if raw_headers:
        try:
            headers = json.loads(raw_headers)
        except json.JSONDecodeError:
            pass

    raw_cookies = os.getenv('SHIPWRIGHTS_COOKIES', '')
    if raw_cookies:
        try:
            cookies = json.loads(raw_cookies)
        except json.JSONDecodeError:
            pass

    return headers, cookies


def _request(path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    headers, cookies = _get_auth()
    url = f'{SW_DASH_BASE_URL.rstrip("/")}{path}'

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.request('GET', url, params=query, headers=headers, cookies=cookies)

        try:
            body = response.json()
        except Exception:
            body = response.text

        return {
            'ok': 200 <= response.status_code < 300,
            'status': response.status_code,
            'body': body,
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def _to_ft_link(ft_id: Any) -> str | None:
    if ft_id is None:
        return None
    value = str(ft_id).strip()
    if not value:
        return None
    return f'https://flavortown.hackclub.com/projects/{value}'


def _pick_ship_cert_fields(payload: dict[str, Any]) -> dict[str, Any]:
    ft_id = payload.get('ftId') or payload.get('ftProjectId')
    return {
        'ftLink': _to_ft_link(ft_id),
        'project': payload.get('project'),
        'ai_summary_type': payload.get('type'),
        'desc': payload.get('desc'),
        'devTime': payload.get('devTime'),
        'submitter': payload.get('submitter'),
        'links': payload.get('links'),
        'notes': payload.get('notes') or [],
        'history': payload.get('history') or [],
    }


async def shipwrights_get_ship_cert_details(ship_cert_id: int) -> str:
    """Get details for a single ship certification by ID.

    Returns ftLink, project, ai_summary_type, desc, devTime, submitter, links, notes, and history.
    """
    result = _request(f'/api/admin/ship_certifications/{ship_cert_id}')

    if not result.get('ok'):
        return json.dumps(result)

    body = result.get('body')
    if not isinstance(body, dict):
        return json.dumps({'ok': False, 'error': 'Unexpected response body', 'raw': body})

    return json.dumps({'ok': True, 'data': _pick_ship_cert_fields(body)})


async def shipwrights_get_latest_submitted_projects(
    limit: int = 10,
    status: str = 'pending',
    include_details: bool = False,
) -> str:
    """Get the latest submitted ship certifications.

    limit: number of results (1-50, default 10).
    status: filter by status (default 'pending').
    include_details: if True, fetches full details (desc, links, notes, history) for each project.
    """
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    query: dict[str, Any] = {'sortBy': 'newest'}
    if status:
        query['status'] = status

    result = _request('/api/admin/ship_certifications', query=query)

    if not result.get('ok'):
        return json.dumps(result)

    body = result.get('body')
    certs = body.get('certifications', []) if isinstance(body, dict) else []
    certs = certs[:limit]


    if not include_details:
        simplified = []
        for cert in certs:
            ft_id = cert.get('ftProjectId')
            simplified.append({
                "ship_cert_id": cert.get("id"),
                'ftLink': _to_ft_link(ft_id),
                'project': cert.get('project'),
                'ai_summary_type': cert.get('type'),
                'devTime': cert.get('devTime'),
                'submitter': cert.get('submitter'),
                'status': cert.get('verdict'),
                'createdAt': cert.get('createdAt'),
            })
        return json.dumps({
            'ok': True,
            'count': len(simplified),
            'items': simplified,
            'note': 'Set include_details=true to fetch desc/links/notes/history per project.',
        })

    detailed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for cert in certs:
        cert_id = cert.get('id')
        if cert_id is None:
            continue

        item_result = _request(f'/api/admin/ship_certifications/{cert_id}')

        if not item_result.get('ok'):
            errors.append({
                'shipCertId': cert_id,
                'status': item_result.get('status'),
                'error': item_result.get('error') or 'request_failed',
            })
            continue

        item_body = item_result.get('body')
        if isinstance(item_body, dict):
            detailed.append(_pick_ship_cert_fields(item_body))

    return json.dumps({'ok': True, 'count': len(detailed), 'items': detailed, 'errors': errors})
