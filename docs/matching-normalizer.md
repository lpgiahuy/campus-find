# Chuẩn hóa tiếng Việt cho Matching (task #8)

Tài liệu cho người dùng lại `normalizer.py` / `aliases.py` (#9, #11, #12, #16) và người thêm từ đồng nghĩa.

## 1. Mục đích

Tên đồ và màu là **chữ tự do** người dùng gõ. Trước khi so bằng rapidfuzz (#9, #11), hai chuỗi phải về cùng một dạng, nếu không thì cùng một món đồ vẫn bị chấm điểm thấp:

| Người mất gõ | Người nhặt gõ | Sau chuẩn hóa (cả hai) |
|---|---|---|
| `Ví da nâu` | `vi da nau` | `vi da nau` |
| `khóa` | `khoá` (dấu đặt kiểu cũ) | `khoa` |
| `Ví` (NFD, gõ từ macOS) | `Ví` (NFC) | `vi` |
| `iPhone-13, màu ĐEN!` | `iphone 13 mau den` | `iphone 13 mau den` |
| `Ba lô` | `balo` | `balo` |
| `AirPods` | `tai nghe` | `tai nghe` |
| màu `Black` | màu `đen` | `den` |

**Chỉ dùng khi so khớp.** DB vẫn lưu nguyên tiếng Việt có dấu (chuẩn hóa để *lưu* là việc của `normalize_vietnamese_text` trong `app/shared/utils.py` — hàm khác, không đổi).

## 2. Cách dùng

```python
from app.modules.matching.engine.aliases import COLOR_ALIASES, ITEM_ALIASES, apply_aliases
from app.modules.matching.engine.normalizer import normalize

name = apply_aliases(normalize(report.item_name), ITEM_ALIASES)
color = apply_aliases(normalize(report.color), COLOR_ALIASES)  # color None → ""
```

- Luôn gọi `normalize()` **trước** `apply_aliases()` — bảng alias đã ở dạng chuẩn hóa nên chỉ khớp với chuỗi đã chuẩn hóa.
- Tên đồ dùng `ITEM_ALIASES`, màu dùng `COLOR_ALIASES`. **Không dùng lẫn** (xem mục 4.2).
- Chỉ cần tìm kiếm không dấu (vd. #16) thì dùng riêng `normalize()`.

## 3. `normalize(text: str | None) -> str`

File: `app/modules/matching/engine/normalizer.py`.

```python
_NON_ALNUM.sub(" ", unidecode(text).lower()).strip()
```

| Bước | Làm gì | Ví dụ |
|---|---|---|
| `unidecode` | Bỏ dấu, `đ` → `d`, ký tự không phải Latin → gần đúng hoặc rỗng | `Đồng hồ 😀` → `Dong ho ` |
| `lower()` | Chữ thường | `Dong ho` → `dong ho` |
| `[^a-z0-9]+` → `" "` | Dấu câu, xuống dòng, khoảng trắng liên tiếp → 1 khoảng trắng | `iphone-13,  den!` → `iphone 13 den ` |
| `strip()` | Bỏ khoảng trắng đầu / cuối | |

- `None`, `""`, chỉ khoảng trắng, chỉ ký tự lạ → `""`.
- **Không có bước NFC riêng:** `unidecode` xử lý được cả chuỗi NFD (dấu tách rời) — đã kiểm bằng test `test_normalize_nfc_and_nfd_equal`.
- Gọi lại trên kết quả không đổi gì (idempotent).

**Hệ quả cần biết:** bỏ dấu làm một số từ trùng nhau (`ví` / `vì` → `vi`, `ô` / `o`). Chấp nhận được vì #10 đã lọc ứng viên cùng danh mục, tên đồ thường ngắn.

## 4. `apply_aliases(text: str, table: Mapping[str, str]) -> str`

File: `app/modules/matching/engine/aliases.py`.

### 4.1 Cách thay

1. Gộp mọi biến thể trong bảng thành **một** regex, sắp **dài trước ngắn sau**, bọc bằng `\b…\b`.
2. `re.sub` **một lượt**, mỗi chỗ khớp thay bằng từ chuẩn.

Nhờ vậy:

| Tính chất | Ví dụ |
|---|---|
| Chỉ thay nguyên từ | `balomini` giữ nguyên |
| Cụm dài thắng cụm ngắn | `pin du phong` → `sac du phong` (không bị cắt) |
| Không thay dây chuyền | Kết quả của lượt thay không bị thay tiếp |

`re` tự cache pattern đã biên dịch theo chuỗi pattern, nên dựng chuỗi regex mỗi lần gọi không tốn đáng kể.

### 4.2 Hai bảng riêng

`ITEM_ALIASES` (tên đồ) và `COLOR_ALIASES` (màu) tách riêng vì có từ chỉ đúng nghĩa trong một ngữ cảnh: `ghi` là màu xám, nhưng trong tên đồ `sổ ghi chép` mà thay thì thành `so xam chep`.

### 4.3 Thay hẳn bằng từ chuẩn

`airpods` → `tai nghe` (mất tên hãng), không phải `tai nghe airpods`. Đã đo bằng rapidfuzz `token_set_ratio`:

| So | Điểm |
|---|---|
| `tai nghe pro` vs `tai nghe sony` (thay hẳn) | 80.0 |
| `tai nghe airpods pro` vs `tai nghe sony` (giữ hãng) | 76.2 |

Giữ hãng chỉ giảm ~4 điểm mà làm hàm hết idempotent và sinh token lặp → chọn thay hẳn.

## 5. Thêm từ đồng nghĩa

Sửa `_ITEM_GROUPS` hoặc `_COLOR_GROUPS` trong `aliases.py` — dạng `{từ chuẩn: [biến thể]}`, **viết có dấu bình thường**:

```python
_ITEM_GROUPS = {
    "balo": ["ba lô", "balô", "backpack", "cặp đeo lưng"],
    ...
    "mu bao hiem": ["nón bảo hiểm", "helmet"],  # thêm nhóm mới
}
```

Khi import, `_build()` chạy `normalize()` cho cả từ chuẩn và biến thể, bỏ biến thể trùng với từ chuẩn sau chuẩn hóa (`balô` → `balo`).

Quy tắc (test `test_alias_table_is_normalized_and_idempotent` tự kiểm, chạy `pytest` là biết):

1. **Từ chuẩn không được chứa biến thể nào** (theo nguyên từ). Vd. thêm biến thể `sac` cho nhóm khác sẽ hỏng vì từ chuẩn `sac du phong` chứa `sac`.
2. **Tránh biến thể một âm tiết dễ trùng sau khi bỏ dấu** (`ô`, `dù`, `ví`) — dễ thay nhầm trong câu khác.
3. Một biến thể chỉ thuộc một nhóm (nhóm sau ghi đè nhóm trước).

**Đổi bảng alias làm thay đổi điểm match đã lưu** → khi #12 có `algorithm_version`, nhớ tăng version sau mỗi lần đổi bảng.

## 6. Test

`tests/unit/test_normalizer.py` (không cần DB):

```bash
pytest tests/unit/test_normalizer.py -q
```

| Nhóm | Kiểm |
|---|---|
| `normalize` | Bảng vào / ra mục 1, NFC ≡ NFD, idempotent, `None` / rỗng |
| `apply_aliases` | Thay đúng, nguyên từ, cụm dài trước, bảng màu không áp vào tên đồ |
| Cả bảng | Mọi khóa / giá trị đã chuẩn hóa, từ chuẩn không chứa biến thể, gọi 2 lần ra cùng kết quả |

## 7. Ngoài phạm vi

| Không làm | Ở đâu |
|---|---|
| Sai chính tả (`tai nge`, `bal0`) — so khớp mờ | #9 (rapidfuzz) |
| Trọng số, công thức điểm, `score_breakdown` | #11 |
| Bỏ từ thừa (`cái`, `chiếc`, `bị mất`…) | Để #11 quyết sau khi thử dữ liệu thật |
| Alias địa điểm | Địa điểm là ID catalog, so bằng `==` |
