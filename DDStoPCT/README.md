# DDS to PCT

A small Python command-line converter for block-compressed DDS textures used
with SnowRunner's TCIP PCT texture format.

## Supported formats

| DDS format | PCT format | Conversion |
| --- | --- | --- |
| DXT1 / BC1 | BC1 (`0x0C`) | Compressed blocks copied unchanged |
| DXT3 / BC2 | BC3 (`0x0F`) | Alpha blocks transcoded; color blocks copied |
| DXT5 / BC3 | BC3 (`0x0F`) | Compressed blocks copied unchanged |
| DX10 BC7 UNORM | BC7 (`0x33`) | Compressed blocks copied unchanged |
| DX10 BC7 UNORM_SRGB | BC7 (`0x34`) | Compressed blocks copied unchanged |

The PCT format IDs for BC1, BC3, and BC7 are based on the reverse-engineered
format mapping in [SRPCT](https://github.com/Pieselka/SRPCT), specifically
[`SRPCT_Core.h`](https://github.com/Pieselka/SRPCT/blob/fc09defcf076280c3c30b8427725e50646bf87ea/src/SRPCT_Core.h)
and its [format notes](https://github.com/Pieselka/SRPCT/blob/fc09defcf076280c3c30b8427725e50646bf87ea/README.md).
That mapping documents BC1 as `0x0C`, BC3 as `0x0F`, and BC7 as `0x33`/`0x34`;
it does not document BC2 as a PCT format. For DXT3/BC2 input, the converter
re-encodes each explicit 4-bit alpha block into a BC3 interpolated-alpha block
and stores the result as PCT BC3. This keeps the color blocks intact but can
change alpha values by at most 17/255 (17 levels in 8-bit alpha).

The converter supports legacy `DXT1`, `DXT3`, and `DXT5` DDS headers, and DX10
headers for BC1, BC2, BC3, and BC7. It supports single 2D textures and their
mip chains. Uncompressed textures, texture arrays, cube maps, and 3D textures
are not supported. DDS payload and mip sizes are validated before writing.

## Requirements

- Python 3.10 or later
- No third-party Python packages

## Usage

Convert one file (the output defaults to the same name with a `.pct` extension):

```powershell
py DDStoPCT.py "C:\textures\truck.dds"
```

Choose an output filename:

```powershell
py DDStoPCT.py "C:\textures\truck.dds" "C:\converted\truck.pct"
```

Convert a directory recursively. Relative subdirectories are preserved in the
output directory:

```powershell
py DDStoPCT.py "C:\textures" "C:\converted"
```

If no output directory is supplied, converted PCT files are written beside
their corresponding DDS files. Unsupported or invalid files are reported;
batch conversion continues for the remaining files and exits with a non-zero
status if any conversion failed.
