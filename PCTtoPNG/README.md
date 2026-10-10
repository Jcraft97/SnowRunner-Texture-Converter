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
