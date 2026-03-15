import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def save_to_csv(
    records: list[dict],
    columns: list[str],
    output_path: str = "output/result.csv",
    append: bool = False,
) -> str:
    """
    추출된 레코드를 CSV로 저장.
    append=True 이면 기존 파일에 이어 붙임 (누적 모드).
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # columns 순서에 맞게 정렬, 없는 키는 빈 문자열
    rows = []
    for rec in records:
        row = {col: rec.get(col, "") for col in columns}
        rows.append(row)

    file_exists = Path(output_path).exists()
    mode = "a" if append and file_exists else "w"
    write_header = not (append and file_exists)

    with open(output_path, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    action = "추가" if (append and file_exists) else "생성"
    print(f"CSV {action}: {output_path} ({len(rows)}행)")
    return output_path


def save_to_excel(
    records: list[dict],
    columns: list[str],
    output_path: str = "output/result.xlsx",
    append: bool = False,
    sheet_name: str = "견적서",
) -> str:
    """
    추출된 레코드를 Excel로 저장.
    append=True 이면 기존 파일의 시트 끝에 이어 붙임.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    rows = [{col: rec.get(col, None) for col in columns} for rec in records]
    new_df = pd.DataFrame(rows, columns=columns)

    if append and Path(output_path).exists():
        existing_df = pd.read_excel(output_path, sheet_name=sheet_name)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        combined_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 컬럼 너비 자동 조절
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 50)

    action = "추가" if (append and Path(output_path).exists()) else "생성"
    print(f"Excel {action}: {output_path} ({len(new_df)}행 추가, 총 {len(combined_df)}행)")
    return output_path


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys

    config = load_config()
    columns = config["columns"]

    # 테스트: debug_parsed.json 또는 인자로 받은 JSON 파일 사용
    json_path = sys.argv[1] if len(sys.argv) > 1 else "output/result.json"
    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_to_csv(records, columns, f"output/result_{timestamp}.csv")
    save_to_excel(records, columns, f"output/result_{timestamp}.xlsx")
