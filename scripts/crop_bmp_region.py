"""Read only a confirmed text rectangle from an uncompressed 24/32-bit BMP."""
import argparse
import struct
from pathlib import Path


def crop_region(source, output, box, alpha=None):
    from PIL import Image
    left, top, right, bottom = box
    with source.open('rb') as stream:
        header = stream.read(54)
        if len(header) != 54 or header[:2] != b'BM':
            raise ValueError('expected a Windows BMP')
        offset = struct.unpack_from('<I', header, 10)[0]
        dib = struct.unpack_from('<I', header, 14)[0]
        width, signed_height = struct.unpack_from('<ii', header, 18)
        bits = struct.unpack_from('<H', header, 28)[0]
        compression = struct.unpack_from('<I', header, 30)[0]
        height = abs(signed_height)
        if dib < 40 or bits not in (24, 32) or compression != 0 or width <= 0:
            raise ValueError('only uncompressed Windows 24/32-bit BMP is supported')
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError('rectangle exceeds image bounds')
        pixel_bytes = bits // 8
        stride = ((width * bits + 31) // 32) * 4
        row_size = (right-left) * pixel_bytes
        rows = []
        for y in range(top, bottom):
            stored_y = height-1-y if signed_height > 0 else y
            stream.seek(offset + stored_y*stride + left*pixel_bytes)
            row = stream.read(row_size)
            if len(row) != row_size:
                raise ValueError('truncated pixel rectangle')
            rows.append(row)
    mode, raw_mode = ('RGB', 'BGR') if bits == 24 else ('RGBA', 'BGRA')
    image = Image.frombytes(mode, (right-left, bottom-top), b''.join(rows), 'raw', raw_mode)
    if alpha:
        if alpha.stat().st_size != width*height:
            raise ValueError('expected a headerless top-down 8-bit alpha map')
        rows = []
        with alpha.open('rb') as stream:
            for y in range(top, bottom):
                stream.seek(y*width+left)
                rows.append(stream.read(right-left))
        image = image.convert('RGBA')
        image.putalpha(Image.frombytes('L', image.size, b''.join(rows)))
    with output.open('xb') as target:
        image.save(target, format='PNG')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--box', nargs=4, type=int, required=True, metavar=('LEFT','TOP','RIGHT','BOTTOM'))
    parser.add_argument('--alpha', type=Path)
    args = parser.parse_args()
    crop_region(args.source, args.output, args.box, args.alpha)


if __name__ == '__main__':
    main()
