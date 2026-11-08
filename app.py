from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import streamlit as st

from comparator import analyze_intonation


DIFFICULTY_TOLERANCES = {
    "Easy (±25 centów)": 25,
    "Standard (±15 centów)": 15,
    "Pro (±8 centów)": 8,
}


def show_analysis(
    audio_bytes: bytes,
    suffix: str,
    file_name: str,
    tolerance_cents: int,
) -> None:
    with TemporaryDirectory() as temp_dir:
        audio_path = Path(temp_dir) / f"audio{suffix}"
        audio_path.write_bytes(audio_bytes)

        try:
            percent_in_tune, mean_error, figure = analyze_intonation(
                audio_path,
                tolerance_cents=tolerance_cents,
                show_plot=False,
            )
        except ValueError:
            st.warning(
                "Nie wykryto wyraźnych dźwięków. Nagraj głośniej lub sprawdź mikrofon."
            )
            return

        st.metric("Czystość intonacji", f"{percent_in_tune:.1f}%")
        st.caption(f"Średni błąd bezwzględny: {mean_error:.2f} centów")
        st.pyplot(figure)
        plt.close(figure)


st.set_page_config(page_title="Analiza intonacji")
st.title("Analiza czystości intonacji")
difficulty = st.radio(
    "Poziom trudności",
    options=list(DIFFICULTY_TOLERANCES),
    index=1,
    horizontal=True,
)
tolerance_cents = DIFFICULTY_TOLERANCES[difficulty]

upload_tab, microphone_tab = st.tabs(["Wgraj plik", "Nagraj z mikrofonu"])

with upload_tab:
    uploaded_file = st.file_uploader(
        "Wybierz plik audio",
        type=["wav", "mp3"],
    )
    if uploaded_file is not None:
        st.audio(uploaded_file)
        show_analysis(
            uploaded_file.getvalue(),
            Path(uploaded_file.name).suffix.lower(),
            uploaded_file.name,
            tolerance_cents,
        )

with microphone_tab:
    recording = st.audio_input("Nagraj dźwięk")
    if recording is not None:
        st.audio(recording)
        show_analysis(
            recording.getvalue(),
            ".wav",
            "Nagranie z mikrofonu",
            tolerance_cents,
        )
