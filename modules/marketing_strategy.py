# modules/marketing_strategy.py

import os
import json
import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from openai import OpenAI
from modules.ui import shell_open, shell_close, goto

load_dotenv()


# =========================
# Helpers: data
# =========================
def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.replace("\ufeff", "").str.strip()
    return df


def _build_segment(df_pred: pd.DataFrame, df_raw: pd.DataFrame, risk_group: str, top_n: int = 300) -> pd.DataFrame:
    df_pred = _clean_columns(df_pred)
    df_raw = _clean_columns(df_raw)

    required_pred = {"customer_id", "churn_proba", "risk_group", "risk_tier"}
    missing = required_pred - set(df_pred.columns)
    if missing:
        raise ValueError(f"예측 결과(df)에 필요한 컬럼이 없습니다: {sorted(missing)}")

    if "customer_id" not in df_raw.columns:
        raise ValueError("원본 데이터(df_raw)에 customer_id 컬럼이 없습니다.")

    df_pred["customer_id"] = df_pred["customer_id"].astype(str)
    df_raw["customer_id"] = df_raw["customer_id"].astype(str)

    merged = df_pred.merge(df_raw, on="customer_id", how="left", suffixes=("", "_raw"))
    seg = (
        merged[merged["risk_group"] == risk_group]
        .sort_values("churn_proba", ascending=False)
        .head(int(top_n))
        .reset_index(drop=True)
    )
    return seg


def _select_customer_fields(row: pd.Series) -> dict:
    # 프롬프트/JSON 생성에 사용할 핵심 필드만 (너무 길면 품질/비용 하락)
    keep = [
        "customer_id", "churn_proba", "risk_tier", "risk_group",
        "age", "gender", "region", "tenure_months", "income_band", "card_grade",
        "contract_cancelled", "complaints_6m", "marketing_open_rate_6m",
        # 있으면 추가 활용되는 것들
        "spent_change_ratio", "recent_3m_spent", "past_3m_spent",
        "total_spent_6m", "total_txn_6m", "total_login_6m",
        "points_balance", "revolving_usage", "cash_service_usage",
    ]
    out = {}
    for k in keep:
        if k in row.index:
            v = row[k]
            out[k] = None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
    return out


def _summarize_segment(seg: pd.DataFrame) -> dict:
    if len(seg) == 0:
        return {"count": 0, "avg_churn_proba": None}
    return {
        "count": int(len(seg)),
        "avg_churn_proba": float(seg["churn_proba"].mean()) if "churn_proba" in seg.columns else None
    }


# =========================
# OpenAI
# =========================
def _call_openai_json(model: str, prompt: str) -> dict:
    api_key = os.getenv("GPT_API_KEY")
    if not api_key:
        raise ValueError("환경변수 GPT_API_KEY가 없습니다. .env에 GPT_API_KEY=sk-... 를 설정하세요.")

    client = OpenAI(api_key=api_key)
    resp = client.responses.create(model=model, input=prompt)

    text = getattr(resp, "output_text", None)
    if not text:
        # fallback
        try:
            text = resp.output[0].content[0].text
        except Exception:
            text = str(resp)

    # JSON 파싱
    try:
        return json.loads(text)
    except Exception:
        # 모델이 실수로 앞뒤에 텍스트를 섞는 경우 방어: JSON 구간만 추출 시도
        stripped = text.strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(stripped[start:end+1])
            except Exception:
                pass

        # 그래도 실패하면 원문을 보여줄 수 있게 예외에 포함
        raise ValueError("GPT 응답이 JSON 파싱에 실패했습니다.\n\n원문:\n" + text)


# =========================
# Prompt: JSON only
# =========================
def _make_ui_json_prompt(customer: dict, brand_context: str, seg_summary: dict) -> str:
    # “이미지처럼” 만들기 위한 JSON 스키마(키 이름 고정)
    schema = {
        "strategy_cards": [
            {
                "title": "추천 전략 01 - 핵심 전략",
                "headline": "즉각 혜택 제공",
                "desc": "단기 혜택으로 이탈을 지연시키고 재방문을 유도",
                "bullets": ["혜택 중심 메시지", "유효기간 명확화", "재방문 트리거 설계"],
                "kpi_left_label": "이탈률",
                "kpi_left_value": 18,
                "kpi_left_direction": "down",
                "kpi_right_label": "반응률",
                "kpi_right_value": 25,
                "kpi_right_direction": "up"
            }
        ],
        "channel_table": [
            {"channel": "Push", "score": 5, "message_point": "혜택 + 긴급성", "reason": "즉각 반응"},
            {"channel": "SMS", "score": 4, "message_point": "이탈 방지", "reason": "도달률 높음"},
            {"channel": "Email", "score": 3, "message_point": "정보성 콘텐츠", "reason": "장기유지"},
            {"channel": "In-app", "score": 3, "message_point": "행동 유도", "reason": "UX 연결"}
        ],
        "message_examples": [
            {"channel": "Push", "text": "지금 돌아오면 OOO 혜택을 드려요. 오늘까지!"},
            {"channel": "Email", "text": "최근 사용이 줄어들어 걱정돼요. 다시 시작하실 수 있도록 맞춤 혜택을 준비했어요."}
        ]
    }

    return f"""
너는 금융 CRM 마케팅 전략가야.
아래 고객 1명에 대해, 화면(UI)을 그릴 수 있는 데이터만 생성해줘. (디자인은 Streamlit이 처리)

[고객 프로필]
{customer}

[브랜드/정책/제약]
{brand_context if brand_context else "제약 없음"}

[세그먼트 참고]
- segment_count: {seg_summary.get("count")}
- segment_avg_churn_proba: {seg_summary.get("avg_churn_proba")}

[출력 규칙]
- 반드시 JSON만 출력해. (설명/마크다운/코드블록/주석 금지)
- 키 이름 변경 금지. 아래 스키마의 최상위 키를 그대로 사용: strategy_cards, channel_table, message_examples
- strategy_cards는 정확히 3개 생성해.
  - 각각 성격이 다르게: (1) 이탈 원인 분석 (2) 혜택/ 오퍼 3개  (3) 재활성화 유도
  - bullets는 각 카드마다 3~4개 짧은 문구로
  - kpi 값은 과장 금지(합리적 범위) / direction은 up 또는 down
- channel_table은 4개 채널(Push, SMS, Email, In-app)로 고정하고 score는 1~5 정수.
- message_examples는 2~4개로, 채널별 예시 문구를 짧고 구체적으로.

[JSON 스키마 예시(형태 참고, 값은 너가 생성)]
{json.dumps(schema, ensure_ascii=False)}
""".strip()


# =========================
# UI render helpers
# =========================
def _stars(n: int) -> str:
    n = int(max(1, min(5, n)))
    return "★" * n + "☆" * (5 - n)


def _render_strategy_cards(cards: list):
    cols = st.columns(3)
    for i in range(3):
        c = cards[i] if i < len(cards) else None
        with cols[i]:
            if not c:
                st.empty()
                continue

            bullets = c.get("bullets", [])[:4]
            bullets_html = "".join([f"<div style='margin-top:6px;'>☐ {b}</div>" for b in bullets])

            left_dir = "↓" if c.get("kpi_left_direction") == "down" else "↑"
            right_dir = "↑" if c.get("kpi_right_direction") == "up" else "↓"

            st.markdown(
                f"""
                <div style="border:1px solid #E7ECF5;border-radius:16px;padding:16px;background:#fff;">
                  <div style="color:#2F6BFF;font-weight:800;font-size:13px;">{c.get("title","")}</div>
                  <div style="font-weight:900;font-size:22px;margin-top:6px;color:#111827;">
                    {c.get("headline","")}
                  </div>
                  <div style="color:#667085;margin-top:6px;font-size:13px;line-height:1.4;">
                    {c.get("desc","")}
                  </div>

                  <div style="margin-top:12px;color:#111827;font-size:14px;line-height:1.65;">
                    {bullets_html}
                  </div>

                  <hr style="border:none;border-top:1px solid #EEF2F7;margin:14px 0;" />

                  <div style="display:flex;justify-content:flex-end;gap:18px;">
                    <div style="font-size:12px;color:#667085;">
                      {c.get("kpi_left_label","")} <b style="color:#111827;">{c.get("kpi_left_value","")}%</b> {left_dir}
                    </div>
                    <div style="font-size:12px;color:#667085;">
                      {c.get("kpi_right_label","")} <b style="color:#111827;">{c.get("kpi_right_value","")}%</b> {right_dir}
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True
            )


def _render_channel_table(channel_table: list):
    st.markdown("#### 채널")
    df = pd.DataFrame(channel_table).copy()

    # 컬럼 표준화
    if "score" in df.columns:
        df["추천도"] = df["score"].apply(_stars)
    else:
        df["추천도"] = ""

    # 보기용 컬럼
    col_map = {
        "channel": "채널",
        "추천도": "추천도",
        "message_point": "메시지 포인트",
        "reason": "이유"
    }
    cols = [c for c in ["channel", "추천도", "message_point", "reason"] if c in df.columns]
    view = df[cols].rename(columns=col_map)

    st.dataframe(view, use_container_width=True, hide_index=True)


def _render_message_box(examples: list):
    st.markdown("#### 메시지 예시")
    html = "<div style='border:1px solid #E7ECF5;border-radius:16px;padding:16px;background:#fff;'>"
    for ex in (examples or [])[:4]:
        ch = ex.get("channel", "")
        tx = ex.get("text", "")
        html += (
            f"<div style='margin-bottom:12px;line-height:1.5;'>"
            f"<span style='color:#2F6BFF;font-weight:800;'>{ch}:</span> "
            f"<span style='color:#111827;'>{tx}</span>"
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# =========================
# Page
# =========================
def render():
    shell_open()

    st.markdown('<div class="cs-title">마케팅 전략 (UI 카드형 · 고객 선택)</div>', unsafe_allow_html=True)
    st.markdown('<div class="cs-sub">표에서 고객을 선택하면, GPT가 UI 렌더링용 JSON을 만들고 화면을 카드/표로 구성합니다.</div>', unsafe_allow_html=True)

    df = st.session_state.get("df")
    df_raw = st.session_state.get("df_raw")

    if df is None or df_raw is None:
        st.warning("먼저 데이터 입력 → 예측 실행 후, 이 페이지로 이동하세요.")
        if st.button("데이터 입력으로 이동", use_container_width=True):
            goto("data")
        shell_close()
        return

    # Controls
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        risk_group = st.selectbox("위험군", ["고위험", "중위험", "저위험", "안정"], index=0)
    with c2:
        top_n = st.slider("표시 고객 수(상위 N명)", 50, 1000, 300, 50)
    with c3:
        model = st.selectbox("모델", ["gpt-4.1-mini", "gpt-4.1-nano"], index=0)

    # Context
    st.markdown("<div class='cs-card'>", unsafe_allow_html=True)
    st.markdown("<div class='cs-section-title'>정책/제약(선택)</div>", unsafe_allow_html=True)
    brand_context = st.text_area(
        "예: 캐시백 상한 2만원, 과도한 할인 금지, 콜센터 제외, 쿠폰 유효기간 7일 등",
        height=80,
        placeholder="제약을 적어두면 전략이 더 현실적으로 나옵니다."
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Segment build
    try:
        seg = _build_segment(df, df_raw, risk_group=risk_group, top_n=top_n)
        seg_summary = _summarize_segment(seg)
    except Exception as e:
        st.error(f"세그먼트 구성 오류: {e}")
        shell_close()
        return

    if len(seg) == 0:
        st.warning("선택한 위험군에 고객이 없습니다.")
        shell_close()
        return

    # Customer selection by clicking row (A)
    st.markdown("### 고객 리스트 (행 클릭으로 선택)")
    event = st.dataframe(
        seg,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
    )

    selected_rows = event.selection.rows
    if not selected_rows:
        st.info("표에서 고객 한 명을 클릭하세요.")
        shell_close()
        return

    selected_row = seg.iloc[int(selected_rows[0])]
    customer = _select_customer_fields(selected_row)

    # Profile preview (compact)
    st.markdown("<div class='cs-card'>", unsafe_allow_html=True)
    st.markdown("<div class='cs-section-title'>선택 고객</div>", unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    p1.metric("customer_id", str(customer.get("customer_id", "-")))
    p2.metric("risk_tier", str(customer.get("risk_tier", "-")))
    churn = customer.get("churn_proba", None)
    p3.metric("churn_proba", f"{float(churn):.4f}" if churn is not None else "-")
    st.markdown("</div>", unsafe_allow_html=True)

    # Generate button
    if "ui_cache" not in st.session_state:
        st.session_state.ui_cache = {}

    cache_key = (
        str(customer.get("customer_id")) + "|" +
        risk_group + "|" + model + "|" +
        (brand_context or "")
    )

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    gen = st.button("전략 생성", use_container_width=True)

    if gen:
        try:
            if cache_key in st.session_state.ui_cache:
                data = st.session_state.ui_cache[cache_key]
            else:
                prompt = _make_ui_json_prompt(customer, brand_context, seg_summary)
                with st.spinner("마케팅 전략 생성 중입니다..."):
                    data = _call_openai_json(model=model, prompt=prompt)
                st.session_state.ui_cache[cache_key] = data

            # Basic validation
            cards = data.get("strategy_cards", [])
            channels = data.get("channel_table", [])
            examples = data.get("message_examples", [])

            st.markdown("### 추천 전략")
            _render_strategy_cards(cards[:3])

            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            left, right = st.columns([1.25, 1])

            with left:
                _render_channel_table(channels)

            with right:
                _render_message_box(examples)

        except Exception as e:
            st.error(str(e))

    # Footer nav
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    if st.button("← 고객 추출로", use_container_width=True):
        goto("extract")

    shell_close()
