#!/usr/bin/env python3
"""Parse and patch NekoSDK ADVSCRIPT2 text records."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass


MAGIC = b"NEKOSDK_ADVSCRIPT2"
MARKER_PATTERN = re.compile(
    rb"\x5B\x83\x65\x83\x4C\x83\x58\x83\x67\x95\x5C\x8E\xA6\x5D"
    rb"|\x5B\x83\x8D\x83\x4F\x92\xC7\x89\xC1\x5D"
)


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


@dataclass(frozen=True)
class TextField:
    length_offset: int
    start: int
    end: int


@dataclass(frozen=True)
class Record:
    chunk_index: int
    name: TextField
    text: TextField


def split_chunks(data: bytes) -> list[bytes]:
    starts = [match.start() - 4 for match in MARKER_PATTERN.finditer(data)]
    chunks: list[bytes] = []
    start = 0
    for end in starts:
        if end < start:
            raise ValueError(f"overlapping script chunks at 0x{end:X}")
        chunks.append(data[start:end])
        start = end
    chunks.append(data[start:])
    return chunks


def parse_records(data: bytes) -> list[Record]:
    if not data.startswith(MAGIC):
        return []

    records: list[Record] = []
    chunks = split_chunks(data)
    for chunk_index, chunk in enumerate(chunks[1:], 1):
        pos = 0
        prefix_length = read_u32(chunk, pos)
        pos += 4 + prefix_length

        name_length_pos = pos
        name_length = read_u32(chunk, pos)
        pos += 4
        if name_length == 0:
            name_start = name_end = pos
        else:
            name_start = pos
            name_end = pos + name_length - 1
            if name_end > len(chunk):
                raise ValueError(f"chunk {chunk_index}: name exceeds chunk")
            if chunk[name_end] != 0:
                raise ValueError(f"chunk {chunk_index}: name is not NUL terminated")
        pos += name_length

        text_length_pos = pos
        text_length = read_u32(chunk, pos)
        pos += 4
        if text_length == 0:
            text_start = text_end = pos
        else:
            text_start = pos
            text_end = pos + text_length - 1
            if text_end > len(chunk):
                raise ValueError(f"chunk {chunk_index}: text exceeds chunk")
            if chunk[text_end] != 0:
                raise ValueError(f"chunk {chunk_index}: text is not NUL terminated")

        records.append(
            Record(
                chunk_index=chunk_index,
                name=TextField(name_length_pos, name_start, name_end),
                text=TextField(text_length_pos, text_start, text_end),
            )
        )
    return records


def decode_field(chunk: bytes, field: TextField) -> str:
    return chunk[field.start : field.end].decode("cp932", "replace")


def replace_field(chunk: bytearray, field: TextField, value: bytes) -> None:
    if b"\0" in value:
        raise ValueError("replacement text contains NUL")
    old_length = read_u32(chunk, field.length_offset)
    old_size = field.end - field.start
    expected_length = old_size + 1 if old_length else old_size
    if old_length != expected_length:
        raise ValueError(
            f"length mismatch at 0x{field.length_offset:X}: "
            f"field={old_length}, bytes={expected_length}"
        )
    # Empty source fields can omit the terminator, so write the whole field.
    chunk[field.start : field.start + old_length] = value + b"\0"
    write_u32(chunk, field.length_offset, len(value) + 1)


def patch_script(data: bytes, replacements: dict[int, tuple[str | None, str]]) -> bytes:
    """Replace chunk text/name fields. Keys are chunk indices."""
    records = parse_records(data)
    by_chunk = {record.chunk_index: record for record in records}
    chunks = [bytearray(chunk) for chunk in split_chunks(data)]

    for chunk_index, (new_name, new_text) in replacements.items():
        record = by_chunk.get(chunk_index)
        if record is None:
            raise KeyError(f"chunk {chunk_index} does not exist")
        chunk = chunks[chunk_index]
        fields: list[tuple[TextField, bytes]] = []
        if new_name is not None:
            fields.append((record.name, new_name.encode("gbk")))
        if new_text is not None:
            fields.append((record.text, new_text.encode("gbk")))
        for field, value in sorted(fields, key=lambda item: item[0].start, reverse=True):
            replace_field(chunk, field, value)

    return b"".join(bytes(chunk) for chunk in chunks)
