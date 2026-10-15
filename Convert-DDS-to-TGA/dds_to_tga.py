"""Convert Expeditions DXT1/DXT3 DDS textures to SnowRunner 32-bit TGA."""

from __future__ import annotations

import argparse
import struct
import sys
from collections.abc import Iterator
from pathlib import Path


DDS_MAGIC = b"DDS "
DDS_HEADER_SIZE = 124
DDS_PIXEL_FORMAT_SIZE = 32
DDS_FOURCC_FLAG = 0x4
DDS_MIPMAPCOUNT_FLAG = 0x20000
DDS_FOURCC_BLOCK_BYTES = {b"DXT1": 8, b"DXT3": 16}
MAX_DIMENSION = 16384


def _mip_dimensions(width: int, height: int, mip_count: int) -> Iterator[tuple[int, int]]:
    for _ in range(mip_count):
        yield width, height
        width = max(1, width // 2)
        height = max(1, height // 2)


def _mip_sizes(width: int, height: int, mip_count: int, block_bytes: int) -> list[int]:
    return [
        ((mip_width + 3) // 4) * ((mip_height + 3) // 4) * block_bytes
        for mip_width, mip_height in _mip_dimensions(width, height, mip_count)
    ]


def _rgb565(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 0x1F
    green = (value >> 5) & 0x3F
    blue = value & 0x1F
    return (red << 3) | (red >> 2), (green << 2) | (green >> 4), (blue << 3) | (blue >> 2)


def _decode_dxt_color(block: bytes, dxt1: bool) -> list[tuple[int, int, int, int]]:
    color0, color1 = struct.unpack_from("<HH", block, 0)
    colors = [(*_rgb565(color0), 255), (*_rgb565(color1), 255)]
    if color0 > color1 or not dxt1:
        colors += [
            tuple((2 * colors[0][index] + colors[1][index]) // 3 for index in range(4)),
            tuple((colors[0][index] + 2 * colors[1][index]) // 3 for index in range(4)),
        ]
    else:
        colors += [
            tuple((colors[0][index] + colors[1][index]) // 2 for index in range(4)),
            (0, 0, 0, 0),
        ]
    indices = int.from_bytes(block[4:8], "little")
    return [colors[(indices >> (2 * pixel)) & 3] for pixel in range(16)]


def _decode_dxt_top_level(payload: bytes, width: int, height: int, fourcc: bytes) -> bytes:
    block_bytes = DDS_FOURCC_BLOCK_BYTES[fourcc]
    dxt3 = fourcc == b"DXT3"
    pixels = bytearray(width * height * 4)
    offset = 0
    for block_y in range(0, height, 4):
        for block_x in range(0, width, 4):
            if offset + block_bytes > len(payload):
                raise ValueError("DDS payload ended inside a compressed block")
            block = payload[offset : offset + block_bytes]
            offset += block_bytes
            if dxt3:
                alpha_bits = int.from_bytes(block[:8], "little")
                decoded = _decode_dxt_color(block[8:], dxt1=False)
                decoded = [
                    (red, green, blue, ((alpha_bits >> (4 * index)) & 0xF) * 17)
                    for index, (red, green, blue, _) in enumerate(decoded)
                ]
            else:
                decoded = _decode_dxt_color(block, dxt1=True)
            for local_y in range(4):
                for local_x in range(4):
                    x = block_x + local_x
                    y = block_y + local_y
                    if x >= width or y >= height:
                        continue
                    red, green, blue, alpha = decoded[local_y * 4 + local_x]
                    pixel = (y * width + x) * 4
                    pixels[pixel : pixel + 4] = bytes((blue, green, red, alpha))
    return bytes(pixels)


def _parse_dds(dds_data: bytes) -> tuple[int, int, int, bytes, bytes]:
    if len(dds_data) < 4 + DDS_HEADER_SIZE:
        raise ValueError("DDS file is too small to contain a complete header")
    if dds_data[:4] != DDS_MAGIC:
        raise ValueError("unrecognized DDS file: missing DDS signature")

    (header_size,) = struct.unpack_from("<I", dds_data, 4)
    if header_size != DDS_HEADER_SIZE:
        raise ValueError(f"invalid DDS header size: {header_size}")
    (flags,) = struct.unpack_from("<I", dds_data, 8)
    height, width = struct.unpack_from("<II", dds_data, 12)
    (mip_count_field,) = struct.unpack_from("<I", dds_data, 28)
    (pixel_format_size,) = struct.unpack_from("<I", dds_data, 76)
    (pixel_format_flags,) = struct.unpack_from("<I", dds_data, 80)
    fourcc = dds_data[84:88]

    if pixel_format_size != DDS_PIXEL_FORMAT_SIZE:
        raise ValueError(f"invalid DDS pixel format size: {pixel_format_size}")
    if not pixel_format_flags & DDS_FOURCC_FLAG:
        raise ValueError("only DXT1 and DXT3 DDS files are supported")
    if fourcc == b"DX10":
        raise ValueError("unsupported DDS compression FourCC b'DX10'; expected DXT1 or DXT3")
    if fourcc not in DDS_FOURCC_BLOCK_BYTES:
        raise ValueError(
            f"unsupported DDS compression FourCC {fourcc!r}; expected DXT1 or DXT3"
        )

    if not 0 < width <= MAX_DIMENSION or not 0 < height <= MAX_DIMENSION:
        raise ValueError(f"invalid texture dimensions: {width}x{height}")
    mip_count = mip_count_field if flags & DDS_MIPMAPCOUNT_FLAG else 1
    if not 0 < mip_count <= max(width, height).bit_length():
        raise ValueError(f"invalid DDS mip count: {mip_count}")

    payload = dds_data[4 + DDS_HEADER_SIZE :]
    expected_size = sum(_mip_sizes(width, height, mip_count, DDS_FOURCC_BLOCK_BYTES[fourcc]))
    if len(payload) != expected_size:
        raise ValueError(
            "DDS payload size does not match its dimensions and compressed mip chain "
            f"(expected {expected_size}, found {len(payload)})"
        )
    return width, height, mip_count, fourcc, payload


def _build_sr_tga(width: int, height: int, bgra: bytes) -> bytes:
    if len(bgra) != width * height * 4:
        raise ValueError("decoded pixel buffer size does not match the texture dimensions")
    header = struct.pack(
        "<BBBHHBHHHHBB",
        0,
        0,
        2,
        0,
        0,
        0,
        0,
        0,
        width,
        height,
        32,
        0x28,
    )
    return header + bgra


def dds_to_tga(dds_data: bytes) -> bytes:
    """Decode the top-level Expeditions DXT1/DXT3 image to a SnowRunner TGA."""
    width, height, _mip_count, fourcc, payload = _parse_dds(dds_data)
    top_level_size = _mip_sizes(width, height, 1, DDS_FOURCC_BLOCK_BYTES[fourcc])[0]
    pixels = _decode_dxt_top_level(payload[:top_level_size], width, height, fourcc)
    return _build_sr_tga(width, height, pixels)


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = input_path.with_suffix(".tga")
    tga_data = dds_to_tga(input_path.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(tga_data)
    return output_path


def convert_directory(input_dir: Path, output_dir: Path | None = None) -> tuple[int, list[str]]:
    dds_files = sorted(
        path for path in input_dir.rglob("*") if path.is_file() and path.suffix.casefold() == ".dds"
    )
    converted = 0
    errors = []

    for input_path in dds_files:
        relative_path = input_path.relative_to(input_dir).with_suffix(".tga")
        target_dir = output_dir if output_dir is not None else input_dir
        output_path = target_dir / relative_path
        try:
            convert_file(input_path, output_path)
            converted += 1
        except (OSError, ValueError) as error:
            errors.append(f"{input_path}: {error}")

    return converted, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert Expeditions DXT1/DXT3 DDS textures to SnowRunner 32-bit TGA."
    )
    parser.add_argument("input", type=Path, help="input .dds file or directory")
    parser.add_argument("output", nargs="?", type=Path, help="output .tga path or directory")
    args = parser.parse_args(argv)

    if args.input.is_dir():
        converted, errors = convert_directory(args.input, args.output)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if converted == 0 and not errors:
            print(f"error: no .dds files found in {args.input}", file=sys.stderr)
            return 1
        print(f"Converted {converted} DDS file(s).")
        return 1 if errors else 0

    try:
        output_path = convert_file(args.input, args.output)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
