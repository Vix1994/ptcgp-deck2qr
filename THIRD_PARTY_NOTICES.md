# Third-party notices

This file records third-party data and software notices that apply independently of
the license, or absence of a license, for `ptcgp-deck2qr` itself.

## pokemon-tcg-pocket-database

The compact card-print index distributed in:

- `userscript/generated/card-map.json`; and
- `userscript/release/game8-ptcgp-deck-qr.card-map.json`

is generated from [`flibustier/pokemon-tcg-pocket-database`][database].

Source details:

- Upstream version: `2.9.1`
- Upstream file: `dist/cards.json`
- Card count: `3,761`
- SHA-256: `eea30451bdbcf70788fb8e188c7fbe69182f32fa7597fc12ee0272dc9f4e006a`
- Transformation: set code and collector number are mapped to the numeric deck-builder
  identifier encoded in the upstream image filename

The generated index does not redistribute the complete upstream `cards.json` or any
card artwork. Pokémon names, artwork, logos, and trademarks may be subject to rights
not granted by the upstream project's MIT License.

The upstream copyright and license notice follows.

> MIT License
>
> Copyright (c) 2025 Jon (flibustier)
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

[database]: https://github.com/flibustier/pokemon-tcg-pocket-database
