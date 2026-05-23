from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup


def discover_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for prop in ["og:image", "twitter:image"]:
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            urls.append(urljoin(base_url, str(tag["content"])))
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            urls.append(urljoin(base_url, str(src)))
        srcset = img.get("srcset")
        if srcset:
            for part in str(srcset).split(","):
                first = part.strip().split(" ")[0]
                if first:
                    urls.append(urljoin(base_url, first))
    dedup = []
    seen = set()
    for u in urls:
        if u not in seen:
            dedup.append(u)
            seen.add(u)
    return dedup
