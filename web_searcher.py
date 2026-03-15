"""
web_searcher.py — 제품명/Cat.No.로 제조사 사이트를 검색하여 빈 필드 자동 채우기

흐름:
  1. 빈 필드가 있는 레코드 감지
  2. Cat.No. → 제조사 URL 직접 접근 (Thermo Fisher, Sigma-Aldrich 등) — 병렬
  3. 크롤링 실패 시 DuckDuckGo 검색으로 대체
  4. Gemini AI로 빈 필드 파싱
  5. 원본 레코드에 병합
"""

import os
import time
import json
import re
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MAX_PAGE_CHARS = 4000
REQUEST_TIMEOUT = 5       # 10 → 5초로 단축
SEARCH_DELAY = 0.5        # 1.5 → 0.5초로 단축
MAX_WORKERS = 5           # 동시 처리 제품 수

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SKIP_FIELDS = {"No.", "주문일자", "입고일자", "용도", "Lot No.", "위치", "비고"}

VENDOR_URL_TEMPLATES = [
    ("https://www.thermofisher.com/order/catalog/product/{cat}", None),
    ("https://www.sigmaaldrich.com/KR/ko/product/sigma/{cat_lower}", None),
    ("https://www.sigmaaldrich.com/KR/ko/product/aldrich/{cat_lower}", None),
    ("https://www.abcam.com/products/{cat_lower}", None),
    ("https://www.bio-rad.com/en-kr/sku/{cat}", None),
]

# Gemini API 동시 호출 제한용 세마포어 (분당 15회 대비)
_ai_semaphore = threading.Semaphore(3)


def _needs_fill(record: dict, columns: list[str]) -> list[str]:
    return [
        col for col in columns
        if col not in SKIP_FIELDS and not record.get(col)
    ]


def _fetch_text(url: str) -> str:
    """URL 크롤링 후 텍스트 반환"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text[:MAX_PAGE_CHARS]
    except Exception:
        return ""


def _fetch_vendor_url(url: str) -> tuple[str, str]:
    """단일 벤더 URL 크롤링. (텍스트, url) 반환"""
    text = _fetch_text(url)
    if len(text) > 200:
        return f"[출처: {url}]\n{text}", url
    return "", ""


def _search_vendor_direct(cat_no: str) -> tuple[str, str]:
    """Cat.No.로 제조사 URL들을 병렬로 시도. (웹텍스트, 사용된URL) 반환"""
    if not cat_no:
        return "", ""
    cat_clean = cat_no.strip().replace(" ", "")
    urls = [
        template.format(cat=cat_clean, cat_lower=cat_clean.lower())
        for template, _ in VENDOR_URL_TEMPLATES
    ]

    # 벤더 URL을 병렬로 동시 요청
    with ThreadPoolExecutor(max_workers=len(urls)) as executor:
        futures = {executor.submit(_fetch_vendor_url, url): url for url in urls}
        for future in as_completed(futures):
            text, url = future.result()
            if text:
                # 첫 번째 성공 결과 즉시 반환, 나머지 취소
                for f in futures:
                    f.cancel()
                return text, url

    return "", ""


def _search_duckduckgo(query: str) -> tuple[str, str]:
    """DuckDuckGo로 검색 후 상위 결과 크롤링. (웹텍스트, 사용된URL) 반환"""
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=3)
        if not results:
            return "", ""

        combined = ""
        first_url = ""

        # 검색 결과 snippet 먼저 모으기
        urls_to_crawl = []
        for r in results:
            url = r.get("href", "")
            body = r.get("body", "")
            if body:
                combined += f"[출처: {url}]\n{body[:500]}\n"
                if not first_url:
                    first_url = url
            if url:
                urls_to_crawl.append(url)

        # 페이지 본문을 병렬 크롤링
        with ThreadPoolExecutor(max_workers=len(urls_to_crawl)) as executor:
            futures = {executor.submit(_fetch_text, url): url for url in urls_to_crawl}
            for future in as_completed(futures):
                page_text = future.result()
                if page_text:
                    combined += page_text + "\n"
                if len(combined) > MAX_PAGE_CHARS:
                    break

        time.sleep(SEARCH_DELAY)
        return combined[:MAX_PAGE_CHARS], first_url
    except Exception:
        return "", ""


def _fill_with_ai(record: dict, empty_fields: list[str], web_text: str, model: str) -> dict:
    """AI로 빈 필드 채우기 (세마포어로 동시 호출 제한)"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not web_text.strip():
        return {}

    fields_str = ", ".join(f'"{f}"' for f in empty_fields)
    product_info = json.dumps(
        {k: v for k, v in record.items() if v}, ensure_ascii=False
    )

    prompt = f"""
아래는 제품 정보와 웹 검색으로 찾은 제품 관련 텍스트입니다.
이 텍스트에서 비어있는 필드의 값을 찾아 JSON으로 반환하세요.

## 현재 알고 있는 제품 정보
{product_info}

## 채워야 할 빈 필드
{fields_str}

## 컬럼별 추출 기준
- "브랜드": 제조사 브랜드명 (예: Thermo Fisher, Sigma-Aldrich, Abcam)
- "입고단위": 제품 용량/규격 (예: 500ml, 100ug, 1kit)
- "보관 온도": 보관 조건 (예: -20°C, 4°C, RT)
- "대리점": 판매 대리점명 (모르면 null)

## 웹 검색 텍스트
{web_text}

## 규칙
- 텍스트에서 명확히 확인되는 값만 채우세요.
- 불확실하면 null로 남기세요.
- JSON만 반환하세요. 설명 없이.

## 출력 예시
{{"브랜드": "Thermo Fisher", "입고단위": "500ml", "보관 온도": "4°C"}}
"""

    with _ai_semaphore:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=512,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            text = response.text.strip()
            text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return {}


def _enrich_single(
    idx: int,
    record: dict,
    columns: list[str],
    model: str,
) -> tuple[int, dict, int, str]:
    """단일 레코드 보완 (스레드에서 실행). (원본인덱스, 결과레코드, 채운수, 메시지) 반환"""
    empty_fields = _needs_fill(record, columns)
    product_name = record.get("제품명", "")
    cat_no = record.get("Cat. No.", "")

    if not empty_fields:
        return idx, record, 0, f"빈 필드 없음"

    # 1순위: Cat.No.로 제조사 URL 병렬 접근
    web_text, source_url = "", ""
    if cat_no:
        web_text, source_url = _search_vendor_direct(cat_no)

    # 2순위: DuckDuckGo 검색
    if not web_text:
        query = f"{product_name} {cat_no} specification datasheet".strip()
        web_text, source_url = _search_duckduckgo(query)

    # AI로 빈 필드 채우기
    filled = {}
    if web_text:
        filled = _fill_with_ai(record, empty_fields, web_text, model)

    # 병합
    new_record = dict(record)
    filled_count = 0
    for field, value in filled.items():
        if field in columns and not new_record.get(field) and value:
            new_record[field] = value
            filled_count += 1

    # 비고에 출처 URL 추가
    if filled_count > 0 and source_url and "비고" in columns:
        existing = new_record.get("비고") or ""
        source_note = f"[웹검색출처] {source_url}"
        new_record["비고"] = f"{existing} | {source_note}".strip(" |") if existing else source_note

    msg = f"{filled_count}개 필드 보완" if web_text else "검색 결과 없음"
    return idx, new_record, filled_count, msg


def enrich_records(
    records: list[dict],
    columns: list[str],
    model: str = "gemini-3-flash-preview",
    progress_callback=None,
) -> list[dict]:
    """
    빈 필드가 있는 레코드에 대해 웹 검색으로 정보 보완 (병렬 처리).

    Args:
        records: AI가 추출한 레코드 리스트
        columns: 컬럼 목록
        model: Gemini 모델명
        progress_callback: (current, total, message) 콜백 (UI 진행 표시용)

    Returns:
        보완된 레코드 리스트 (순서 유지)
    """
    total = len(records)
    results = [None] * total
    completed = 0
    lock = threading.Lock()

    def on_done(future):
        nonlocal completed
        idx, new_record, _, msg = future.result()
        results[idx] = new_record
        product_name = records[idx].get("제품명", "")
        with lock:
            completed += 1
            cur = completed
        if progress_callback:
            progress_callback(cur, total, f"[{cur}/{total}] {product_name[:30]} - {msg}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i, record in enumerate(records):
            f = executor.submit(_enrich_single, i, record, columns, model)
            f.add_done_callback(on_done)
            futures.append(f)

        # 모든 작업 완료 대기
        for f in futures:
            f.result()

    return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from csv_writer import load_config

    config = load_config()
    columns = config["columns"]
    model = config.get("ai_model", "gemini-3-flash-preview")

    test_records = [
        {
            "No.": 1, "주문일자": "2026-02-24", "입고일자": None, "대리점": "지앤바이오",
            "용도": None, "제품명": "Nuclease-Free Water (not DEPC-Treated)",
            "Cat. No.": "AM9932", "브랜드": None, "수량": 4, "입고단위": None,
            "Lot No.": None, "보관 온도": None, "위치": None, "비고": None,
        },
        {
            "No.": 2, "주문일자": "2026-02-24", "입고일자": None, "대리점": "지앤바이오",
            "용도": None, "제품명": "HEPES (1M)", "Cat. No.": "15630080",
            "브랜드": None, "수량": 1, "입고단위": None,
            "Lot No.": None, "보관 온도": None, "위치": None, "비고": None,
        },
    ]

    def cb(cur, tot, msg):
        print(msg)

    import time as _time
    start = _time.time()
    result = enrich_records(test_records, columns, model, progress_callback=cb)
    print(f"\n소요시간: {_time.time() - start:.1f}초")
    print(json.dumps(result, ensure_ascii=False, indent=2))
