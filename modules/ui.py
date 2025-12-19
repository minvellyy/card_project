
import streamlit as st
from datetime import datetime

# =========================
# Theme / Design Tokens
# =========================
PALETTE = {
    "bg": "#ECF2FF",
    "card": "#FFFFFF",
    "primary": "#2563E4",
    "soft": "#D8E5FD",
    "text": "#111827",
    "subtext": "#6B7280",
    "bar": "#0B0B0B",
}

# =========================
# Global CSS (Figma Tone & Manner)
# =========================
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');

/* 전체 폰트 적용 */
html, body, [class*="css"] {{
  font-family: 'Manrope', sans-serif;
}}

/* 앱 전체 배경색 */
.stApp {{
  background: {PALETTE["bg"]};
}}

/* Streamlit 기본 UI 숨기기 */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{visibility: hidden;}}

/* ===== 상단바 ===== */
.cs-topbar {{
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 48px;
  background: {PALETTE["bar"]};
  z-index: 9999;
  display: flex;
  align-items: center;
  padding: 0 18px;
  gap: 18px;
}}

/* 로고 */
.cs-logo {{
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-weight: 800;
  text-decoration: none;
}}
.cs-dot {{
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: {PALETTE["primary"]};
  box-shadow: 0 0 0 2px rgba(37,99,228,0.25);
}}

/* 네비게이션 */
.cs-nav {{
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: 16px;
  flex: 1;
}}
.cs-nav a {{
  color: rgba(255,255,255,0.85);
  font-size: 13px;
  font-weight: 800;
  padding: 7px 10px;
  border-radius: 8px;
  text-decoration: none;
  display: inline-block;
}}
.cs-nav a.active {{
  background: rgba(255,255,255,0.12);
  color: #fff;
}}
.cs-nav a:hover {{
  background: rgba(255,255,255,0.08);
}}

/* 우측 정보 */
.cs-right {{
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(255,255,255,0.75);
  font-size: 12px;
  font-weight: 800;
}}
.cs-right a {{
  color: rgba(255,255,255,0.85);
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.2);
  font-size: 12px;
  font-weight: 800;
}}
.cs-right a:hover {{
  background: rgba(255,255,255,0.1);
}}
.cs-pad {{ height: 58px; }}

/* ===== 공통 레이아웃 ===== */
.cs-shell {{
  max-width: 1040px;
  margin: 0 auto;
  padding: 10px 14px 40px 14px;
}}
.cs-title {{
  font-size: 28px;
  font-weight: 800;
  color: {PALETTE["text"]};
  margin: 6px 0;
}}
.cs-sub {{
  color: {PALETTE["subtext"]};
  font-size: 13px;
  font-weight: 800;
  margin-bottom: 12px;
}}
.cs-card {{
  background: {PALETTE["card"]};
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 10px 24px rgba(17,24,39,0.06);
  border: 1px solid rgba(17,24,39,0.06);
}}
.cs-section-title {{
  font-size: 16px;
  font-weight: 900;
  color: {PALETTE["text"]};
  margin: 0 0 10px 0;
}}
.cs-note {{
  color: {PALETTE["subtext"]};
  font-size: 12px;
  font-weight: 800;
}}
</style>
"""

# =========================
# App init
# =========================
def init_app():
    st.set_page_config(
        page_title="ChurnSight",
        page_icon="📉",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # ---- Session defaults ----
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "df" not in st.session_state:
        st.session_state.df = None
    if "selected_risk" not in st.session_state:
        st.session_state.selected_risk = "즉시 이탈 위험"
    if "last_run_at" not in st.session_state:
        st.session_state.last_run_at = None
    if "after_login_route" not in st.session_state:
        st.session_state.after_login_route = "data"

# =========================
# Layout helpers
# =========================
def shell_open():
    st.markdown('<div class="cs-shell">', unsafe_allow_html=True)

def shell_close():
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Routing helpers
# =========================
def goto(route: str):
    """
    세션 라우트 + URL 쿼리 파라미터를 동시에 갱신
    로그인 정보도 함께 전달
    """
    st.session_state.route = route
    st.query_params.clear()
    st.query_params["route"] = route
    
    # 로그인 상태를 URL에 포함
    if st.session_state.logged_in:
        st.query_params["u"] = st.session_state.user_id or ""
        st.query_params["auth"] = "1"
    
    st.rerun()

def sync_route_from_query():
    """
    URL의 쿼리 파라미터를 세션에 반영 (route + 로그인 상태)
    """
    qp_route = st.query_params.get("route")
    qp_auth = st.query_params.get("auth")
    qp_user = st.query_params.get("u")
    
    # 라우트 복원
    if qp_route:
        st.session_state.route = qp_route
    
    # 로그인 상태 복원
    if qp_auth == "1" and qp_user:
        st.session_state.logged_in = True
        st.session_state.user_id = qp_user

# =========================
# Auth helpers
# =========================
def require_login():
    """로그인 확인"""
    if not st.session_state.logged_in:
        st.session_state.after_login_route = st.session_state.route
        goto("login")

def logout():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.query_params.clear()
    st.query_params["route"] = "login"
    st.rerun()

# =========================
# Topbar (Clickable links via query params)
# =========================
def topbar(active: str):
    """
    상단바의 메뉴는 <a href="?route=..."> 링크로 구성.
    로그인 정보도 URL에 포함시킴
    """
    # 로그인 상태를 URL에 포함
    auth_params = ""
    if st.session_state.logged_in:
        auth_params = f"&auth=1&u={st.session_state.user_id or ''}"
    
    def nav_link(key: str, text: str):
        cls = "active" if key == active else ""
        return f'<a class="{cls}" href="?route={key}{auth_params}" target="_self">{text}</a>'

    nav_html = (
        nav_link("data", "데이터 입력")
        + nav_link("extract", "이탈가능 고객 추출")
        + nav_link("strategy", "마케팅 전략")
    )

    right_text = (
        f"Logged in: {st.session_state.user_id or '-'}"
        if st.session_state.logged_in
        else "Not logged in"
    )

    # 로그인/로그아웃 링크
    auth_link = (
        f'<a href="?route=login&action=logout" target="_self">Logout</a>'
        if st.session_state.logged_in
        else '<a href="?route=login" target="_self">Login</a>'
    )

    st.markdown(
        f"""
        <div class="cs-topbar">
          <a class="cs-logo" href="?route=data{auth_params}" target="_self">
            <span class="cs-dot"></span> ChurnSight
          </a>

          <div class="cs-nav">{nav_html}</div>

          <div class="cs-right">
            <span>{right_text}</span>
            <span style="opacity:.6;">|</span>
            {auth_link}
          </div>
        </div>
        <div class="cs-pad"></div>
        """,
        unsafe_allow_html=True,
    )