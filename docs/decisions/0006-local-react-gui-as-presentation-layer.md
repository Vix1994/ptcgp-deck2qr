# ADR 0006: Local React GUI as a presentation layer

Status: Accepted

## Context

The recognition pipeline and CLI already implement the current product boundary. A local GUI should
make screenshot selection, explicit energy input, diagnostics, and Deck Text easier to use without
creating a second recognition implementation or expanding the milestone into QR generation, cloud
accounts, history, collection management, or deck editing.

The application is distributed as Python software, while the GUI benefits from component state and
clear empty, loading, success, and failure states.

## Decision

- Use React and Vite for the GUI source under `frontend/`.
- Commit the Vite production build under `src/ptcgp_deck2qr/webgui/` as Python package data.
- Serve the build and one `/api/recognize` endpoint with the Python standard library.
- Bind to `127.0.0.1` by default and open the system browser from `ptcgp-deck2qr gui`.
- Call `pipeline.recognize_image` unchanged. React must not implement detection, matching,
  validation, or Deck Text serialization.
- Limit the GUI to screenshot upload, one-to-three explicit energy selections, optional screenshot
  style override, recognition, original/annotated image viewing, diagnostics, and Deck Text
  copy/download.
- Serve only the four known output artifacts. The GUI is not a general filesystem browser.
- Do not package official logos, card art, screenshots, characters, or other Pokémon assets.

## Consequences

- Node.js is required to modify or rebuild the frontend, but not to run the packaged GUI.
- React adds a small bundled runtime while keeping the interaction states easier to maintain.
- The image is base64-encoded for the local JSON request, so request and image size limits are
  enforced.
- Only one recognition job runs at a time for a GUI process, protecting the shared output directory.
- A cloud or multi-user deployment would require a separate security and storage design.

## Alternatives considered

- **Tkinter:** avoids a frontend build, but makes responsive preview and visual iteration harder.
- **Framework-free JavaScript:** has less bundle overhead, but centralizes many interacting states in
  manual DOM mutation.
- **Flask, FastAPI, or a hosted service:** unnecessary for one local endpoint and would add runtime
  dependencies or widen the product boundary.
- **Recognition logic in JavaScript:** rejected because it would duplicate the authoritative Python
  pipeline and its fail-closed rules.
