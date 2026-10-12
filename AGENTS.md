# Project guidance

## Purpose

This project contains command-line texture converters. The DDS-to-PCT and
PCT-to-TGA tools target SnowRunner's little-endian `TCIP` PCT format. The
PCT-to-PNG tool handles a separate 72-byte H2A Pict PCT variant.

## Image format notes

- DDS-to-PCT accepts DX10 BC7 2D textures in formats 98 (UNORM) and 99 (sRGB),
  including mip chains. It writes TCIP format IDs 51 (BC7 UNORM) and 52
  (BC7 sRGB).
- PCT-to-TGA decodes TCIP BC7 format IDs 51 and 52 to top-level TGA images.
- PCT-to-PNG decodes H2A Pict DXT1 (`0x0C`), BC7A (`0x34`), raw 4/8-bit
  grayscale, and raw 16-bit RGB565 to PNG.
- A `.pct` extension alone does not identify the PCT variant. Do not conflate
  TCIP and H2A Pict headers or assume their format IDs have the same meaning.
- There is no Expeditions-specific PCT writer. DDS codec support does not imply
  that the produced SnowRunner TCIP PCT is an Expeditions texture.

Do not commit generated output, local archives, virtual environments, or Python
cache files. Do not download other git repos.

## File names

- `SR` = SnowRunner
- `EX` = Expeditions

## Git commits

After completing the requested work, commit the task-related changes by default; do not wait for the user to ask for a commit. Preserve pre-existing unrelated work by leaving it unstaged and out of the commit. Then push the commit. If a commit cannot be created, report the specific blocker and the uncommitted state.

Add this trailer to commits:

```text
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## Reference documentation

Here is the official truck-modding documentation:

<https://expeditions-guides.saber.games/truck_modding/getting_started/intro/>
