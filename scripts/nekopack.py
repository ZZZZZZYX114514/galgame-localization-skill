#!/usr/bin/env python3
"""Read and rebuild NEKOPACK4A archives used by Waffle/NekoSDK games."""

from __future__ import annotations

import argparse
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MAGIC = b"NEKOPACK4A"


@dataclass
class Entry:
    name: bytes
    offset: int
    size: int

    @property
    def key(self) -> int:
        return sum(self.name)


def read_entries(data: bytes) -> list[Entry]:
    if data[:10] != MAGIC:
        raise ValueError("not a NEKOPACK4A archive")

    index_size = struct.unpack_from("<I", data, 0x0A)[0]
    pos = 0x0E
    index_end = pos + index_size
    if index_end > len(data):
        raise ValueError("archive index exceeds file")
    entries: list[Entry] = []

    while pos < index_end:
        if pos + 4 > index_end:
            raise ValueError("truncated index record")
        name_len = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if name_len == 0:
            break
        if name_len > 0x100:
            raise ValueError(f"unreasonable filename length at 0x{pos - 4:X}: {name_len}")
        if pos + name_len + 8 > index_end:
            raise ValueError("entry exceeds index")

        name = data[pos : pos + name_len]
        pos += name_len
        key = sum(name)
        offset, size = struct.unpack_from("<II", data, pos)
        pos += 8
        entry = Entry(name, offset ^ key, size ^ key)
        if entry.offset < index_end or entry.offset + entry.size > len(data):
            raise ValueError("entry payload exceeds archive bounds")
        entries.append(entry)

    if pos != index_end:
        raise ValueError(f"index ended at 0x{pos:X}, expected 0x{index_end:X}")
    return entries


def decode_entry(data: bytes, entry: Entry) -> bytes:
    if entry.size < 8:
        raise ValueError(f"{entry.name!r}: entry is too small ({entry.size} bytes)")

    key = entry.size // 8 + 0x22
    header = bytearray(data[entry.offset : entry.offset + 4])
    for i in range(len(header)):
        header[i] ^= key & 0xFF
        key <<= 3

    compressed = bytes(header) + data[entry.offset + 4 : entry.offset + entry.size - 4]
    unpacked_size = struct.unpack_from("<I", data, entry.offset + entry.size - 4)[0]
    unpacked = zlib.decompress(compressed)
    if len(unpacked) != unpacked_size:
        raise ValueError(
            f"{entry.name!r}: decompressed to {len(unpacked)} bytes, expected {unpacked_size}"
        )
    return unpacked


def encode_entry(payload: bytes) -> bytes:
    compressed = bytearray(zlib.compress(payload, 9))
    size = len(compressed) + 4
    key = size // 8 + 0x22
    for i in range(4):
        compressed[i] ^= key & 0xFF
        key <<= 3
    return bytes(compressed) + struct.pack("<I", len(payload))


def build_archive(payloads: list[tuple[bytes, bytes]]) -> bytes:
    index = bytearray()
    body = bytearray()
    data_start = 0x0E + sum(4 + len(name) + 8 for name, _ in payloads) + 4

    for name, payload in payloads:
        packed = encode_entry(payload)
        key = sum(name)
        offset = data_start + len(body)
        index += struct.pack("<I", len(name))
        index += name
        index += struct.pack("<II", offset ^ key, len(packed) ^ key)
        body += packed

    # The engine scans until a zero filename length, including for missing optional resources.
    index += struct.pack("<I", 0)
    return MAGIC + struct.pack("<I", len(index)) + index + body


def build_archive_packed(items: list[tuple[bytes, bytes]]) -> bytes:
    """Build an archive from already-encoded entry blobs."""
    index = bytearray()
    body = bytearray()
    data_start = 0x0E + sum(4 + len(name) + 8 for name, _ in items) + 4

    for name, packed in items:
        key = sum(name)
        offset = data_start + len(body)
        index += struct.pack("<I", len(name))
        index += name
        index += struct.pack("<II", offset ^ key, len(packed) ^ key)
        body += packed

    index += struct.pack("<I", 0)
    return MAGIC + struct.pack("<I", len(index)) + index + body


def iter_archive(archive: Path):
    data = archive.read_bytes()
    for entry in read_entries(data):
        yield entry.name.rstrip(b"\0"), decode_entry(data, entry)


def command_list(args: argparse.Namespace) -> None:
    data = args.archive.read_bytes()
    entries = read_entries(data)
    for entry in entries:
        filename = entry.name.rstrip(b"\0").decode("cp932", "replace")
        print(f"{entry.offset:10d} {entry.size:10d} {filename}")
    print(f"{len(entries)} entries")


def command_extract(args: argparse.Namespace) -> None:
    args.out.mkdir(parents=True, exist_ok=True)
    for name, payload in iter_archive(args.archive):
        relative = name.decode("cp932")
        target = (args.out / relative).resolve()
        if not target.is_relative_to(args.out.resolve()):
            raise ValueError("entry path escapes extraction directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        print(relative)


def command_pack(args: argparse.Namespace) -> None:
    source = args.source
    payloads: list[tuple[bytes, bytes]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix().encode("cp932") + b"\0"
        payloads.append((relative, path.read_bytes()))
    args.output.write_bytes(build_archive(payloads))
    print(f"wrote {args.output} ({len(payloads)} entries)")


def command_verify(args: argparse.Namespace) -> None:
    data = args.archive.read_bytes()
    entries = read_entries(data)
    rebuilt = build_archive([(entry.name, decode_entry(data, entry)) for entry in entries])
    print(f"entries: {len(entries)}")
    print(f"archive: {len(data):,} bytes")
    print(f"rebuilt: {len(rebuilt):,} bytes")
    for before, after in zip(entries, read_entries(rebuilt)):
        if before.name != after.name:
            raise ValueError(f"name mismatch: {before.name!r} != {after.name!r}")
        if decode_entry(data, before) != decode_entry(rebuilt, after):
            raise ValueError(f"payload mismatch: {before.name!r}")
    print("all payloads round-trip correctly")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("list")
    p.add_argument("archive", type=Path)
    p.set_defaults(func=command_list)

    p = sub.add_parser("extract")
    p.add_argument("archive", type=Path)
    p.add_argument("out", type=Path)
    p.set_defaults(func=command_extract)

    p = sub.add_parser("pack")
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.set_defaults(func=command_pack)

    p = sub.add_parser("verify")
    p.add_argument("archive", type=Path)
    p.set_defaults(func=command_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
