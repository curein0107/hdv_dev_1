from __future__ import annotations

import hmac

import streamlit as st


def require_optional_password() -> bool:
    """Simple optional gate for Streamlit Community Cloud.

    Configure in secrets:
        [auth]
        password = "..."
    If the secret is absent, the app remains open.
    """
    try:
        expected = str(st.secrets.get("auth", {}).get("password", ""))
    except Exception:
        expected = ""

    if not expected:
        return True
    if st.session_state.get("authenticated"):
        return True

    st.markdown("## 서비스 로그인")
    supplied = st.text_input("접속 비밀번호", type="password")
    if st.button("로그인", type="primary", use_container_width=True):
        if hmac.compare_digest(supplied, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    return False
