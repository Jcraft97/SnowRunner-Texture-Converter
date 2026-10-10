# Image Converter

Python command-line tools for converting compressed image textures used in
SnowRunner and for decoding a separate H2A Pict PCT variant.

## Image formats

### DDS to SnowRunner TCIP PCT

[`Convert_DDS-to-PCT`](./Convert_DDS-to-PCT/) converts block-compressed DDS
textures to SnowRunner's little-endian `TCIP` PCT format.

| DDS input | TCIP PCT format ID | Handling |
| --- | --- | --- |
| DXT1 / BC1 | `0x0C` (12) | Compressed blocks copied unchanged |
| DXT3 / BC2 | `0x0F` (15) | Explicit alpha is transcoded to BC3; color blocks are copied |
| DXT5 / BC3 | `0x0F` (15) | Compressed blocks copied unchanged |
| DX10 BC7 UNORM | `0x33` (51) | Compressed blocks copied unchanged |
| DX10 BC7 UNORM_SRGB | `0x34` (52) | Compressed blocks copied unchanged |

Legacy DDS headers support DXT1, DXT3, and DXT5. DX10 DDS headers support BC1,
BC2, BC3, and BC7. The converter accepts single 2D textures and mip chains;
uncompressed textures, arrays, cube maps, and 3D textures are not supported.

### SnowRunner TCIP PCT to TGA

[`Convert_PCT-to-TGA`](./Convert_PCT-to-TGA/) reads little-endian `TCIP` PCT
files with BC7 format IDs 51 and 52. It decodes the top-level image to a
top-origin, 32-bit TGA. Decoding requires the Python package
`texture2ddecoder`.

### H2A Pict PCT to PNG

[`Convert_PCT-to-PNG`](./Convert_PCT-to-PNG/) handles a separate PCT variant
with a 72-byte H2A Pict header. It decodes DXT1 (`0x0C`) and BC7A (`0x34`)
compressed textures, as well as raw 4-bit and 8-bit grayscale and 16-bit
RGB565 pixel data, to RGBA PNG. BC7A decoding requires `texture2ddecoder`;
other decoding and PNG writing use the Python standard library.

The `.pct` extension does not identify which PCT variant a file uses. TCIP PCT
and H2A Pict have different headers and format meanings; use the matching
converter rather than assuming the formats are interchangeable.

### Expeditions

There is no Expeditions-specific PCT writer in this project. The
DDS-to-PCT converter writes SnowRunner TCIP PCT files, even when its DDS input
uses a supported compression format. The Expeditions DDS examples in the
workspace use DXT1 and DXT3; accepting those DDS codecs does not establish
support for Expeditions' texture containers or output format.

## Project layout

Each converter has its own folder and README with usage details:

- [`Convert_DDS-to-PCT`](./Convert_DDS-to-PCT/README.md)
- [`Convert_PCT-to-PNG`](./Convert_PCT-to-PNG/README.md)
- [`Convert_PCT-to-TGA`](./Convert_PCT-to-TGA/README.md)

## Reference documentation

Here is the official truck-modding documentation:

<https://expeditions-guides.saber.games/truck_modding/getting_started/intro/>
