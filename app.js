/* Offline YIN-based intonation analysis. */
(() => {
  'use strict';

  const SAMPLE_RATE = 16000;
  const FRAME_LENGTH = 1024;
  const HOP_LENGTH = 256;
  const MIN_HZ = 65;
  const MAX_HZ = 2000;
  const RMS_GATE = 0.05;
  const YIN_THRESHOLD = 0.15;
  const $ = (selector) => document.querySelector(selector);
  const recordButton = $('#recordButton');
  const recordLabel = $('#recordLabel');
  const uploadButton = $('#uploadButton');
  const fileInput = $('#fileInput');
  const statusEl = $('#status');
  const results = $('#results');
  const canvas = $('#chart');
  const tooltip = $('#tooltip');
  const ctx = canvas.getContext('2d');
  let tolerance = 15;
  let analysis = null;
  let recorder = null;
  let stream = null;
  let chunks = [];
  let busy = false;

  function setStatus(message) { statusEl.textContent = message; }

  document.querySelectorAll('.difficulty').forEach((button) => {
    button.addEventListener('click', () => {
      tolerance = Number(button.dataset.tolerance);
      document.querySelectorAll('.difficulty').forEach((item) => {
        const selected = item === button;
        item.classList.toggle('selected', selected);
        item.setAttribute('aria-checked', String(selected));
      });
      if (analysis) drawChart();
    });
  });

  uploadButton.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = '';
    if (!file) return;
    busy = true;
    setControls();
    try {
      if (!/\.wav$/i.test(file.name) && file.type !== 'audio/wav' && file.type !== 'audio/x-wav') {
        throw new Error('Wybierz plik WAV.');
      }
      setStatus(`Analizuję ${file.name}…`);
      await analyzeBlob(file);
    } catch (error) {
      showError(error);
    } finally {
      busy = false;
      setControls();
    }
  });

  recordButton.addEventListener('click', async () => {
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
      setStatus('Przetwarzam nagranie…');
      return;
    }
    if (busy) return;
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        throw new Error('Nagrywanie wymaga przeglądarki obsługującej mikrofon przez HTTPS lub localhost.');
      }
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.addEventListener('dataavailable', (event) => { if (event.data.size) chunks.push(event.data); });
      recorder.addEventListener('stop', async () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
        recorder = null;
        busy = true;
        setControls();
        try {
          setStatus('Analizuję nagranie…');
          await analyzeBlob(blob);
        } catch (error) {
          showError(error);
        } finally {
          busy = false;
          setControls();
        }
      });
      recorder.start();
      recordButton.classList.add('recording');
      recordLabel.textContent = 'STOP';
      setStatus('Nagrywam… naciśnij STOP, gdy skończysz.');
    } catch (error) {
      showError(error);
      if (stream) stream.getTracks().forEach((track) => track.stop());
      stream = null;
      setControls();
    }
  });

  function setControls() {
    const isRecording = recorder && recorder.state === 'recording';
    recordButton.disabled = busy;
    uploadButton.disabled = busy || Boolean(isRecording);
    if (!isRecording) {
      recordButton.classList.remove('recording');
      recordLabel.textContent = busy ? 'ANALYZING' : 'RECORD';
    }
  }

  async function analyzeBlob(blob) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error('Ta przeglądarka nie obsługuje Web Audio API.');
    const audioContext = new AudioContextClass();
    try {
      const buffer = await audioContext.decodeAudioData(await blob.arrayBuffer());
      const mono = mixToMono(buffer);
      const resampled = resample(mono, buffer.sampleRate, SAMPLE_RATE);
      analysis = analyzeSignal(resampled, SAMPLE_RATE);
      results.hidden = false;
      $('#score').innerHTML = `${analysis.percent.toFixed(1)}<span>%</span>`;
      $('#meanError').textContent = analysis.mean.toFixed(1);
      drawChart();
      setStatus(`Analiza gotowa · ${analysis.count} stabilnych ramek.`);
      results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } finally {
      await audioContext.close();
    }
  }

  function mixToMono(buffer) {
    const mono = new Float32Array(buffer.length);
    const channels = buffer.numberOfChannels;
    for (let channel = 0; channel < channels; channel++) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < mono.length; i++) mono[i] += data[i] / channels;
    }
    return mono;
  }

  // Linear resampling to a common, lightweight analysis rate.
  function resample(input, sourceRate, targetRate) {
    if (sourceRate === targetRate) return input;
    const length = Math.max(1, Math.round(input.length * targetRate / sourceRate));
    const output = new Float32Array(length);
    const ratio = sourceRate / targetRate;
    for (let i = 0; i < length; i++) {
      const position = i * ratio;
      const left = Math.min(input.length - 1, Math.floor(position));
      const fraction = position - left;
      const right = Math.min(input.length - 1, left + 1);
      output[i] = input[left] * (1 - fraction) + input[right] * fraction;
    }
    return output;
  }

  function analyzeSignal(signal, sampleRate) {
    if (signal.length < FRAME_LENGTH) throw new Error('Nagranie jest za krótkie. Nagraj dłuższy dźwięk.');
    let peak = 0;
    for (let i = 0; i < signal.length; i++) peak = Math.max(peak, Math.abs(signal[i]));
    if (!peak) throw new Error('Nagranie jest ciszą. Spróbuj ponownie.');

    // Normalize consistently before applying the RMS silence threshold.
    const normalized = new Float32Array(signal.length);
    for (let i = 0; i < signal.length; i++) normalized[i] = signal[i] / peak;

    const minTau = Math.max(2, Math.floor(sampleRate / MAX_HZ));
    const maxTau = Math.min(Math.floor(sampleRate / MIN_HZ), Math.floor(FRAME_LENGTH / 2));
    const frames = [];
    for (let center = 0; center < normalized.length; center += HOP_LENGTH) {
      const frame = new Float32Array(FRAME_LENGTH);
      const start = center - Math.floor(FRAME_LENGTH / 2);
      let energy = 0;
      let validSamples = 0;
      for (let i = 0; i < FRAME_LENGTH; i++) {
        const sourceIndex = start + i;
        if (sourceIndex >= 0 && sourceIndex < normalized.length) {
          const sample = normalized[sourceIndex];
          frame[i] = sample;
          energy += sample * sample;
          validSamples++;
        }
      }
      const rms = Math.sqrt(energy / Math.max(1, validSamples));
      if (rms <= RMS_GATE) continue;
      const hz = yin(frame, sampleRate, minTau, maxTau);
      if (Number.isFinite(hz) && hz >= MIN_HZ && hz <= MAX_HZ) {
        frames.push({ time: center / sampleRate, midi: 69 + 12 * Math.log2(hz / 440) });
      }
    }
    if (frames.length < 3) throw new Error('Nie wykryto wyraźnych dźwięków. Nagraj głośniej lub sprawdź mikrofon.');

    const smoothed = medianFilter(frames.map((frame) => frame.midi), 5);
    const stableFrames = [];
    for (let i = 0; i < smoothed.length; i++) {
      if (i && Math.abs(smoothed[i] - smoothed[i - 1]) >= 0.3) continue;
      stableFrames.push({ time: frames[i].time, midi: smoothed[i] });
    }
    if (stableFrames.length < 3) throw new Error('Za mało stabilnych ramek dźwięku — przytrzymaj nutę chwilę dłużej.');

    const rounded = stableFrames.map((frame) => Math.round(frame.midi));
    const points = [];
    for (let i = 1; i < stableFrames.length - 1; i++) {
      if (rounded[i - 1] !== rounded[i] || rounded[i] !== rounded[i + 1]) continue;
      const cents = (stableFrames[i].midi - rounded[i]) * 100;
      points.push({ time: stableFrames[i].time, cents, midi: rounded[i] });
    }
    if (!points.length) throw new Error('Nie znaleziono ciągłych, stabilnych nut. Przytrzymaj pojedynczą nutę dłużej.');

    const inTune = points.filter((point) => Math.abs(point.cents) <= tolerance);
    return {
      points,
      count: points.length,
      percent: 100 * inTune.length / points.length,
      mean: points.reduce((sum, point) => sum + Math.abs(point.cents), 0) / points.length,
    };
  }

  // YIN difference function + cumulative mean normalized difference, with parabolic refinement.
  function yin(frame, sampleRate, minTau, maxTau) {
    const difference = new Float64Array(maxTau + 1);
    for (let tau = minTau; tau <= maxTau; tau++) {
      let sum = 0;
      // A stride of two keeps the pure-JS implementation responsive on phones.
      for (let i = 0; i < FRAME_LENGTH - tau; i += 2) {
        const delta = frame[i] - frame[i + tau];
        sum += delta * delta;
      }
      difference[tau] = sum;
    }
    const cmnd = new Float64Array(maxTau + 1);
    cmnd[0] = 1;
    let running = 0;
    for (let tau = 1; tau <= maxTau; tau++) {
      running += difference[tau];
      cmnd[tau] = running > 0 ? difference[tau] * tau / running : 1;
    }

    let candidate = -1;
    for (let tau = minTau; tau <= maxTau; tau++) {
      if (cmnd[tau] < YIN_THRESHOLD) {
        while (tau + 1 <= maxTau && cmnd[tau + 1] < cmnd[tau]) tau++;
        candidate = tau;
        break;
      }
    }
    if (candidate < 0) {
      let lowest = Infinity;
      for (let tau = minTau; tau <= maxTau; tau++) {
        if (cmnd[tau] < lowest) { lowest = cmnd[tau]; candidate = tau; }
      }
    }
    if (candidate < 0) return NaN;
    let refined = candidate;
    if (candidate > minTau && candidate < maxTau) {
      const left = cmnd[candidate - 1];
      const middle = cmnd[candidate];
      const right = cmnd[candidate + 1];
      const denominator = left - 2 * middle + right;
      if (Math.abs(denominator) > 1e-12) refined += 0.5 * (left - right) / denominator;
    }
    return sampleRate / refined;
  }

  function medianFilter(values, kernelSize) {
    const radius = Math.floor(kernelSize / 2);
    return values.map((_, index) => {
      const window = [];
      for (let j = Math.max(0, index - radius); j <= Math.min(values.length - 1, index + radius); j++) window.push(values[j]);
      window.sort((a, b) => a - b);
      return window[Math.floor(window.length / 2)];
    });
  }

  function drawChart() {
    if (!analysis) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const width = rect.width;
    const height = rect.height;
    const pad = { left: 42, right: 12, top: 12, bottom: 28 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const points = analysis.points;
    const start = points[0].time;
    const end = points[points.length - 1].time;
    const duration = Math.max(.01, end - start);
    const maxAbs = Math.max(50, tolerance * 1.6, ...points.map((point) => Math.abs(point.cents) * 1.12));
    const yMin = -maxAbs;
    const yMax = maxAbs;
    const x = (time) => pad.left + (time - start) / duration * plotW;
    const y = (cents) => pad.top + (yMax - cents) / (yMax - yMin) * plotH;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(126, 201, 121, .13)';
    const bandTop = y(tolerance);
    const bandBottom = y(-tolerance);
    ctx.fillRect(pad.left, bandTop, plotW, bandBottom - bandTop);
    ctx.strokeStyle = '#363633';
    ctx.lineWidth = 1;
    ctx.font = '9px "DM Mono", monospace';
    ctx.fillStyle = '#858581';
    ctx.textAlign = 'right';
    [-maxAbs, 0, maxAbs].forEach((value) => {
      const py = y(value);
      ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(width - pad.right, py); ctx.stroke();
      ctx.fillText(`${Math.round(value)}c`, pad.left - 7, py + 3);
    });
    ctx.strokeStyle = 'rgba(167,230,161,.45)';
    [tolerance, -tolerance].forEach((value) => {
      ctx.beginPath(); ctx.moveTo(pad.left, y(value)); ctx.lineTo(width - pad.right, y(value)); ctx.stroke();
    });
    ctx.textAlign = 'left';
    ctx.fillStyle = '#858581';
    ctx.fillText('0s', pad.left, height - 7);
    ctx.textAlign = 'right';
    ctx.fillText(`${duration.toFixed(1)}s`, width - pad.right, height - 7);

    points.forEach((point) => {
      ctx.beginPath();
      ctx.arc(x(point.time), y(point.cents), 2.5, 0, Math.PI * 2);
      ctx.fillStyle = Math.abs(point.cents) <= tolerance ? '#a7e6a1' : '#f2f0eb';
      ctx.fill();
    });
    canvas._plot = { points, x, y, pad, plotW, plotH };
  }

  function showError(error) {
    setStatus(error && error.message ? error.message : 'Wystąpił błąd podczas analizy.');
  }

  canvas.addEventListener('pointermove', (event) => {
    const plot = canvas._plot;
    if (!plot) return;
    const rect = canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    let closest = null;
    let distance = 15;
    plot.points.forEach((point) => {
      const d = Math.hypot(plot.x(point.time) - px, plot.y(point.cents) - py);
      if (d < distance) { distance = d; closest = point; }
    });
    if (!closest) { tooltip.hidden = true; return; }
    tooltip.hidden = false;
    tooltip.textContent = `${closest.time.toFixed(2)}s · ${closest.cents >= 0 ? '+' : ''}${closest.cents.toFixed(1)} cents`;
    const xPos = Math.min(rect.width - 170, Math.max(4, px + 12));
    const yPos = Math.max(4, py - 34);
    tooltip.style.left = `${xPos}px`;
    tooltip.style.top = `${yPos}px`;
  });
  canvas.addEventListener('pointerleave', () => { tooltip.hidden = true; });
  window.addEventListener('resize', drawChart);

  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
    window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js').catch(() => {
      setStatus('Tryb offline niedostępny — sprawdź połączenie, aby wczytać aplikację.');
    }));
  }
})();
