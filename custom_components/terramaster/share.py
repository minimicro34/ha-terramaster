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


def share_page_url(base_url: str, entry_id: str, share_name: str | None = None) -> str:
    """Build an absolute URL for the shared-folder connection page."""
    parameters = {"entry_id": entry_id}
    if share_name is not None:
        parameters["share"] = share_name
    query = urlencode(parameters)
    return f"{base_url.rstrip('/')}{SHARE_VIEW_PATH}?{query}"


class TerraMasterShareView(HomeAssistantView):
    """Show safe links for the protocols available on shared folders."""

    url = SHARE_VIEW_PATH
    name = "api:terramaster:share"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Render the connection page for one or all shared folders."""
        entry_id = request.query.get("entry_id")
        share_name = request.query.get("share")
        entry = (
            self._hass.config_entries.async_get_entry(entry_id)
            if entry_id is not None
            else None
        )
        if entry is None or entry.domain != DOMAIN:
            raise web.HTTPNotFound

        data = getattr(entry.runtime_data, "data", None)
        shares = tuple(getattr(data, "shares", ()))
        if share_name is not None:
            shares = tuple(share for share in shares if share.name == share_name)
        if not shares:
            raise web.HTTPNotFound

        is_french = request.headers.get("Accept-Language", "").lower().startswith("fr")
        language = "fr" if is_french else "en"
        prompt = (
            "Sélectionnez un dossier et un protocole de connexion :"
            if is_french
            else "Select a shared folder and a connection protocol:"
        )
        unavailable = (
            "Aucun protocole de connexion actif n'a été détecté."
            if is_french
            else "No active connection protocol was detected."
        )
        labels = {"smb": "SMB / CIFS", "nfs": "NFS", "afp": "AFP"}
        sections: list[str] = []
        host = str(entry.data[CONF_HOST])
        for share in shares:
            urls = share_connection_urls(host, share)
            links = "\n".join(
                f'<li><a href="{escape(url, quote=True)}">{labels[protocol]}</a></li>'
                for protocol, url in urls.items()
            )
            if not links:
                links = f'<li class="unavailable">{unavailable}</li>'
            sections.append(
                f"<section><h2>{escape(share.name)}</h2>"
                f"<p><code>{escape(share.path)}</code></p><ul>{links}</ul></section>"
            )
        safe_title = (
            escape(shares[0].name)
            if share_name is not None
            else ("Partages TerraMaster" if is_french else "TerraMaster shares")
        )
        page_sections = "\n".join(sections)
        body = f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: sans-serif; }}
    body {{ margin: 2rem auto; max-width: 36rem; padding: 0 1rem; }}
    section {{ border-top: 1px solid #8886; margin-top: 1.5rem; }}
    li {{ margin: 1rem 0; }}
    a {{ font-size: 1.2rem; }}
    .unavailable {{ opacity: .7; }}
  </style>
</head>
<body>
  <h1>{safe_title}</h1>
  <p>{prompt}</p>
  {page_sections}
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
