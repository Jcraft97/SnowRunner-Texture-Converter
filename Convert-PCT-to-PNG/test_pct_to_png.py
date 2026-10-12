import struct
import tempfile
import unittest
from pathlib import Path

from pct_to_png import decode_pct, convert_file, _swap_red_blue


class PCTTests(unittest.TestCase):
    def test_decodes_sample_8_bit_file(self):
        source = Path("testpct/trucks_img_lib_i10.pct")
        width, height, rgba = decode_pct(source.read_bytes())
        self.assertEqual((width, height), (328, 460))
        self.assertEqual(len(rgba), width * height * 4)
        self.assertTrue(any(r != g or g != b for r, g, b, _ in zip(rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4])))

    def test_decodes_sample_4_bit_file(self):
        source = Path("testpct/trucks_img_lib_i1.pct")
        width, height, rgba = decode_pct(source.read_bytes())
        self.assertEqual((width, height), (328, 460))
        self.assertEqual(len(rgba), width * height * 4)
        self.assertTrue(any(r != g or g != b for r, g, b, _ in zip(rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4])))

    def test_writes_png_signature(self):
        source = Path("testpct/trucks_img_lib_i1.pct")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "image.png"
            convert_file(source, target)
            self.assertEqual(target.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_rgb565(self):
        header = bytearray(72)
        struct.pack_into("<II", header, 16, 1, 1)
        struct.pack_into("<I", header, 62, 2)
        width, height, rgba = decode_pct(bytes(header) + b"\x00\xF8")
        self.assertEqual((width, height, rgba), (1, 1, bytes((255, 0, 0, 255))))

    def test_swaps_only_red_and_blue(self):
        self.assertEqual(_swap_red_blue(bytes((1, 2, 3, 4))), bytes((3, 2, 1, 4)))


if __name__ == "__main__":
    unittest.main()
