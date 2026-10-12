# PCT to PNG converter

`pct_to_png.py` converts the supplied Halo 2 Anniversary PCT/H2A Pict texture
files to PNG using only the Python standard library. These files have a
72-byte header and DDS-compatible compressed payloads. The converter supports
the supplied DXT1 and BC7A color textures, correcting the source BGRA channel
order for PNG, as well as the fallback raw RGB565 and grayscale paths.

Install the one decoder dependency first:

```text
py -m pip install -r requirements.txt
```

## Project Layout

- `pct_to_tga.py` validates TCIP PCT headers and mip layouts and converts BC7
  formats 51 and 52 to top-origin 32-bit TGA. It supports single files and
  recursive directory conversion, with an optional destination preserving
  source-relative paths.
- `test_pct_to_tga.py` covers BC7 conversion, PCT validation, mip sizing,
  directory traversal, and per-file error handling.
- `requirements.txt` pins `texture2ddecoder==1.0.6`, required only for PCT
  texture conversion and the PCT converter tests. Archive extraction,
  CombineXMesh parsing, and FBX export use only the Python standard library;
  there are no other third-party runtime dependencies.
  
## Usage

Convert one file next to the source:

```text
py pct_to_png.py testpct/trucks_img_lib_i1.pct
```

Convert every PCT in a directory into an output directory:

```text
py pct_to_png.py testpct --output png
```

The output PNGs are standard RGBA PNG files and do not require Pillow or any
other third-party package.
