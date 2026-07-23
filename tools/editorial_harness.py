"""Regression checks for the Metric Studio chapter-two blog series.

This is deliberately an editorial harness, not a grammar scorer.  It prevents
the failures that matter for this series: shrinking a long post into a summary,
changing an agreed title, losing the research-to-personal-project bridge, and
putting discarded dashboard-card graphics back into a post.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "blog_drafts"

POSTS = {
    "01_알파는_봉우리인가_대륙인가.md": {
        "title": "# 『문병로 교수의 메트릭 스튜디오』 2장 「시장관찰」 1. 알파는 단일 최적값인가, 안정적인 구간인가",
        "min_words": 4000,
        "anchors": ["금융인공지능 프로젝트", "내가 만든 실험", "4-1. 전략 자체에서 바꾼 것", "4-2. 비용과 체결은 어떻게 넣었는가", "4-3. 무엇을 통과해야 남는 조합으로 볼 것인가", "GitHub에서 확인할 수 있는 것"],
        "allowed_images": {
            "book_figure_18_liquidity_universe_recreated.png",
            "11_participation_sensitivity.png",
            "01a_signal_stability.png",
            "01b_liquidity_stability.png",
        },
    },
    "02_거래회전율은_관심이_아니었다.md": {
        "title": "# 『문병로 교수의 메트릭 스튜디오』 2장 「시장관찰」 2. 거래회전율은 관심을 측정하는가",
        "min_words": 2100,
        "anchors": ["이전 프로젝트", "뉴스", "GitHub에서 확인할 수 있는 것"],
        "allowed_images": {"03_observed_news_attention.png"},
    },
    "03_모델합의는_알파가_아니었다.md": {
        "title": "# 『문병로 교수의 메트릭 스튜디오』 2장 「시장관찰」 3. 여러 모델의 합의는 증거를 늘리는가",
        "min_words": 2100,
        "anchors": ["이전 프로젝트", "독립", "GitHub에서 확인할 수 있는 것"],
        "allowed_images": {"04_model_consensus_cumulative.png"},
    },
    "04_시장은_신호의_실패방식으로_드러난다.md": {
        "title": "# 『문병로 교수의 메트릭 스튜디오』 2장 「시장관찰」 4. 시장 상태는 모델의 공동 실패로 읽을 수 있을까",
        "min_words": 2100,
        "anchors": ["모멘텀", "반전", "GitHub에서 확인할 수 있는 것"],
        "allowed_images": {"05_model_failure_coherence.png"},
    },
}

# These were explicitly rejected: card summaries and dense dashboard graphics.
FORBIDDEN_IMAGES = {
    "02_evidence_decision_boundary.png",
    "10_suspension_screened_smallcap.png",
    "12_stop_loss_daily_close_audit.png",
    "01_robustness_map.png",
}

# Expressions explicitly rejected in editorial review.  These checks protect
# the agreed scope of post 1: liquidity/capacity, not a stop-loss sidebar.
FORBIDDEN_TEXT = {
    "01_알파는_봉우리인가_대륙인가.md": [
        "결과를 신뢰하지 않기 위해 다시 한 일",
        "손절매는 손실을 막는 규칙인가",
    ],
}


def words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def image_names(text: str) -> set[str]:
    return set(re.findall(r"blog_assets/([^`\]]+\.(?:png|jpg|jpeg|svg))", text))


def check_post(filename: str, rule: dict[str, object]) -> list[str]:
    text = (DRAFTS / filename).read_text(encoding="utf-8")
    errors: list[str] = []
    first_line = text.splitlines()[0] if text else ""

    if "title" in rule and first_line != rule["title"]:
        errors.append(f"제목 변경: {first_line!r}")
    if "title_prefix" in rule and not first_line.startswith(str(rule["title_prefix"])):
        errors.append(f"연재 제목 접두어 누락: {first_line!r}")
    if words(text) < int(rule["min_words"]):
        errors.append(f"분량 부족: {words(text)}어절 < {rule['min_words']}어절")
    for anchor in rule["anchors"]:
        if str(anchor) not in text:
            errors.append(f"필수 전개 누락: {anchor}")

    used = image_names(text)
    bad = used & FORBIDDEN_IMAGES
    if bad:
        errors.append("금지된 카드형 이미지: " + ", ".join(sorted(bad)))
    extra = used - set(rule["allowed_images"])
    if extra:
        errors.append("허용 목록 밖 이미지: " + ", ".join(sorted(extra)))
    for phrase in FORBIDDEN_TEXT.get(filename, []):
        if phrase in text:
            errors.append(f"제외하기로 한 문구가 다시 들어감: {phrase}")
    return errors


def main() -> int:
    all_errors: list[str] = []
    for filename, rule in POSTS.items():
        errors = check_post(filename, rule)
        if errors:
            all_errors.extend(f"{filename}: {error}" for error in errors)
        else:
            print(f"PASS {filename}")
    if all_errors:
        print("\n".join(all_errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
