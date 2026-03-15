import pdfplumber
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> dict:
    """
    PDF에서 텍스트와 표(table)를 추출.
    반환값: {"text": str, "tables": list[list[list]], "page_count": int}
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    all_text = []
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            # 표 추출
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    all_tables.append(table)

            # 텍스트 추출 (표 영역 제외하면 더 깔끔하지만 일단 전체 추출)
            text = page.extract_text()
            if text:
                all_text.append(f"[페이지 {i+1}]\n{text}")

    return {
        "text": "\n\n".join(all_text),
        "tables": all_tables,
        "page_count": page_count,
    }


def format_tables_as_text(tables: list) -> str:
    """표 데이터를 AI가 읽기 쉬운 텍스트 형식으로 변환"""
    result = []
    for t_idx, table in enumerate(tables):
        result.append(f"[표 {t_idx + 1}]")
        for row in table:
            cleaned = [cell.strip() if cell else "" for cell in row]
            result.append(" | ".join(cleaned))
        result.append("")
    return "\n".join(result)


def extract_for_ai(pdf_path: str) -> str:
    """AI 분석용으로 텍스트 + 표를 합쳐서 반환"""
    data = extract_text_from_pdf(pdf_path)

    parts = []
    if data["text"]:
        parts.append("=== 본문 텍스트 ===")
        parts.append(data["text"])

    if data["tables"]:
        parts.append("\n=== 표 데이터 ===")
        parts.append(format_tables_as_text(data["tables"]))

    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "Data/견적서(260224)-켈젠.pdf"
    print(f"PDF 분석 중: {pdf_path}\n")

    data = extract_text_from_pdf(pdf_path)
    print(f"총 페이지 수: {data['page_count']}")
    print(f"추출된 표 수: {len(data['tables'])}")
    print("\n--- 추출된 텍스트 ---")
    print(data["text"])

    if data["tables"]:
        print("\n--- 추출된 표 ---")
        print(format_tables_as_text(data["tables"]))
