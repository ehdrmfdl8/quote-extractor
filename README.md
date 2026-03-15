# 📄 견적서 자동 추출기 (quote-extractor)

한국어 견적서 PDF에서 물품 정보를 AI로 자동 추출하여 CSV/Excel로 저장하는 도구입니다.

**지원 기능**
- PDF에서 제품명, Cat. No., 수량, 입고단위, 날짜, 대리점 등 자동 추출
- Google Gemini AI 기반 한국어 견적서 이해
- CSV / Excel 동시 출력
- 웹 UI (브라우저에서 PDF 드래그 앤 드롭)
- Google Sheets 헤더를 읽어 추출 컬럼 자동 설정

---

## 사전 준비

### 1. Python 설치

Python 3.12 이상이 필요합니다.
[python.org/downloads](https://www.python.org/downloads/)에서 최신 버전을 설치하세요.

### 2. uv 설치

의존성 관리 도구입니다. 터미널(명령 프롬프트)에서 아래를 실행하세요.

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Mac / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. 저장소 다운로드

```bash
git clone https://github.com/your-username/quote-extractor.git
cd quote-extractor
```

### 4. 의존성 설치

```bash
uv sync
```

---

## 설정

### A. Gemini API 키 발급

1. [aistudio.google.com](https://aistudio.google.com) 접속 (Google 계정 로그인)
2. 좌측 메뉴 **"Get API key"** → **"Create API key in new project"**
3. 발급된 키 복사

### B. `.env` 파일 생성

프로젝트 폴더에 `.env` 파일을 만들고 아래 내용을 입력합니다.

```
GEMINI_API_KEY=여기에_발급받은_키_붙여넣기
```

### C. Google Sheets 연결 (선택)

추출할 컬럼을 구글 시트의 헤더에서 자동으로 읽어오는 기능입니다.
사용하지 않으면 `config.json`의 `columns` 항목을 직접 편집하면 됩니다.

<details>
<summary>구글 시트 연결 방법 보기</summary>

**서비스 계정 생성**
1. [console.cloud.google.com](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성 → **API 및 서비스** → **라이브러리** → `Google Sheets API` 활성화
3. **사용자 인증 정보** → **서비스 계정 만들기**
4. **키 탭** → **새 키 만들기(JSON)** → 다운로드한 파일을 프로젝트 폴더에 저장

**시트 공유**
- 다운로드한 JSON 파일에서 `"client_email"` 값을 복사
- 분석할 구글 시트를 해당 이메일로 공유 (편집자 권한)

**`config.json` 수정**
```json
{
  "google_sheets": {
    "credentials_file": "다운로드한_키파일명.json",
    "sheet_id": "구글시트_URL에서_추출한_ID",
    "sheet_name": "시트이름",
    "header_row": 1
  }
}
```

**컬럼 자동 로드 실행**
```bash
uv run sheets_reader.py
```

</details>

---

## 사용 방법

### 방법 1 — 웹 UI (비기술 사용자 권장)

```bash
uv run streamlit run demo.py
```

브라우저가 자동으로 열립니다. (또는 http://localhost:8501 접속)

1. PDF 파일을 업로드 영역에 드래그 앤 드롭
2. **추출 시작** 버튼 클릭
3. 결과 확인 후 CSV / Excel 다운로드

### 방법 2 — 명령어 (CLI)

```bash
# 기본 실행 (CSV + Excel 동시 출력)
uv run main.py Data/견적서.pdf

# 여러 견적서를 하나의 파일에 누적
uv run main.py Data/견적서1.pdf --append --out output/통합결과
uv run main.py Data/견적서2.pdf --append --out output/통합결과

# CSV만 출력
uv run main.py Data/견적서.pdf --csv-only

# Excel만 출력
uv run main.py Data/견적서.pdf --excel-only
```

결과 파일은 `output/` 폴더에 자동 저장됩니다.

---

## 프로젝트 구조

```
quote-extractor/
├── .env                  ← API 키 (직접 생성 필요, git에 포함 안 됨)
├── config.json           ← 추출 컬럼 정의, AI 모델 설정
├── demo.py               ← 웹 UI (Streamlit)
├── main.py               ← CLI 진입점
├── pdf_reader.py         ← PDF 텍스트/표 추출
├── ai_analyzer.py        ← Gemini AI 분석 요청
├── csv_writer.py         ← CSV/Excel 저장
├── sheets_reader.py      ← Google Sheets 헤더 읽기
└── output/               ← 결과 파일 저장 폴더
```

---

## 추출 항목 설정

`config.json`의 `columns` 항목에서 추출할 컬럼을 자유롭게 수정할 수 있습니다.

```json
{
  "columns": ["No.", "주문일자", "제품명", "Cat. No.", "수량", "입고단위"],
  "ai_model": "gemini-2.5-flash"
}
```

---

## 자주 묻는 질문

**Q. PDF를 올렸는데 텍스트가 추출이 안 돼요.**
A. 스캔 이미지로 만들어진 PDF일 수 있습니다. 현재 버전은 텍스트 기반 PDF를 지원합니다.

**Q. API 키 오류가 납니다.**
A. `.env` 파일이 프로젝트 루트 폴더에 있는지, 키 값이 정확한지 확인하세요.

**Q. 무료로 사용할 수 있나요?**
A. Gemini API 무료 티어(하루 1,500회 요청)로 충분히 사용 가능합니다.

---

## 라이선스

MIT License
