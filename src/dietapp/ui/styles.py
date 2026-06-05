from __future__ import annotations

from textwrap import dedent

import streamlit as st

APP_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Cormorant+Garamond:wght@500;700&display=swap');

:root {
    --paper: #f7f2e8;
    --card: rgba(255, 250, 243, 0.82);
    --ink: #15251b;
    --muted: #5c6d5d;
    --green: #2c6e49;
    --green-soft: #dfeadf;
    --sand: #efe2cb;
    --terracotta: #c06549;
    --border: rgba(21, 37, 27, 0.08);
    --shadow: 0 16px 40px rgba(21, 37, 27, 0.09);
}

html, body, [class*="css"]  {
    font-family: 'Space Grotesk', sans-serif;
    color: var(--ink);
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at top left, rgba(192, 101, 73, 0.18), transparent 32%),
        radial-gradient(circle at top right, rgba(44, 110, 73, 0.16), transparent 34%),
        linear-gradient(180deg, #faf6ee 0%, #f2ebdf 100%);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #173923 0%, #29593b 100%);
}

[data-testid="stSidebar"],
[data-testid="collapsedControl"] {
    display: none;
}

[data-testid="stSidebar"] * {
    color: #f8f6f1;
}

.hero {
    background: linear-gradient(135deg, rgba(255,255,255,0.82), rgba(239,226,203,0.86));
    border: 1px solid var(--border);
    border-radius: 28px;
    padding: 2.2rem 2rem 1.8rem;
    box-shadow: var(--shadow);
    margin-bottom: 1.2rem;
    position: relative;
    overflow: hidden;
}

.hero:before {
    content: "";
    position: absolute;
    inset: auto -40px -60px auto;
    width: 220px;
    height: 220px;
    border-radius: 999px;
    background: radial-gradient(circle, rgba(192,101,73,0.22) 0%, rgba(192,101,73,0) 72%);
}

.hero-kicker {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--green);
    font-weight: 700;
    margin-bottom: 0.6rem;
}

.hero h1 {
    font-family: 'Cormorant Garamond', serif;
    font-size: clamp(2.2rem, 3vw, 3.5rem);
    line-height: 0.95;
    margin: 0 0 0.9rem;
}

.hero p {
    max-width: 860px;
    color: var(--muted);
    margin: 0;
    font-size: 1.02rem;
}

.section-label {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--green);
    margin: 1.6rem 0 0.65rem;
}

.metric-card,
.day-shell,
.meal-card,
.shopping-card,
.prep-card {
    background: var(--card);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    border-radius: 24px;
}

.metric-card {
    padding: 1.1rem 1.15rem;
    min-height: 128px;
}

.metric-label {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: var(--muted);
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    margin: 0.35rem 0 0.2rem;
    color: var(--ink);
}

.metric-caption {
    color: var(--muted);
    font-size: 0.9rem;
    line-height: 1.35;
}

.day-shell {
    padding: 1.2rem;
    margin-bottom: 1rem;
}

.day-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 0.85rem;
}

.day-heading {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
}

.day-title h3 {
    font-family: 'Cormorant Garamond', serif;
    font-size: 2rem;
    margin: 0;
}

.meal-card {
    padding: 1rem;
    height: 100%;
}

.meal-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: var(--terracotta);
}

.meal-base {
    font-weight: 700;
    margin: 0.4rem 0 0.75rem;
    line-height: 1.35;
}

.meal-variant {
    margin-bottom: 0.75rem;
    padding-top: 0.7rem;
    border-top: 1px dashed rgba(21,37,27,0.12);
}

.meal-variant:first-of-type {
    border-top: 0;
    padding-top: 0;
}

.meal-person {
    font-size: 0.83rem;
    text-transform: uppercase;
    letter-spacing: 0.11em;
    color: var(--green);
    font-weight: 700;
}

.meal-name {
    font-weight: 700;
    margin: 0.2rem 0;
}

.meal-text,
.meal-meta,
.shopping-card li,
.prep-card li {
    color: var(--muted);
    line-height: 1.45;
}

.meal-meta {
    margin-top: 0.7rem;
    font-size: 0.9rem;
}

.tag {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    margin-right: 0.35rem;
    border-radius: 999px;
    background: var(--green-soft);
    color: var(--green);
    font-size: 0.78rem;
    font-weight: 700;
}

.tag-source-ai {
    background: rgba(28, 90, 62, 0.12);
    color: var(--green);
}

.tag-source-fallback {
    background: rgba(184, 103, 61, 0.14);
    color: var(--terracotta);
}

.provider-recovery-note {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    flex-wrap: wrap;
    margin: 0.75rem 0 0.2rem;
    padding: 0.85rem 1rem;
    border-radius: 18px;
    background: rgba(44, 110, 73, 0.08);
    border: 1px solid rgba(44, 110, 73, 0.15);
}

.provider-recovery-text {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.4;
}

.tag-provider-recovery {
    background: rgba(44, 110, 73, 0.14);
    color: var(--green);
    margin-right: 0;
}

.shopping-card,
.prep-card {
    padding: 1rem 1.1rem;
}

.shopping-card h4,
.prep-card h4 {
    margin-top: 0;
}

.download-shell {
    padding-top: 0.8rem;
}
</style>
"""


HERO_MARKUP = """
<div class="hero">
    <div class="hero-kicker">Meal planning per due</div>
    <h1>Una settimana sola, una cucina sola, due diete diverse.</h1>
    <p>
        DietAPP genera un piano alimentare condiviso per una coppia con versioni onnivora e vegetariana,
        usando basi comuni, avanzi utili e meno passaggi possibile ai fornelli.
    </p>
</div>
"""


def inject_styles() -> None:
    st.markdown(dedent(APP_STYLES).strip(), unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown(dedent(HERO_MARKUP).strip(), unsafe_allow_html=True)
