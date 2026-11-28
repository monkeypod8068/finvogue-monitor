"""その日の判定から、Xのカード用の画像(og/*.png)と、その画像を指す日付ページ(d/*.html)を作る。

使い方: python scripts/make_og.py   (リポジトリの直下で実行)
入力: latest.json, stage_history.json
出力: og/YYYY-MM-DD-morning.png（または evening）, d/YYYY-MM-DD-morning.html
公開データ(latest.json)だけから作るので、個人の情報は入らない。
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://monkeypod8068.github.io/finvogue-monitor/"
W, H = 1200, 630
PAPER, INK, MUTED, FAINT, LINE = "#fbfaf7", "#1c1b19", "#6d6a63", "#9c988f", "#e7e3da"
STAGE_BG = ["#cfe3d6", "#e7c35f", "#d47a52", "#6e1f1f"]
STAGE_FG = [INK, INK, "#ffffff", "#ffffff"]
STAGES = ["平常", "注意", "調整拡大", "暴落型"]
LABELS = ["今の状況", "次の焦点", "見るべき数字"]
NO_START = "」』）)。、，．・ー％%"

CJK_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-{w}.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-{w}.ttc",
]


FALLBACK = {"Black": ["Black", "Bold"], "Bold": ["Bold"], "Medium": ["Medium", "Regular"], "Regular": ["Regular"]}


def cjk(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    # GitHub Actionsの fonts-noto-cjk は Regular と Bold だけなので、無い太さは近いものを使う
    for w in FALLBACK.get(weight, [weight]) + ["Bold", "Regular"]:
        for c in CJK_CANDIDATES:
            p = Path(c.format(w=w))
            if p.exists():
                return ImageFont.truetype(str(p), size, index=0)   # index 0 = 日本語(JP)
    import glob
    hits = sorted(glob.glob("/usr/share/fonts/**/NotoSansCJK*.tt[cf]", recursive=True))
    if hits:
        return ImageFont.truetype(hits[0], size, index=0)
    raise SystemExit("日本語フォント(Noto Sans CJK)が見つかりません")


def serif(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlayfairDisplay-Bold.woff"), size)


def fit(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    """幅に収まらなければ末尾を「…」で切る"""
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def wrap2(draw, text: str, font, width: int) -> list[str]:
    """2行までで折り返す(日本語なので1文字単位)"""
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > width and ch in NO_START:
            cur += ch          # 行頭に来てはいけない記号は、前の行の末尾にぶら下げる
            continue
        if draw.textlength(cur + ch, font=font) > width:
            lines.append(cur)
            cur = ch
            if len(lines) == 2:
                break
        else:
            cur += ch
    if len(lines) < 2 and cur:
        lines.append(cur)
    if len(lines) == 2 and "".join(lines) != text:
        lines[1] = fit(draw, lines[1] + "…", font, width) if not lines[1].endswith("…") else lines[1]
        lines[1] = fit(draw, lines[1], font, width)
    return lines


def summary_items(d: dict) -> list[tuple[str, str]]:
    out = []
    for i, s in enumerate(d.get("summary") or []):
        if isinstance(s, dict):
            out.append((s.get("label") or LABELS[min(i, 2)], s.get("text", "")))
        else:
            out.append((LABELS[min(i, 2)], str(s)))
    return out[:3]


def md(s: str) -> str:
    p = s.split("-")
    return f"{int(p[1])}/{int(p[2])}"


# Xはカード画像の左下(下から約90px)にページのタイトルを重ねて表示するので、
# 文字や帯は SAFE_BOTTOM より上に収め、下の帯域は空けておく。
SAFE_BOTTOM = H - 100


def render(d: dict, days: list[dict]) -> Image.Image:
    st = int(d.get("stage", 0))
    img = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(img)
    # 上部: ロゴと日付
    dr.text((60, 24), "FinVogue", font=serif(42), fill=INK)
    upd = str(d.get("updated", ""))[:10]
    ed = d.get("edition", "")
    right = f"{md(upd)} {ed}" if upd else ed
    if d.get("us_date"):
        right += f"｜米国 {md(str(d['us_date']))} 終値"
    f = cjk(24, "Medium")
    dr.text((W - 60 - dr.textlength(right, font=f), 36), right, font=f, fill=MUTED)

    # 段階のパネル
    x0, y0, x1, y1 = 60, 92, W - 60, 238
    dr.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=STAGE_BG[st])
    fg = STAGE_FG[st]
    dr.text((x0 + 36, y0 + 16), "現在の判定（4段階）", font=cjk(21, "Medium"), fill=fg)
    dr.text((x0 + 36, y0 + 40), f"段階{st}　{STAGES[st]}", font=cjk(60, "Black"), fill=fg)
    # 前日からの変化
    prev = days[-2]["stage"] if len(days) >= 2 else None
    if prev is not None and prev != st:
        chg = f"段階{prev}→{st}に{'上昇' if st > prev else '低下'}"
    elif days:
        run = 1
        for x in reversed(days[:-1]):
            if x["stage"] != st:
                break
            run += 1
        chg = f"{run}日連続" if run > 1 else ""
    else:
        chg = ""
    if chg:
        fc = cjk(30, "Bold")
        tw = dr.textlength(chg, font=fc)
        bx = x1 - 36 - tw - 32
        dr.rounded_rectangle((bx, y0 + 50, x1 - 36, y0 + 100), radius=25,
                             outline=fg, width=2)
        dr.text((bx + 16, y0 + 55), chg, font=fc, fill=fg)
    # 4段階の目盛り
    sw = (x1 - x0 - 72 - 18) / 4
    for i in range(4):
        sx = x0 + 36 + i * (sw + 6)
        dr.rounded_rectangle((sx, y1 - 22, sx + sw, y1 - 14), radius=3,
                             fill=fg if i <= st else None, outline=fg)

    # 直近30営業日の帯(パネルのすぐ下。Xのタイトル表示と重ならない位置)
    y = 248
    if len(days) >= 5:
        fs = cjk(18, "Medium")
        n = len(days)
        dr.text((60, y), f"段階の推移（直近{n}営業日） {md(days[0]['date'])}〜{md(days[-1]['date'])}",
                font=fs, fill=FAINT)
        by, bh = y + 28, 18
        bw = (W - 120 - 2 * (n - 1)) / n
        for i, x in enumerate(days):
            bx = 60 + i * (bw + 2)
            dr.rounded_rectangle((bx, by, bx + bw, by + bh), radius=3, fill=STAGE_BG[int(x["stage"])])
        y = by + bh + 18
    else:
        y += 8

    # 3行まとめ(各2行まで)
    fl, ft = cjk(21, "Medium"), cjk(25, "Bold")
    for lab, txt in summary_items(d):
        dr.text((60, y + 4), lab, font=fl, fill=MUTED)
        for line in wrap2(dr, txt, ft, W - 60 - 210):
            if y + 30 > SAFE_BOTTOM:
                break
            dr.text((210, y), line, font=ft, fill=INK)
            y += 31
        y += 8
    # 下端のライン
    dr.rectangle((0, H - 8, W, H), fill="#6e1f1f")
    return img


def page(d: dict, png: str, slug: str) -> str:
    st = int(d.get("stage", 0))
    title = f"段階{st}｜{STAGES[st]} — マーケット・ストレス・モニター {md(str(d.get('updated', ''))[:10])}{d.get('edition', '')} | FinVogue"
    desc = d.get("headline", "")
    img = BASE_URL + png
    url = BASE_URL + f"d/{slug}.html"
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="FinVogue">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(img)}">
<meta property="og:image:width" content="{W}">
<meta property="og:image:height" content="{H}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@finvogue_jp">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(img)}">
<link rel="canonical" href="{e(url)}">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
</head><body style="font-family:sans-serif;padding:40px;color:#1c1b19">
<p><a href="../">マーケット・ストレス・モニター（FinVogue）へ移動します</a></p>
<script>setTimeout(function(){{location.replace("../")}},300)</script>
</body></html>
"""


def main() -> int:
    d = json.loads((ROOT / "latest.json").read_text(encoding="utf-8"))
    try:
        days = json.loads((ROOT / "stage_history.json").read_text(encoding="utf-8")).get("days", [])
    except Exception:  # noqa: BLE001
        days = []
    date = str(d.get("updated", ""))[:10]
    kind = "evening" if "夕" in str(d.get("edition", "")) else "morning"
    if kind == "evening":
        # Xに投稿するのは朝版だけなので、夕方版の画像は作らない(リポジトリの容量を抑える)
        print("[skip] 夕方版は画像を作りません")
        return 0
    if len(date) != 10:
        print("latest.json の updated が読めません", file=sys.stderr)
        return 1
    slug = f"{date}-{kind}"
    png = f"og/{slug}.png"
    (ROOT / "og").mkdir(exist_ok=True)
    (ROOT / "d").mkdir(exist_ok=True)
    render(d, days).save(ROOT / png, optimize=True)
    (ROOT / "d" / f"{slug}.html").write_text(page(d, png, slug), encoding="utf-8")
    print(f"[ok] {png} / d/{slug}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
