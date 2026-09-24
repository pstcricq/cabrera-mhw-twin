"""Cabrera heatwave dashboard: page setup and navigation.

Run it with `make dashboard`; the theme lives in .streamlit/config.toml.
"""

import streamlit as st

st.set_page_config(
    page_title="Cabrera heatwave twin",
    page_icon=":material/waves:",
    layout="wide",
)

st.navigation(
    [
        st.Page("overview.py", title="Overview", icon=":material/home:", default=True),
        st.Page(
            "year_explorer.py",
            title="Year explorer",
            icon=":material/calendar_month:",
        ),
        st.Page("trends.py", title="Trends & what-if", icon=":material/trending_up:"),
        st.Page("validation.py", title="Validation", icon=":material/fact_check:"),
        st.Page("method.py", title="Method & data", icon=":material/menu_book:"),
    ]
).run()
