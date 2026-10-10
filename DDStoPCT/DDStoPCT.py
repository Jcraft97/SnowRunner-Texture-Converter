"""Convert compressed DDS textures to SnowRunner TCIP PCT textures."""

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
DDS_DEPTH_FLAG = 0x800000
DDS_CUBEMAP_CAPS2 = 0x200
DDS_VOLUME_CAPS2 = 0x200000
DDS_RESOURCE_DIMENSION_TEXTURE2D = 3
DDS_RESOURCE_MISC_TEXTURECUBE = 0x4

DXGI_BC1_FORMATS = {71: 12, 72: 12}
DXGI_BC2_FORMATS = {74, 75}
DXGI_BC3_FORMATS = {77: 15, 78: 15}
DXGI_BC7_FORMATS = {98: 51, 99: 52}
LEGACY_FOURCC_FORMATS = {
    b"DXT1": (8, 12, False),
    b"DXT3": (16, 15, True),
    b"DXT5": (16, 15, False),
}
PCT_BLOCK_BYTES = {12: 8, 15: 16, 51: 16, 52: 16}

PCT_WIDTH_OFFSET = 16
PCT_HEIGHT_OFFSET = 20
PCT_FORMAT_OFFSET = 38
PCT_MIP_COUNT_OFFSET = 48
PCT_TABLE_POINTER_OFFSET = 54
PCT_MIP_TABLE_OFFSET = 0x3E
PCT_HEADER_PREFIX = bytes.fromhex(
    "f0000a0000005443495002012000000000040000000400000100000001000000"
    "f2002a00000033000000f900340000000b00000007019200000000000000"
)
PCT_FOOTER_SIZE = 6
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


def _encode_bc3_alpha(dxt3_alpha: bytes) -> bytes:
    alpha_values = [
        ((dxt3_alpha[index // 2] >> (4 * (index % 2))) & 0x0F) * 17
        for index in range(16)
    ]
    alpha0 = max(alpha_values)
    alpha1 = min(alpha_values)
    if alpha0 == alpha1:
        palette = [alpha0] * 8
    else:
        palette = [
            alpha0,
            alpha1,
            *(
                ((8 - index) * alpha0 + (index - 1) * alpha1) // 7
                for index in range(2, 8)
            ),
        ]

    packed_indices = 0
    for index, alpha in enumerate(alpha_values):
        palette_index = min(range(8), key=lambda candidate: abs(palette[candidate] - alpha))
        packed_indices |= palette_index << (3 * index)
    return bytes((alpha0, alpha1)) + packed_indices.to_bytes(6, "little")


def _dxt3_to_bc3(payload: bytes) -> bytes:
    output = bytearray(len(payload))
    for offset in range(0, len(payload), 16):
        output[offset : offset + 8] = _encode_bc3_alpha(payload[offset : offset + 8])
        output[offset + 8 : offset + 16] = payload[offset + 8 : offset + 16]
    return bytes(output)


def _parse_dds(dds_data: bytes) -> tuple[int, int, int, int, bytes, bool]:
    if len(dds_data) < 4 + DDS_HEADER_SIZE:
        raise ValueError("DDS file is too small to contain a complete header")
    if dds_data[:4] != DDS_MAGIC:
        raise ValueError("unrecognized DDS file: missing DDS signature")

    (header_size,) = struct.unpack_from("<I", dds_data, 4)
    if header_size != DDS_HEADER_SIZE:
        raise ValueError(f"invalid DDS header size: {header_size}")
    (flags,) = struct.unpack_from("<I", dds_data, 8)
    height, width = struct.unpack_from("<II", dds_data, 12)
    (depth,) = struct.unpack_from("<I", dds_data, 24)
    (mip_count_field,) = struct.unpack_from("<I", dds_data, 28)
    (pixel_format_size,) = struct.unpack_from("<I", dds_data, 76)
    (pixel_format_flags,) = struct.unpack_from("<I", dds_data, 80)
    fourcc = dds_data[84:88]

    if pixel_format_size != DDS_PIXEL_FORMAT_SIZE:
        raise ValueError(f"invalid DDS pixel format size: {pixel_format_size}")
    if not pixel_format_flags & DDS_FOURCC_FLAG:
        raise ValueError("only block-compressed DDS files are supported")

    payload_offset = 4 + DDS_HEADER_SIZE
    transcode_dxt3 = False
    if fourcc == b"DX10":
        if len(dds_data) < payload_offset + 20:
            raise ValueError("DDS DX10 extended header is truncated")
        dxgi_format, resource_dimension, misc_flag, array_size = struct.unpack_from(
            "<4I", dds_data, payload_offset
        )
        if resource_dimension != DDS_RESOURCE_DIMENSION_TEXTURE2D:
            raise ValueError("only 2D DDS textures are supported")
        if misc_flag & DDS_RESOURCE_MISC_TEXTURECUBE:
            raise ValueError("DDS cube textures are not supported")
        if array_size != 1:
            raise ValueError("DDS texture arrays are not supported")
        if dxgi_format in DXGI_BC1_FORMATS:
            block_bytes, pct_format = 8, DXGI_BC1_FORMATS[dxgi_format]
        elif dxgi_format in DXGI_BC2_FORMATS:
            block_bytes, pct_format = 16, 15
            transcode_dxt3 = True
        elif dxgi_format in DXGI_BC3_FORMATS:
            block_bytes, pct_format = 16, DXGI_BC3_FORMATS[dxgi_format]
        elif dxgi_format in DXGI_BC7_FORMATS:
            block_bytes, pct_format = 16, DXGI_BC7_FORMATS[dxgi_format]
        else:
            raise ValueError(
                f"unsupported DXGI format {dxgi_format}; supported formats are BC1, BC2, BC3, and BC7"
            )
        payload_offset += 20
    elif fourcc in LEGACY_FOURCC_FORMATS:
        (caps2,) = struct.unpack_from("<I", dds_data, 112)
        if caps2 & DDS_CUBEMAP_CAPS2:
            raise ValueError("DDS cube textures are not supported")
        if flags & DDS_DEPTH_FLAG or caps2 & DDS_VOLUME_CAPS2 or depth > 1:
            raise ValueError("only 2D DDS textures are supported")
        block_bytes, pct_format, transcode_dxt3 = LEGACY_FOURCC_FORMATS[fourcc]
    else:
        raise ValueError(
            f"unsupported DDS compression FourCC {fourcc!r}; expected DXT1, DXT3, DXT5, or DX10"
        )

    if not 0 < width <= MAX_DIMENSION or not 0 < height <= MAX_DIMENSION:
        raise ValueError(f"invalid texture dimensions: {width}x{height}")
    mip_count = mip_count_field if flags & DDS_MIPMAPCOUNT_FLAG else 1
    if not 0 < mip_count <= max(width, height).bit_length():
        raise ValueError(f"invalid DDS mip count: {mip_count}")

    payload = dds_data[payload_offset:]
    expected_size = sum(_mip_sizes(width, height, mip_count, block_bytes))
    if len(payload) != expected_size:
        raise ValueError(
            "DDS payload size does not match its dimensions and compressed mip chain "
            f"(expected {expected_size}, found {len(payload)})"
        )
    return width, height, mip_count, pct_format, payload, transcode_dxt3


def _build_pct_header(
    width: int, height: int, mip_count: int, pct_format: int, mip_sizes: list[int]
) -> bytes:
    if len(PCT_HEADER_PREFIX) != PCT_MIP_TABLE_OFFSET:
        raise ValueError("internal PCT header prefix has an unexpected size")
    table_end = PCT_MIP_TABLE_OFFSET + (mip_count * 2 - 1) * 4
    terminal_offset = table_end + 10
    header = bytearray(PCT_HEADER_PREFIX)
    struct.pack_into("<I", header, PCT_WIDTH_OFFSET, width)
    struct.pack_into("<I", header, PCT_HEIGHT_OFFSET, height)
    struct.pack_into("<I", header, PCT_FORMAT_OFFSET, pct_format)
    struct.pack_into("<I", header, PCT_MIP_COUNT_OFFSET, mip_count)
    struct.pack_into("<Q", header, PCT_TABLE_POINTER_OFFSET, table_end)
    header.extend(struct.pack("<I", mip_sizes[0]))
    cumulative_size = mip_sizes[0]
    if mip_count > 1:
        header.extend(struct.pack("<I", cumulative_size))
    for mip_index, mip_size in enumerate(mip_sizes[1:], start=1):
        header.extend(struct.pack("<I", mip_size))
        cumulative_size += mip_size
        if mip_index + 1 < mip_count:
            header.extend(struct.pack("<I", cumulative_size))
    header.extend(struct.pack("<HQ", 0x0104, terminal_offset))
    header.extend(struct.pack("<HI", 0x00FF, terminal_offset))
    return bytes(header)


def dds_to_pct(dds_data: bytes) -> bytes:
    """Convert a BC-compressed DDS texture into a SnowRunner TCIP PCT file."""
    width, height, mip_count, pct_format, payload, transcode_dxt3 = _parse_dds(dds_data)
    output_format = 15 if transcode_dxt3 else pct_format
    output_block_bytes = PCT_BLOCK_BYTES[output_format]
    mip_sizes = _mip_sizes(width, height, mip_count, output_block_bytes)

    if transcode_dxt3:
        converted_mips = []
        offset = 0
        for mip_size in mip_sizes:
            converted_mips.append(_dxt3_to_bc3(payload[offset : offset + mip_size]))
            offset += mip_size
        payload = b"".join(converted_mips)

    header = _build_pct_header(width, height, mip_count, output_format, mip_sizes)
    total_size = len(header) + len(payload) + PCT_FOOTER_SIZE
    terminal_descriptor_offset = len(header) - 6
    result = bytearray(header)
    struct.pack_into("<I", result, terminal_descriptor_offset + 2, total_size - PCT_FOOTER_SIZE)
    result.extend(payload)
    result.extend(struct.pack("<HI", 1, total_size))
    return bytes(result)


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = input_path.with_suffix(".pct")
    pct_data = dds_to_pct(input_path.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pct_data)
    return output_path


def convert_directory(input_dir: Path, output_dir: Path | None = None) -> tuple[int, list[str]]:
    dds_files = sorted(
        path for path in input_dir.rglob("*") if path.is_file() and path.suffix.casefold() == ".dds"
    )
    converted = 0
    errors = []

    for input_path in dds_files:
        relative_path = input_path.relative_to(input_dir).with_suffix(".pct")
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
        description="Convert compressed DDS textures to SnowRunner TCIP PCT textures."
    )
    parser.add_argument("input", type=Path, help="input .dds file or directory")
    parser.add_argument("output", nargs="?", type=Path, help="output .pct path or directory")
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
