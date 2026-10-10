"""Convert the PCT files used by the supplied image library to PNG.

The files in ``testpct`` contain a 72-byte H2A Pict header followed by a DDS-
compatible texture payload.  The supplied files use DXT1 color textures and
BC5/DXN two-channel normal maps.

This module intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import binascii
import struct
from pathlib import Path
from typing import Iterable


HEADER_SIZE = 72
WIDTH_OFFSET = 16
HEIGHT_OFFSET = 20
# The field begins at byte 62.  The surrounding PCT record is a mixture of
# 16-bit and 32-bit fields, so it is easy to misread this as offset 60 when
# viewing the header in 4-byte groups.
PAYLOAD_SIZE_OFFSET = 62
FORMAT_OFFSET = 38


class PCTError(ValueError):
    """Raised when a PCT file cannot be decoded."""


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def _write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    rows = b"".join(b"\x00" + rgba[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += _png_chunk(b"IDAT", __import__("zlib").compress(rows, 9))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _gray_rgba(values: Iterable[int]) -> bytes:
    output = bytearray()
    for value in values:
        output += bytes((value, value, value, 255))
    return bytes(output)


def _swap_red_blue(rgba: bytes) -> bytes:
    """Convert the source texture's BGRA channel order to PNG RGBA."""
    output = bytearray(rgba)
    for index in range(0, len(output), 4):
        output[index], output[index + 2] = output[index + 2], output[index]
    return bytes(output)


def _rgb565(value: int) -> tuple[int, int, int]:
    r = (value >> 11) & 0x1F
    g = (value >> 5) & 0x3F
    b = value & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _decode_dxt_color(block: bytes, dxt1: bool) -> list[tuple[int, int, int, int]]:
    c0, c1 = struct.unpack_from("<HH", block, 0)
    colors = [(*_rgb565(c0), 255), (*_rgb565(c1), 255)]
    if c0 > c1 or not dxt1:
        colors += [
            tuple((2 * colors[0][i] + colors[1][i]) // 3 for i in range(4)),
            tuple((colors[0][i] + 2 * colors[1][i]) // 3 for i in range(4)),
        ]
    else:
        colors += [
            tuple((colors[0][i] + colors[1][i]) // 2 for i in range(4)),
            (0, 0, 0, 0),
        ]
    indices = int.from_bytes(block[4:8], "little")
    return [colors[(indices >> (2 * pixel)) & 3] for pixel in range(16)]


def _decode_dxt(data: bytes, width: int, height: int, format_id: int) -> bytes:
    """Decode the DXT1/DXT5 variants used by H2A Pict textures."""
    if format_id == 0x0C:
        block_size, dxt1 = 8, True
    elif format_id == 0x34:
        # H2A uses this id for DXN/BC5 normal maps: two BC4 channels, not
        # DXT5 color plus alpha.  Decode each channel independently below.
        block_size, dxt1 = 16, False
    else:
        raise PCTError(f"unsupported H2A Pict texture format: 0x{format_id:X}")

    rgba = bytearray(width * height * 4)
    offset = 0
    for block_y in range(0, height, 4):
        for block_x in range(0, width, 4):
            if offset + block_size > len(data):
                raise PCTError("compressed texture payload ended inside a DXT block")
            block = data[offset : offset + block_size]
            offset += block_size
            if format_id == 0x34:
                def bc4_values(channel: bytes) -> list[int]:
                    a0, a1 = channel[0], channel[1]
                    values = [a0, a1]
                    if a0 > a1:
                        values += [(6 * a0 + a1) // 7, (5 * a0 + 2 * a1) // 7,
                                   (4 * a0 + 3 * a1) // 7, (3 * a0 + 4 * a1) // 7,
                                   (2 * a0 + 5 * a1) // 7, (a0 + 6 * a1) // 7]
                    else:
                        values += [(4 * a0 + a1) // 5, (3 * a0 + 2 * a1) // 5,
                                   (2 * a0 + 3 * a1) // 5, (a0 + 4 * a1) // 5, 0, 255]
                    indices = int.from_bytes(channel[2:8], "little")
                    return [values[(indices >> (3 * i)) & 7] for i in range(16)]

                red = bc4_values(block[:8])
                green = bc4_values(block[8:])
                pixels = []
                for r8, g8 in zip(red, green):
                    r = r8 / 127.5 - 1.0
                    g = g8 / 127.5 - 1.0
                    b = max(0.0, 1.0 - r * r - g * g) ** 0.5
                    pixels.append((r8, g8, round((b + 1.0) * 127.5), 255))
            elif dxt1:
                pixels = _decode_dxt_color(block, True)
            else:
                alpha0, alpha1 = block[0], block[1]
                alphas = [alpha0, alpha1]
                if alpha0 > alpha1:
                    alphas += [(6 * alpha0 + alpha1) // 7, (5 * alpha0 + 2 * alpha1) // 7,
                               (4 * alpha0 + 3 * alpha1) // 7, (3 * alpha0 + 4 * alpha1) // 7,
                               (2 * alpha0 + 5 * alpha1) // 7, (alpha0 + 6 * alpha1) // 7]
                else:
                    alphas += [(4 * alpha0 + alpha1) // 5, (3 * alpha0 + 2 * alpha1) // 5,
                               (2 * alpha0 + 3 * alpha1) // 5, (alpha0 + 4 * alpha1) // 5, 0, 255]
                alpha_indices = int.from_bytes(block[2:8], "little")
                pixels = _decode_dxt_color(block[8:], False)
                pixels = [(*pixel[:3], alphas[(alpha_indices >> (3 * i)) & 7]) for i, pixel in enumerate(pixels)]
            for local_y in range(4):
                for local_x in range(4):
                    x, y = block_x + local_x, block_y + local_y
                    if x < width and y < height:
                        rgba[(y * width + x) * 4 : (y * width + x + 1) * 4] = bytes(pixels[local_y * 4 + local_x])
    return bytes(rgba)


def decode_pct(data: bytes) -> tuple[int, int, bytes]:
    """Return ``(width, height, RGBA pixels)`` for a PCT byte string."""

    if len(data) < HEADER_SIZE:
        raise PCTError(f"file is too small for a {HEADER_SIZE}-byte PCT header")

    width = _u32(data, WIDTH_OFFSET)
    height = _u32(data, HEIGHT_OFFSET)
    payload_size = _u32(data, PAYLOAD_SIZE_OFFSET)
    if not width or not height:
        raise PCTError("header contains an empty image size")
    if width > 100_000 or height > 100_000:
        raise PCTError(f"unreasonable image size: {width}x{height}")
    if payload_size > len(data) - HEADER_SIZE:
        raise PCTError("header payload length exceeds the file size")

    payload = data[HEADER_SIZE : HEADER_SIZE + payload_size]
    pixels = width * height

    # H2A Pict stores its texture format in the PCT header and its payload as
    # DDS-compatible compressed blocks.  0x34 is BC7A (BC7 with alpha).
    format_id = _u32(data, FORMAT_OFFSET)
    if format_id == 0x0C:
        return width, height, _swap_red_blue(_decode_dxt(payload, width, height, format_id))
    if format_id == 0x34:
        try:
            import texture2ddecoder
        except ImportError as error:
            raise PCTError("BC7A textures require texture2ddecoder; install requirements.txt") from error
        return width, height, _swap_red_blue(texture2ddecoder.decode_bc7(payload, width, height))

    bits_per_pixel = payload_size * 8 / pixels

    if bits_per_pixel == 4:
        # Pixels are packed high nibble first, with a row ending on a nibble
        # boundary.  The supplied 4-bit files have an even pixel count.
        values = bytearray()
        for byte in payload:
            values.append((byte >> 4) * 17)
            values.append((byte & 0x0F) * 17)
        values = values[:pixels]
    elif bits_per_pixel == 8:
        values = payload[:pixels]
    elif bits_per_pixel == 16:
        # Support the common RGB565 variant for PCT files outside this sample.
        rgba = bytearray()
        for index in range(0, pixels * 2, 2):
            word = struct.unpack_from("<H", payload, index)[0]
            r = ((word >> 11) & 0x1F) * 255 // 31
            g = ((word >> 5) & 0x3F) * 255 // 63
            b = (word & 0x1F) * 255 // 31
            rgba += bytes((r, g, b, 255))
        return width, height, bytes(rgba)
    else:
        raise PCTError(f"unsupported pixel depth: {bits_per_pixel:g} bits per pixel")

    if len(values) != pixels:
        raise PCTError("pixel payload does not match the dimensions in the header")
    return width, height, _gray_rgba(values)


def convert_file(source: Path, destination: Path) -> tuple[int, int]:
    width, height, rgba = decode_pct(source.read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_png(destination, width, height, rgba)
    return width, height


def _destination_for(source: Path, output: Path | None, multiple: bool) -> Path:
    if output is None:
        return source.with_suffix(".png")
    if multiple or output.is_dir() or output.suffix == "":
        return output / f"{source.stem}.png"
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PCT image files to PNG.")
    parser.add_argument("inputs", nargs="+", type=Path, help="PCT files or directories")
    parser.add_argument("-o", "--output", type=Path, help="PNG path, or output directory for multiple inputs")
    args = parser.parse_args()

    sources: list[Path] = []
    for item in args.inputs:
        if item.is_dir():
            sources.extend(sorted(item.glob("*.pct")))
        else:
            sources.append(item)
    if not sources:
        parser.error("no .pct files found")

    multiple = len(sources) > 1
    if multiple and args.output and args.output.suffix:
        parser.error("--output must be a directory when converting multiple files")

    failures = 0
    for source in sources:
        destination = _destination_for(source, args.output, multiple)
        try:
            width, height = convert_file(source, destination)
            print(f"{source} -> {destination} ({width}x{height})")
        except (OSError, PCTError) as error:
            failures += 1
            print(f"error: {source}: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
