# So khớp mờ cho Matching (Task #9)

Tài liệu hướng dẫn sử dụng `fuzzy.py` cho các task tiếp theo (#11 `scorer.py`, #12 matching tự động, #16 tìm kiếm nâng cao).

## 1. Mục đích

Sau khi qua bước chuẩn hóa ở Task #8 (`normalizer.py` và `aliases.py`), văn bản người dùng gõ vẫn có thể chênh lệch do:
1. **Lỗi gõ phím / sai chính tả (Typo / Misspelling):** `bluetoth` vs `bluetooth`, `tai nge` vs `tai nghe`, `bal0` vs `balo`.
2. **Dấu tiếng Việt & không dấu (Diacritics):** `vi da` vs `ví da`, `khoa` vs `khóa` (xử lý qua pipeline chuẩn hóa).
3. **Đảo trật tự từ (Word Reordering):** `tai nghe bluetooth` vs `bluetooth tai nghe`, `ví da nam` vs `nam ví da`.
4. **Chuỗi con & mô tả chi tiết (Subset / Super-set):** `ví da bò nâu` vs `ví da`.

Task #9 cung cấp module so khớp mờ (Fuzzy String Matching) kết hợp giữa khoảng cách chỉnh sửa **Levenshtein** và độ tương đồng tập từ **Token Similarity** thông qua thư viện `rapidfuzz`.

## 2. Cách dùng trong Python

```python
from app.modules.matching.engine.fuzzy import (
    detailed_fuzzy_match,
    fuzzy_match,
    levenshtein_similarity,
    token_similarity,
)

# 1. So khớp đơn giản lấy điểm số (0.0 - 100.0)
score = fuzzy_match("bluetoth", "bluetooth")
# -> 94.12

# 2. Tự động kết hợp bảng alias (item hoặc color)
item_score = fuzzy_match("AirPods Pro", "tai nghe pro", alias_table="item")
# -> 100.0

color_score = fuzzy_match("BLACK", "đen", alias_table="color")
# -> 100.0

# 3. Lấy giải trình chi tiết (phục vụ score_breakdown cho Task #11)
result = detailed_fuzzy_match("ví da", "ví da bò", alias_table="item")
print(result.score)  # 93.33
print(result.breakdown.levenshtein_ratio)  # 76.92
print(result.breakdown.token_sort_ratio)  # 76.92
print(result.breakdown.token_set_ratio)  # 100.0
print(result.breakdown.length_penalty)  # 0.67
```

## 3. Thuật toán kết hợp (Phương án A - Composite Strategy)

File: `app/modules/matching/engine/fuzzy.py`.

### 3.1. Các thành phần độ đo
| Độ đo | Hàm trong `rapidfuzz` | Vai trò chính |
|---|---|---|
| **Levenshtein Ratio** | `fuzz.ratio` | Bắt lỗi gõ phím, sai chính tả 1-2 ký tự (`bluetoth` vs `bluetooth`: 94.12%) |
| **Token Sort Ratio** | `fuzz.token_sort_ratio` | Bắt đảo trật tự từ ngữ (`tai nghe bluetooth` vs `bluetooth tai nghe`: 100.0%) |
| **Token Set Ratio** | `fuzz.token_set_ratio` | Bắt từ con / mô tả chi tiết hơn (`ví da` vs `ví da bò`: 100.0%) |

### 3.2. Công thức phạt độ dài (Length Penalty)
Nếu chỉ dùng `token_set_ratio`, một từ ngắn (ví dụ `tai nghe`) sẽ khớp 100% với chuỗi dài bất kỳ có chứa nó (như `tai nghe bluetooth sony wh-1000xm4`). Vì vậy hệ thống áp dụng hệ số phạt tỷ lệ độ dài:

$$\text{length\_penalty} = \frac{\min(\text{len}(T_A), \text{len}(T_B))}{\max(\text{len}(T_A), \text{len}(T_B))}$$

$$\text{penalty} = \begin{cases} \text{length\_penalty}^{0.5} & \text{khi } \min(\text{len}) = 1 \text{ và } \max(\text{len}) > 1 \\ 0.7 + 0.3 \times \text{length\_penalty} & \text{ngược lại} \end{cases}$$

$$\text{penalized\_token\_set} = \text{token\_set\_ratio} \times \text{penalty}$$

$$\text{final\_score} = \max(\text{Levenshtein}, \max(\text{TokenSort}, \text{penalized\_token\_set}))$$

### 3.3. Bảng kết quả thực nghiệm

| Chuỗi A | Chuỗi B | Điểm cuối | Phân tích |
|---|---|---|---|
| `bluetoth` | `bluetooth` | **94.12** | Levenshtein bắt lỗi thiếu 1 chữ 'o' |
| `vi da` | `ví da` | **100.0** | Normalize bỏ dấu về cùng chuỗi `vi da` |
| `tai nge` | `tai nghe` | **93.33** | Bắt lỗi chính tả `nge` -> `nghe` |
| `bal0` | `balo` | **75.0** | Bắt lỗi gõ nhầm số 0 thay chữ o |
| `tai nghe bluetooth` | `bluetooth tai nghe` | **100.0** | Token Sort xử lý trật tự từ |
| `ví da` | `ví da bò` | **93.33** | Token Set xử lý mô tả chi tiết hơn |
| `ví da` | `ví da bò nâu` | **90.0** | Token Set kèm phạt độ dài |
| `tai nghe` | `balo laptop` | **21.05** | Hai đồ khác loại có điểm rất thấp |

## 4. REST API Endpoint

Router: `app/modules/matching/controller.py` (đã đăng ký vào `/api/v1/matching`).

- **Method / Path:** `POST /api/v1/matching/similarity`
- **Request Body (`FuzzyCheckRequest`):**
  ```json
  {
    "text_a": "bluetoth",
    "text_b": "bluetooth",
    "alias_type": "item"
  }
  ```
- **Response (`ApiResponse[FuzzySimilarityResult]`):**
  ```json
  {
    "success": true,
    "message": "Tính toán độ tương đồng thành công",
    "data": {
      "score": 94.12,
      "normalized_a": "bluetoth",
      "normalized_b": "bluetooth",
      "breakdown": {
        "levenshtein_ratio": 94.12,
        "token_sort_ratio": 94.12,
        "token_set_ratio": 94.12,
        "length_penalty": 1.0
      }
    }
  }
  ```

## 5. Kiểm thử

- Unit tests: `tests/unit/test_fuzzy.py` (47 tests).
- Integration tests: `tests/integration/test_matching_api.py` (3 tests).

Chạy kiểm thử:
```bash
pytest tests/unit/test_fuzzy.py tests/integration/test_matching_api.py -v
```
