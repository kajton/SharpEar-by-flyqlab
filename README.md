# Sharp Ear

**Intonation practice. In the browser.**

[Open Sharp Ear](https://kajton.github.io/SharpEar-by-flyqlab/)

## Operation

1. Select a tolerance: Easy (±25 cents), Standard (±15 cents), or Pro (±8 cents).
2. Record a note, or upload a WAV file.
3. Read the in-tune score and pitch deviation chart.

Microphone access requires a secure connection and browser permission.

## System notes

- Runs as a static web app. No account or server-side audio processing is required.
- The app shell is cached for offline use after the first successful load.
- Audio input: microphone recording or WAV upload.
- Pitch analysis requires a browser with Web Audio API support.

## Deployment

GitHub Actions builds and deploys the app to GitHub Pages when changes are pushed to `main`.
Pull requests run the build checks without deploying.

## Local operation

Serve the repository root over HTTP, then open the local address in a browser. Use `localhost` for microphone access.
