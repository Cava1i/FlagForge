# README Logo Update Design

> Goal: add a centered, pure-graphic rectangular logo to the top of the README.

## Architecture

Create a single self-contained SVG at `docs/assets/logo.svg` and reference it from the README with a centered HTML block. The SVG will stay text-free and use a dark terminal-like frame, an abstract scan/capture motif, orchestration nodes, and a flag glyph to match the project's CTF theme.

## Testing

Verify the README references the relative asset path correctly and inspect the SVG for a clean rectangular composition with no visible text.
