import contextlib
import io
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ImageConverter.PCTtoTGA.pct_to_tga import convert_directory, main as pct_main, pct_to_tga


def make_pct(
    width: int,
    height: int,
    first_block: bytes,
    format_id: int = 51,
    mip_count: int | None = None,
) -> bytes:
    if mip_count is None:
        mip_count = max(width, height).bit_length()
    table_end = 64
    terminal_offset = 74
    payload_offset = terminal_offset + 6
    header = bytearray(payload_offset)
    header[6:10] = b"TCIP"
    struct.pack_into("<II", header, 16, width, height)
    struct.pack_into("<I", header, 38, format_id)
    struct.pack_into("<I", header, 0x30, mip_count)
    struct.pack_into("<Q", header, 0x36, table_end)
    struct.pack_into("<H", header, table_end, 0x0104)
    struct.pack_into("<Q", header, table_end + 2, terminal_offset)
    struct.pack_into("<H", header, terminal_offset, 0x00FF)
    top_level_size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    mip_chain_size = 0
    mip_width, mip_height = width, height
    for _ in range(mip_count):
        mip_chain_size += ((mip_width + 3) // 4) * ((mip_height + 3) // 4) * 16
        mip_width = max(1, mip_width // 2)
        mip_height = max(1, mip_height // 2)
    pct_data = (
        bytes(header)
        + first_block * (top_level_size // 16)
        + bytes(mip_chain_size - top_level_size)
        + b"\x01\x00"
        + bytes(4)
    )
    return pct_data[:-4] + struct.pack("<I", len(pct_data))


class PctToTgaTests(unittest.TestCase):
    def test_cli_converts_file_to_requested_output_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pct"
            output = root / "custom-name.tga"
            source.write_bytes(make_pct(4, 4, bytes(16)))
            pixels = bytes((0, 0, 255, 255)) * 16

            with patch(
                "pct_to_tga.texture2ddecoder.decode_bc7", return_value=pixels
            ), contextlib.redirect_stdout(io.StringIO()):
                result = pct_main([str(source), str(output)])

            self.assertEqual(result, 0)
            self.assertEqual(output.read_bytes()[18:], pixels)

    def test_cli_reports_directory_failures_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            (source / "valid.pct").write_bytes(make_pct(4, 4, bytes(16)))
            (source / "broken.pct").write_bytes(b"not a PCT")
            pixels = bytes((0, 0, 255, 255)) * 16
            stderr = io.StringIO()

            with patch(
                "pct_to_tga.texture2ddecoder.decode_bc7", return_value=pixels
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                stderr
            ):
                result = pct_main([str(source)])

            self.assertEqual(result, 1)
            self.assertTrue((source / "valid.tga").is_file())
            self.assertIn("broken.pct", stderr.getvalue())

    def test_cli_rejects_directory_without_pct_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = pct_main([temp_dir])

            self.assertEqual(result, 1)
            self.assertIn("no .pct files found", stderr.getvalue())

    def test_converts_bc7_pixels_to_top_origin_bgra_tga(self):
        bc7_block = bytes(16)
        expected_pixels = bytes((0, 0, 255, 255)) * 16

        with patch("pct_to_tga.texture2ddecoder.decode_bc7", return_value=expected_pixels) as decode:
            tga = pct_to_tga(make_pct(4, 4, bc7_block))

        self.assertEqual(len(tga), 18 + 4 * 4 * 4)
        self.assertEqual(tga[2], 2)
        self.assertEqual(struct.unpack_from("<HH", tga, 12), (4, 4))
        self.assertEqual((tga[16], tga[17]), (32, 0x28))
        self.assertEqual(tga[18:], expected_pixels)
        decode.assert_called_once_with(bc7_block, 4, 4)

    def test_uses_pointer_chain_instead_of_mip_size_guess(self):
        pct = make_pct(4, 4, bytes(16))
        expected_pixels = bytes((0, 0, 255, 255)) * 16

        with patch("pct_to_tga.texture2ddecoder.decode_bc7", return_value=expected_pixels) as decode:
            pct_to_tga(pct)

        decode.assert_called_once_with(bytes(16), 4, 4)

    def test_uses_declared_mip_count_for_payload_size(self):
        pct = make_pct(4, 4, bytes(16), mip_count=2)
        expected_pixels = bytes((0, 0, 255, 255)) * 16

        with patch("pct_to_tga.texture2ddecoder.decode_bc7", return_value=expected_pixels):
            tga = pct_to_tga(pct)

        self.assertEqual(tga[18:], expected_pixels)

    def test_rejects_unknown_format(self):
        pct = bytearray(make_pct(4, 4, bytes(16)))
        struct.pack_into("<I", pct, 38, 12)

        with self.assertRaisesRegex(ValueError, "unsupported PCT format 12"):
            pct_to_tga(bytes(pct))

    def test_rejects_truncated_mip_chain(self):
        pct = bytearray(make_pct(4, 4, bytes(16)))
        del pct[-7]
        struct.pack_into("<I", pct, len(pct) - 4, len(pct))

        with self.assertRaisesRegex(ValueError, "payload size"):
            pct_to_tga(bytes(pct))

    def test_converts_pct_files_recursively_and_preserves_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            destination = root / "converted"
            nested = source / "nested"
            nested.mkdir(parents=True)
            pct_data = make_pct(4, 4, bytes(16))
            (source / "root.PCT").write_bytes(pct_data)
            (nested / "child.pct").write_bytes(pct_data)
            (nested / "not-a-texture.pct_header").write_bytes(b"ignored")

            converted, errors = convert_directory(source, destination)

            self.assertEqual(converted, 2)
            self.assertEqual(errors, [])
            self.assertTrue((destination / "root.tga").is_file())
            self.assertTrue((destination / "nested" / "child.tga").is_file())

    def test_directory_conversion_continues_after_bad_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            (source / "valid.pct").write_bytes(make_pct(4, 4, bytes(16)))
            (source / "broken.pct").write_bytes(b"not a PCT")

            converted, errors = convert_directory(source)

            self.assertEqual(converted, 1)
            self.assertEqual(len(errors), 1)
            self.assertTrue((source / "valid.tga").is_file())


if __name__ == "__main__":
    unittest.main()