"""Build the evidence figures used in the Metric Studio chapter 2 blog post.

Uses only committed CSV/JSON results so that every published number can be
traced back to the experiment output. Run from the repository root:

    python tools/build_blog_assets.py
"""

from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
ASSETS = ROOT / "blog_assets"

COLORS = {
    "reversal_1m": "#B7C0CC",
    "momentum_6m": "#B7C0CC",
    "low_volatility": "#247BA0",
    "small_cap": "#E76F51",
}
LABELS = {
    "reversal_1m": "1M reversal",
    "momentum_6m": "6M momentum",
    "low_volatility": "Low volatility",
    "small_cap": "Small cap",
}
SIGNALS = list(LABELS)
PCTS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
COSTS = [0.5, 1.0, 1.5, 2.0]


def save_svg(name: str, content: str) -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / name).write_text(content, encoding="utf-8")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(Path("C:/Windows/Fonts") / name, size)


def save_png(image: Image.Image, name: str) -> None:
    ASSETS.mkdir(exist_ok=True)
    image.save(ASSETS / name, format="PNG", optimize=True)


def topology_map(rows: list[dict[str, str]]) -> None:
    counts: dict[tuple[str, float, float], int] = defaultdict(int)
    for row in rows:
        if row["robust"] == "True":
            counts[(row["signal"], round(float(row["universe_pct"]), 1), round(float(row["cost_multiplier"]), 1))] += 1

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img" aria-labelledby="title desc">',
        '<title id="title">Robust strategy count by liquidity universe and cost assumption</title>',
        '<desc id="desc">Four panels show how many strategy configurations remain robust at each liquidity universe and cost multiplier. Only low volatility and small cap retain robust configurations.</desc>',
        '<rect width="1200" height="720" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#1F2937}.muted{fill:#6B7280}.small{font-size:14px}.axis{font-size:13px}.title{font-size:25px;font-weight:700}.panel{font-size:18px;font-weight:700}.note{font-size:15px}</style>',
        '<text x="60" y="52" class="title">Robust strategies are regions, not isolated peaks</text>',
        '<text x="60" y="78" class="muted small">Count of configurations meeting all four rules: positive net CAGR, t &gt; 1.96, MDD &gt; -60%, mean fill ≥ 80%</text>',
    ]
    panel_positions = [(60, 130), (630, 130), (60, 410), (630, 410)]
    cell_w, cell_h = 48, 35
    for (signal, (x0, y0)) in zip(SIGNALS, panel_positions):
        svg.append(f'<text x="{x0}" y="{y0 - 18}" class="panel">{LABELS[signal]}</text>')
        for col, pct in enumerate(PCTS):
            x = x0 + 72 + col * cell_w
            svg.append(f'<text x="{x + 16}" y="{y0 - 3}" text-anchor="middle" class="axis muted">{int(pct * 100)}</text>')
        svg.append(f'<text x="{x0 + 264}" y="{y0 - 28}" text-anchor="middle" class="axis muted">liquidity universe (%)</text>')
        for row_i, cost in enumerate(COSTS):
            y = y0 + row_i * cell_h
            svg.append(f'<text x="{x0 + 60}" y="{y + 23}" text-anchor="end" class="axis muted">{cost:.1f}×</text>')
            for col, pct in enumerate(PCTS):
                x = x0 + 72 + col * cell_w
                count = counts[(signal, pct, cost)]
                color = COLORS[signal] if count else "#EEF1F4"
                opacity = 0.25 + min(count, 8) / 10 if count else 1
                svg.append(f'<rect x="{x}" y="{y}" width="42" height="29" rx="3" fill="{color}" opacity="{opacity:.2f}"/>')
                if count:
                    svg.append(f'<text x="{x + 21}" y="{y + 20}" text-anchor="middle" class="small" fill="#FFFFFF" style="fill:#FFFFFF">{count}</text>')
        svg.append(f'<text x="{x0 + 8}" y="{y0 + 78}" transform="rotate(-90 {x0 + 8} {y0 + 78})" class="axis muted">cost multiplier</text>')
    svg.extend([
        '<line x1="60" y1="662" x2="1140" y2="662" stroke="#D1D5DB"/>',
        '<text x="60" y="692" class="note">Reading rule: one number is the count of robust configurations after changing holdings and AUM. Blank cells have no surviving configuration.</text>',
        '</svg>',
    ])
    save_svg("01_robustness_map.svg", "".join(svg))

    image = Image.new("RGB", (1200, 720), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "Robust strategies are regions, not isolated peaks", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "Count of configurations meeting all four rules: positive net CAGR, t > 1.96, MDD > -60%, mean fill >= 80%", fill="#6B7280", font=font(14))
    for signal, (x0, y0) in zip(SIGNALS, panel_positions):
        draw.text((x0, y0 - 21), LABELS[signal], fill="#1F2937", font=font(18, True))
        draw.text((x0 + 165, y0 - 39), "liquidity universe (%)", fill="#6B7280", font=font(13))
        for col, pct in enumerate(PCTS):
            x = x0 + 72 + col * cell_w
            draw.text((x + 13, y0 - 4), str(int(pct * 100)), fill="#6B7280", font=font(12))
        for row_i, cost in enumerate(COSTS):
            y = y0 + row_i * cell_h
            draw.text((x0 + 31, y + 8), f"{cost:.1f}x", fill="#6B7280", font=font(12))
            for col, pct in enumerate(PCTS):
                x = x0 + 72 + col * cell_w
                count = counts[(signal, pct, cost)]
                color = COLORS[signal] if count else "#EEF1F4"
                draw.rounded_rectangle((x, y, x + 42, y + 29), radius=3, fill=color)
                if count:
                    draw.text((x + 17, y + 6), str(count), fill="white", font=font(13, True))
        draw.text((x0, y0 + 151), "cost multiplier", fill="#6B7280", font=font(13))
    draw.line((60, 662, 1140, 662), fill="#D1D5DB", width=1)
    draw.text((60, 681), "Reading rule: one number is the count of robust configurations after changing holdings and AUM. Blank cells have no surviving configuration.", fill="#374151", font=font(14))
    save_png(image, "01_robustness_map.png")


def evidence_summary() -> None:
    report = json.loads((RESULTS / "reality_check_report.json").read_text(encoding="utf-8"))
    continents = list(csv.DictReader((RESULTS / "alpha_topology_continents.csv").open(encoding="utf-8")))
    best = report["best_node"]
    max_nodes = max(int(row["nodes"]) for row in continents)
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="560" viewBox="0 0 1200 560" role="img" aria-labelledby="title desc">',
        '<title id="title">Evidence summary and decision boundary</title>',
        '<desc id="desc">The figure summarises the two connected robust regions and shows that the strongest small-cap result passed a family-wise bootstrap check but remains unsuitable as an investment conclusion because delisting bias is not yet audited.</desc>',
        '<rect width="1200" height="560" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#1F2937}.muted{fill:#6B7280}.title{font-size:25px;font-weight:700}.sub{font-size:15px}.label{font-size:18px;font-weight:700}.value{font-size:26px;font-weight:700}.small{font-size:14px}.box{stroke:#D1D5DB;stroke-width:1.5}</style>',
        '<text x="60" y="52" class="title">What the experiment establishes — and what it does not</text>',
        '<text x="60" y="78" class="muted sub">KRX adjusted-price, volume and market-cap panel · 1,728 tested configurations · 309 monthly observations</text>',
        '<rect x="60" y="115" width="510" height="185" rx="8" fill="#F8FAFC" class="box"/>',
        '<text x="88" y="151" class="label">Connected robust regions</text>',
    ]
    y = 190
    for row in continents:
        signal = row["signals"]
        nodes = int(row["nodes"])
        width = 260 * nodes / max_nodes
        color = COLORS[signal]
        svg.extend([
            f'<text x="88" y="{y}" class="small">{html.escape(LABELS[signal])}</text>',
            f'<rect x="220" y="{y - 15}" width="260" height="20" rx="3" fill="#E5E7EB"/>',
            f'<rect x="220" y="{y - 15}" width="{width:.1f}" height="20" rx="3" fill="{color}"/>',
            f'<text x="495" y="{y}" class="small">{nodes} nodes</text>',
        ])
        y += 52
    svg.extend([
        '<rect x="630" y="115" width="510" height="185" rx="8" fill="#F8FAFC" class="box"/>',
        '<text x="658" y="151" class="label">Best tested node</text>',
        f'<text x="658" y="192" class="value">t = {best["t_stat"]:.2f} · family-wise p = {report["family_wise_p_value"]:.3f}</text>',
        f'<text x="658" y="224" class="small">Small cap · liquidity top 90% · 50 holdings · KRW 100m · 0.5× cost</text>',
        f'<text x="658" y="254" class="small">Net CAGR {best["net_cagr"] * 100:.1f}% · MDD {best["mdd"] * 100:.1f}% · mean fill {best["mean_fill"] * 100:.1f}%</text>',
        '<rect x="60" y="342" width="1080" height="145" rx="8" fill="#FFF7ED" stroke="#FB923C" stroke-width="1.5"/>',
        '<text x="88" y="380" class="label">Decision boundary</text>',
        '<text x="88" y="412" class="small">The bootstrap result rejects a simple “best result from many trials” explanation. It does not remove survivorship or delisting bias.</text>',
        '<text x="88" y="442" class="small">Therefore this is a strong hypothesis for the next audit, not an investable small-cap strategy.</text>',
        '<text x="60" y="528" class="muted small">Source: results/alpha_topology_nodes.csv, results/alpha_topology_continents.csv, results/reality_check_report.json</text>',
        '</svg>',
    ])
    save_svg("02_evidence_decision_boundary.svg", "".join(svg))

    image = Image.new("RGB", (1200, 560), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "What the experiment establishes — and what it does not", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "KRX adjusted-price, volume and market-cap panel · 1,728 tested configurations · 309 monthly observations", fill="#6B7280", font=font(15))
    draw.rounded_rectangle((60, 115, 570, 300), radius=8, fill="#F8FAFC", outline="#D1D5DB", width=2)
    draw.text((88, 137), "Connected robust regions", fill="#1F2937", font=font(18, True))
    y = 181
    for row in continents:
        signal = row["signals"]
        nodes = int(row["nodes"])
        width = int(260 * nodes / max_nodes)
        draw.text((88, y), LABELS[signal], fill="#1F2937", font=font(14))
        draw.rounded_rectangle((220, y - 2, 480, y + 18), radius=3, fill="#E5E7EB")
        draw.rounded_rectangle((220, y - 2, 220 + width, y + 18), radius=3, fill=COLORS[signal])
        draw.text((495, y), f"{nodes} nodes", fill="#1F2937", font=font(14))
        y += 52
    draw.rounded_rectangle((630, 115, 1140, 300), radius=8, fill="#F8FAFC", outline="#D1D5DB", width=2)
    draw.text((658, 137), "Best tested node", fill="#1F2937", font=font(18, True))
    draw.text((658, 178), f"t = {best['t_stat']:.2f} · family-wise p = {report['family_wise_p_value']:.3f}", fill="#1F2937", font=font(24, True))
    draw.text((658, 216), "Small cap · liquidity top 90% · 50 holdings · KRW 100m · 0.5x cost", fill="#1F2937", font=font(14))
    draw.text((658, 247), f"Net CAGR {best['net_cagr'] * 100:.1f}% · MDD {best['mdd'] * 100:.1f}% · mean fill {best['mean_fill'] * 100:.1f}%", fill="#1F2937", font=font(14))
    draw.rounded_rectangle((60, 342, 1140, 487), radius=8, fill="#FFF7ED", outline="#FB923C", width=2)
    draw.text((88, 364), "Decision boundary", fill="#1F2937", font=font(18, True))
    draw.text((88, 402), "The bootstrap result rejects a simple “best result from many trials” explanation. It does not remove survivorship or delisting bias.", fill="#1F2937", font=font(14))
    draw.text((88, 434), "Therefore this is a strong hypothesis for the next audit, not an investable small-cap strategy.", fill="#1F2937", font=font(14))
    draw.text((60, 518), "Source: alpha_topology_nodes.csv · alpha_topology_continents.csv · reality_check_report.json", fill="#6B7280", font=font(14))
    save_png(image, "02_evidence_decision_boundary.png")


def main() -> None:
    with (RESULTS / "alpha_topology_nodes.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    topology_map(rows)
    evidence_summary()


if __name__ == "__main__":
    main()
