import contextlib
import io
import struct
import tempfile
import unittest
from pathlib import Path

from dds_to_tga import convert_directory, dds_to_tga, main as dds_main


def _rgb565(red: int, green: int, blue: int) -> int:
    return ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)


def make_dds(width: int, height: int, fourcc: bytes, payload: bytes, mip_count: int = 1) -> bytes:
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000
    struct.pack_into("<I", header, 8, flags)
    struct.pack_into("<II", header, 12, height, width)
    struct.pack_into("<I", header, 28, mip_count)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 0x4)
    header[84:88] = fourcc
    struct.pack_into("<I", header, 108, 0x401008)
    return bytes(header) + payload


def solid_dxt1_block(red: int, green: int, blue: int) -> bytes:
    color = _rgb565(red, green, blue)
    return struct.pack("<HH", color, color) + bytes(4)


def solid_dxt3_block(red: int, green: int, blue: int, alpha_nibble: int) -> bytes:
    alpha = bytes([alpha_nibble | (alpha_nibble << 4)] * 8)
    return alpha + solid_dxt1_block(red, green, blue)


class DdsToTgaTests(unittest.TestCase):
    def test_converts_dxt1_to_top_origin_bgra_tga(self):
        payload = solid_dxt1_block(255, 0, 0)
        tga = dds_to_tga(make_dds(4, 4, b"DXT1", payload))

        self.assertEqual(len(tga), 18 + 4 * 4 * 4)
        self.assertEqual(tga[2], 2)
        self.assertEqual(struct.unpack_from("<HH", tga, 12), (4, 4))
        self.assertEqual((tga[16], tga[17]), (32, 0x28))
        self.assertEqual(tga[18:22], bytes((0, 0, 255, 255)))

    def test_converts_dxt3_explicit_alpha(self):
        payload = solid_dxt3_block(0, 255, 0, 0x8)
        tga = dds_to_tga(make_dds(4, 4, b"DXT3", payload))

        self.assertEqual(tga[18:22], bytes((0, 255, 0, 0x88)))

    def test_decodes_only_the_top_mip(self):
        payload = solid_dxt1_block(0, 0, 255) + solid_dxt1_block(255, 255, 255)
        tga = dds_to_tga(make_dds(4, 4, b"DXT1", payload, mip_count=2))

        self.assertEqual(tga[18:22], bytes((255, 0, 0, 255)))

    def test_matches_expeditions_sample_header(self):
        sample = Path(__file__).resolve().parents[1] / "test_convert_DDS_EX" / "trucks_addon_sideboard_01__d.dds"
        width, height = struct.unpack_from("<II", sample.read_bytes(), 12)
        self.assertEqual((width, height), (2048, 2048))

        tga = dds_to_tga(sample.read_bytes())
        self.assertEqual(struct.unpack_from("<HH", tga, 12), (2048, 2048))
        self.assertEqual((tga[16], tga[17]), (32, 0x28))
        self.assertEqual(len(tga), 18 + 2048 * 2048 * 4)

    def test_matches_expeditions_dxt3_sample_size(self):
        sample = Path(__file__).resolve().parents[1] / "test_convert_DDS_EX" / "trucks_addon_sideboard_grille_01__d_a.dds"
        self.assertEqual(sample.read_bytes()[84:88], b"DXT3")

        tga = dds_to_tga(sample.read_bytes())
        self.assertEqual(len(tga), 18 + 2048 * 2048 * 4)
        self.assertEqual((tga[16], tga[17]), (32, 0x28))

    def test_rejects_dx10_bc7(self):
        with self.assertRaisesRegex(ValueError, "expected DXT1 or DXT3"):
            dds_to_tga(make_dds(4, 4, b"DX10", bytes(8)))

    def test_rejects_truncated_payload(self):
        dds = bytearray(make_dds(4, 4, b"DXT1", solid_dxt1_block(255, 0, 0)))
        del dds[-1]
        with self.assertRaisesRegex(ValueError, "payload size"):
            dds_to_tga(bytes(dds))

    def test_cli_converts_file_to_requested_output_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.dds"
            output = root / "custom-name.tga"
            source.write_bytes(make_dds(4, 4, b"DXT1", solid_dxt1_block(255, 0, 0)))

            with contextlib.redirect_stdout(io.StringIO()):
                result = dds_main([str(source), str(output)])

            self.assertEqual(result, 0)
            self.assertEqual(output.read_bytes()[18:22], bytes((0, 0, 255, 255)))

    def test_cli_reports_directory_failures_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            (source / "valid.dds").write_bytes(make_dds(4, 4, b"DXT1", solid_dxt1_block(255, 0, 0)))
            (source / "broken.dds").write_bytes(b"not a DDS")
            stderr = io.StringIO()

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                result = dds_main([str(source)])

            self.assertEqual(result, 1)
            self.assertTrue((source / "valid.tga").is_file())
            self.assertIn("broken.dds", stderr.getvalue())

    def test_cli_rejects_directory_without_dds_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = dds_main([temp_dir])

            self.assertEqual(result, 1)
            self.assertIn("no .dds files found", stderr.getvalue())

    def test_converts_dds_files_recursively_and_preserves_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            destination = root / "converted"
            nested = source / "nested"
            nested.mkdir(parents=True)
            dds_data = make_dds(4, 4, b"DXT1", solid_dxt1_block(255, 0, 0))
            (source / "root.DDS").write_bytes(dds_data)
            (nested / "child.dds").write_bytes(dds_data)
            (nested / "not-a-texture.dds_header").write_bytes(b"ignored")

            converted, errors = convert_directory(source, destination)

            self.assertEqual(converted, 2)
            self.assertEqual(errors, [])
            self.assertTrue((destination / "root.tga").is_file())
            self.assertTrue((destination / "nested" / "child.tga").is_file())


if __name__ == "__main__":
    unittest.main()
