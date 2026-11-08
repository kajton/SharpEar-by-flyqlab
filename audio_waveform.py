from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import medfilt


audio_path = Path(__file__).with_name("test3.mp3")
audio, sample_rate = librosa.load(audio_path, sr=None)
audio = librosa.util.normalize(audio)
duration = len(audio) / sample_rate

print(f"Sample rate: {sample_rate} Hz")
print(f"Duration: {duration:.2f} seconds")

f0, voiced_flag, voiced_probs = librosa.pyin(
    audio,
    sr=sample_rate,
    fmin=190,
    fmax=3500,
)
hop_length = 512
times = librosa.times_like(f0, sr=sample_rate, hop_length=hop_length)
valid_f0 = voiced_flag & (voiced_probs > 0.3) & np.isfinite(f0)
f0_filtered = np.full_like(f0, np.nan)
valid_indices = np.flatnonzero(valid_f0)
if valid_indices.size:
    segment_starts = np.r_[0, np.flatnonzero(np.diff(valid_indices) > 1) + 1]
    segment_ends = np.r_[segment_starts[1:], valid_indices.size]
    for start, end in zip(segment_starts, segment_ends):
        indices = valid_indices[start:end]
        segment = f0[indices]
        padded_segment = np.pad(segment, (2, 2), mode="edge")
        f0_filtered[indices] = medfilt(padded_segment, kernel_size=5)[2:-2]
f0_midi = librosa.hz_to_midi(f0_filtered)

onset_frames = librosa.onset.onset_detect(
    y=audio,
    sr=sample_rate,
    hop_length=hop_length,
    wait=10,
    pre_avg=3,
    post_avg=3,
    pre_max=3,
    post_max=3,
    delta=0.05,
)
onset_times = librosa.frames_to_time(
    onset_frames,
    sr=sample_rate,
    hop_length=hop_length,
)

plt.figure(figsize=(12, 4))
plt.step(times, f0_midi, where="mid")
for onset_time in onset_times:
    plt.axvline(onset_time, color="tab:red", linestyle="--", alpha=0.7)
plt.title("Fundamental frequency: test.mp3")
plt.xlabel("Time (seconds)")
plt.ylabel("MIDI note number")
plt.tight_layout()
plt.show()
