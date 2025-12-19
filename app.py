
import streamlit as st

from modules.ui import init_app, topbar, require_login, goto, sync_route_from_query, logout
from modules import login, data_input, extract_customers, marketing_strategy

init_app()
sync_route_from_query()  # URL에서 route와 로그인 상태 복원

# logout action 처리
if st.query_params.get("action") == "logout":
    logout()

# 라우팅 상태
if "route" not in st.session_state:
    st.session_state.route = "login"

route = st.session_state.route

# 로그인 필요 페이지는 보호
if route != "login":
    require_login()

# 상단바는 로그인 페이지 제외하고 표시
if route != "login":
    topbar(route)

# 실제 페이지 렌더
if route == "login":
    login.render()
elif route == "data":
    data_input.render()
elif route == "extract":
    extract_customers.render()
elif route == "strategy":
    marketing_strategy.render()
else:
    goto("data")