from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """
    Apply shared MineLens frontend styling.
    """

    st.markdown(
        """
        <style>

            /* =====================================================
               MAIN PAGE LAYOUT
               ===================================================== */

            .block-container,
            div[data-testid="stMainBlockContainer"],
            .stMainBlockContainer {
                max-width: 1160px !important;
                padding-top: 3.5rem !important;
                padding-bottom: 4rem !important;
            }


            /* =====================================================
               MINELENS PAGE HEADER
               ===================================================== */

            .minelens-eyebrow {
                font-size: 0.76rem;
                font-weight: 700;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                opacity: 0.60;
                margin-top: 0;
                margin-bottom: 0.45rem;
                line-height: 1.3;
            }

            .minelens-title {
                font-size: 3rem;
                font-weight: 760;
                letter-spacing: -0.045em;
                line-height: 1.05;
                margin-top: 0;
                margin-bottom: 0.55rem;
            }

            .minelens-subtitle {
                font-size: 1.08rem;
                line-height: 1.65;
                opacity: 0.72;
                max-width: 900px;
                margin-top: 0;
                margin-bottom: 1.6rem;
            }


            /* =====================================================
               GENERAL TEXT
               ===================================================== */

            .example-text {
                opacity: 0.62;
                font-size: 0.90rem;
                margin-top: 0.35rem;
                margin-bottom: 0.7rem;
            }


            /* =====================================================
               FORMS
               ===================================================== */

            div[data-testid="stForm"] {
                border: none;
                padding: 0;
            }


            /* =====================================================
               METRICS
               ===================================================== */

            div[data-testid="stMetricValue"] {
                font-size: 1.55rem;
            }

            div[data-testid="stMetricLabel"] {
                font-size: 0.82rem;
                opacity: 0.72;
            }


            /* =====================================================
               CAPTIONS
               ===================================================== */

            div[data-testid="stCaptionContainer"] {
                opacity: 0.86;
            }


            /* =====================================================
               BORDERED CONTAINERS
               ===================================================== */

            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 12px;
            }


            /* =====================================================
               DATAFRAMES
               ===================================================== */

            div[data-testid="stDataFrame"] {
                border-radius: 10px;
                overflow: hidden;
            }


            /* =====================================================
               BUTTONS
               ===================================================== */

            div[data-testid="stButton"] button,
            div[data-testid="stDownloadButton"] button,
            div[data-testid="stLinkButton"] a {
                border-radius: 9px;
            }


            /* =====================================================
               TABS
               ===================================================== */

            button[data-baseweb="tab"] {
                font-weight: 600;
            }


            /* =====================================================
               MOBILE / SMALL WINDOWS
               ===================================================== */

            @media (max-width: 768px) {

                .block-container,
                div[data-testid="stMainBlockContainer"],
                .stMainBlockContainer {
                    padding-top: 3rem !important;
                    padding-left: 1rem !important;
                    padding-right: 1rem !important;
                }

                .minelens-title {
                    font-size: 2.25rem;
                }

                .minelens-subtitle {
                    font-size: 1rem;
                }
            }


            /* =====================================================
               STREAMLIT CHROME
               ===================================================== */

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