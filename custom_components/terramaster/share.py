"""Secure connection page for TerraMaster shared folders."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from html import escape
from typing import cast
from urllib.parse import quote, urlencode

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_SHARE_TOKEN, DOMAIN
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
    data: TerraMasterData,
    share: TerraMasterShare,
) -> TerraMasterShareStorage:
    """Resolve a share to its longest matching mount point and RAID array."""
    matching_volumes = tuple(
        volume
        for volume in data.volumes
        if share.path == volume.mountpoint.rstrip("/")
        or share.path.startswith(
            f"{volume.mountpoint.rstrip('/')}/"
        )
    )

    volume = (
        max(
            matching_volumes,
            key=lambda item: len(item.mountpoint),
        )
        if matching_volumes
        else None
    )

    storage_names = {
        share.device.rsplit("/", 1)[-1],
    }

    if volume is not None:
        storage_names.add(
            volume.device.rsplit("/", 1)[-1],
        )
        storage_names.update(
            part
            for part in volume.mountpoint.split("/")
            if part
        )

    raid = next(
        (
            item
            for item in data.raids
            if item.name in storage_names
        ),
        None,
    )

    return TerraMasterShareStorage(
        volume=volume,
        raid=raid,
    )


def _format_bytes(value: int) -> str:
    """Format a byte count for the connection page."""
    amount = float(value)

    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(amount) < 1000 or unit == "PB":
            precision = 0 if unit == "B" else 2
            return f"{amount:.{precision}f} {unit}"

        amount /= 1000

    return f"{amount:.2f} PB"


def share_connection_urls(
    host: str,
    share: TerraMasterShare,
    username: str | None = None,
) -> dict[str, str]:
    """Return connection URLs for the protocols available on a share."""
    url_host = (
        f"[{host}]"
        if ":" in host and not host.startswith("[")
        else host
    )

    encoded_name = quote(
        share.name,
        safe="",
    )

    encoded_username = (
        quote(username, safe="")
        if username
        else None
    )

    authenticated_host = (
        f"{encoded_username}@{url_host}"
        if encoded_username
        else url_host
    )

    urls: dict[str, str] = {}

    if "smb" in share.protocols:
        urls["smb"] = (
            f"smb://{authenticated_host}/{encoded_name}"
        )

    if "nfs" in share.protocols:
        urls["nfs"] = (
            f"nfs://{url_host}"
            f"{quote(share.path, safe='/')}"
        )

    if "afp" in share.protocols:
        urls["afp"] = (
            f"afp://{authenticated_host}/{encoded_name}"
        )

    return urls


def share_page_url(
    base_url: str,
    entry_id: str,
    token: str,
    share_name: str | None = None,
) -> str:
    """Build an absolute URL for the shared-folder connection page."""
    parameters = {
        "entry_id": entry_id,
        "token": token,
    }

    if share_name is not None:
        parameters["share"] = share_name

    query = urlencode(parameters)

    return (
        f"{base_url.rstrip('/')}"
        f"{SHARE_VIEW_PATH}?{query}"
    )


class TerraMasterShareView(HomeAssistantView):
    """Show safe links for TerraMaster shared folders."""

    url = SHARE_VIEW_PATH
    name = "api:terramaster:share"

    # Direct navigation from an entity does not include a Home Assistant
    # bearer token. Access is protected by a random per-entry URL token.
    requires_auth = False

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the shared-folder view."""
        self._hass = hass

    async def get(
        self,
        request: web.Request,
    ) -> web.Response:
        """Render the connection page for one or all shared folders."""
        entry_id = request.query.get("entry_id")
        provided_token = request.query.get("token")
        share_name = request.query.get("share")

        entry = (
            self._hass.config_entries.async_get_entry(entry_id)
            if entry_id is not None
            else None
        )

        if entry is None or entry.domain != DOMAIN:
            raise web.HTTPNotFound

        expected_token = entry.data.get(CONF_SHARE_TOKEN)

        if (
            not isinstance(expected_token, str)
            or not isinstance(provided_token, str)
            or not secrets.compare_digest(
                expected_token,
                provided_token,
            )
        ):
            raise web.HTTPUnauthorized

        data = cast(
            TerraMasterData | None,
            getattr(
                entry.runtime_data,
                "data",
                None,
            ),
        )

        if data is None:
            raise web.HTTPNotFound

        shares = data.shares

        if share_name is not None:
            shares = tuple(
                share
                for share in shares
                if share.name == share_name
            )

        if not shares:
            raise web.HTTPNotFound

        is_french = request.headers.get(
            "Accept-Language",
            "",
        ).lower().startswith("fr")

        language = "fr" if is_french else "en"

        all_shares_title = (
            "Partages TerraMaster"
            if is_french
            else "TerraMaster shares"
        )

        prompt = (
            "Sélectionnez un dossier et un protocole de connexion."
            if is_french
            else "Select a shared folder and a connection protocol."
        )

        unavailable = (
            "Aucun protocole de connexion actif n’a été détecté."
            if is_french
            else "No active connection protocol was detected."
        )

        open_label = (
            "Ouvrir avec"
            if is_french
            else "Open with"
        )

        user_label = (
            "Utilisateur proposé"
            if is_french
            else "Suggested username"
        )

        hidden_label = (
            "Partage masqué"
            if is_french
            else "Hidden share"
        )

        recycle_label = (
            "Corbeille activée"
            if is_french
            else "Recycle bin enabled"
        )

        labels = {
            "smb": "SMB / CIFS",
            "nfs": "NFS",
            "afp": "AFP",
        }

        protocol_icons = {
            "smb": "▣",
            "nfs": "◆",
            "afp": "●",
        }

        detail_labels = (
            {
                "volume": "Volume",
                "raid": "RAID",
                "filesystem": "Système de fichiers",
                "capacity": "Capacité",
                "used": "Utilisé",
                "available": "Disponible",
                "usage": "Occupation",
            }
            if is_french
            else {
                "volume": "Volume",
                "raid": "RAID",
                "filesystem": "Filesystem",
                "capacity": "Capacity",
                "used": "Used",
                "available": "Available",
                "usage": "Usage",
            }
        )

        sections: list[str] = []

        host = str(entry.data[CONF_HOST])
        username = str(entry.data[CONF_USERNAME])

        for share in shares:
            urls = share_connection_urls(
                host,
                share,
                username,
            )

            protocol_badges = "".join(
                (
                    f'<span class="badge protocol-{protocol}">'
                    f'<span aria-hidden="true">'
                    f"{protocol_icons[protocol]}"
                    f"</span> "
                    f"{escape(labels[protocol])}"
                    f"</span>"
                )
                for protocol in share.protocols
            )

            if not protocol_badges:
                protocol_badges = (
                    '<span class="badge unavailable-badge">'
                    f"{escape(unavailable)}"
                    "</span>"
                )

            property_badges: list[str] = []

            if share.hidden:
                property_badges.append(
                    '<span class="badge secondary">'
                    f"{escape(hidden_label)}"
                    "</span>"
                )

            if share.recycle_bin:
                property_badges.append(
                    '<span class="badge secondary">'
                    f"{escape(recycle_label)}"
                    "</span>"
                )

            badges = (
                protocol_badges
                + "".join(property_badges)
            )

            links = "\n".join(
                (
                    f'<a class="button protocol-{protocol}" '
                    f'href="{escape(url, quote=True)}">'
                    '<span class="protocol-icon" '
                    'aria-hidden="true">'
                    f"{protocol_icons[protocol]}"
                    "</span>"
                    "<span>"
                    f"{escape(open_label)} "
                    f"{escape(labels[protocol])}"
                    "</span>"
                    "</a>"
                )
                for protocol, url in urls.items()
            )

            if not links:
                links = (
                    '<p class="unavailable">'
                    f"{escape(unavailable)}"
                    "</p>"
                )

            storage = resolve_share_storage(
                data,
                share,
            )

            details: list[tuple[str, str]] = []

            if storage.volume is not None:
                details.extend(
                    (
                        (
                            detail_labels["volume"],
                            storage.volume.name,
                        ),
                        (
                            detail_labels["filesystem"],
                            storage.volume.filesystem,
                        ),
                        (
                            detail_labels["capacity"],
                            _format_bytes(
                                storage.volume.size,
                            ),
                        ),
                        (
                            detail_labels["used"],
                            _format_bytes(
                                storage.volume.used,
                            ),
                        ),
                        (
                            detail_labels["available"],
                            _format_bytes(
                                storage.volume.available,
                            ),
                        ),
                        (
                            detail_labels["usage"],
                            f"{storage.volume.usage:.1f} %",
                        ),
                    )
                )

            if storage.raid is not None:
                raid_value = storage.raid.name

                if storage.raid.level:
                    raid_value = (
                        f"{raid_value} · "
                        f"{storage.raid.level.upper()}"
                    )

                details.insert(
                    1,
                    (
                        detail_labels["raid"],
                        raid_value,
                    ),
                )

            detail_rows = "".join(
                (
                    "<div>"
                    f"<dt>{escape(label)}</dt>"
                    f"<dd>{escape(value)}</dd>"
                    "</div>"
                )
                for label, value in details
            )

            detail_list = (
                f"<dl>{detail_rows}</dl>"
                if detail_rows
                else ""
            )

            username_note = (
                '<p class="username">'
                f"{escape(user_label)} : "
                f"<strong>{escape(username)}</strong>"
                "</p>"
            )

            sections.append(
                "<section>"
                '<div class="share-heading">'
                f"<h2>{escape(share.name)}</h2>"
                "</div>"
                '<p class="path">'
                f"<code>{escape(share.path)}</code>"
                "</p>"
                f'<div class="badges">{badges}</div>'
                f"{detail_list}"
                f"{username_note}"
                f'<div class="actions">{links}</div>'
                "</section>"
            )

        safe_title = (
            escape(shares[0].name)
            if share_name is not None
            else all_shares_title
        )

        page_sections = "\n".join(sections)

        body = f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>{safe_title}</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family:
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0 auto;
      max-width: 52rem;
      padding: 2rem 1rem 4rem;
    }}

    header {{
      margin-bottom: 1.5rem;
    }}

    h1 {{
      margin: 0 0 .45rem;
    }}

    header p {{
      margin: 0;
      opacity: .72;
    }}

    section {{
      background:
        color-mix(
          in srgb,
          Canvas 96%,
          #03a9f4 4%
        );
      border: 1px solid #8885;
      border-radius: 1rem;
      box-shadow: 0 .3rem 1rem #0002;
      margin-top: 1.2rem;
      padding: 1.2rem;
    }}

    .share-heading {{
      align-items: center;
      display: flex;
      justify-content: space-between;
      gap: 1rem;
    }}

    h2 {{
      margin: 0;
    }}

    .path {{
      margin: .55rem 0;
      opacity: .72;
      overflow-wrap: anywhere;
    }}

    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: .45rem;
      margin: .8rem 0 1rem;
    }}

    .badge {{
      border: 1px solid #8886;
      border-radius: 999px;
      font-size: .82rem;
      font-weight: 650;
      padding: .3rem .65rem;
    }}

    .secondary {{
      opacity: .72;
    }}

    .unavailable-badge {{
      opacity: .62;
    }}

    dl {{
      border-top: 1px solid #8884;
      margin: 1rem 0 0;
      padding-top: .6rem;
    }}

    dl div {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      padding: .4rem 0;
    }}

    dt {{
      opacity: .7;
    }}

    dd {{
      margin: 0;
      text-align: right;
    }}

    .username {{
      border-top: 1px solid #8884;
      font-size: .9rem;
      margin: 1rem 0 0;
      opacity: .75;
      padding-top: .8rem;
    }}

    .actions {{
      display: grid;
      gap: .7rem;
      grid-template-columns:
        repeat(
          auto-fit,
          minmax(12rem, 1fr)
        );
      margin-top: 1rem;
    }}

    .button {{
      align-items: center;
      background: #03a9f4;
      border-radius: .7rem;
      color: white;
      display: flex;
      font-size: .95rem;
      font-weight: 650;
      gap: .6rem;
      justify-content: center;
      padding: .85rem 1rem;
      text-align: center;
      text-decoration: none;
    }}

    .button:hover {{
      filter: brightness(1.08);
    }}

    .button:focus-visible {{
      outline: 3px solid #03a9f477;
      outline-offset: 2px;
    }}

    .protocol-icon {{
      font-size: 1.1rem;
    }}

    .unavailable {{
      opacity: .7;
    }}

    @media (max-width: 34rem) {{
      body {{
        padding-top: 1.25rem;
      }}

      dl div {{
        align-items: flex-start;
        flex-direction: column;
        gap: .2rem;
      }}

      dd {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{safe_title}</h1>
    <p>{escape(prompt)}</p>
  </header>

  <main>
    {page_sections}
  </main>
</body>
</html>"""

        return web.Response(
            text=body,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Content-Security-Policy": (
                    "default-src 'none'; "
                    "style-src 'unsafe-inline'; "
                    "base-uri 'none'; "
                    "form-action 'none'; "
                    "frame-ancestors 'none'"
                ),
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )
