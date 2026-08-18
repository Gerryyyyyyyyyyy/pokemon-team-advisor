"""Kleine, kontrollierte Live-Suche für die Streamlit-Oberfläche.

Streamlits normales ``text_input`` übergibt einen neuen Wert erst nach Enter
oder wenn das Feld den Fokus verliert. Diese lokale Komponente meldet jede
Änderung bereits während des Tippens. Der Suchtext wird nur als Zustand
übertragen und niemals als HTML interpretiert.
"""

import streamlit as st

_LIVE_SEARCH_HTML = """
<label for="live-search-input"></label>
<input id="live-search-input" type="search" autocomplete="off" />
"""

_LIVE_SEARCH_CSS = """
:host {
    color: var(--st-text-color);
    font-family: var(--st-font);
}

label {
    display: block;
    margin-bottom: 0.35rem;
    font-size: 0.875rem;
    font-weight: 400;
}

input {
    box-sizing: border-box;
    width: 100%;
    min-height: 2.5rem;
    padding: 0.5rem 0.75rem;
    color: var(--st-text-color);
    background: var(--st-background-color);
    border: 1px solid color-mix(in srgb, var(--st-text-color) 20%, transparent);
    border-radius: var(--st-border-radius);
    font: inherit;
    outline: none;
}

input:focus {
    border-color: var(--st-primary-color);
    box-shadow: 0 0 0 1px var(--st-primary-color);
}
"""

_LIVE_SEARCH_JS = """
export default function(component) {
    const { data, parentElement, setStateValue, setTriggerValue } = component;
    const label = parentElement.querySelector('label');
    const input = parentElement.querySelector('input');

    // textContent und DOM-Properties interpretieren Nutzereingaben nicht als HTML.
    label.textContent = data.label;
    input.placeholder = data.placeholder;
    input.maxLength = data.maxChars;

    if (input.value !== data.value) {
        input.value = data.value ?? '';
    }

    input.oninput = (event) => {
        const value = event.target.value.slice(0, data.maxChars);

        // Der Zustand speichert den Text. Das zusätzliche Trigger-Ereignis sorgt
        // dafür, dass Streamlit die Treffer sofort neu berechnet.
        setStateValue('value', value);
        setTriggerValue('changed', value);
    };
}
"""

_live_search_component = st.components.v2.component(
    "pokemon_live_search",
    html=_LIVE_SEARCH_HTML,
    css=_LIVE_SEARCH_CSS,
    js=_LIVE_SEARCH_JS,
)


def _limited_text(value: object, *, max_chars: int) -> str:
    """Nur Zeichenketten übernehmen und ihre maximale Länge erzwingen."""
    if not isinstance(value, str):
        return ""
    return value[:max_chars]


def live_search_input(
    label: str,
    *,
    placeholder: str,
    key: str,
    max_chars: int = 80,
) -> str:
    """Ein Suchfeld rendern, das seinen Wert bereits während des Tippens meldet."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive.")

    raw_state = st.session_state.get(key, {})
    raw_current_value: object = ""
    if isinstance(raw_state, dict):
        raw_current_value = raw_state.get("value")
    else:
        # Streamlit verwendet je nach Version ein dictionary-ähnliches
        # ComponentResult-Objekt. Dieses unterstützt auch Attributzugriff.
        raw_current_value = getattr(raw_state, "value", "")
    current_value = _limited_text(raw_current_value, max_chars=max_chars)

    result = _live_search_component(
        data={
            "label": label,
            "placeholder": placeholder,
            "value": current_value,
            "maxChars": max_chars,
        },
        default={"value": current_value},
        key=key,
        on_value_change=lambda: None,
        on_changed_change=lambda: None,
        height="content",
    )

    # Der Triggerwert gehört zum aktuellen Tastendruck. Bei anderen Neuläufen
    # greifen wir auf den dauerhaft gespeicherten Zustandswert zurück.
    changed_value = _limited_text(result.changed, max_chars=max_chars)
    if changed_value:
        return changed_value
    return _limited_text(result.value, max_chars=max_chars)
