"""Secure connection page for TerraMaster shared folders."""

from __future__ import annotations

from html import escape
from urllib.parse import quote, urlencode

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import TerraMasterShare

SHARE_VIEW_PATH = "/api/terramaster/share"


def share_connection_urls(host: str, share: TerraMasterShare) -> dict[str, str]:
    """Return connection URLs for the protocols available on a share."""
    url_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    encoded_name = quote(share.name, safe="")
    urls: dict[str, str] = {}
    if "smb" in share.protocols:
        urls["smb"] = f"smb://{url_host}/{encoded_name}"
    if "nfs" in share.protocols:
        urls["nfs"] = f"nfs://{url_host}{quote(share.path, safe='/')}"
    if "afp" in share.protocols:
        urls["afp"] = f"afp://{url_host}/{encoded_name}"
    return urls


def share_page_url(base_url: str, entry_id: str, share_name: str) -> str:
    """Build an absolute, frontend-clickable URL for a shared folder."""
    query = urlencode({"entry_id": entry_id, "share": share_name})
    return f"{base_url.rstrip('/')}{SHARE_VIEW_PATH}?{query}"


class TerraMasterShareView(HomeAssistantView):
    """Show safe links for the protocols available on a shared folder."""

    url = SHARE_VIEW_PATH
    name = "api:terramaster:share"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Render the connection page for a shared folder."""
        entry_id = request.query.get("entry_id")
        share_name = request.query.get("share")
        entry = (
            self._hass.config_entries.async_get_entry(entry_id)
            if entry_id is not None
            else None
        )
        if entry is None or entry.domain != DOMAIN or share_name is None:
            raise web.HTTPNotFound

        data = getattr(entry.runtime_data, "data", None)
        share = next(
            (item for item in getattr(data, "shares", ()) if item.name == share_name),
            None,
        )
        if share is None:
            raise web.HTTPNotFound

        urls = share_connection_urls(str(entry.data[CONF_HOST]), share)
        if not urls:
            raise web.HTTPNotFound

        labels = {"smb": "SMB / CIFS", "nfs": "NFS", "afp": "AFP"}
        links = "\n".join(
            f'<li><a href="{escape(url, quote=True)}">{labels[protocol]}</a></li>'
            for protocol, url in urls.items()
        )
        is_french = request.headers.get("Accept-Language", "").lower().startswith("fr")
        language = "fr" if is_french else "en"
        prompt = (
            "Ouvrir ce dossier partagé TerraMaster avec :"
            if is_french
            else "Open this TerraMaster shared folder with:"
        )
        safe_name = escape(share.name)
        body = f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TerraMaster – {safe_name}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: sans-serif; }}
    body {{ margin: 2rem auto; max-width: 36rem; padding: 0 1rem; }}
    li {{ margin: 1rem 0; }}
    a {{ font-size: 1.2rem; }}
  </style>
</head>
<body>
  <h1>{safe_name}</h1>
  <p>{prompt}</p>
  <ul>{links}</ul>
</body>
</html>"""
        return web.Response(
            text=body,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; "
                    "base-uri 'none'; frame-ancestors 'none'"
                ),
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )
