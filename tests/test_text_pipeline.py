import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nekopack import build_archive_packed, decode_entry, encode_entry, read_entries
from nekosdk import parse_records, patch_script, split_chunks
from text_pipeline import apply, extract


def string_field(value):
    encoded = value.encode('cp932') + b'\0'
    return struct.pack('<I', len(encoded)) + encoded


def sample_script(empty_name=False):
    command = string_field('[テキスト表示]')
    name = struct.pack('<I', 0) if empty_name else string_field('案内人')
    return (b'NEKOSDK_ADVSCRIPT2\0\0' + command + name
            + string_field('次の駅へ行こう。') + b'\x01\x02synthetic-tail')


class TextPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.archive = self.directory / 'original.pak'
        self.units = self.directory / 'units.jsonl'
        self.output = self.directory / 'translated.pak'
        self.source = sample_script()
        self.original_blob = encode_entry(b'opaque synthetic resource')
        self.archive.write_bytes(build_archive_packed([
            (b'chapter.txt\0', encode_entry(self.source)),
            (b'resource.bin\0', self.original_blob),
        ]))

    def translated_units(self, **changes):
        report = extract(self.archive, self.units)
        self.assertEqual(report, {'records': 1, 'warnings': []})
        unit = json.loads(self.units.read_text('utf-8'))
        self.assertEqual(unit['name'], '案内人')
        self.assertEqual(unit['text'], '次の駅へ行こう。')
        unit.update(translation_name='向导', translation='去下一站吧。')
        unit.update(changes)
        self.units.write_text(json.dumps(unit, ensure_ascii=False) + '\n', 'utf-8')
        return unit

    def test_extract_apply_updates_fields_and_preserves_opaque_entry(self):
        original = self.archive.read_bytes()
        self.translated_units()
        report = apply(self.archive, self.units, self.output)
        self.assertEqual(report['records'], 1)
        packed = self.output.read_bytes()
        entries = read_entries(packed)
        payload = decode_entry(packed, entries[0])
        record = parse_records(payload)[0]
        chunk = split_chunks(payload)[record.chunk_index]
        self.assertEqual(chunk[record.name.start:record.name.end].decode('gbk'), '向导')
        self.assertEqual(chunk[record.text.start:record.text.end].decode('gbk'), '去下一站吧。')
        self.assertTrue(payload.endswith(b'\x01\x02synthetic-tail'))
        opaque = entries[1]
        self.assertEqual(packed[opaque.offset:opaque.offset + opaque.size], self.original_blob)
        self.assertEqual(self.archive.read_bytes(), original)

    def test_source_revision_mismatch_leaves_output_absent(self):
        self.translated_units(source_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'source revision mismatch'):
            apply(self.archive, self.units, self.output)
        self.assertFalse(self.output.exists())

    def test_unencodable_translation_leaves_output_absent(self):
        self.translated_units(translation='出发\U0001f680')
        with self.assertRaises(UnicodeEncodeError):
            apply(self.archive, self.units, self.output)
        self.assertFalse(self.output.exists())

    def test_duplicate_translation_leaves_output_absent(self):
        unit = self.translated_units()
        self.units.write_text((json.dumps(unit) + '\n') * 2, 'utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            apply(self.archive, self.units, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.translated_units()
        self.output.write_bytes(b'existing release')
        with self.assertRaises(FileExistsError):
            apply(self.archive, self.units, self.output)
        self.assertEqual(self.output.read_bytes(), b'existing release')

    def test_zero_length_speaker_can_receive_a_translation(self):
        source = sample_script(empty_name=True)
        record = parse_records(source)[0]
        payload = patch_script(source, {record.chunk_index: ('旁白', '下一站。')})
        updated = parse_records(payload)[0]
        chunk = split_chunks(payload)[updated.chunk_index]
        self.assertEqual(chunk[updated.name.start:updated.name.end].decode('gbk'), '旁白')
        self.assertEqual(chunk[updated.text.start:updated.text.end].decode('gbk'), '下一站。')
        self.assertTrue(payload.endswith(b'\x01\x02synthetic-tail'))


if __name__ == '__main__':
    unittest.main()
