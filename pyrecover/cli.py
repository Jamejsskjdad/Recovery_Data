from __future__ import annotations
import argparse, json
from .scan.metadata_scan import scan_deleted
from .recover.export import export_record


def main():
    ap = argparse.ArgumentParser(prog='pyrecover')
    sub = ap.add_subparsers(dest='cmd', required=True)

    s1 = sub.add_parser('scan-mft', help='Quét MFT và liệt kê file đã xóa')
    s1.add_argument('--image', required=True)
    s1.add_argument('--filter', default=None, help='lọc theo tên thư mục (đơn giản)')
    s1.add_argument('--name-contains', default=None)

    s2 = sub.add_parser('export', help='Xuất file theo record id')
    s2.add_argument('--image', required=True)
    s2.add_argument('--record', type=int, required=True)
    s2.add_argument('--out', required=True)

    args = ap.parse_args()

    if args.cmd == 'scan-mft':
        items = scan_deleted(args.image, args.filter, args.name_contains)
        print(json.dumps(items, ensure_ascii=False, indent=2))
    elif args.cmd == 'export':
        export_record(args.image, args.record, args.out)
        print(f"Exported record {args.record} -> {args.out}")

if __name__ == '__main__':
    main()
