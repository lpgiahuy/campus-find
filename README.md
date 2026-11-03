# CampusFind API — University Lost-and-Found Management

## 1. Thông tin đồ án

| Nội dung | Thông tin |
| :--- | :--- |
| **Tên đồ án** | CampusFind — University Lost-and-Found Management REST API |
| **Môn học** | IE221 — Kỹ thuật lập trình Python |
| **Lớp** | IE221.R11 |
| **Giảng viên hướng dẫn** | ThS. Phạm Thế Sơn |
| **Học kỳ / Năm học** | 2026 – 2027 (Học kỳ 1) |

---

## 2. Thành viên tham gia

| Vai trò | Họ và tên | MSSV |
| :--- | :--- | :---: |
| Thành viên 1 | Lê Phạm Gia Huy | 24520668 |
| Thành viên 2 | Nguyễn Huy Hoàng | 24520555 |

---

## 3. Hướng dẫn khởi chạy

Xem [hướng dẫn sử dụng chi tiết](docs/user-guide.md) để thiết lập môi trường, PostgreSQL, migration và dữ liệu mẫu.

Xem thêm [hướng dẫn Migration với Alembic](docs/user-guide.md#4-migration-tạo-cấu-trúc-database) để tạo, kiểm tra và áp dụng migration.

```powershell
# 1. Tạo và kích hoạt môi trường ảo
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Cài đặt các thư viện
pip install -r requirements-dev.txt

# 3. Tạo file cấu hình môi trường từ template
Copy-Item .env.example .env

# 4. Khởi chạy server phát triển
uvicorn app.main:app --reload
```

Sau khi tạo `.env`, thay `user` và `password` trong `DATABASE_URL` bằng thông tin PostgreSQL trên máy của bạn. `.env` chỉ dùng trên máy cá nhân và đã được Git bỏ qua; `.env.example` chỉ chứa giá trị mẫu. Các thiết lập JWT, tài khoản admin và matching sẽ được bổ sung khi triển khai những chức năng tương ứng.

---

## 4. Đường dẫn kiểm tra nhanh

* **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## 5. Database và dữ liệu mẫu

Tạo một database PostgreSQL trống và điền `DATABASE_URL` trong `.env`, sau đó chạy. Nếu `.env` cũ có `SYNC_DATABASE_URL`, hãy xóa dòng đó để migration và seed dùng cùng database với ứng dụng, hoặc tự cập nhật cả hai URL cho khớp.

```powershell
alembic upgrade head
python -m scripts.seed_demo --admin-email admin@example.com --admin-name "Campus Admin"
```

Script seed yêu cầu nhập và xác nhận mật khẩu admin trong terminal; không lưu mật khẩu trong repo. Danh mục và địa điểm mẫu được thêm nếu chưa tồn tại. Nếu email đã tồn tại, seed dừng và không thay đổi tài khoản.

Migration ban đầu chỉ chạy trên database trống. Nếu đã tạo bảng bằng script SQL trong pgAdmin, không chạy migration lên database đó: hãy dùng database trống riêng để kiểm thử migration. Không dùng `alembic stamp` cho database có sẵn khi chưa đối chiếu schema, index và trigger. Schema ban đầu được lưu trong `alembic/versions/initial_schema.sql`; các thay đổi sau này được quản lý bằng migration mới.

Để kiểm thử migration, tạo một database **trống, riêng cho test** rồi đặt `TEST_DATABASE_URL` trỏ tới database này và chạy:

```powershell
$env:TEST_DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/campusfind_test"
python -m pytest tests/integration/test_migration.py
Remove-Item Env:TEST_DATABASE_URL
```

Test sẽ tạo các bảng trong database test và không xóa chúng. Không trỏ biến này tới database đang sử dụng.

## 6. Kiểm thử tự động (CI)

GitHub Actions chạy test khi có push, pull request hoặc khi được kích hoạt thủ công trong tab **Actions**. Workflow tạo PostgreSQL tạm để kiểm thử migration từ database trống; thông tin kết nối trong workflow chỉ dùng cho database tạm này. Xem kết quả tại tab **Actions** của repository sau khi đưa workflow lên GitHub.

