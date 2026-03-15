import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(".env 파일에 GEMINI_API_KEY가 없습니다.")
    return genai.Client(api_key=api_key)


def build_prompt(extracted_text: str, columns: list[str]) -> str:
    columns_str = ", ".join(f'"{c}"' for c in columns)
    return f"""
당신은 한국어 견적서에서 물품 정보를 추출하는 전문가입니다.

아래는 견적서 PDF에서 추출한 텍스트와 표 데이터입니다.
이 데이터에서 각 물품(제품)의 정보를 추출하여 JSON 배열로 반환해주세요.

## 추출할 컬럼
{columns_str}

## 추출 규칙
1. 각 물품을 JSON 배열의 원소 하나로 표현하세요.
2. 해당 컬럼 정보가 없으면 null로 남기세요.
3. 금액/숫자에 공백이 포함된 경우(예: "5 96,000") 공백을 제거하여 올바른 숫자로 복원하세요 (예: "596,000").
4. 컬럼 매핑 기준:
   - "No." → 순번 (1부터 시작)
   - "주문일자" → 견적서 날짜 (YYYY-MM-DD 형식)
   - "입고일자" → null (견적서에는 없음)
   - "대리점" → 공급업체/판매처 상호명
   - "용도" → null (견적서에는 없음)
   - "제품명" → 제품명 (원문 그대로)
   - "Cat. No." → 제품번호/카탈로그 번호
   - "브랜드" → 브랜드명 (제품명이나 제품번호에서 유추 가능하면 기입, 없으면 null)
   - "수량" → 수량 (숫자만)
   - "입고단위" → 규격/용량 (예: 1000ml, 100g)
   - "Lot No." → null (견적서에는 없음)
   - "보관 온도" → null (견적서에는 없음)
   - "위치" → null (견적서에는 없음)
   - "비고" → 납기, 특이사항 등 (제품별 비고가 있으면 기입)
5. 합계/소계/부가세 행은 제외하세요.
6. 반드시 JSON 배열만 반환하세요. 설명 텍스트 없이 JSON만 출력하세요.

## 견적서 데이터
{extracted_text}

## 출력 형식 예시
[
  {{
    "No.": 1,
    "주문일자": "2026-02-24",
    "입고일자": null,
    "대리점": "지앤바이오",
    "용도": null,
    "제품명": "Nuclease-Free Water (not DEPC-Treated)",
    "Cat. No.": "AM9932",
    "브랜드": null,
    "수량": 4,
    "입고단위": "1000ml",
    "Lot No.": null,
    "보관 온도": null,
    "위치": null,
    "비고": null
  }}
]
"""


def extract_json_from_response(text: str) -> list[dict]:
    """AI 응답에서 JSON 배열 파싱 (마크다운 코드블록 처리 포함)"""
    # ```json ... ``` 코드블록 제거
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # 1) 전체가 JSON 배열인 경우
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 2) [ ... ] 블록 찾아서 파싱
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            # 원인 파악을 위해 오류 위치 주변 텍스트 출력
            snippet = text[start:][max(0, e.pos - 30) : e.pos + 30]
            raise ValueError(
                f"JSON 파싱 실패 (pos={e.pos}): {e.msg}\n"
                f"문제 위치 근처: {repr(snippet)}"
            ) from e

    raise ValueError(f"JSON 배열을 찾을 수 없습니다.\n응답 첫 200자: {repr(text[:200])}")


def analyze_pdf_text(extracted_text: str, columns: list[str], model: str = "gemini-2.5-flash") -> list[dict]:
    """
    추출된 PDF 텍스트를 AI로 분석하여 구조화된 데이터 반환
    """
    client = get_client()
    prompt = build_prompt(extracted_text, columns)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=16384,
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # thinking 비활성화
        ),
    )

    raw_text = response.text
    return extract_json_from_response(raw_text)


if __name__ == "__main__":
    import sys
    from pdf_reader import extract_for_ai

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "Data/견적서(260224)-켈젠.pdf"

    # config에서 컬럼 로드
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    columns = config["columns"]
    model = config.get("ai_model", "gemini-2.5-flash")

    print(f"PDF 텍스트 추출 중...")
    extracted = extract_for_ai(pdf_path)

    print(f"AI 분석 중 (모델: {model})...")
    results = analyze_pdf_text(extracted, columns, model)

    print(f"\n추출된 제품 수: {len(results)}개\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))
