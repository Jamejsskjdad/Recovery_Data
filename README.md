# PyRecover - Data Recovery Tool

Một công cụ khôi phục dữ liệu mạnh mẽ được viết bằng Python, tập trung vào việc khôi phục file đã xóa từ hệ thống file NTFS trên Windows.

## Tính năng

- 🔍 **Quét MFT**: Phân tích Master File Table để tìm file đã xóa
- 📁 **Khôi phục file**: Hỗ trợ cả resident và non-resident data
- 🖥️ **Giao diện GUI**: Giao diện đồ họa thân thiện với người dùng
- 💻 **Giao diện CLI**: Dòng lệnh cho người dùng nâng cao
- 🔧 **File carving**: Khôi phục file từ dữ liệu thô (đang phát triển)

## Cài đặt

### Yêu cầu hệ thống
- Windows 10/11
- Python 3.8+
- Quyền Administrator

### Cài đặt dependencies
```bash
pip install -r requirements.txt
```

## Sử dụng

### Giao diện đồ họa (GUI)
```bash
python pyrecover/gui_app.py
```

### Giao diện dòng lệnh (CLI)

#### Quét MFT và tìm file đã xóa
```bash
python -m pyrecover.cli scan-mft --image "C:" --filter "Documents"
```

#### Xuất file theo record ID
```bash
python -m pyrecover.cli export --image "C:" --record 12345 --out "recovered_file.dat"
```

## Cấu trúc dự án

```
pyrecover/
├── core/           # Core engine
├── fs/             # File system support
├── scan/           # Scanning modules
├── recover/        # Recovery modules
├── carve/          # File carving
├── cli.py          # Command line interface
└── gui_app.py      # Graphical interface
```

## Lưu ý quan trọng

⚠️ **Chạy với quyền Administrator**: Ứng dụng cần quyền Administrator để truy cập raw device.

⚠️ **Backup dữ liệu**: Luôn backup dữ liệu quan trọng trước khi sử dụng công cụ khôi phục.

## Đóng góp

Dự án đang trong giai đoạn phát triển. Mọi đóng góp đều được chào đón!

## License

MIT License
