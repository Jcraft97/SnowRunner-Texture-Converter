"""Convert SnowRunner TCIP PCT textures with BC7 format IDs 51 and 52 to TGA."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

try:
    import texture2ddecoder
except ImportError:
    texture2ddecoder = None


PCT_MAGIC_OFFSET = 6
PCT_WIDTH_OFFSET = 16
PCT_FORMAT_OFFSET = 38
PCT_MIP_COUNT_OFFSET = 0x30
PCT_TABLE_POINTER_OFFSET = 0x36
PCT_MIN_HEADER_SIZE = 0x3E
PCT_FOOTER_SIZE = 6
PCT_LAYOUT_CHAIN_MARKER = 0x0104
PCT_TERMINAL_MARKER = 0x00FF
PCT_BC7_FORMATS = {51, 52}
MAX_DIMENSION = 16384


def _bc7_mip_chain_size(width: int, height: int, mip_count: int) -> int:
    size = 0
    for mip_index in range(mip_count):
        size += ((width + 3) // 4) * ((height + 3) // 4) * 16
        if width == 1 and height == 1:
            if mip_index + 1 != mip_count:
                raise ValueError("PCT mip count exceeds the texture dimensions")
            break
        width = max(1, width // 2)
        height = max(1, height // 2)
    return size


def pct_to_tga(pct_data: bytes) -> bytes:
    if len(pct_data) < PCT_MIN_HEADER_SIZE + PCT_FOOTER_SIZE:
        raise ValueError("file is too small to contain a TCIP PCT header")
    if pct_data[PCT_MAGIC_OFFSET : PCT_MAGIC_OFFSET + 4] != b"TCIP":
        raise ValueError("unrecognized PCT file: missing TCIP signature")

    width, height = struct.unpack_from("<II", pct_data, PCT_WIDTH_OFFSET)
    (format_id,) = struct.unpack_from("<I", pct_data, PCT_FORMAT_OFFSET)
    (mip_count,) = struct.unpack_from("<I", pct_data, PCT_MIP_COUNT_OFFSET)
    if not 0 < width <= MAX_DIMENSION or not 0 < height <= MAX_DIMENSION:
        raise ValueError(f"invalid texture dimensions: {width}x{height}")
    if not 0 < mip_count <= max(width, height).bit_length():
        raise ValueError(f"invalid texture mip count: {mip_count}")
    if format_id not in PCT_BC7_FORMATS:
        raise ValueError(f"unsupported PCT format {format_id}; expected BC7 formats 51 or 52")
    if texture2ddecoder is None:
        raise ValueError("BC7 decoding requires texture2ddecoder; install requirements.txt")

    payload_end = len(pct_data) - PCT_FOOTER_SIZE
    if pct_data[payload_end : payload_end + 2] != b"\x01\x00":
        raise ValueError("PCT file has an invalid engine footer")
    (declared_size,) = struct.unpack_from("<I", pct_data, payload_end + 2)
    if declared_size != len(pct_data):
        raise ValueError("PCT footer size does not match the file size")

    (table_end,) = struct.unpack_from("<Q", pct_data, PCT_TABLE_POINTER_OFFSET)
    if table_end + 2 > payload_end:
        raise ValueError("PCT mip table pointer is outside the file")
    (layout_marker,) = struct.unpack_from("<H", pct_data, table_end)
    if layout_marker == PCT_LAYOUT_CHAIN_MARKER:
        if table_end + 10 > payload_end:
            raise ValueError("PCT mip table pointer chain is truncated")
        (terminal_offset,) = struct.unpack_from("<Q", pct_data, table_end + 2)
    elif layout_marker == PCT_TERMINAL_MARKER:
        terminal_offset = table_end
    else:
        raise ValueError(f"unsupported PCT layout marker 0x{layout_marker:04X}")

    if terminal_offset + PCT_FOOTER_SIZE > payload_end:
        raise ValueError("PCT terminal descriptor is outside the file")
    (terminal_marker,) = struct.unpack_from("<H", pct_data, terminal_offset)
    if terminal_marker != PCT_TERMINAL_MARKER:
        raise ValueError("PCT layout chain does not end at a terminal descriptor")
    payload_offset = terminal_offset + PCT_FOOTER_SIZE

    chain_size = _bc7_mip_chain_size(width, height, mip_count)
    if payload_end - payload_offset != chain_size:
        raise ValueError("PCT payload size does not match its dimensions and BC7 mip chain")

    top_level_size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    pixels = texture2ddecoder.decode_bc7(
        pct_data[payload_offset : payload_offset + top_level_size], width, height
    )
    if len(pixels) != width * height * 4:
        raise ValueError("BC7 decoder returned an unexpected pixel buffer size")

    tga_header = struct.pack(
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
    return tga_header + pixels


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = input_path.with_suffix(".tga")
    tga_data = pct_to_tga(input_path.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(tga_data)
    return output_path


def convert_directory(input_dir: Path, output_dir: Path | None = None) -> tuple[int, list[str]]:
    pct_files = sorted(
        path for path in input_dir.rglob("*") if path.is_file() and path.suffix.casefold() == ".pct"
    )
    converted = 0
    errors = []

    for input_path in pct_files:
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
    parser = argparse.ArgumentParser(description="Convert a SnowRunner PCT texture to TGA.")
    parser.add_argument("input", type=Path, help="input .pct file")
    parser.add_argument("output", nargs="?", type=Path, help="output .tga path")
    args = parser.parse_args(argv)

    if args.input.is_dir():
        converted, errors = convert_directory(args.input, args.output)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if converted == 0 and not errors:
            print(f"error: no .pct files found in {args.input}", file=sys.stderr)
            return 1
        print(f"Converted {converted} PCT file(s).")
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