"""Build the illustrated Word version of Metric Studio chapter 2, part 1."""

from docx import Document

import build_parts_02_04_docx as packet


packet.OUTPUT = packet.ROOT / "deliverables" / "문병로_교수의_메트릭_스튜디오_02_1부_게시용.docx"
packet.IMAGE_MAP = {
    "01_알파는_봉우리인가_대륙인가.md": [
        ("09_book_excerpt_liquidity.png", "책 2장 발췌 - 유동성 유니버스와 슬리피지"),
        ("01_robustness_map.png", "그림 1. 유동성·비용 조건별로 살아남은 전략 조합"),
        ("02_evidence_decision_boundary.png", "그림 2. 다중검정 보정 뒤의 의사결정 경계"),
        ("10_suspension_screened_smallcap.png", "그림 3. 거래정지 편입 제외 뒤 소형주 전략 성과"),
    ]
}


def main():
    packet.OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    packet.style_document(doc)
    packet.add_cover(
        doc,
        subtitle_text="2장 시장관찰 | ①\n유동성 상위 80%는 누구에게 최적인가",
        description="책의 유동성 조건을 그대로 반복하지 않고, 비용·규모·유동성의\n작은 변화에도 남는 패턴만 알파로 부를 수 있는지 검증한 연구 기록",
    )
    packet.add_article(doc, "01_알파는_봉우리인가_대륙인가.md")
    doc.core_properties.title = "문병로 교수의 메트릭 스튜디오 02 | 2장 시장관찰 ①"
    doc.core_properties.author = "beneficial5"
    doc.core_properties.subject = "한국 주식 데이터 기반 연구 노트"
    doc.save(packet.OUTPUT)
    print(packet.OUTPUT)


if __name__ == "__main__":
    main()
