#!/usr/bin/env python3
"""Desenha os cards SVG do README do perfil e reescreve o README.md.

Textos e links ficam em perfil.json. Os dados de atividade vêm de
data/contributions.json (gravado por fetch_contributions.py).

  STATIC=1  desenha o quadro final, sem animação (para conferir o layout)
  DEMO=1    usa atividade de exemplo e grava em preview-out/ (nunca em cards/)
"""
import base64
import datetime
import io
import json
import os
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"
DEMO = os.environ.get("DEMO") == "1"
OUT = ROOT / ("preview-out" if DEMO else "cards")

# chave: (arquivo, família no SVG, peso, fontes de reserva)
FONTS = {
    "d": ("Archivo-800.ttf", "AKd", 800, "'Helvetica Neue',Arial,sans-serif"),
    "b": ("Inter-600.ttf", "AKb", 600, "'Helvetica Neue',Arial,sans-serif"),
    "t": ("Inter-400.ttf", "AKt", 400, "'Helvetica Neue',Arial,sans-serif"),
    "m": ("PlexMono-Regular.ttf", "AKm", 400, "ui-monospace,Menlo,Consolas,monospace"),
}
THEMES = {
    "light": dict(bg="#f7f9fc", fg="#0f1b2d", dim="#52607a", acc="#1a56db",
                  line="#c9d3e3", soft="#e4ebf7", on="#ffffff"),
    "dark": dict(bg="#0e1726", fg="#eaf0fa", dim="#9aa8c0", acc="#7aa7ff",
                 line="#27364f", soft="#18253b", on="#0e1726"),
}
MIN_DIAS_ATIVOS = 30
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_LONGOS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
                "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

ANIM = """
.up{animation:up .7s cubic-bezier(.2,.8,.2,1) both}
.fade{animation:fade .6s ease both}
.grow{transform-box:fill-box;transform-origin:bottom;animation:grow .8s cubic-bezier(.2,.8,.2,1) both}
.wipe{transform-box:fill-box;transform-origin:left;animation:wipe .9s cubic-bezier(.2,.8,.2,1) both}
.pulse{animation:pulse 2.2s ease-in-out infinite}
.nudge{animation:nudge 2.4s ease-in-out infinite}
@keyframes up{from{opacity:0;transform:translateY(14px)}}
@keyframes fade{from{opacity:0}}
@keyframes grow{from{transform:scaleY(0)}}
@keyframes wipe{from{transform:scaleX(0)}}
@keyframes pulse{50%{opacity:.3}}
@keyframes nudge{50%{transform:translateX(6px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""

_fonts = {}


def font(key):
    if key not in _fonts:
        _fonts[key] = TTFont(ROOT / "fonts" / FONTS[key][0], recalcTimestamp=False)
    return _fonts[key]


def measure(text, key, size, ls=0.0):
    f = font(key)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    adv = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upm // 2 for c in text)
    return adv / upm * size + ls * len(text)


def fit(text, key, size, maxw, ls=0.0):
    while size > 8 and measure(text, key, size, ls) > maxw:
        size -= 0.5
    return size


def woff_b64(key, chars):
    opts = subset.Options()
    opts.layout_features = ["kern"]
    opts.hinting = False
    opts.name_IDs = [1, 2]
    opts.notdef_outline = True
    opts.drop_tables += ["meta"]
    f = TTFont(ROOT / "fonts" / FONTS[key][0], recalcTimestamp=False)
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(f)
    f.flavor = "woff"
    buf = io.BytesIO()
    f.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


class Card:
    def __init__(self, w, h, theme, label):
        self.w, self.h, self.p, self.label = w, h, THEMES[theme], label
        self.body, self.used = [], {k: set() for k in FONTS}

    def add(self, s):
        self.body.append(s)

    @staticmethod
    def _anim(cls, delay):
        if not cls:
            return ""
        return f' class="{cls}" style="animation-delay:{int(delay)}ms"'

    def frame(self, fill=None, stroke=None):
        p = self.p
        self.add(f'<rect x=".75" y=".75" width="{self.w - 1.5}" height="{self.h - 1.5}" rx="10" '
                 f'fill="{fill or p["bg"]}" stroke="{stroke or p["line"]}" stroke-width="1.5"/>')

    def text(self, x, y, s, key, size, fill, anchor="start", cls="", delay=0, ls=0.0):
        self.used[key].update(s)
        extra = f' letter-spacing="{ls}"' if ls else ""
        anc = f' text-anchor="{anchor}"' if anchor != "start" else ""
        inner = (f'<text class="f{key}" x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" '
                 f'fill="{fill}"{anc}{extra}>{escape(s)}</text>')
        self.add(f"<g{self._anim(cls, delay)}>{inner}</g>" if cls else inner)

    def rect(self, x, y, w, h, fill, rx=0, stroke=None, cls="", delay=0, opacity=None):
        st = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
        op = f' opacity="{opacity}"' if opacity is not None else ""
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" '
                 f'fill="{fill}"{st}{op}{self._anim(cls, delay)}/>')

    def svg(self):
        css = []
        for key, chars in self.used.items():
            if not chars:
                continue
            _, fam, weight, fallback = FONTS[key]
            css.append(f"@font-face{{font-family:{fam};font-weight:{weight};"
                       f"src:url(data:font/woff;base64,{woff_b64(key, chars)}) format('woff')}}")
            css.append(f".f{key}{{font-family:{fam},{fallback};font-weight:{weight}}}")
        if not STATIC:
            css.append(ANIM)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}" role="img" aria-label="{escape(self.label)}">'
                f"<title>{escape(self.label)}</title><style>{''.join(css)}</style>"
                f"{''.join(self.body)}</svg>\n")


# ------------------------------------------------------------------ cards

def hero(P, theme):
    c = Card(800, 344, theme, f'{P["nome"]}: {P["cargo"]}. {P["frase"]}')
    p = c.p
    c.frame()
    tw = measure(P["selo"], "m", 13, 1)
    c.rect(40, 34, tw + 44, 30, p["soft"], rx=15, cls="fade")
    c.add(f'<circle cx="57" cy="49" r="4" fill="{p["acc"]}"{c._anim("pulse", 0)}/>')
    c.text(70, 53.5, P["selo"], "m", 13, p["acc"], cls="fade", ls=1)
    size = fit(P["nome"], "d", 80, 720, -1.5)
    c.text(38, 150, P["nome"], "d", size, p["fg"], cls="up", delay=120, ls=-1.5)
    c.text(40, 190, P["cargo"], "b", fit(P["cargo"], "b", 23, 720), p["acc"], cls="up", delay=260)
    c.text(40, 222, P["frase"], "t", fit(P["frase"], "t", 20, 720), p["dim"], cls="up", delay=360)
    c.rect(40, 253, 720, 1.5, p["line"], cls="wipe", delay=450)
    for i, (rotulo, valor) in enumerate(P["fatos"][:3]):
        x = 40 + i * 240
        c.text(x, 284, rotulo.upper(), "m", 12, p["dim"], cls="up", delay=560 + i * 90, ls=1.2)
        c.text(x, 310, valor, "b", fit(valor, "b", 17, 220), p["fg"], cls="up", delay=600 + i * 90)
    return c.svg()


def tile(P, theme, i):
    rotulo, verbo, linhas = P["blocos"][i]
    c = Card(400, 280, theme, f'{verbo}: {" ".join(linhas)}')
    p = c.p
    base = i * 140
    c.frame()
    c.text(32, 52, rotulo, "m", 16, p["acc"], cls="fade", delay=base, ls=1)
    c.text(30, 150, verbo, "d", fit(verbo, "d", 58, 336, -1), p["fg"], cls="up", delay=base + 120, ls=-1)
    for n, linha in enumerate(linhas[:2]):
        c.text(32, 204 + n * 31, linha, "t", fit(linha, "t", 23, 336), p["dim"],
               cls="up", delay=base + 240 + n * 80)
    return c.svg()


def stack(P, theme):
    blocks, y, n = [], 96, 0
    for grupo, itens in P["tecnologias"]:
        chips, x, top = [], 40, y + 12
        for item in itens:
            w = measure(item, "m", 15) + 28
            if x + w > 760:
                x, top = 40, top + 42
            chips.append((x, top, w, item))
            x += w + 8
        blocks.append((grupo, y, chips))
        y = top + 34 + 34
    h = y - 34 + 38
    c = Card(800, int(h), theme, "Tecnologias: " + "; ".join(
        f"{g}: {', '.join(i)}" for g, i in P["tecnologias"]))
    p = c.p
    c.frame()
    c.text(40, 60, "Tecnologias", "d", 24, p["fg"], cls="up")
    for grupo, gy, chips in blocks:
        c.text(40, gy, grupo.upper(), "m", 12, p["dim"], cls="fade", delay=100 + n * 40, ls=1.2)
        for x, top, w, item in chips:
            d = 160 + n * 45
            c.rect(x, top, w, 34, "none", rx=6, stroke=p["line"], cls="fade", delay=d)
            c.text(x + 14, top + 22.5, item, "m", 15, p["fg"], cls="fade", delay=d)
            n += 1
    return c.svg()


def education(P, theme):
    rows = P["formacao"]
    c = Card(800, 96 + len(rows) * 64 + 8, theme, "Formação: " + "; ".join(
        f"{r[0]} em {r[1]}, {r[2]}, {r[3]} ({r[4].lower()})" for r in rows))
    p = c.p
    c.frame()
    c.text(40, 60, "Formação", "d", 24, p["fg"], cls="up")
    for i, (tipo, titulo, inst, periodo, status) in enumerate(rows):
        y, d = 96 + i * 64, 140 + i * 90
        if i:
            c.rect(40, y - 14, 720, 1.5, p["line"], cls="wipe", delay=d)
        c.text(40, y + 14, titulo, "b", fit(titulo, "b", 19, 560), p["fg"], cls="up", delay=d)
        c.text(40, y + 36, f"{tipo} · {inst} · {periodo}".upper(), "m", 12, p["dim"],
               cls="fade", delay=d + 60, ls=1)
        feito = status.lower().startswith("conclu")
        c.text(760, y + 24, status.upper(), "m", 12, p["dim"] if feito else p["acc"],
               anchor="end", cls="fade", delay=d + 60, ls=1.2)
    return c.svg()


def monthly(days):
    last = datetime.date.fromisoformat(days[-1]["date"])
    keys = []
    y, m = last.year, last.month
    for _ in range(12):
        keys.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    keys.reverse()
    sums = {k: 0 for k in keys}
    for d in days:
        k = (int(d["date"][:4]), int(d["date"][5:7]))
        if k in sums:
            sums[k] += d["count"]
    return [(k, sums[k]) for k in keys]


def activity(data, theme):
    days = data["days"]
    months = monthly(days)
    total = sum(d["count"] for d in days)
    ativos = sum(1 for d in days if d["count"])
    best_key, best = max(months, key=lambda kv: kv[1])
    upd = datetime.date.fromisoformat(data["updated"]).strftime("%d.%m.%Y")
    c = Card(800, 432, theme,
             f"Atividade nos últimos 12 meses: {total} contribuições em {ativos} dias ativos; "
             f"melhor mês, {MESES_LONGOS[best_key[1] - 1]}.")
    p = c.p
    c.frame()
    c.text(40, 60, "Atividade nos últimos 12 meses", "d", 24, p["fg"], cls="up")
    c.text(760, 58, f"ATUALIZADO EM {upd}", "m", 12, p["dim"], anchor="end", cls="fade", ls=1)
    stats = [(f"{total:,}".replace(",", "."), "CONTRIBUIÇÕES"), (str(ativos), "DIAS ATIVOS"),
             (MESES_LONGOS[best_key[1] - 1], "MELHOR MÊS")]
    for i, (num, rot) in enumerate(stats):
        x = 40 + i * 240
        c.text(x - 1, 122, num, "d", fit(num, "d", 40, 220), p["fg"], cls="up", delay=120 + i * 90)
        c.text(x, 144, rot, "m", 12, p["dim"], cls="fade", delay=160 + i * 90, ls=1.2)
    base, maxh, gap = 266, 88, 12
    bw = (720 - 11 * gap) / 12
    for i, (key, v) in enumerate(months):
        x = 40 + i * (bw + gap)
        h = max(2, v / best * maxh) if best else 2
        top = v == best and best > 0
        c.rect(x, base - h, bw, h, p["acc"] if top else p["line"], rx=2, cls="grow", delay=350 + i * 45)
        c.text(x + bw / 2, base + 20, MESES[key[1] - 1], "m", 12, p["dim"], anchor="middle",
               cls="fade", delay=350 + i * 45)
    c.rect(40, base, 720, 1.5, p["fg"])
    hgap = 2.6
    cell = (720 - 52 * hgap) / 53
    first = datetime.date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7  # domingo no topo, como no GitHub
    cols = {}
    for n, d in enumerate(days):
        cols.setdefault((n + offset) // 7, []).append(((n + offset) % 7, d["level"]))
    opac = {1: ".3", 2: ".55", 3: ".8", 4: "1"}
    skip = max(0, len(cols) - 53)
    for col in sorted(cols)[skip:]:
        x = 40 + (col - skip) * (cell + hgap)
        c.add(f'<g{c._anim("fade", 700 + (col - skip) * 9)}>')
        for row, lvl in cols[col]:
            yy = 304 + row * (cell + hgap)
            if lvl:
                c.rect(x, yy, cell, cell, p["acc"], rx=2, opacity=opac.get(lvl, "1"))
            else:
                c.rect(x, yy, cell, cell, p["soft"], rx=2)
        c.add("</g>")
    return c.svg()


def button(theme, rotulo, filled):
    c = Card(600, 110, theme, rotulo)
    p = c.p
    if filled:
        c.frame(fill=p["acc"], stroke=p["acc"])
        fg, arrow = p["on"], p["on"]
    else:
        c.frame()
        fg, arrow = p["fg"], p["acc"]
    c.text(40, 67, rotulo, "b", 32, fg, cls="up")
    c.text(552, 67, "→", "b", 32, arrow, anchor="end", cls="nudge")
    return c.svg()


# ------------------------------------------------------------------ dados e README

def demo_data():
    seed, days = 7, []
    start = datetime.date.today() - datetime.timedelta(days=370)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)
    for n in range(371):
        seed = (seed * 16807) % 2147483647
        r = seed / 2147483647
        day = start + datetime.timedelta(days=n)
        if day > datetime.date.today():
            break
        weekend = day.weekday() >= 5
        lvl = 0 if r < (0.7 if weekend else 0.3) else 1 if r < 0.6 else 2 if r < 0.8 else 3 if r < 0.93 else 4
        days.append({"date": day.isoformat(), "count": lvl * 2, "level": lvl})
    return {"updated": datetime.date.today().isoformat(), "days": days}


def picture(name, alt, width):
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="./cards/{name}-dark.svg">'
            f'<img src="./cards/{name}-light.svg" width="{width}" alt="{escape(alt, quote=True)}"></picture>')


def readme(P, has_activity):
    L = []
    L.append(f'<a href="{P["linkedin"]}">' + picture(
        "hero", f'{P["nome"]}. {P["cargo"]}. {P["frase"]} ' + ". ".join(
            f"{r}: {v}" for r, v in P["fatos"]) + ".", "100%") + "</a>")
    L.append('<p align="center">\n' + "\n".join(
        picture(f"bloco-{i + 1}", f'{b[1]}: {" ".join(b[2])}', "32%")
        for i, b in enumerate(P["blocos"])) + "\n</p>")
    L.append(picture("tecnologias", "Tecnologias. " + ". ".join(
        f"{g}: {', '.join(i)}" for g, i in P["tecnologias"]) + ".", "100%"))
    if P.get("formacao"):
        L.append(picture("formacao", "Formação. " + ". ".join(
            f"{r[0]} em {r[1]}, {r[2]}, {r[3]} ({r[4].lower()})" for r in P["formacao"]) + ".", "100%"))
    if has_activity:
        L.append(picture("atividade", "Atividade no GitHub nos últimos 12 meses.", "100%"))
    L.append('<p align="center">\n'
             f'<a href="{P["linkedin"]}">{picture("linkedin", "LinkedIn", "48.5%")}</a>\n'
             f'<a href="mailto:{P["email"]}">{picture("email", "E-mail: " + P["email"], "48.5%")}</a>\n'
             "</p>")
    return "\n\n".join(L) + "\n"


def main():
    P = json.loads((ROOT / "perfil.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    data = None
    if DEMO:
        data = demo_data()
    else:
        path = ROOT / "data" / "contributions.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
    # O card de atividade só entra com histórico suficiente para não parecer vazio.
    has_activity = bool(data and sum(1 for d in data["days"] if d["count"]) >= MIN_DIAS_ATIVOS)
    files = {}
    for theme in THEMES:
        files[f"hero-{theme}.svg"] = hero(P, theme)
        for i in range(3):
            files[f"bloco-{i + 1}-{theme}.svg"] = tile(P, theme, i)
        files[f"tecnologias-{theme}.svg"] = stack(P, theme)
        if P.get("formacao"):
            files[f"formacao-{theme}.svg"] = education(P, theme)
        if has_activity:
            files[f"atividade-{theme}.svg"] = activity(data, theme)
        files[f"linkedin-{theme}.svg"] = button(theme, "LinkedIn", True)
        files[f"email-{theme}.svg"] = button(theme, "E-mail", False)
    for old in OUT.glob("*.svg"):
        if old.name not in files:
            old.unlink()
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    if not DEMO:
        (ROOT / "README.md").write_text(readme(P, has_activity), encoding="utf-8")
    kb = sum(len(v.encode()) for v in files.values()) / 1024
    print(f"{len(files)} cards em {OUT.name}/ ({kb:.0f} KB), atividade: {'sim' if has_activity else 'não'}")


if __name__ == "__main__":
    main()
