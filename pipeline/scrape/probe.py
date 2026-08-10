"""Discovery-Sonde 2: Struktur der schlussgang JSON:API node/event."""
from __future__ import annotations

import json
import re
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main():
    base = "https://backend.schlussgang.ch/jsonapi/node/event"
    body = get(f"{base}?page[limit]=3&sort=-nid")
    print("Rohsuche statistic-final:", re.findall(r"event-ranking-list/(\d+)-statistic-final", body)[:10])
    print("Rohsuche event-ranking:", re.findall(r"event-ranking-list/(\d+)-", body)[:10])

    doc = json.loads(body)
    data = doc.get("data", [])
    print(f"\nAnzahl Events in Antwort: {len(data)}")
    if data:
        e = data[0]
        print("type:", e.get("type"), "id:", e.get("id"))
        attrs = e.get("attributes", {})
        print("\nATTRIBUTE-Keys:")
        for k in attrs:
            v = attrs[k]
            sv = str(v)[:60]
            print(f"  {k} = {sv}")
        print("\nRELATIONSHIP-Keys:", list(e.get("relationships", {}).keys()))
        # Felder, die wie eine ID / ein Datum / ein Titel aussehen
        for k, v in attrs.items():
            if re.search(r"id|drupal_internal|nummer|date|titel|title|typ|name", k, re.I):
                print(f"  [wichtig] {k} = {str(v)[:80]}")

    # Gesamtzahl der Events (meta oder pager)
    print("\nmeta:", json.dumps(doc.get("meta", {}))[:200])
    print("links.next vorhanden:", "next" in doc.get("links", {}))


if __name__ == "__main__":
    main()
