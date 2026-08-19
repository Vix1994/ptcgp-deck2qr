# Deck Text Format v1

Status: normative draft  
Media type: `text/plain`  
Encoding: UTF-8  
Canonical extension: `.txt`

This document is the normative definition of the text boundary between screenshot recognition and future consumers such as a QR encoder.

## Example

```text
# PTCGP-DECK 1
name: miraizone - ori
energy: lightning

[pokemon]
2 Magnemite | A1-097
2 Magneton | A1-098
2 Magnezone | A1-099
1 Miraidon ex | B3a-019
2 Oricorio | B3a-020

[trainer]
2 Poké Ball | PROMO-A-005
2 Professor's Research | PROMO-A-007
1 Cyrus | A2-150
```

## Grammar

The following EBNF is informative; the prose requirements are normative.

```text
document      = header, newline, metadata, newline, sections ;
header        = "# PTCGP-DECK 1" ;
metadata      = [ name-line ], energy-line ;
name-line     = "name:", space, value, newline ;
energy-line   = "energy:", space, energy, { ",", energy }, newline ;
sections      = pokemon-section, newline, trainer-section ;
pokemon-section = "[pokemon]", newline, { card-line } ;
trainer-section = "[trainer]", newline, { card-line } ;
card-line     = count, space, name, space, "|", space, print-id, newline ;
print-id      = set-code, "-", card-number ;
```

## Header

The first line must be exactly:

```text
# PTCGP-DECK 1
```

Consumers must reject unsupported major versions.

## Metadata

### Name

`name` is optional and informational. A writer should use the input file stem when a reliable deck name is unavailable.

### Energy

`energy` is required and contains one to three unique, comma-separated values. Order is significant and must be preserved.

Allowed v1 values are:

```text
grass
fire
water
lightning
psychic
fighting
darkness
metal
```

Whitespace around commas is accepted by parsers but omitted by canonical writers.

## Sections

Both `[pokemon]` and `[trainer]` section headers are required. A section may be empty, although deck validation may reject a deck without Pokémon.

Every card line has the form:

```text
<count> <display name> | <set code>-<card number>
```

Requirements:

- `count` is a positive base-10 integer.
- The pipe separator is required.
- The display name is informational and must not be used as the identity key.
- Identity is the pair `(set code, card number)`.
- Set-code matching is case-sensitive in canonical output.
- Canonical card numbers are zero-padded to at least three digits.
- Parsers accept unpadded positive card numbers and canonicalize them when writing.

## Comments and unknown fields

Version 1 does not permit inline comments, additional metadata fields, duplicate section headers, or unknown sections. Strict rejection keeps the format deterministic and prevents spelling mistakes from being silently ignored.

## Canonicalization

A canonical writer must:

1. Emit UTF-8 with LF newlines.
2. End the file with exactly one newline.
3. Use lowercase energy names with no spaces around commas.
4. Use the authoritative database display name.
5. Aggregate identical `(set, number)` entries within the same section.
6. Emit Pokémon before Trainers.
7. Sort by set release order, then set code, then numeric card number.
8. Zero-pad card numbers to at least three digits.
9. Omit trailing whitespace and extra blank lines.

## Validation

A valid PTCGP deck for the current milestone must:

- Contain exactly 20 cards after summing counts.
- Contain at least one Pokémon entry.
- Use counts of 1 or 2 for normal game decks.
- Contain one to three unique allowed energies.
- Resolve every print ID through the configured card database.
- Resolve each print into the section in which it appears.

Parser validity and game-deck validity are separate operations. A parser may successfully read a syntactically valid 19-card document; the deck validator must reject it.

## Print aliases

Some database print IDs reference the same visual asset and semantic entity. Recognition cannot visually distinguish these aliases.

The canonical Deck Text writer selects one deterministic print ID: earliest set release date, then set code, then numeric card number. All candidates, confidence, and alias diagnostics belong in `recognition.json`, not in the canonical Deck Text.

## Compatibility policy

- Clarifications that do not change accepted documents may update this file without a version bump.
- Any change to syntax, required fields, identity, or canonical output requires a new format version and an ADR.
- Writers must never emit a format version they cannot parse back losslessly.
