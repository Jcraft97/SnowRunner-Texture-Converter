## Convert PCT textures

Convert one extracted SnowRunner PCT texture to a 32-bit TGA beside the source:

```powershell
python pct_to_tga.py "C:\path\to\truck_texture.pct"
```

An optional second argument sets the output file:

```powershell
python pct_to_tga.py "C:\path\to\truck_texture.pct" "C:\path\to\truck_texture.tga"
```

Pass a folder to convert its `.pct` files recursively. An optional destination
folder preserves the source-relative subfolders:

```powershell
python pct_to_tga.py "C:\path\to\pct_folder"
python pct_to_tga.py "C:\path\to\pct_folder" "C:\path\to\tga_output"
```

Without an output path, TGA files are written beside their PCT sources.

The converter supports little-endian TCIP PCT files with BC7 format IDs 51 and
52. It validates dimensions, mip layout and size, but writes only the decoded
top-level image to TGA. Directory conversion continues after individual file
errors, reports them, and exits non-zero if any file fails. An empty input
folder also returns a non-zero status.