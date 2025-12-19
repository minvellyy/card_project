import streamlit as st
import pandas as pd
from datetime import datetime

from modules.ui import shell_open, shell_close, goto
from modules.inference import predict_and_build

def render():
    shell_open()

    st.markdown('<div class="cs-title">데이터 입력</div>', unsafe_allow_html=True)
    st.markdown('<div class="cs-sub">이탈 예측을 위한 데이터를 업로드하고 분석을 실행합니다.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1])
    with col1:
        up = st.file_uploader("CSV 업로드", type=["csv"])
        st.text_input("데이터 설명(선택)", placeholder="예: 2025-12 기준 카드 이용 로그", key="data_desc")

        # 사용자가 선택한 ID 컬럼
        id_col = st.selectbox(
            "고객 ID 컬럼",
            options=["customer_id", "id"],
            index=0
        )

        st.selectbox(
            "예측 대상(라벨) 컬럼(선택)",
            options=["score", "churn_label"],
            index=0
        )

    with col2:
        st.markdown("<div class='cs-note'>권장 입력</div>", unsafe_allow_html=True)
        st.markdown(
            """
            - 최근 3~6개월 이용/결제/접속/혜택 사용 로그<br>
            - 고객 프로필(가입기간/등급/한도 등)<br>
            - 캠페인 반응(열람/클릭/전환)
            """,
            unsafe_allow_html=True
        )
        run = st.button("예측 결과 보기", use_container_width=True)

    if run:
        if up is None:
            st.error("CSV 파일을 업로드하세요.")
            shell_close()
            return

        with st.spinner("분석 중입니다..."):
            try:
                df_raw = pd.read_csv(up)

                # ID 컬럼 사전 체크 (UX 개선)
                if id_col not in df_raw.columns:
                    st.error(f"선택한 ID 컬럼 '{id_col}'이 업로드 파일에 없습니다.")
                    shell_close()
                    return

                # 핵심 실행 위치
                result_df = predict_and_build(df_raw, id_col=id_col)

                # 결과를 세션에 저장
                st.session_state.df = result_df
                st.session_state.df_raw = df_raw
                st.session_state.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M")

                st.success("분석이 완료되었습니다.")

                # 다음 단계로 이동
                goto("extract")

            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")

    shell_close()
