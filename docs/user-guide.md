# Hướng dẫn sử dụng CampusFind

Tài liệu này hướng dẫn thiết lập project trên Windows bằng PowerShell và PostgreSQL. Mỗi thành viên có thể chạy database trên máy riêng; dữ liệu giữa các máy không tự đồng bộ.

## 1. Chuẩn bị

- Python 3.11 trở lên.
- PostgreSQL đang chạy và pgAdmin để quản lý database.
- Mã nguồn project trên máy tính.

Mở PowerShell tại thư mục gốc của project, tức thư mục chứa `README.md` và `pyproject.toml`.

## 2. Tạo môi trường Python và cài thư viện

Chạy lần đầu:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

`.venv` là môi trường Python riêng của project. Khi kích hoạt thành công, đầu dòng terminal thường có `(.venv)`. Khi mở terminal mới, chỉ cần chạy lại `.venv\Scripts\Activate.ps1`; không cần tạo lại hoặc cài lại thư viện mỗi lần.

Nếu PowerShell chặn script, có thể cho phép chạy trong **cửa sổ terminal hiện tại** rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Chạy `deactivate` khi muốn thoát môi trường ảo.

## 3. Tạo database và cấu hình kết nối

Trong pgAdmin, tạo một database PostgreSQL trống, ví dụ `uit-campus-find`. Ghi nhớ tên database, username, mật khẩu và cổng PostgreSQL của máy bạn. Nếu đang kết nối qua Query Tool, có thể xem tên database, user và cổng bằng:

```sql
SELECT current_database(), current_user, current_setting('port');
```

Tạo `.env` từ file mẫu nếu chưa có file `.env`:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và sửa dòng sau theo thông tin của bạn:

```env
DATABASE_URL=postgresql+asyncpg://TEN_USER:MAT_KHAU@localhost:5432/uit-campus-find
```

`DATABASE_URL` là bắt buộc: nếu không khai báo trong `.env` hoặc biến môi trường, project sẽ báo lỗi cấu hình khi khởi động.

`localhost` là PostgreSQL trên chính máy bạn. Nếu username hoặc mật khẩu có ký tự đặc biệt như `@`, `:` hoặc `/`, cần mã hóa URL các ký tự đó (ví dụ `@` thành `%40`). Không đưa `.env` hoặc mật khẩu lên Git. Nếu `.env` có `SYNC_DATABASE_URL` cũ, hãy xóa dòng đó hoặc cập nhật cho cùng database; nếu bỏ dòng này, project tự suy ra URL đồng bộ từ `DATABASE_URL`.

> Nếu đã có `.env`, không chạy lệnh copy đè lên cấu hình hiện tại; chỉ chỉnh những giá trị cần thiết.

## 4. Migration: tạo cấu trúc database

Migration là các bước thay đổi cấu trúc database được lưu theo phiên bản trong `alembic/versions/`. Bảng `alembic_version` cho Alembic biết database đã áp dụng phiên bản nào.

Với database **mới và trống**, sau khi cấu hình `.env`, chạy:

```powershell
alembic upgrade head
```

Lệnh này áp dụng các migration chưa chạy đến phiên bản mới nhất, bao gồm schema ban đầu với 9 bảng và trigger. Kiểm tra phiên bản và lịch sử bằng:

```powershell
alembic current
alembic history
```

Nếu database đã được tạo bảng thủ công hoặc restore từ backup, không chạy migration ban đầu một cách tùy tiện: hãy kiểm tra schema và phiên bản trước. `alembic stamp` chỉ ghi nhận phiên bản, không tạo hay kiểm tra bảng; chỉ sử dụng sau khi đã đối chiếu schema, index và trigger. Không chạy `alembic downgrade base` trên database cần giữ dữ liệu vì thao tác này có thể xóa bảng.

Khi thay đổi ORM model trong tương lai, có thể tạo bản nháp migration bằng `alembic revision --autogenerate -m "mo ta thay doi"`. Luôn đọc và chỉnh bản nháp trước khi áp dụng, đặc biệt với thay đổi dữ liệu và trigger. Commit file migration cùng thay đổi model để thành viên khác cập nhật bằng `alembic upgrade head`.

## 5. Tạo admin và dữ liệu mẫu

Sau khi database đã có các bảng, chạy:

```powershell
python -m scripts.seed_demo --admin-email admin@example.com --admin-name "Campus Admin"
```

Thay email và tên bằng giá trị bạn muốn. Chương trình yêu cầu nhập và xác nhận mật khẩu admin tối thiểu 12 ký tự; ký tự mật khẩu có thể không hiện khi gõ. Script thêm các danh mục và địa điểm mẫu nếu chúng chưa tồn tại. Nếu email đã tồn tại, script dừng và không thay đổi tài khoản.

Admin được lưu trong database, nhưng API đăng nhập vẫn thuộc phần chưa triển khai. Database đã được seed trước đó không cần chạy lại chỉ để tạo cùng tài khoản.

## 6. Chạy và kiểm tra ứng dụng

Trong terminal đã kích hoạt `.venv`, chạy:

```powershell
uvicorn app.main:app --reload
```

Mở các địa chỉ sau trong trình duyệt:

- [Health check](http://localhost:8000/health): kiểm tra API đang chạy; endpoint này không kiểm tra kết nối database.
- [Swagger UI](http://localhost:8000/docs): xem tài liệu API và thử endpoint.
- [ReDoc](http://localhost:8000/redoc): xem tài liệu API.

Nhấn `Ctrl+C` trong terminal để dừng server. Các API nghiệp vụ hiện vẫn là khung, chưa đăng ký vào API v1.

## 7. Chạy test

```powershell
python -m pytest
```

Test migration cần một database PostgreSQL **trống, riêng cho test**. Đặt biến môi trường trỏ tới database đó, chạy test, rồi xóa biến khỏi terminal:

```powershell
$env:TEST_DATABASE_URL="postgresql+asyncpg://TEN_USER:MAT_KHAU@localhost:5432/campusfind_test"
python -m pytest tests/integration/test_migration.py
Remove-Item Env:TEST_DATABASE_URL
```

Test sẽ tạo bảng và không xóa chúng. Không trỏ `TEST_DATABASE_URL` tới database đang sử dụng. Nếu không đặt biến này, test migration sẽ được bỏ qua.

## 8. Khi làm việc theo nhóm

Mỗi người tự cấu hình `.env` và database trên máy mình. Migration giúp mọi người có cùng cấu trúc, còn dữ liệu sẽ độc lập. Nếu cần chia sẻ dữ liệu tại một thời điểm, có thể backup database rồi gửi cho thành viên khác restore; sau đó các bản sao vẫn không tự đồng bộ.

Khi lấy code mới có migration, kiểm tra file migration và chạy `alembic upgrade head` trên database của mình. Với database có dữ liệu quan trọng, nên backup trước khi áp dụng thay đổi.
