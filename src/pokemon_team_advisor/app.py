"""Streamlit entry point for the project foundation."""

import streamlit as st


def main() -> None:
    """Render the phase-one placeholder without recommendation logic."""
    st.set_page_config(page_title="Pokémon Team Advisor", page_icon="⚡")
    st.title("Pokémon Team Advisor")
    st.info("Phase 1 ist eingerichtet. Datenanalyse und Empfehlungen folgen schrittweise.")
    st.markdown(
        "Wähle später fünf Pokémon aus, um gemeinsame Schwächen zu analysieren "
        "und erklärbare Vorschläge für den sechsten Platz zu erhalten."
    )


if __name__ == "__main__":
    main()
