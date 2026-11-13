import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from crop_bmp_region import crop_region


def synthetic_bmp(bits, top_down):
    # Top row is blue, red, green. Bottom row is white, black, yellow.
    rows = [
        [(0, 0, 255, 20), (255, 0, 0, 100), (0, 255, 0, 200)],
        [(255, 255, 255, 255), (0, 0, 0, 50), (255, 255, 0, 150)],
    ]
    stored_rows = rows if top_down else rows[::-1]
    stride = ((3 * bits + 31) // 32) * 4
    body = bytearray()
    for row in stored_rows:
        pixels = bytearray()
        for red, green, blue, alpha in row:
            pixels.extend([blue, green, red])
            if bits == 32:
                pixels.append(alpha)
        body.extend(pixels + b'\0' * (stride - len(pixels)))
    header = b'BM' + struct.pack('<IHHI', 54 + len(body), 0, 0, 54)
    header += struct.pack('<IiiHHIIiiII', 40, 3, -2 if top_down else 2,
                          1, bits, 0, len(body), 0, 0, 0, 0)
    return header + body


class CropTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / 'synthetic.bmp'
        self.output = self.directory / 'label.png'

    def test_bottom_up_24_bit_rectangle_with_row_padding(self):
        self.source.write_bytes(synthetic_bmp(24, False))
        crop_region(self.source, self.output, (1, 0, 3, 1))
        with Image.open(self.output) as image:
            self.assertEqual(image.size, (2, 1))
            self.assertEqual([image.getpixel((x, 0)) for x in range(2)], [(255, 0, 0), (0, 255, 0)])

    def test_top_down_32_bit_rectangle_preserves_alpha(self):
        self.source.write_bytes(synthetic_bmp(32, True))
        crop_region(self.source, self.output, (1, 0, 3, 1))
        with Image.open(self.output) as image:
            self.assertEqual([image.getpixel((x, 0)) for x in range(2)], [(255, 0, 0, 100), (0, 255, 0, 200)])

    def test_reads_header_and_selected_pixels_only(self):
        self.source.write_bytes(synthetic_bmp(24, False))
        reads = []
        original_open = Path.open

        class AuditedReader:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def seek(self, position):
                return self.stream.seek(position)

            def read(self, size=-1):
                start = self.stream.tell()
                result = self.stream.read(size)
                reads.append((start, start + len(result)))
                return result

        def audited_open(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return AuditedReader(stream) if path == self.source else stream

        with patch.object(Path, 'open', audited_open):
            crop_region(self.source, self.output, (1, 0, 3, 1))
        self.assertEqual(reads, [(0, 54), (69, 75)])

    def test_external_alpha_reads_matching_rectangle(self):
        self.source.write_bytes(synthetic_bmp(24, False))
        alpha = self.directory / 'synthetic.alp'
        alpha.write_bytes(bytes([20, 100, 200, 255, 50, 150]))
        crop_region(self.source, self.output, (1, 0, 3, 1), alpha)
        with Image.open(self.output) as image:
            self.assertEqual([image.getpixel((x, 0)) for x in range(2)], [(255, 0, 0, 100), (0, 255, 0, 200)])

    def test_invalid_rectangle_leaves_output_absent(self):
        self.source.write_bytes(synthetic_bmp(24, False))
        with self.assertRaises(ValueError):
            crop_region(self.source, self.output, (1, 0, 4, 1))
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
