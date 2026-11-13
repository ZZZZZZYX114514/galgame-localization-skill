import argparse
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nekopack import build_archive, build_archive_packed, encode_entry, read_entries, decode_entry, command_pack, command_extract

class ArchiveTests(unittest.TestCase):
    def test_missing_optional_file_lookup_stops_at_index_sentinel(self):
        for data in [build_archive([(b"sample.txt\0", b"synthetic")]),
                     build_archive_packed([(b"sample.txt\0", encode_entry(b"synthetic"))])]:
            end = 14 + struct.unpack_from("<I", data, 10)[0]
            position = 14
            names = []
            while position < end:
                length = struct.unpack_from("<I", data, position)[0]
                position += 4
                if length == 0:
                    break
                names.append(data[position:position+length])
                position += length + 8
            self.assertEqual(data[end-4:end], b"\0" * 4)
            self.assertEqual(position, end)
            self.assertNotIn(b"missing.alp\0", names)
            entries = read_entries(data)
            self.assertEqual(entries[0].offset, end)
            self.assertEqual(decode_entry(data, entries[0]), b"synthetic")

    def test_empty_archive_has_terminator(self):
        data = build_archive([])
        self.assertEqual(data[14:], b"\0" * 4)
        self.assertEqual(read_entries(data), [])

    def test_cp932_filename_survives_pack_and_extract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / '①.txt').write_bytes(b'synthetic content')
            archive = root / 'sample.pak'
            target = root / 'extracted'
            command_pack(argparse.Namespace(source=source, output=archive))
            entries = read_entries(archive.read_bytes())
            self.assertEqual(entries[0].name, b'\x87\x40.txt\0')
            command_extract(argparse.Namespace(archive=archive, out=target))
            self.assertEqual((target / '①.txt').read_bytes(), b'synthetic content')

if __name__ == "__main__":
    unittest.main()
