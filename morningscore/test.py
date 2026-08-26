import streamlit as st
from colors import INK, PAPER, MUTED, FILLED, EMPTY, GRADIENT
from config import WINDOW_START, WINDOW_END, SLOT_MINUTES, MAX_SCORE



def slot_grid(score):
    """Sixty blocks, one per five minutes of the morning. Filled = survived."""
    blocks = []
    for index in range(MAX_SCORE):
        colour = GRADIENT[score] if index < score else EMPTY
        hour = 8 + (index * SLOT_MINUTES) // 60
        minute = (index * SLOT_MINUTES) % 60
        blocks.append(
            f'<div class="slot" style="background:{colour}" '
            f'title="{hour:02d}:{minute:02d}"></div>'
        )
    return f'<div class="grid">{"".join(blocks)}</div>'




st.set_page_config(page_title="Morning score", layout="centered")

st.markdown(f"""
<style>
    .stApp {{ background: {PAPER}; }}
    header, footer, #MainMenu {{ visibility: hidden; }}
    .block-container {{ padding-top: 2.5rem; max-width: 720px; }}
    h1, h2, h3, p, span, div {{ color: {INK}; }}
    .grid {{
        display: flex;
        margin: 0.5rem 0 1.5rem 0;
    }}
    .grid {{
        display: flex;
        width: 100%;
        max-width: 480px;
        margin: 0.5rem 0 1.5rem 0;
    }}

    .grid > * {{
        flex: 1 1 0;
        min-width: 0;          /* lets blocks shrink below intrinsic size */
        height: 40px;
        border-right: 2px solid {PAPER};
    }}

    .grid > *:last-child {{
        border-right: none;
    }}

    .slot {{ border-radius: 2px; }}   /* aspect-ratio removed */
    .headline {{
        font-size: 4.5rem; font-weight: 700; line-height: 1;
        letter-spacing: -0.03em; margin-bottom: 0.2rem;
    }}
    .sub {{ color: {MUTED}; font-size: 0.95rem; margin-bottom: 1.5rem; }}
    .label {{
        color: {MUTED}; font-size: 0.75rem; text-transform: uppercase;
        letter-spacing: 0.1em; margin-bottom: 0.3rem;
    }}
</style>
""", unsafe_allow_html=True)

days = {
            "day": "yesterday",
            "first_ping": "10.45",
            "score": "40",
        }

st.markdown('<div class="label">This morning</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="headline">{10}<span style="color:{MUTED};font-size:1.5rem">'
    f' / {MAX_SCORE}</span></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="sub">{"still going"}</div>', unsafe_allow_html=True)
st.markdown(slot_grid(10), unsafe_allow_html=True)