"""Secure connection page for TerraMaster shared folders."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import cast
from urllib.parse import quote, urlencode

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import (
    TerraMasterData,
    TerraMasterRaid,
    TerraMasterShare,
    TerraMasterVolume,
)

SHARE_VIEW_PATH = "/api/terramaster/share"


@dataclass(frozen=True, slots=True)
class TerraMasterShareStorage:
    """Storage objects backing a shared folder."""

    volume: TerraMasterVolume | None
    raid: TerraMasterRaid | None


def resolve_share_storage(
    data: TerraMasterData, share: TerraMasterShare
) -> TerraMasterShareStorage:
    """Resolve a share to its longest matching mount point and RAID array."""
    matching_volumes = tuple(
        volume
        for volume in data.volumes
        if share.path == volume.mountpoint.rstrip("/")
        or share.path.startswith(f"{volume.mountpoint.rstrip('/')}/")
    )
    volume = (
        max(matching_volumes, key=lambda item: len(item.mountpoint))
        if matching_volumes
        else None
    )

    storage_names = {share.device.rsplit("/", 1)[-1]}
    if volume is not None:
        storage_names.add(volume.device.rsplit("/", 1)[-1])
        storage_names.update(part for part in volume.mountpoint.split("/") if part)
    raid = next((item for item in data.raids if item.name in storage_names), None)
    return TerraMasterShareStorage(volume=volume, raid=raid)


def _format_bytes(value: int) -> str:
    """Format a byte count for the connection page."""
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(amount) < 1000 or unit == "PB":
            precision = 0 if unit == "B" else 2
            return f"{amount:.{precision}f} {unit}"
        amount /= 1000
    return f"{amount:.2f} PB"


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

        data = cast(TerraMasterData | None, getattr(entry.runtime_data, "data", None))
        if data is None:
            raise web.HTTPNotFound
        shares = data.shares
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
        detail_labels = (
            {
                "volume": "Volume",
                "raid": "RAID",
                "filesystem": "Système de fichiers",
                "capacity": "Capacité",
                "used": "Utilisé",
                "available": "Disponible",
            }
            if is_french
            else {
                "volume": "Volume",
                "raid": "RAID",
                "filesystem": "Filesystem",
                "capacity": "Capacity",
                "used": "Used",
                "available": "Available",
            }
        )
        open_label = "Ouvrir en" if is_french else "Open with"
        sections: list[str] = []
        host = str(entry.data[CONF_HOST])
        for share in shares:
            urls = share_connection_urls(host, share)
            links = "\n".join(
                f'<a class="button" href="{escape(url, quote=True)}">'
                f"{open_label} {labels[protocol]}</a>"
                for protocol, url in urls.items()
            )
            if not links:
                links = f'<p class="unavailable">{unavailable}</p>'

            storage = resolve_share_storage(data, share)
            details: list[tuple[str, str]] = []
            if storage.volume is not None:
                details.extend(
                    (
                        (detail_labels["volume"], storage.volume.name),
                        (detail_labels["filesystem"], storage.volume.filesystem),
                        (
                            detail_labels["capacity"],
                            _format_bytes(storage.volume.size),
                        ),
                        (detail_labels["used"], _format_bytes(storage.volume.used)),
                        (
                            detail_labels["available"],
                            _format_bytes(storage.volume.available),
                        ),
                    )
                )
            if storage.raid is not None:
                raid_value = storage.raid.name
                if storage.raid.level:
                    raid_value = f"{raid_value} · {storage.raid.level.upper()}"
                details.insert(1, (detail_labels["raid"], raid_value))
            detail_rows = "".join(
                f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
                for label, value in details
            )
            detail_list = f"<dl>{detail_rows}</dl>" if detail_rows else ""
            sections.append(
                f"<section><h2>{escape(share.name)}</h2>"
                f'<p class="path"><code>{escape(share.path)}</code></p>'
                f'{detail_list}<div class="actions">{links}</div></section>'
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
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 2rem auto; max-width: 42rem; padding: 0 1rem; }}
    section {{ border: 1px solid #8885; border-radius: 1rem; margin-top: 1rem;
      padding: 1rem; }}
    h2 {{ margin-top: 0; }}
    .path {{ opacity: .75; overflow-wrap: anywhere; }}
    dl div {{ display: flex; justify-content: space-between; gap: 1rem;
      padding: .35rem 0; }}
    dt {{ opacity: .7; }}
    dd {{ margin: 0; text-align: right; }}
    .actions {{ display: grid; gap: .7rem; margin-top: 1rem; }}
    .button {{ background: #03a9f4; border-radius: .65rem; color: #fff;
      display: block; font-size: 1rem; font-weight: 600; padding: .8rem 1rem;
      text-align: center; text-decoration: none; }}
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
