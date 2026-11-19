# CampusFind — Kiến Trúc Hệ Thống (System Architecture)

## 1. Giới thiệu tổng quan

CampusFind là hệ thống Web RESTful API phục vụ quản lý, tìm kiếm và đối soát hoàn trả tài sản thất lạc trong khuôn viên trường đại học (ĐH CNTT - UIT). Hệ thống được tổ chức theo **MVC cho REST API**, kết hợp **Controller → Service → Repository** cho các nghiệp vụ.

---

**Trạng thái hiện tại:** Sơ đồ và trách nhiệm bên dưới mô tả kiến trúc dự kiến. Đã có bộ khung FastAPI, schema chung, dependency injection, ORM, migration và seed. Các controller, service, repository và schema nghiệp vụ, JWT, matching và các quy tắc phân quyền trong ứng dụng chưa được triển khai. Endpoint `/health` nằm trong `app/api/v1/health.py`; model dữ liệu là các ORM model trong `app/db/models.py`. Trigger kiểm tra claim và bàn giao đã nằm trong migration SQL.

## 2. Mô hình MVC trong Web API & Phân tầng kiến trúc

CampusFind trả dữ liệu JSON thay vì render HTML. MVC trong project được tổ chức như sau:

*   **Model (M)**: Các lớp SQLAlchemy ORM Models định nghĩa cấu trúc bảng CSDL, quan hệ PK/FK và các ràng buộc toàn vẹn dữ liệu.
*   **View / trình bày dữ liệu**: Schema Pydantic xác định cấu trúc request và response JSON; FastAPI tuần tự hóa response. Đây là cách áp dụng vai trò trình bày của MVC cho API, không phải một View HTML truyền thống. Các schema nghiệp vụ sẽ được bổ sung sau.
*   **Controller (C)**: Các controller sử dụng FastAPI `APIRouter` để tiếp nhận HTTP Request, trích xuất tham số, kiểm tra xác thực và điều phối dữ liệu trả về.
*   **Tầng mở rộng Service & Repository**: Để tránh hiện tượng "Fat Controller", toàn bộ logic nghiệp vụ được đưa vào **Service Layer**, và toàn bộ thao tác truy vấn CSDL được đưa vào **Repository Layer**.

```mermaid
flowchart TD
    Client["Client (Swagger UI / Postman / Mobile / Web)"] -->|"1. HTTP Request (JSON)"| Controller["Controller (FastAPI APIRouter)\napp/modules/.../controller.py"]
    Controller -->|"2. Validate Input"| ViewIn["Pydantic Schema\napp/modules/.../schemas.py"]
    Controller -->|"3. Dependency Injection (Depends)"| Service["Service Layer (Business Logic)\napp/modules/.../service.py"]
    
    Service -->|"4. Kiểm tra quyền, State Machine, Matching"| Logic{"Hợp lệ?"}
    Logic -- "Lỗi nghiệp vụ" -->|"Ném AppException"| ExcHandler["Exception Handler\napp/core/exceptions.py"]
    ExcHandler -->|"Trả ApiErrorResponse"| Client

    Logic -- "Thành công" -->|"5. Gọi Data Access"| Repo["Repository Layer\napp/modules/.../repository.py"]
    Repo -->|"6. Kế thừa BaseRepository"| Model["Model (SQLAlchemy ORM)\napp/db/models.py"]
    Model <-->|"7. Async Query / Row Lock"| DB[("PostgreSQL 16 Database")]

    Repo -->|"8. Trả Entity"| Service
    Service -->|"9. Trả kết quả"| Controller
    Controller -->|"10. Đóng gói ApiResponse"| ViewOut["Response Schema / JSON\napp/shared/schemas.py"]
    ViewOut -->|"11. JSON Response UTF-8"| Client

    subgraph Cross-Cutting Concerns
        Config["app/core/config.py (Pydantic Settings)"]
        Security["app/core/security.py (JWT & Argon2/Bcrypt)"]
        Exceptions["app/core/exceptions.py (Uniform RFC Error Handlers)"]
        Logging["app/core/logging.py (SafeLogFilter che một số mẫu nhạy cảm)"]
        DI["app/core/dependencies.py (get_db, get_service, get_pagination)"]
    end
```

---

### Trách nhiệm dự kiến của từng tầng

1.  **Controller Layer (`controller.py`)**:
    *   Tiếp nhận HTTP requests (`GET`, `POST`, `PATCH`, `DELETE`).
    *   Sử dụng Dependency Injection (`Depends`) để inject DB Session và Service.
    *   Validate dữ liệu đầu vào thông qua Pydantic schema.
    *   Tuyệt đối **không** chứa logic nghiệp vụ tính điểm, không gọi trực tiếp SQL.

2.  **Service Layer (`service.py` kế thừa `BaseService`)**:
    *   "Bộ não" điều hành nghiệp vụ: kiểm tra tài khoản khóa/mở, quyền sở hữu (ownership), state machine của báo cáo, claim và biên bản bàn giao.
    *   Điều phối transaction và khóa dòng `with_for_update` trên bảng `found_reports` để chống bàn giao trùng.
    *   Gọi Matching Engine để tính toán độ tương đồng giữa các báo cáo.

3.  **Repository Layer (`repository.py` kế thừa `BaseRepository`)**:
    *   Đóng gói toàn bộ truy vấn SQLAlchemy ORM (`select`, `insert`, `update`, `delete`).
    *   Xử lý logic phân trang (`offset`, `limit`), lọc điều kiện và sắp xếp.

4.  **Matching Engine (`app/modules/matching/engine/`)**:
    *   `normalizer.py`: `normalize()` bỏ dấu, chữ thường, chỉ giữ `a-z0-9`, gộp khoảng trắng — chỉ dùng khi so khớp. Chi tiết: [matching-normalizer.md](matching-normalizer.md).
    *   `aliases.py`: Bảng từ đồng nghĩa tên đồ / màu (balo / ba lô, tai nghe / airpods, đen / black…) và `apply_aliases()`.
    *   `fuzzy.py`: So khớp mờ ký tự & token qua Levenshtein / Token Similarity (rapidfuzz), xử lý lỗi chính tả và biến thể thứ tự từ. Chi tiết: [matching-fuzzy.md](matching-fuzzy.md).
    *   `scorer.py`: Tính điểm tương đồng có trọng số \(S = 100(0.35N + 0.25C + 0.15K + 0.15L + 0.10T)\), phân loại ngưỡng HIGH (≥80), MEDIUM (60–79), LOW (<60) và trả về `score_breakdown` giải thích nguyên nhân. Chi tiết: [matching-scorer.md](matching-scorer.md).

---

## 3. Cấu trúc thư mục thực tế của Repository

```text
IE221 - UIT CampusFind/
├── app/
│   ├── main.py                     # Entry point FastAPI, lifespan, CORS, exception handlers
│   ├── api/
│   │   └── v1/
│   │       ├── health.py           # Endpoint /health (đăng ký trực tiếp, không có tiền tố v1)
│   │       └── router.py           # Router v1, chưa đăng ký router nghiệp vụ
│   ├── core/
│   │   ├── config.py               # Pydantic Settings đọc cấu hình từ .env
│   │   ├── dependencies.py         # DI: get_db, get_service factory, get_pagination
│   │   ├── exceptions.py           # Custom Domain Exceptions & Uniform JSON Handlers
│   │   ├── logging.py              # Logging và lọc một số mẫu nhạy cảm
│   │   └── security.py             # Khung cho hash mật khẩu và JWT
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy Declarative Base
│   │   ├── models.py               # ORM models cho 9 bảng
│   │   └── session.py              # Async SQLAlchemy Engine & AsyncSession Maker
│   ├── modules/                    # 7 Feature Modules độc lập (Modular Monolith)
│   │   ├── auth/                   # Đăng ký, đăng nhập & cấp phát JWT token
│   │   │   ├── controller.py | schemas.py | service.py
│   │   ├── users/                  # Hồ sơ cá nhân & Admin quản lý tài khoản (users)
│   │   │   ├── repository.py | controller.py | schemas.py | service.py
│   │   ├── catalog/                # Danh mục đồ & địa điểm (categories, locations)
│   │   │   ├── repository.py | controller.py | schemas.py | service.py
│   │   ├── reports/                # Tin báo mất & tin nhặt đồ (lost_reports, found_reports)
│   │   │   ├── repository.py | controller.py | schemas.py | service.py
│   │   ├── matching/               # Đối soát tin trùng khớp & thông báo (matches)
│   │   │   ├── engine/
│   │   │   │   ├── aliases.py      # Khung từ đồng nghĩa tiếng Việt
│   │   │   │   ├── fuzzy.py        # So khớp mờ (Levenshtein & Token Similarity)
│   │   │   │   ├── normalizer.py   # Khung chuẩn hóa Unicode
│   │   │   │   └── scorer.py       # Khung tính điểm
│   │   │   ├── repository.py | controller.py | schemas.py | service.py
│   │   ├── claims/                 # Gửi yêu cầu nhận đồ, nộp bằng chứng, xét duyệt (claims, claim_evidence)
│   │   │   ├── repository.py | controller.py | schemas.py | service.py
│   │   └── handovers/              # Bàn giao giao dịch nguyên tử & Thống kê (handover_records)
│   │       ├── repository.py | controller.py | schemas.py | service.py
│   │
│   └── shared/                     # Lớp dùng chung toàn hệ thống
│       ├── enums.py                # Khung enum cho các bước sau
│       ├── repository.py           # Generic BaseRepository[ModelType] (CRUD chuẩn hóa)
│       ├── service.py              # Generic BaseService
│       ├── schemas.py              # ApiResponse, ApiErrorResponse, PaginatedResponse
│       └── utils.py                # Khung tiện ích dùng chung
│
├── alembic/                        # Quản lý Database Migrations
│   ├── env.py                      # Nạp metadata của các ORM model
│   ├── script.py.mako              # Template sinh file migration
│   └── versions/                   # Các revision và SQL schema ban đầu
│
├── tests/                          # Bộ kiểm thử tự động với Pytest
│   ├── conftest.py                 # AsyncClient fixtures với HTTPX
│   ├── unit/                       # Thư mục unit tests
│   └── integration/                # Integration tests (health check, exception handlers)
│       ├── test_health_and_auth.py
│       └── test_exception_handlers.py
│
├── scripts/
│   └── seed_demo.py                # Script nạp CSDL mẫu tiếng Việt (Admin, Categories, Locations)
│
├── docs/
│   ├── architecture.md             # Tài liệu kiến trúc hệ thống (file này)
│   ├── erd.md                      # Sơ đồ và chi tiết 9 bảng
│   ├── data-flow.md                # Sơ đồ luồng dữ liệu dự kiến
│   └── user-guide.md               # Hướng dẫn thiết lập môi trường và chạy dự án
│
├── pyproject.toml                  # Khai báo dependency chuẩn PEP 621 & cấu hình Ruff/Pytest
├── requirements.txt                # Cài project với dependencies trong pyproject.toml
├── requirements-dev.txt            # Cài project và nhóm dependencies dev
├── alembic.ini                     # Cấu hình Alembic CLI
├── .env.example                    # Template biến môi trường
├── .gitignore                      # Git ignore tiêu chuẩn
└── README.md                       # Thông tin đồ án, thành viên và hướng dẫn chạy
```

---

## 4. Định hướng bảo trì, nâng cấp và mở rộng

Các mục sau là định hướng thiết kế; các tính năng và lớp bảo vệ nghiệp vụ chưa được triển khai trong ứng dụng.

1.  **Tính độc lập của Feature Modules (High Cohesion, Low Coupling)**:
    Mỗi nghiệp vụ lớn nằm trọn trong một module con (`catalog`, `reports`, `matching`, `claims`, `handovers`). Khi cần thay đổi luồng Claim hoặc bổ sung loại bằng chứng mới, chỉ cần cập nhật trong `app/modules/claims/` mà không gây ảnh hưởng đến `matching` hay `catalog`.
2.  **Khả năng nâng cấp Matching Engine không ảnh hưởng API**:
    Toàn bộ thuật toán được đóng gói bên trong thư mục `engine/`. Nếu sau này đồ án mở rộng bổ sung embedding vector hoặc mô hình AI, chỉ cần thay thế hoặc cắm thêm Strategy mới trong `MatchScoringStrategy` mà giữ nguyên Router và Schema response.
3.  **Bảo mật và bảo vệ dữ liệu nhạy cảm**:
    *   Dự kiến sử dụng hai schema response riêng biệt: `ReadPublic` (cho danh sách chung) và `ReadPrivate` (chỉ trả về `private_identifiers` khi người dùng là chủ tin hoặc Admin).
    *   Dự kiến thông tin liên hệ (`contact_phone`) chỉ được hiển thị khi cả claimant và finder cùng kích hoạt `contact_consent = True`.
4.  **An toàn giao dịch (Atomic Handover)**:
    Sử dụng cơ chế khóa dòng `with_for_update` của PostgreSQL trong SQLAlchemy transaction nhằm ngăn chặn tình trạng race condition khi 2 admin hoặc 2 claim cố gắng hoàn tất bàn giao cùng lúc cho một đồ nhặt được.

