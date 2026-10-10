# Image Converter

Python command-line tools for converting compressed image textures used in
SnowRunner and for decoding a separate H2A Pict PCT variant for Expeditions.

## What files you need:

### SnowRunner

TGAs are used for textures for the trucks. These files then converted by `SnowRunnerEditor` to PCT and DDS formats.

### Expeditions

Expeditions works the same.

Note: Expeditions has its on editor called `ExpeditionsEditor`, They seem to be the same. 

## What files are there:

### SnowRunner 

DDS file for trucks are found in the `editor.pak` file.

PCT files are in the `shared_textures.pak`

### Expeditions

DDS file for trucks are found in the `editor.pak` file.

Expeditions does not include the PCT files in the released version of the game. 
Hence the DDS to PCT converter. 

# Image formats

SnowRunner and Expeditions use diffrent formats for their files. 

### SnowRunner

TGA:  

PCT: Little-endian `TCIP` PCT files with BC7 format IDs 51 and 52

DDS: 

### Expeditions

TGA:

PCT:

DDS: DXT1 and DXT3

# Converter Info

### SnowRunner TCIP PCT to TGA

[`Convert_PCT-to-TGA`](./Convert_PCT-to-TGA/) reads little-endian `TCIP` PCT
files with BC7 format IDs 51 and 52. It decodes the top-level image to a
top-origin, 32-bit TGA. Decoding requires the Python package
`texture2ddecoder`.

This converter is tested and proven.


### H2A Pict PCT to PNG
This converter was buit for the ingame truck store pics and has not been tested with anthing else.

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
