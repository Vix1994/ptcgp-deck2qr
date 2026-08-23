# Changelog

All notable changes will be documented in this file.

The project follows Keep a Changelog structure. A public release versioning policy will be selected before the first release.

## Unreleased

### Fixed

- Parse the live Game8 card-cell format where the image alt contains only the set and
  card number while the adjacent cell text contains the card name and quantity.
- Recover one missing interior or edge contour in a strongly regular portrait grid when the predicted crop
  independently passes strict artwork-only entity matching.
- Match portrait screenshot cards by artwork ROI instead of allowing borders, language, or lower
  rules text to determine entity identity.
- Normalize regular multi-row portrait crops to shared grid centers and dominant card dimensions so
  one shortened or shifted contour cannot misalign its artwork ROI.
- Replace exact portrait artwork cropping with shifted hash recall, five-scale local alignment,
  occlusion-tolerant 3×3 patch scoring, and leading-candidate ORB/RANSAC verification.
- Limit expensive patch and feature verification to reranked candidates, reducing the supplied
  20-card screenshot from about 6.0 seconds to 2.9 seconds cold / 1.7 seconds warm on the same runtime.

### Added

- Initial Python project scaffold.
- Product, architecture, development, testing, data, Card Database, and Deck Text documentation.
- Baseline lint, format, type-check, test, and CI configuration.
- Deck Text v1 model, strict parser, canonical writer, and validation.
- External database adapter, source-validated fingerprint index, classical matcher, and recognition CLI.
- Synthetic fixture coverage and fail-closed `recognition.json` / `recognized.png` diagnostics.
- Region-proposal to physical-card-slot resolution with stable global grid identities.
- Independent Game8 Tampermonkey adapter with a compact source-hashed card-print map,
  fail-closed 20-card parsing, energy confirmation, and local deck-share QR generation.
- GitHub Raw userscript distribution with a lightweight Tampermonkey update metadata
  endpoint.
- Retained upstream attribution, versioned provenance, and MIT License notice for the
  generated card-print index.
- Modular Tampermonkey distribution with a small loader, independently versioned core
  and card-map resources, and generated SHA-256 integrity pins.
