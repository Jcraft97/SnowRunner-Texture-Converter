# DDS to TGA

A small Python command-line converter for Expeditions editor DDS textures into
the 32-bit TGA layout SnowRunner's editor expects for truck mods.

## Supported formats

| DDS format | TGA output |
| --- | --- |
| Legacy DXT1 (BC1) | Uncompressed 32-bit BGRA, top origin |
| Legacy DXT3 (BC2) | Uncompressed 32-bit BGRA, top origin, explicit alpha |

Only single 2D DXT1 and DXT3 textures and their mip chains are supported. The
converter validates header and payload size, then writes only the decoded
top-level image. DX10 BC7, DXT5, uncompressed RGB, texture arrays, cube maps,
and 3D textures are rejected.

The TGA header matches the SnowRunner templates in `template_SR_TGA`: image
type 2, 32 bits per pixel, image descriptor `0x28` (top-left origin with 8-bit
alpha), and no Truevision footer.

## Requirements

- Python 3.10 or later
- No third-party Python packages

## Usage

Convert one file (the output defaults to the same name with a `.tga` extension):

```powershell
py dds_to_tga.py "C:\textures\truck.dds"
```

Choose an output filename:

```powershell
py dds_to_tga.py "C:\textures\truck.dds" "C:\converted\truck.tga"
```

Convert a directory recursively. Relative subdirectories are preserved in the
output directory:

```powershell
py dds_to_tga.py "C:\textures" "C:\converted"
```

If no output directory is supplied, converted TGA files are written beside
their corresponding DDS files. Unsupported or invalid files are reported;
batch conversion continues for the remaining files and exits with a non-zero
status if any conversion failed.

Expeditions sample inputs used while building this converter live in
`test_convert_DDS_EX`.
