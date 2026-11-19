#!/usr/bin/env python3
"""Lê o calendário público de contribuições do GitHub e grava data/contributions.json.

Usa a mesma página que o perfil mostra, então não precisa de token. As
contribuições privadas só entram na conta se a opção "Include private
contributions on my profile" estiver ligada nas configurações do GitHub.
"""
import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse(html: str) -> list[dict]:
    counts = {}
    for m in re.finditer(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>', html, re.S):
        n = re.match(r"\s*(\d[\d,]*)", m.group(2))
        counts[m.group(1)] = int(n.group(1).replace(",", "")) if n else 0
    days = []
    for m in re.finditer(r"<td\b[^>]*>", html):
        tag = m.group(0)
        date = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        if not date:
            continue
        level = re.search(r'data-level="(\d)"', tag)
        cid = re.search(r'\bid="([^"]+)"', tag)
        lvl = int(level.group(1)) if level else 0
        count = counts.get(cid.group(1), 0) if cid else 0
        if lvl and not count:
            count = lvl  # página sem o texto do dia: usa o nível como aproximação
        days.append({"date": date.group(1), "count": count, "level": lvl})
    return sorted(days, key=lambda d: d["date"])


def main() -> int:
    user = json.loads((ROOT / "perfil.json").read_text(encoding="utf-8"))["usuario"]
    if len(sys.argv) > 1:
        user = sys.argv[1]
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "profile-cards"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    days = parse(html)
    if not days:
        print("Calendário não encontrado na página; mantendo o arquivo atual.")
        return 1
    out = {
        "user": user,
        "updated": datetime.date.today().isoformat(),
        "total": sum(d["count"] for d in days),
        "days": days,
    }
    path = ROOT / "data" / "contributions.json"
    if len(sys.argv) > 2:
        path = Path(sys.argv[2])
    path.parent.mkdir(exist_ok=True)
    if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("days") == days:
        print(f"{user}: sem mudança ({out['total']} contribuições)")
        return 0
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{user}: {out['total']} contribuições em {len(days)} dias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
