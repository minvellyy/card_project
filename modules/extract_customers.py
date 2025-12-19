import streamlit as st
from modules.ui import shell_open, shell_close, goto

def render():
    shell_open()

    st.markdown('<div class="cs-title">이탈가능 고객 추출</div>', unsafe_allow_html=True)
    st.markdown('<div class="cs-sub">위험 이탈 수준을 선택하면 해당 고객군을 요약/확인할 수 있습니다.</div>', unsafe_allow_html=True)

    # 세션에서 데이터 가져오기
    df = st.session_state.get("df")
    df_raw = st.session_state.get("df_raw")

    if df is None:
        st.warning("먼저 데이터 입력 페이지에서 예측을 실행하세요.")
        if st.button("데이터 입력으로 이동", use_container_width=True):
            goto("data")
        shell_close()
        return

    if df_raw is None:
        st.error("원본 데이터(df_raw)가 없습니다. data_input에서 df_raw를 session_state에 저장하세요.")
        shell_close()
        return

    df = df.copy()
    df_raw = df_raw.copy()

    # (중요) 컬럼명 정리: BOM/공백 제거
    df.columns = df.columns.str.replace("\ufeff", "").str.strip()
    df_raw.columns = df_raw.columns.str.replace("\ufeff", "").str.strip()

    # (중요) 필수 컬럼 확인을 먼저
    required_pred = {"customer_id", "churn_proba", "risk_group", "risk_tier"}
    missing_pred = required_pred - set(df.columns)
    if missing_pred:
        st.error(f"예측 결과(df)에 필요한 컬럼이 없습니다: {sorted(missing_pred)}")
        st.write("현재 df 컬럼:", list(df.columns))
        shell_close()
        return

    if "customer_id" not in df_raw.columns:
        st.error("원본 데이터(df_raw)에 customer_id 컬럼이 없습니다.")
        st.write("현재 df_raw 컬럼:", list(df_raw.columns))
        shell_close()
        return

    # 타입 맞추기
    df["customer_id"] = df["customer_id"].astype(str)
    df_raw["customer_id"] = df_raw["customer_id"].astype(str)

    # merge: df_raw에서 customer_id는 제거하고 붙여서 중복 방지
    df_merged = df.merge(df_raw, on="customer_id", how="left", suffixes=("", "_raw"))


    # 드롭다운
    colA, colB, colC = st.columns([1, 1.2, 1])
    with colB:
        st.markdown(
            "<div style='text-align:center; font-weight:900; margin-bottom:6px;'>위험 이탈 수준</div>",
            unsafe_allow_html=True
        )
        options = ["고위험", "중위험", "저위험", "안정"]
        default_selected = st.session_state.get("selected_risk", options[0])
        default_idx = options.index(default_selected) if default_selected in options else 0
        st.session_state.selected_risk = st.selectbox(" ", options, index=default_idx, label_visibility="collapsed")

    rk = st.session_state.selected_risk

    # 여기부터는 df_merged만 사용
    df_g = (
        df_merged[df_merged["risk_group"] == rk]
        .sort_values("churn_proba", ascending=False)
        .head(50)
        .reset_index(drop=True)
    )

    st.markdown(
        f"<div class='cs-card'><div class='cs-section-title'>{rk}</div></div>",
        unsafe_allow_html=True
    )

    RAW_COLS = [
        "age", "gender", "region", "tenure_months",
        "income_band", "card_grade", "contract_cancelled", "complaints_6m",
        "marketing_open_rate_6m", "spent_m6", "txn_m6", "login_m6", "spent_m5",
        "txn_m5", "login_m5", "spent_m4", "txn_m4", "login_m4", "spent_m3",
        "txn_m3", "login_m3", "spent_m2", "txn_m2", "login_m2", "spent_m1",
        "txn_m1", "login_m1", "total_spent_6m", "total_txn_6m",
        "total_login_6m", "points_balance", "revolving_usage",
        "cash_service_usage", "churn"
    ]
    PRED_COLS = ["churn_proba", "risk_tier", "risk_group"]

    show_cols = ["customer_id"] + PRED_COLS + RAW_COLS
    show_cols = [c for c in show_cols if c in df_g.columns]
    show_cols = list(dict.fromkeys(show_cols))  # 혹시 모를 중복 제거

    st.dataframe(df_g[show_cols], use_container_width=True, hide_index=True)

    # 다음 페이지 이동
    col1, col2 = st.columns([1, 1])
    with col2:
        if st.button("마케팅 전략 페이지로 →", use_container_width=True):
            goto("strategy")

    shell_close()
