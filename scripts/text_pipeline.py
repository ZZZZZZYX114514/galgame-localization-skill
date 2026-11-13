"""Extract and apply the two supported NekoSDK dialogue command forms."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from nekopack import read_entries, decode_entry, encode_entry, build_archive_packed
from nekosdk import MAGIC, parse_records, split_chunks, decode_field, patch_script


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def extract(archive, output):
    data = archive.read_bytes()
    units, warnings = [], []
    for entry in read_entries(data):
        name = entry.name.rstrip(b'\0').decode('cp932')
        if not name.lower().endswith(('.txt', '.scr')):
            continue
        try:
            payload = decode_entry(data, entry)
            if not payload.startswith(MAGIC):
                continue
            records = parse_records(payload)
            chunks = split_chunks(payload)
            for record in records:
                chunk = chunks[record.chunk_index]
                text = decode_field(chunk, record.text)
                speaker = decode_field(chunk, record.name)
                if not text.strip():
                    continue
                if '\ufffd' in text + speaker:
                    raise ValueError('source text has undecodable characters')
                units.append({'id': f'{name}|{record.chunk_index}', 'entry': name,
                              'chunk': record.chunk_index, 'source_sha256': sha256(payload),
                              'name': speaker, 'text': text,
                              'translation_name': None, 'translation': None})
        except (ValueError, IndexError, UnicodeError) as error:
            warnings.append({'entry': name, 'error': str(error)})
        except Exception as error:
            # Surface decompression and structural failures instead of hiding coverage gaps.
            warnings.append({'entry': name, 'error': type(error).__name__ + ': ' + str(error)})
    with output.open('x', encoding='utf-8', newline='\n') as target:
        for unit in units:
            target.write(json.dumps(unit, ensure_ascii=False) + '\n')
    return {'records': len(units), 'warnings': warnings}


def apply(archive, translations, output):
    if archive.resolve() == output.resolve():
        raise ValueError('use a separate staging output, not the source archive')
    data = archive.read_bytes()
    groups = defaultdict(dict)
    hashes = {}
    ids = set()
    for line in translations.read_text('utf-8').splitlines():
        if not line.strip():
            continue
        unit = json.loads(line)
        key = (unit['entry'], unit['chunk'])
        if key in ids:
            raise ValueError('duplicate entry/chunk translation')
        ids.add(key)
        text = unit['translation']
        name = unit.get('translation_name')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('each selected record needs a nonempty translation')
        text.encode('gbk', errors='strict')
        if name is not None:
            name.encode('gbk', errors='strict')
        expected_hash = hashes.setdefault(unit['entry'], unit['source_sha256'])
        if expected_hash != unit['source_sha256']:
            raise ValueError('conflicting source hashes')
        groups[unit['entry']][unit['chunk']] = (name, text)
    if not ids:
        raise ValueError('no selected translation records')
    packed, expected, found = [], {}, set()
    for entry in read_entries(data):
        filename = entry.name.rstrip(b'\0').decode('cp932')
        if filename in groups:
            payload = decode_entry(data, entry)
            if sha256(payload) != hashes[filename]:
                raise ValueError(f'source revision mismatch for {filename}')
            patched = patch_script(payload, groups[filename])
            if len(parse_records(patched)) != len(parse_records(payload)):
                raise ValueError('dialogue record count changed')
            expected[entry.name] = patched
            packed.append((entry.name, encode_entry(patched)))
            found.add(filename)
        else:
            packed.append((entry.name, data[entry.offset:entry.offset+entry.size]))
    if found != set(groups):
        raise ValueError('some requested script entries are missing')
    result = build_archive_packed(packed)
    for entry, (name, blob) in zip(read_entries(result), packed):
        assert entry.name == name
        assert result[entry.offset:entry.offset+entry.size] == blob
        if name in expected:
            assert decode_entry(result, entry) == expected[name]
    with output.open('xb') as target:
        target.write(result)
    return {'records': len(ids), 'scripts': len(found), 'sha256': sha256(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('extract')
    export.add_argument('archive', type=Path)
    export.add_argument('output', type=Path)
    patch = sub.add_parser('apply')
    patch.add_argument('archive', type=Path)
    patch.add_argument('translations', type=Path)
    patch.add_argument('output', type=Path)
    args = parser.parse_args()
    report = extract(args.archive, args.output) if args.command == 'extract' else apply(args.archive, args.translations, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
