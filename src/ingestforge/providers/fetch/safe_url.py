from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

from ingestforge.core.errors import SafeUrlError

BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


def _is_blocked_ip(ip: str) -> bool:
    obj = ipaddress.ip_address(ip)
    if obj.version == 6 and obj.ipv4_mapped is not None:
        obj = obj.ipv4_mapped
    return any(
        [
            obj.is_private,
            obj.is_loopback,
            obj.is_link_local,
            obj.is_multicast,
            obj.is_reserved,
            obj.is_unspecified,
        ]
    )


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise SafeUrlError("only http/https URLs are supported")
    if not parsed.hostname:
        raise SafeUrlError("URL host is required")
    host = parsed.hostname.lower().rstrip(".")
    host_for_netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), host_for_netloc + port, path, "", parsed.query, ""))


def validate_public_url(
    url: str, *, deny_private_networks: bool = True, require_https: bool = False
) -> str:
    norm = normalize_url(url)
    parsed = urlparse(norm)
    if require_https and parsed.scheme != "https":
        raise SafeUrlError("HTTPS is required by profile")
    host = parsed.hostname or ""
    if host in BLOCKED_HOSTS or host.endswith(".local"):
        raise SafeUrlError("localhost/.local hostnames are not allowed")
    try:
        if _is_blocked_ip(host) and deny_private_networks:
            raise SafeUrlError("blocked IP address")
    except ValueError:
        if deny_private_networks:
            try:
                infos = socket.getaddrinfo(host, None)
            except socket.gaierror as exc:
                raise SafeUrlError("DNS resolution failed") from exc
            for info in infos:
                ip = str(info[4][0])
                if _is_blocked_ip(ip):
                    raise SafeUrlError(f"host resolves to blocked address: {ip}") from None
    return norm


def host_allowed(
    url: str, allowed: list[str], denied: list[str], allow_subdomains: bool = True
) -> bool:
    host = (urlparse(url).hostname or "").lower()

    def matches(domain: str) -> bool:
        d = domain.lower().lstrip(".")
        return host == d or (allow_subdomains and host.endswith("." + d))

    if any(matches(d) for d in denied):
        return False
    return not (allowed and not any(matches(d) for d in allowed))
