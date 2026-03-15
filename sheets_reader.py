import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_sheets_service(credentials_file: str):
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def get_columns_from_sheet(config: dict) -> list[str]:
    """구글 시트의 헤더 행을 읽어서 컬럼 목록 반환"""
    gs = config["google_sheets"]
    service = get_sheets_service(gs["credentials_file"])

    sheet = service.spreadsheets()
    range_name = f"{gs['sheet_name']}!{gs['header_row']}:{gs['header_row']}"
    result = sheet.values().get(
        spreadsheetId=gs["sheet_id"],
        range=range_name,
    ).execute()

    values = result.get("values", [])
    if not values:
        print("헤더 행을 찾을 수 없습니다.")
        return []

    columns = [col.strip() for col in values[0] if col.strip()]
    return columns


def update_config_columns(columns: list[str], config_path: str = "config.json"):
    """읽어온 컬럼을 config.json에 저장"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["columns"] = columns

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"config.json 업데이트 완료: {columns}")


def get_sheet_names(config: dict) -> list[str]:
    """스프레드시트의 모든 시트 이름 반환"""
    gs = config["google_sheets"]
    service = get_sheets_service(gs["credentials_file"])
    meta = service.spreadsheets().get(spreadsheetId=gs["sheet_id"]).execute()
    return [s["properties"]["title"] for s in meta["sheets"]]


if __name__ == "__main__":
    config = load_config()

    # 시트 이름 확인
    sheet_names = get_sheet_names(config)
    print(f"스프레드시트 내 시트 목록: {sheet_names}")

    # config의 시트 이름을 첫 번째 시트로 자동 설정
    if sheet_names and config["google_sheets"]["sheet_name"] not in sheet_names:
        config["google_sheets"]["sheet_name"] = sheet_names[0]
        print(f"시트 이름을 '{sheet_names[0]}'으로 자동 설정합니다.")

    columns = get_columns_from_sheet(config)

    if columns:
        print(f"\n발견된 컬럼 ({len(columns)}개):")
        for i, col in enumerate(columns, 1):
            print(f"  {i}. {col}")
        update_config_columns(columns)
    else:
        print("컬럼을 읽지 못했습니다. 시트 공유 여부를 확인해주세요.")
