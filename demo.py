import io
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from pdf_reader import extract_for_ai
from ai_analyzer import analyze_pdf_text
from csv_writer import load_config
from web_searcher import enrich_records

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="견적서 자동 추출기",
    page_icon="📄",
    layout="centered",
)

st.title("📄 견적서 자동 추출기")
st.caption("PDF 견적서를 업로드하면 AI가 자동으로 데이터를 추출합니다.")
st.divider()


# ── 설정 로드 ─────────────────────────────────────────────────
@st.cache_data
def get_config():
    return load_config()


config = get_config()
columns = config["columns"]
model = config.get("ai_model", "gemini-2.5-flash")


# ── PDF 업로드 ────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "PDF 파일을 선택하거나 드래그하세요",
    type=["pdf"],
    help="한국어 견적서 PDF를 업로드해주세요.",
)

web_enrich = st.toggle(
    "🌐 웹 검색으로 빈 필드 자동 보완",
    value=True,
    help="추출 후 빈 항목(브랜드, 입고단위 등)을 웹 검색으로 자동으로 채웁니다. 제품당 2~3초 추가 소요.",
)

if uploaded_file:
    st.success(f"✅ 파일 업로드 완료: **{uploaded_file.name}**")

    if st.button("🔍 추출 시작", type="primary", use_container_width=True):
        # 업로드 파일을 임시 경로에 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            # 1단계: PDF 텍스트 추출
            with st.status("처리 중...", expanded=True) as status:
                st.write("📖 PDF 텍스트 추출 중...")
                extracted = extract_for_ai(tmp_path)

                # 2단계: AI 분석
                st.write(f"🤖 AI 분석 중 (모델: {model})...")
                records = analyze_pdf_text(extracted, columns, model)

                # 3단계: 웹 검색 보완 (옵션)
                if web_enrich:
                    progress_text = st.empty()
                    progress_bar = st.progress(0)
                    total = len(records)

                    def update_progress(cur, tot, msg):
                        progress_text.write(f"🌐 {msg}")
                        progress_bar.progress(cur / tot)

                    st.write("🌐 웹 검색으로 빈 필드 보완 중...")
                    records = enrich_records(records, columns, model, progress_callback=update_progress)
                    progress_text.empty()
                    progress_bar.empty()

                status.update(
                    label=f"✅ 완료! {len(records)}개 제품 추출",
                    state="complete",
                )

            # ── 결과 테이블 ───────────────────────────────────
            st.subheader(f"추출 결과 — {len(records)}개 제품")
            df = pd.DataFrame(
                [{col: r.get(col, None) for col in columns} for r in records],
                columns=columns,
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            # ── 다운로드 버튼 ─────────────────────────────────
            st.divider()
            col1, col2 = st.columns(2)
            base_name = Path(uploaded_file.name).stem

            # CSV
            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
            col1.download_button(
                label="⬇️ CSV 다운로드",
                data=csv_buf.getvalue().encode("utf-8-sig"),
                file_name=f"{base_name}_추출결과.csv",
                mime="text/csv",
                use_container_width=True,
            )

            # Excel
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="견적서")
                ws = writer.sheets["견적서"]
                for col_cells in ws.columns:
                    max_len = max(
                        (len(str(c.value)) if c.value is not None else 0)
                        for c in col_cells
                    )
                    ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 50)

            col2.download_button(
                label="⬇️ Excel 다운로드",
                data=excel_buf.getvalue(),
                file_name=f"{base_name}_추출결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

else:
    # 업로드 전 안내
    with st.expander("💡 사용 방법"):
        st.markdown("""
1. 위의 업로드 영역에 **견적서 PDF**를 드래그하거나 클릭해서 선택합니다.
2. **추출 시작** 버튼을 누릅니다.
3. AI가 자동으로 제품 정보를 분석합니다. (약 10~20초 소요)
4. 결과를 확인하고 **CSV** 또는 **Excel** 파일로 다운로드합니다.
        """)

    with st.expander("📋 추출되는 항목"):
        st.markdown("\n".join(f"- {col}" for col in columns))
