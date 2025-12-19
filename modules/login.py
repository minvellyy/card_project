import streamlit as st
from modules.ui import shell_open, shell_close, goto

# 고정 계정(원하는 값으로 변경)
FIXED_ID = "admin"
FIXED_PW = "1234"

def render():
    shell_open()

    st.markdown('<div class="cs-title">로그인</div>', unsafe_allow_html=True)
    # st.markdown('<div class="cs-sub">고정 계정으로 로그인합니다.</div>', unsafe_allow_html=True)

    # st.markdown('<div class="cs-card">', unsafe_allow_html=True)
    st.markdown('<div class="cs-section-title">계정 입력</div>', unsafe_allow_html=True)

    # 입력창
    login_id = st.text_input("ID", placeholder="ID를 입력하세요", key="login_id")
    login_pw = st.text_input("Password", type="password", placeholder="passwordf를 입력하세요", key="login_pw")

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Login", use_container_width=True):
            # 고정 계정 검증
            if login_id == FIXED_ID and login_pw == FIXED_PW:
                st.session_state.logged_in = True
                st.session_state.user_id = login_id

                # 원래 가려던 페이지로 복귀
                target = st.session_state.get("after_login_route", "data")
                st.session_state.after_login_route = "data"  # 초기화(선택)
                goto(target)
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    with c2:
        st.button("Sign up", use_container_width=True, disabled=True)

    st.markdown("</div>", unsafe_allow_html=True)

    shell_close()
