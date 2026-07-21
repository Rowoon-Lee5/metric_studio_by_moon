"""Build the evidence figures used in the Metric Studio chapter 2 blog post.

Uses only committed CSV/JSON results so that every published number can be
traced back to the experiment output. Run from the repository root:

    python tools/build_blog_assets.py
"""

from __future__ import annotations

import csv
import html
import json
import textwrap
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import numpy as np

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
    "reversal_1m": "1개월 반전",
    "momentum_6m": "6개월 모멘텀",
    "low_volatility": "저변동성",
    "small_cap": "소형주",
}
SIGNALS = list(LABELS)
PCTS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
COSTS = [0.5, 1.0, 1.5, 2.0]


def save_svg(name: str, content: str) -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / name).write_text(content, encoding="utf-8")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "malgunbd.ttf" if bold else "malgun.ttf"
    return ImageFont.truetype(Path("C:/Windows/Fonts") / name, size)


def save_png(image: Image.Image, name: str) -> None:
    ASSETS.mkdir(exist_ok=True)
    image.save(ASSETS / name, format="PNG", optimize=True)


def book_excerpt_card(name: str, theme: str, quote: str, question: str) -> None:
    """Render a short verbatim excerpt supplied in the local chapter-2 note."""
    image = Image.new("RGB", (1200, 520), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 18, 520), fill="#247BA0")
    draw.text((70, 55), "문병로 교수의 메트릭 스튜디오 · 2장 시장관찰", fill="#6B7280", font=font(18, True))
    draw.text((70, 98), theme, fill="#1F2937", font=font(30, True))
    y = 178
    for line in textwrap.wrap(quote, width=31):
        excerpt_line = f"“{line}" if y == 178 else line
        draw.text((100, y), excerpt_line, fill="#1F2937", font=font(27, True))
        y += 48
    draw.line((70, 365, 1130, 365), fill="#D1D5DB", width=2)
    draw.text((70, 400), "이 문장에서 출발한 내 질문", fill="#E76F51", font=font(18, True))
    for index, line in enumerate(textwrap.wrap(question, width=52)):
        draw.text((70, 435 + index * 33), line, fill="#374151", font=font(18))
    save_png(image, name)


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
        '<text x="60" y="52" class="title">견고한 전략은 고립된 봉우리가 아니라 생존 영역이다</text>',
        '<text x="60" y="78" class="muted small">양의 비용 차감 CAGR · t &gt; 1.96 · MDD &gt; -60% · 평균 체결률 ≥ 80%를 모두 충족한 조합 수</text>',
    ]
    panel_positions = [(60, 130), (630, 130), (60, 410), (630, 410)]
    cell_w, cell_h = 48, 35
    for (signal, (x0, y0)) in zip(SIGNALS, panel_positions):
        svg.append(f'<text x="{x0}" y="{y0 - 18}" class="panel">{LABELS[signal]}</text>')
        for col, pct in enumerate(PCTS):
            x = x0 + 72 + col * cell_w
            svg.append(f'<text x="{x + 16}" y="{y0 - 3}" text-anchor="middle" class="axis muted">{int(pct * 100)}</text>')
        svg.append(f'<text x="{x0 + 264}" y="{y0 - 28}" text-anchor="middle" class="axis muted">유동성 유니버스 (%)</text>')
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
        svg.append(f'<text x="{x0 + 8}" y="{y0 + 78}" transform="rotate(-90 {x0 + 8} {y0 + 78})" class="axis muted">비용 배수</text>')
    svg.extend([
        '<line x1="60" y1="662" x2="1140" y2="662" stroke="#D1D5DB"/>',
        '<text x="60" y="692" class="note">읽는 법: 숫자는 보유 종목 수와 운용 규모를 바꾼 뒤에도 남은 견고 전략의 수다. 빈칸은 생존 전략이 없다는 뜻이다.</text>',
        '</svg>',
    ])
    save_svg("01_robustness_map.svg", "".join(svg))

    image = Image.new("RGB", (1200, 720), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "견고한 전략은 고립된 봉우리가 아니라 생존 영역이다", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "양의 비용 차감 CAGR · t > 1.96 · MDD > -60% · 평균 체결률 >= 80%를 모두 충족한 조합 수", fill="#6B7280", font=font(14))
    for signal, (x0, y0) in zip(SIGNALS, panel_positions):
        draw.text((x0, y0 - 21), LABELS[signal], fill="#1F2937", font=font(18, True))
        draw.text((x0 + 165, y0 - 39), "유동성 유니버스 (%)", fill="#6B7280", font=font(13))
        for col, pct in enumerate(PCTS):
            x = x0 + 72 + col * cell_w
            draw.text((x + 13, y0 - 4), str(int(pct * 100)), fill="#6B7280", font=font(12))
        for row_i, cost in enumerate(COSTS):
            y = y0 + row_i * cell_h
            draw.text((x0 + 31, y + 8), f"{cost:.1f}배", fill="#6B7280", font=font(12))
            for col, pct in enumerate(PCTS):
                x = x0 + 72 + col * cell_w
                count = counts[(signal, pct, cost)]
                color = COLORS[signal] if count else "#EEF1F4"
                draw.rounded_rectangle((x, y, x + 42, y + 29), radius=3, fill=color)
                if count:
                    draw.text((x + 17, y + 6), str(count), fill="white", font=font(13, True))
        draw.text((x0, y0 + 151), "비용 배수", fill="#6B7280", font=font(13))
    draw.line((60, 662, 1140, 662), fill="#D1D5DB", width=1)
    draw.text((60, 681), "읽는 법: 숫자는 보유 종목 수와 운용 규모를 바꾼 뒤에도 남은 견고 전략의 수다. 빈칸은 생존 전략이 없다는 뜻이다.", fill="#374151", font=font(14))
    save_png(image, "01_robustness_map.png")


def evidence_summary() -> None:
    report = json.loads((RESULTS / "reality_check_report.json").read_text(encoding="utf-8"))
    continents = list(csv.DictReader((RESULTS / "alpha_topology_continents.csv").open(encoding="utf-8")))
    best = report["best_node"]
    max_nodes = max(int(row["nodes"]) for row in continents)
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="560" viewBox="0 0 1200 560" role="img" aria-labelledby="title desc">',
        '<title id="title">Evidence summary and decision boundary</title>',
        '<desc id="desc">The figure summarises the two connected robust regions and shows that the strongest small-cap result passed a family-wise bootstrap check. The supplied delisted-stock universe is included in the raw price data and trading suspensions are screened at formation.</desc>',
        '<rect width="1200" height="560" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#1F2937}.muted{fill:#6B7280}.title{font-size:25px;font-weight:700}.sub{font-size:15px}.label{font-size:18px;font-weight:700}.value{font-size:26px;font-weight:700}.small{font-size:14px}.box{stroke:#D1D5DB;stroke-width:1.5}</style>',
        '<text x="60" y="52" class="title">이 실험이 말하는 것과 말하지 않는 것</text>',
        '<text x="60" y="78" class="muted sub">KRX 수정주가·거래량·시가총액 패널 · 1,728개 조합 · 월별 310개 관측치</text>',
        '<rect x="60" y="115" width="510" height="185" rx="8" fill="#F8FAFC" class="box"/>',
        '<text x="88" y="151" class="label">연결된 견고 전략 영역</text>',
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
            f'<text x="495" y="{y}" class="small">{nodes}개 조합</text>',
        ])
        y += 52
    svg.extend([
        '<rect x="630" y="115" width="510" height="185" rx="8" fill="#F8FAFC" class="box"/>',
        '<text x="658" y="151" class="label">가장 강한 검정 통과 조합</text>',
        f'<text x="658" y="192" class="value">t = {best["t_stat"]:.2f} · 가족단위 p = {report["family_wise_p_value"]:.3f}</text>',
        f'<text x="658" y="224" class="small">소형주 · 유동성 상위 90% · 50종목 · 1억 원 · 비용 0.5배</text>',
        f'<text x="658" y="254" class="small">비용 차감 CAGR {best["net_cagr"] * 100:.1f}% · MDD {best["mdd"] * 100:.1f}% · 평균 체결률 {best["mean_fill"] * 100:.1f}%</text>',
        '<rect x="60" y="342" width="1080" height="145" rx="8" fill="#FFF7ED" stroke="#FB923C" stroke-width="1.5"/>',
        '<text x="88" y="380" class="label">결론의 경계</text>',
        '<text x="88" y="402" class="small">상장폐지 원본 1,336코드는 수정주가에 모두 포함됐다. 거래정지 종목은 편입 시점에 제외했다.</text>',
        '<text x="88" y="432" class="small">그러나 다음 가격이 없는 433개 보유-월의 실제 결제값은 별도 사건 자료로 연결해야 한다.</text>',
        '<text x="88" y="462" class="small">부트스트랩은 ‘많이 돌려 우연히 최고 결과를 찾았다’는 설명을 기각한다. 경제적 원인은 아직 검정 대상이다.</text>',
        '<text x="60" y="528" class="muted small">출처: alpha_topology_nodes.csv · alpha_topology_continents.csv · reality_check_report.json</text>',
        '</svg>',
    ])
    save_svg("02_evidence_decision_boundary.svg", "".join(svg))

    image = Image.new("RGB", (1200, 560), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "이 실험이 말하는 것과 말하지 않는 것", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "KRX 수정주가·거래량·시가총액 패널 · 1,728개 조합 · 월별 310개 관측치", fill="#6B7280", font=font(15))
    draw.rounded_rectangle((60, 115, 570, 300), radius=8, fill="#F8FAFC", outline="#D1D5DB", width=2)
    draw.text((88, 137), "연결된 견고 전략 영역", fill="#1F2937", font=font(18, True))
    y = 181
    for row in continents:
        signal = row["signals"]
        nodes = int(row["nodes"])
        width = int(260 * nodes / max_nodes)
        draw.text((88, y), LABELS[signal], fill="#1F2937", font=font(14))
        draw.rounded_rectangle((220, y - 2, 480, y + 18), radius=3, fill="#E5E7EB")
        draw.rounded_rectangle((220, y - 2, 220 + width, y + 18), radius=3, fill=COLORS[signal])
        draw.text((495, y), f"{nodes}개 조합", fill="#1F2937", font=font(14))
        y += 52
    draw.rounded_rectangle((630, 115, 1140, 300), radius=8, fill="#F8FAFC", outline="#D1D5DB", width=2)
    draw.text((658, 137), "가장 강한 검정 통과 조합", fill="#1F2937", font=font(18, True))
    draw.text((658, 178), f"t = {best['t_stat']:.2f} · 가족단위 p = {report['family_wise_p_value']:.3f}", fill="#1F2937", font=font(24, True))
    draw.text((658, 216), "소형주 · 유동성 상위 90% · 50종목 · 1억 원 · 비용 0.5배", fill="#1F2937", font=font(14))
    draw.text((658, 247), f"비용 차감 CAGR {best['net_cagr'] * 100:.1f}% · MDD {best['mdd'] * 100:.1f}% · 평균 체결률 {best['mean_fill'] * 100:.1f}%", fill="#1F2937", font=font(14))
    draw.rounded_rectangle((60, 342, 1140, 487), radius=8, fill="#FFF7ED", outline="#FB923C", width=2)
    draw.text((88, 364), "결론의 경계", fill="#1F2937", font=font(18, True))
    draw.text((88, 392), "상장폐지 원본 1,336코드는 수정주가에 모두 포함됐다. 거래정지 종목은 편입 시점에 제외했다.", fill="#1F2937", font=font(14))
    draw.text((88, 422), "그러나 다음 가격이 없는 433개 보유-월의 실제 결제값은 별도 사건 자료로 연결해야 한다.", fill="#1F2937", font=font(14))
    draw.text((88, 452), "부트스트랩은 ‘많이 돌려 우연히 최고 결과를 찾았다’는 설명을 기각한다. 경제적 원인은 아직 검정 대상이다.", fill="#1F2937", font=font(14))
    draw.text((60, 518), "출처: alpha_topology_nodes.csv · alpha_topology_continents.csv · reality_check_report.json", fill="#6B7280", font=font(14))
    save_png(image, "02_evidence_decision_boundary.png")


def news_attention_chart() -> None:
    report = json.loads((RESULTS / "news_attention_raw_report.json").read_text(encoding="utf-8"))
    rows = report["summary"]
    labels = ["뉴스량 하위", "중간", "뉴스량 상위"]
    values = [row["mean_rank_ic_12m"] for row in rows]
    image = Image.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "뉴스량은 모멘텀 예측력을 가르지 못했다", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "원천 뉴스 248종목 · 2000.06~2025.04 · 뉴스량 3분위별 6개월 모멘텀의 평균 12개월 Rank IC", fill="#6B7280", font=font(15))
    x0, y_base, scale = 165, 480, 3400
    draw.line((130, y_base, 1130, y_base), fill="#9CA3AF", width=2)
    for tick in [0.00, 0.04, 0.08]:
        y = y_base - int(tick * scale)
        draw.line((130, y, 1130, y), fill="#E5E7EB", width=1)
        draw.text((78, y - 8), f"{tick:.02f}", fill="#6B7280", font=font(13))
    for index, (label, value, row) in enumerate(zip(labels, values, rows)):
        x = x0 + index * 310
        height = int(value * scale)
        color = "#247BA0" if index != 2 else "#E76F51"
        draw.rounded_rectangle((x, y_base - height, x + 150, y_base), radius=5, fill=color)
        draw.text((x + 24, y_base - height - 34), f"IC {value:.3f}", fill="#1F2937", font=font(18, True))
        draw.text((x + 22, y_base + 20), label, fill="#1F2937", font=font(15, True))
        draw.text((x + 13, y_base + 47), f"192개월 · 월평균 {row['mean_n']:.1f}종목", fill="#6B7280", font=font(13))
    diff = report["high_minus_low"]
    ci = diff["ci_95"]
    draw.text((60, 565), f"상위-하위 IC 차이 {diff['mean_rank_ic']:.3f}, 12개월 블록 부트스트랩 95% CI [{ci[0]:.3f}, {ci[1]:.3f}], p={diff['two_sided_sign_p']:.3f}.", fill="#374151", font=font(14))
    save_png(image, "03_observed_news_attention.png")


def consensus_cumulative_chart() -> None:
    rows = pd.read_csv(RESULTS / "consensus_benchmark_monthly.csv")
    values = (1 + rows.stability_return).cumprod().mul(100).tolist()
    component_values = (1 + rows.mean_component_return).cumprod().mul(100).tolist()
    image = Image.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "모델 합의는 더 안전한 포트폴리오를 만들지 못했다", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "모델 합의 상위 30종목과 48개 구성요소 전략의 동일가중 평균을 비교한 100원 기준 누적자산", fill="#6B7280", font=font(15))
    left, top, right, bottom = 100, 130, 1130, 490
    draw.line((left, bottom, right, bottom), fill="#9CA3AF", width=2)
    draw.line((left, top, left, bottom), fill="#9CA3AF", width=2)
    max_v = max(100.0, max(values), max(component_values))
    ticks = np.linspace(0, max_v, 5)
    for tick in ticks:
        y = bottom - int((tick / max_v) * (bottom - top))
        draw.line((left, y, right, y), fill="#E5E7EB", width=1)
        draw.text((45, y - 8), str(int(round(tick))), fill="#6B7280", font=font(13))
    points = []
    for index, value in enumerate(values):
        x = left + int(index * (right - left) / max(len(values) - 1, 1))
        y = bottom - int((value / max_v) * (bottom - top))
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill="#E76F51", width=3)
    component_points = []
    for index, value in enumerate(component_values):
        x = left + int(index * (right - left) / max(len(component_values) - 1, 1))
        y = bottom - int((value / max_v) * (bottom - top))
        component_points.append((x, y))
    if len(component_points) > 1:
        draw.line(component_points, fill="#247BA0", width=3)
    draw.text((810, 112), "주황: 모델 합의 상위 30종목", fill="#E76F51", font=font(13, True))
    draw.text((810, 136), "파랑: 48개 구성요소 전략 평균", fill="#247BA0", font=font(13, True))
    draw.text((100, 510), "2000", fill="#6B7280", font=font(13))
    draw.text((1040, 510), "2026", fill="#6B7280", font=font(13))
    draw.text((60, 565), f"모델 합의 최종 {values[-1]:.1f}, CAGR -12.9% · 구성요소 평균 최종 {component_values[-1]:.1f}, CAGR 5.8%. 표 수가 많아도 독립적 증거는 아니었다.", fill="#374151", font=font(14))
    save_png(image, "04_model_consensus_cumulative.png")


def failure_coherence_chart() -> None:
    rows = list(csv.DictReader((RESULTS / "model_failure_state_summary.csv").open(encoding="utf-8-sig")))
    image = Image.new("RGB", (1200, 650), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "동시에 실패한 신호가 많을수록 다음 달 시장수익률은 나빠졌다", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "0~4개 팩터 모델 실패 상태 뒤의 다음 달 동일가중 시장 평균수익률", fill="#6B7280", font=font(15))
    center_y, x0, bar_w, step, scale = 320, 190, 130, 190, 1200
    draw.line((120, center_y, 1130, center_y), fill="#6B7280", width=2)
    draw.text((72, center_y - 10), "0%", fill="#6B7280", font=font(13))
    for index, row in enumerate(rows):
        mean = float(row["mean"])
        x = x0 + index * step
        h = int(abs(mean) * scale)
        color = "#247BA0" if mean >= 0 else "#E76F51"
        coords = (x, center_y - h, x + bar_w, center_y) if mean >= 0 else (x, center_y, x + bar_w, center_y + h)
        draw.rounded_rectangle(coords, radius=5, fill=color)
        label_y = center_y - h - 32 if mean >= 0 else center_y + h + 7
        draw.text((x + 25, label_y), f"{mean * 100:.1f}%", fill="#1F2937", font=font(18, True))
        draw.text((x + 20, 535), f"{row['failure_coherence']}개 실패", fill="#1F2937", font=font(14, True))
        draw.text((x + 42, 560), f"n = {row['size']}", fill="#6B7280", font=font(13))
    draw.text((60, 605), "이 패턴은 가설 생성용이다. 3개·4개 실패 상태는 각각 n=2, n=5로 매매 규칙을 만들기에는 표본이 너무 작다.", fill="#374151", font=font(14))
    save_png(image, "05_model_failure_coherence.png")


def suspension_screen_chart() -> None:
    report = json.loads((RESULTS / "suspension_screen_audit_report.json").read_text(encoding="utf-8"))
    rows = {row["variant"]: row for row in report["summary"]}
    labels = [("기존 조합", "unfiltered", "#B7C0CC"), ("거래정지 제외", "suspension_screened", "#247BA0")]
    image = Image.new("RGB", (1200, 560), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 32), "거래정지 상태를 실제 선택 규칙에 넣어도 소형주 결과는 남았다", fill="#1F2937", font=font(25, True))
    draw.text((60, 63), "유동성 상위 90% · 소형주 50종목 · 1억 원 · 비용 0.5배", fill="#6B7280", font=font(15))
    base_y, scale = 410, 550
    draw.line((130, base_y, 1100, base_y), fill="#9CA3AF", width=2)
    for tick in [0, .2, .4, .6]:
        y = base_y - int(tick * scale)
        draw.line((130, y, 1100, y), fill="#E5E7EB", width=1)
        draw.text((65, y - 8), f"{tick * 100:.0f}%", fill="#6B7280", font=font(13))
    for index, (label, key, color) in enumerate(labels):
        row = rows[key]
        x = 280 + index * 360
        h = int(row["cagr"] * scale)
        draw.rounded_rectangle((x, base_y - h, x + 180, base_y), radius=6, fill=color)
        draw.text((x + 35, base_y - h - 34), f"CAGR {row['cagr'] * 100:.1f}%", fill="#1F2937", font=font(20, True))
        draw.text((x + 45, base_y + 20), label, fill="#1F2937", font=font(16, True))
        draw.text((x + 24, base_y + 48), f"t={row['t_stat']:.2f} · MDD {row['mdd'] * 100:.1f}%", fill="#6B7280", font=font(14))
    draw.text((60, 515), f"원본 거래정지 패널에서 비정상 상태 {report['suspension_flag_rows']:,}건, {report['flagged_tickers']:,}개 종목을 선택 시점에 제외했다.", fill="#374151", font=font(14))
    save_png(image, "10_suspension_screened_smallcap.png")


def main() -> None:
    with (RESULTS / "alpha_topology_nodes.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    topology_map(rows)
    evidence_summary()
    news_attention_chart()
    consensus_cumulative_chart()
    failure_coherence_chart()
    suspension_screen_chart()
    book_excerpt_card(
        "09_book_excerpt_liquidity.png",
        "유동성이 미치는 영향",
        "유동성 제한이 수익률에 미치는 영향은 포트폴리오와 그 운영 전략에 따라 다르므로 불변의 법칙은 없다.",
        "유동성 상위 80%는 누구에게 최적인가?",
    )
    book_excerpt_card(
        "06_book_excerpt_popularity.png",
        "인기주와 비인기주의 예후",
        "다른 특별한 이유 없이 인기가 있다는 것만으로 종목을 선택하는 것은 확률적으로 틀린 것이라는 것을 알 수 있다.",
        "거래회전율은 정말 투자자의 관심을 측정하는가?",
    )
    book_excerpt_card(
        "07_book_excerpt_strategy.png",
        "패턴과 운용 전략의 검증",
        "계량 투자의 관점에서는 이들 중 어떤 것도 수치로 검증된 결과가 없다면 받아들여서는 안 된다.",
        "여러 모델이 동시에 고른 종목은 독립된 증거를 얻은 것인가?",
    )
    book_excerpt_card(
        "08_book_excerpt_mixed_results.png",
        "상반된 시장 관찰",
        "같은 시기를 놓고도 이렇게 상반된 결과가 나온다.",
        "시장의 상태를 가격 방향이 아니라 모델의 동시 실패로 볼 수 있는가?",
    )


if __name__ == "__main__":
    main()
