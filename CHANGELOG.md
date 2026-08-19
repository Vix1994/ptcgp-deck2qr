# Changelog

All notable changes will be documented in this file.

The project follows Keep a Changelog structure. A public release versioning policy will be selected before the first release.

## Unreleased

### Fixed

- Parse the live Game8 card-cell format where the image alt contains only the set and
  card number while the adjacent cell text contains the card name and quantity.

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
