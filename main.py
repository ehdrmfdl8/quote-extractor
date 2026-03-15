"""
quote-extractor: 견적서 PDF → CSV/Excel 자동 추출기
사용법:
  uv run main.py <PDF경로> [옵션]

옵션:
  --append        기존 CSV/Excel에 이어 붙이기 (누적 모드)
  --csv-only      CSV만 출력
  --excel-only    Excel만 출력
  --out <경로>    출력 파일 경로 지정 (확장자 제외)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pdf_reader import extract_for_ai
from ai_analyzer import analyze_pdf_text
from csv_writer import save_to_csv, save_to_excel, load_config
from web_searcher import enrich_records


def parse_args():
    parser = argparse.ArgumentParser(description="견적서 PDF → CSV/Excel 추출기")
    parser.add_argument("pdf", help="처리할 PDF 파일 경로")
    parser.add_argument("--append", action="store_true", help="기존 파일에 이어 붙이기 (누적 모드)")
    parser.add_argument("--csv-only", action="store_true", help="CSV만 출력")
    parser.add_argument("--excel-only", action="store_true", help="Excel만 출력")
    parser.add_argument("--out", default=None, help="출력 파일 경로 (확장자 제외)")
    parser.add_argument("--no-enrich", action="store_true", help="웹 검색 보완 건너뛰기")
    return parser.parse_args()


def run(pdf_path: str, append: bool = False, csv_only: bool = False, excel_only: bool = False, out: str = None, web_enrich: bool = True):
    config = load_config()
    columns = config["columns"]
    model = config.get("ai_model", "gemini-2.5-flash")

    pdf_name = Path(pdf_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_out = out or f"output/{pdf_name}_{timestamp}"

    # 1단계: PDF 텍스트 추출
    print(f"[1/3] PDF 텍스트 추출 중: {pdf_path}")
    extracted = extract_for_ai(pdf_path)

    # 2단계: AI 분석
    print(f"[2/4] AI 분석 중 (모델: {model})...")
    records = analyze_pdf_text(extracted, columns, model)
    print(f"      → {len(records)}개 제품 추출 완료")

    # 3단계: 웹 검색으로 빈 필드 보완
    if web_enrich:
        print(f"[3/4] 웹 검색으로 빈 필드 보완 중...")
        def cb(cur, tot, msg):
            print(f"      {msg}")
        records = enrich_records(records, columns, model, progress_callback=cb)
    else:
        print(f"[3/4] 웹 검색 건너뜀 (--no-enrich)")

    # 4단계: 파일 저장
    print(f"[4/4] 파일 저장 중...")
    saved = []
    if not excel_only:
        path = save_to_csv(records, columns, f"{base_out}.csv", append=append)
        saved.append(path)
    if not csv_only:
        path = save_to_excel(records, columns, f"{base_out}.xlsx", append=append)
        saved.append(path)

    print(f"\n완료! 저장된 파일:")
    for p in saved:
        print(f"  {p}")

    return records


if __name__ == "__main__":
    args = parse_args()
    run(
        pdf_path=args.pdf,
        append=args.append,
        csv_only=args.csv_only,
        excel_only=args.excel_only,
        out=args.out,
        web_enrich=not args.no_enrich,
    )
