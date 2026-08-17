"""
Shared page-level error handling (NFR 4.1 REQ-4).

The BRD specifies an exact user-facing message when the dashboard can't
retrieve data: "Unable to retrieve data. Please refresh the page or check
the pipeline status." — never a raw stack trace.

Usage in a page, wrapping whatever data-loading you'd otherwise do at the
top of the script:

    from app.streamlit_utils import safe_page_load

    def _load_all():
        return get_signal_summary(24), get_top_signals(), ...

    summary, top_signals = safe_page_load(_load_all)

If _load_all() raises anything, the real exception is logged (so you can
still debug it from the terminal/logs) but the user only ever sees the
BRD's specified message, and the rest of the page's script stops
executing — no half-rendered page, no stack trace reaching the browser.
"""

import logging

import streamlit as st

logger = logging.getLogger(__name__)

USER_FACING_ERROR = "Unable to retrieve data. Please refresh the page or check the pipeline status."


def safe_page_load(load_fn):
    """Run load_fn(); on any exception, show the BRD's message and halt the page."""
    try:
        return load_fn()
    except Exception:
        logger.exception("Page data load failed")
        st.error(USER_FACING_ERROR)
        st.stop()
