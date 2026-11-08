from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import streamlit as st

from comparator import analyze_intonation
from posthog_client import get_posthog_client
from posthog_logs import get_posthog_logs_logger


DIFFICULTY_TOLERANCES = {
    "Easy (±25 centów)": 25,
    "Standard (±15 centów)": 15,
    "Pro (±8 centów)": 8,
}


def capture_analysis_event(event: str, properties: dict[str, object]) -> None:
    if posthog_client is None:
        return

    try:
        posthog_client.capture(
            event=event,
            properties={"$process_person_profile": False, **properties},
        )
    except Exception:
        pass


def show_analysis(
    audio_bytes: bytes,
    suffix: str,
    input_method: str,
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
        except ValueError as e:
            capture_analysis_event(
                "intonation_analysis_rejected",
                {
                    "input_method": input_method,
                    "tolerance_cents": tolerance_cents,
                    "rejection_reason": "unusable_pitch_data",
                },
            )
            if posthog_logs_logger is not None:
                posthog_logs_logger.warning(
                    "intonation_analysis_rejected",
                    extra={
                        "input_method": input_method,
                        "tolerance_cents": tolerance_cents,
                        "rejection_reason": "unusable_pitch_data",
                    },
                )
            st.warning(f"Błąd analizy: {e}")
            return

        capture_analysis_event(
            "intonation_analysis_completed",
            {
                "input_method": input_method,
                "tolerance_cents": tolerance_cents,
                "percent_in_tune": percent_in_tune,
                "mean_absolute_error_cents": mean_error,
            },
        )
        if posthog_logs_logger is not None:
            posthog_logs_logger.info(
                "intonation_analysis_completed",
                extra={
                    "input_method": input_method,
                    "tolerance_cents": tolerance_cents,
                    "percent_in_tune": percent_in_tune,
                    "mean_absolute_error_cents": mean_error,
                },
            )
        st.metric("Czystość intonacji", f"{percent_in_tune:.1f}%")
        st.caption(f"Średni błąd bezwzględny: {mean_error:.2f} centów")
        st.pyplot(figure)
        plt.close(figure)


st.set_page_config(page_title="Analiza intonacji")
posthog_client = get_posthog_client()
posthog_logs_logger = get_posthog_logs_logger()
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
            "upload",
            tolerance_cents,
        )

with microphone_tab:
    recording = st.audio_input("Nagraj dźwięk")
    if recording is not None:
        st.audio(recording)
        show_analysis(
            recording.getvalue(),
            ".wav",
            "microphone",
            tolerance_cents,
        )
