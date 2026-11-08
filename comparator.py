from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import medfilt


HOP_LENGTH = 512
FRAME_LENGTH = 2048


def _extract_midi(path: str | Path) -> np.ndarray:
    audio, sample_rate = librosa.load(path, sr=None)
    audio = librosa.util.normalize(audio)
    f0 = librosa.yin(
        audio,
        fmin=65,
        fmax=2000,
        sr=sample_rate,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
    )
    rms = librosa.feature.rms(
        y=audio,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
    )[0]

    valid = np.isfinite(f0) & (rms > 0.01)
    if not np.any(valid):
        raise ValueError(f"No audible pitch frames found in {path}")

    return librosa.hz_to_midi(f0[valid])


def compare_audio(ref_path: str | Path, user_path: str | Path) -> float:
    """Align two audio pitch tracks and return their mean absolute error in cents."""
    ref_midi = _extract_midi(ref_path)
    user_midi = _extract_midi(user_path)

    _, warping_path = librosa.sequence.dtw(
        X=ref_midi[np.newaxis, :],
        Y=user_midi[np.newaxis, :],
        metric="euclidean",
    )
    aligned_path = warping_path[::-1]
    ref_aligned_midi = ref_midi[aligned_path[:, 0]]
    user_aligned_midi = user_midi[aligned_path[:, 1]]

    mean_error_cents = float(
        np.mean(np.abs(ref_aligned_midi - user_aligned_midi)) * 100
    )
    print(f"Mean intonation error: {mean_error_cents:.2f} cents")

    alignment_steps = np.arange(len(aligned_path))
    plt.figure(figsize=(12, 5))
    plt.step(
        alignment_steps,
        librosa.midi_to_hz(ref_aligned_midi),
        where="mid",
        label=f"Reference: {Path(ref_path).name}",
    )
    plt.step(
        alignment_steps,
        librosa.midi_to_hz(user_aligned_midi),
        where="mid",
        label=f"User: {Path(user_path).name}",
    )
    plt.yscale("log")
    plt.xlabel("DTW alignment step")
    plt.ylabel("Fundamental frequency (Hz)")
    plt.title("F0 tracks aligned with DTW")
    plt.legend()
    plt.tight_layout()
    plt.show()

    return mean_error_cents


def analyze_intonation(
    file_path: str | Path,
    tolerance_cents: float = 15,
    show_plot: bool = True,
) -> tuple[float, float, plt.Figure]:
    """Analyze pitch accuracy and return the metrics and deviation plot."""
    if tolerance_cents < 0:
        raise ValueError("tolerance_cents must be non-negative")

    y, sample_rate = librosa.load(file_path, sr=None)
    y = librosa.util.normalize(y)
    f0 = librosa.yin(
        y,
        fmin=65,
        fmax=2000,
        sr=sample_rate,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
    )
    rms = librosa.feature.rms(
        y=y,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
    )[0]

    # Use matching frame/hop lengths and reject quiet frames before smoothing pitch.
    voiced = np.isfinite(f0) & (rms > 0.05)
    if not np.any(voiced):
        raise ValueError(f"No audible pitch frames found in {file_path}")

    voiced_f0 = medfilt(f0[voiced], kernel_size=5)
    midi_f0 = librosa.hz_to_midi(voiced_f0)
    times = librosa.times_like(
        f0,
        sr=sample_rate,
        hop_length=HOP_LENGTH,
    )[voiced]

    # Exclude frames whose pitch changes abruptly, such as note transitions or clicks.
    stable = np.abs(np.diff(midi_f0, prepend=midi_f0[0])) < 0.3
    midi_f0 = midi_f0[stable]
    times = times[stable]
    if not midi_f0.size:
        raise ValueError(f"No stable pitch frames found in {file_path}")

    deviation_cents = (midi_f0 - np.round(midi_f0)) * 100
    within_tolerance = np.abs(deviation_cents) <= tolerance_cents
    percent_in_tune = float(np.mean(within_tolerance) * 100)
    mean_absolute_error = float(np.mean(np.abs(deviation_cents)))
    print(f"Within ±{tolerance_cents:g} cents: {percent_in_tune:.2f}%")
    print(f"Mean absolute intonation error: {mean_absolute_error:.2f} cents")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axhspan(
        -tolerance_cents,
        tolerance_cents,
        color="green",
        alpha=0.2,
        label=f"Tolerance (±{tolerance_cents:g} cents)",
    )
    ax.scatter(
        times[within_tolerance],
        deviation_cents[within_tolerance],
        color="tab:blue",
        s=10,
        label="Within tolerance",
    )
    ax.scatter(
        times[~within_tolerance],
        deviation_cents[~within_tolerance],
        color="red",
        s=10,
        label="Outside tolerance",
    )
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Deviation from nearest MIDI note (cents)")
    ax.set_title(f"Intonation analysis: {Path(file_path).name}")
    ax.legend()
    fig.tight_layout()
    if show_plot:
        plt.show()

    return percent_in_tune, mean_absolute_error, fig
