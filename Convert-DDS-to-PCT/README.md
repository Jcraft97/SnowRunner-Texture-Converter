# DDS to PCT

A small Python command-line converter for DX10 BC7 DDS textures used with
SnowRunner's TCIP PCT texture format.

## Supported formats

| DDS format | PCT format | Conversion |
| --- | --- | --- |
| DX10 BC7 UNORM (98) | BC7 (51 / `0x33`) | Compressed blocks copied unchanged |
| DX10 BC7 sRGB (99) | BC7 (52 / `0x34`) | Compressed blocks copied unchanged |

Only single 2D DX10 BC7 textures and their mip chains are supported. Other DX10
formats, legacy DXT headers, uncompressed textures, texture arrays, cube maps,
and 3D textures are rejected. DDS payload and mip sizes are validated before
writing.

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
