from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """
    Apply MineLens frontend styling.
    """

    st.markdown(
        """
        <style>

            .block-container {
                max-width: 1160px;
                padding-top: 2.1rem;
                padding-bottom: 4rem;
            }

            .minelens-eyebrow {
                font-size: 0.76rem;
                font-weight: 700;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                opacity: 0.60;
                margin-bottom: 0.45rem;
            }

            .minelens-title {
                font-size: 3rem;
                font-weight: 760;
                letter-spacing: -0.045em;
                line-height: 1.05;
                margin-bottom: 0.55rem;
            }

            .minelens-subtitle {
                font-size: 1.08rem;
                line-height: 1.65;
                opacity: 0.72;
                max-width: 900px;
                margin-bottom: 1.6rem;
            }

            .example-text {
                opacity: 0.62;
                font-size: 0.90rem;
                margin-top: 0.35rem;
                margin-bottom: 0.7rem;
            }

            div[data-testid="stForm"] {
                border: none;
                padding: 0;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1.55rem;
            }

            div[data-testid="stMetricLabel"] {
                font-size: 0.82rem;
                opacity: 0.72;
            }

            div[data-testid="stCaptionContainer"] {
                opacity: 0.86;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 12px;
            }

            footer {
                visibility: hidden;
            }

            #MainMenu {
                visibility: hidden;
            }

        </style>
        """,
        unsafe_allow_html=True,
    )