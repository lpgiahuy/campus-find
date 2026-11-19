# Weighted Matching Score Engine (Task #11)

Tài liệu hướng dẫn triển khai, công thức tính toán và cách sử dụng **Weighted Matching Score** trong CampusFind (`app/modules/matching/engine/scorer.py`).

---

## 1. Mục tiêu & Nguyên lý

Trong hệ thống tìm kiếm đồ thất lạc CampusFind, sau khi ứng viên được sơ tuyển qua `MatchingRepository` (Task #10), hệ thống cần một cơ chế đánh giá độ tương đồng tổng hợp giữa tin báo mất (**LostReport**) và tin nhặt được (**FoundReport**).

Điểm số cần thỏa mãn các tiêu chí:
1. **Toàn diện (Comprehensive):** Kết hợp đa chiều từ 5 đặc trưng: Tên, Danh mục, Màu sắc, Địa điểm và Thời gian.
2. **Minh bạch & Giải trình được (Explainability):** Cung cấp chi tiết điểm số (`breakdown`) và lý do (`reasons`) giải thích cho người dùng biết vì sao hai tin được đánh giá là trùng khớp.
3. **Phân ngưỡng rõ ràng (Threshold Classification):** Tự động phân loại 3 mức độ tương đồng:
   - **HIGH (Cao):** Điểm số $\ge 80.0$
   - **MEDIUM (Trung bình):** $60.0 \le \text{Điểm số} < 80.0$
   - **LOW (Thấp):** Điểm số $< 60.0$

---

## 2. Công thức tính điểm có trọng số (Weighted Score Formula)

Tổng điểm $S \in [0.0, 100.0]$ được tính theo tổ hợp tuyến tính:

$$S = 100 \times \left(0.35N + 0.25C + 0.15K + 0.15L + 0.10T\right)$$

Trong đó mỗi điểm thành phần $N, C, K, L, T \in [0.0, 1.0]$ (hoặc thang điểm $100$ được nhân trực tiếp với trọng số tương ứng):

$$S = 0.35 \times S_{\text{name}} + 0.25 \times S_{\text{category}} + 0.15 \times S_{\text{color}} + 0.15 \times S_{\text{location}} + 0.10 \times S_{\text{time}}$$

### 2.1. Bảng phân bổ trọng số & Tiêu chí

| Ký hiệu | Tiêu chí | Trọng số | Thuật toán & Phương pháp đánh giá |
|:---:|:---|:---:|:---|
| **$N$** | **Tên tài sản (Name)** | **35%** (0.35) | Chuẩn hóa Unicode + từ đồng nghĩa `item` + Fuzzy Composite Matching (`rapidfuzz`: Levenshtein, Token Sort, Token Set có phạt độ dài). |
| **$C$** | **Danh mục (Category)** | **25%** (0.25) | So khớp chính xác `category_id` (hoặc tên chuẩn hóa): Khớp = 100.0, Khác = 0.0. |
| **$K$** | **Màu sắc (Color)** | **15%** (0.15) | So khớp mờ qua từ đồng nghĩa `color` (`đen` $\leftrightarrow$ `black`). Trường tùy chọn: nếu 1 hoặc cả 2 bên không khai báo $\rightarrow$ Điểm trung tính 50.0. |
| **$L$** | **Địa điểm (Location)** | **15%** (0.15) | So khớp `location_id` (100.0 nếu cùng ID) hoặc so khớp mờ tên địa điểm (nếu có tên). Thiếu $\rightarrow$ Điểm trung tính 50.0. |
| **$T$** | **Thời gian (Time)** | **10%** (0.10) | Hàm suy giảm tuyến tính trong cửa sổ 14 ngày: $\Delta t = 0 \rightarrow 100$, $\Delta t = 7 \text{ ngày} \rightarrow 50$, $\Delta t \ge 14 \text{ ngày} \rightarrow 0$. Thiếu $\rightarrow$ Điểm trung tính 50.0. |

---

## 3. Chi tiết thuật toán từng thành phần

### 3.1. Tiêu chí Tên tài sản ($S_{\text{name}}$)
- Gọi `detailed_fuzzy_match(name_a, name_b, alias_table="item")`.
- Tự động chuẩn hóa dấu tiếng Việt (`ví da` vs `vi da`), bắt lỗi chính tả gõ phím (`bluetoth` vs `bluetooth`), bắt đảo từ ngữ và từ đồng nghĩa (`AirPods Pro` $\leftrightarrow$ `tai nghe pro`).
- Trả về điểm [0.0, 100.0] và chi tiết `levenshtein_ratio`, `token_sort_ratio`, `token_set_ratio`, `length_penalty`.

### 3.2. Tiêu chí Danh mục ($S_{\text{category}}$)
- Nếu `cat_id_a == cat_id_b` $\rightarrow$ $100.0$ điểm.
- Nếu khác ID nhưng có cùng tên danh mục sau khi chuẩn hóa (`normalize`) $\rightarrow$ $100.0$ điểm.
- Khác danh mục $\rightarrow$ $0.0$ điểm.

### 3.3. Tiêu chí Màu sắc ($S_{\text{color}}$)
- Do màu sắc là trường thông tin không bắt buộc trong khai báo:
  - Cả hai bên không cung cấp $\rightarrow$ Điểm trung tính $50.0$.
  - Một bên không cung cấp $\rightarrow$ Điểm trung tính $50.0$.
  - Cả hai bên đều cung cấp $\rightarrow$ So khớp mờ qua bảng `COLOR_ALIASES` (`detailed_fuzzy_match(..., alias_table="color")`).

### 3.4. Tiêu chí Địa điểm ($S_{\text{location}}$)
- Cùng `location_id` $\rightarrow$ $100.0$ điểm.
- Khác `location_id`: nếu có cung cấp tên địa điểm, áp dụng fuzzy matching (ngưỡng $\ge 80$ đạt điểm cao).
- Thiếu thông tin địa điểm $\rightarrow$ Điểm trung tính $50.0$.

### 3.5. Tiêu chí Thời gian ($S_{\text{time}}$)
- Đo khoảng cách thời gian tuyệt đối $\Delta t = |t_{\text{lost}} - t_{\text{found}}|$ (chuẩn hóa UTC an toàn).
- Hàm suy giảm tuyến tính:

$$\text{diff\_days} = \frac{|\Delta t|}{86400}$$

$$S_{\text{time}} = \begin{cases} 100.0 & \text{khi } \Delta t < 60 \text{ giây} \\ \max\left(0.0, 100.0 \times \left(1 - \frac{\text{diff\_days}}{14}\right)\right) & \text{khi } \text{diff\_days} \le 14 \\ 0.0 & \text{khi } \text{diff\_days} > 14 \end{cases}$$

---

## 4. Phân loại ngưỡng tương đồng (Thresholds)

Enum: `MatchLevel` (`app/shared/enums.py`):
```python
class MatchLevel(StrEnum):
    HIGH = "HIGH"        # score >= 80.0
    MEDIUM = "MEDIUM"    # 60.0 <= score < 80.0
    LOW = "LOW"          # score < 60.0
```

---

## 5. Hướng dẫn sử dụng trong Python

### 5.1. Dùng hàm `calculate_match_score`

```python
from datetime import datetime, timezone, timedelta
from app.modules.matching.engine.scorer import calculate_match_score

lost_data = {
    "item_name": "Ví da Pedro",
    "category_id": "c1f72a69-65be-44b4-82f3-324d5ba7b545",
    "color": "đen",
    "location_id": "b3c65c92-3eb4-44aa-9d51-30910f135111",
    "lost_at": datetime.now(timezone.utc),
}

found_data = {
    "item_name": "Bóp da Pedro",
    "category_id": "c1f72a69-65be-44b4-82f3-324d5ba7b545",
    "color": "black",
    "location_id": "b3c65c92-3eb4-44aa-9d51-30910f135111",
    "found_at": datetime.now(timezone.utc) + timedelta(hours=4),
}

result = calculate_match_score(lost=lost_data, found=found_data)

print(result.total_score)  # 96.5
print(result.level)        # MatchLevel.HIGH
for reason in result.reasons:
    print("-", reason)
```

---

## 6. REST API Endpoint

Được đăng ký tại `app/modules/matching/controller.py` trên router v1 `/api/v1/matching/score`.

- **Method / Path:** `POST /api/v1/matching/score`
- **Content-Type:** `application/json`

### 6.1. Request Body (`MatchScoreRequest`)

```json
{
  "lost": {
    "item_name": "Ví da nam Pedro",
    "category_id": "c1f72a69-65be-44b4-82f3-324d5ba7b545",
    "category_name": "Phụ kiện",
    "color": "đen",
    "location_id": "b3c65c92-3eb4-44aa-9d51-30910f135111",
    "location_name": "Thư viện",
    "timestamp": "2026-11-10T10:00:00Z"
  },
  "found": {
    "item_name": "Bóp da Pedro",
    "category_id": "c1f72a69-65be-44b4-82f3-324d5ba7b545",
    "category_name": "Phụ kiện",
    "color": "black",
    "location_id": "b3c65c92-3eb4-44aa-9d51-30910f135111",
    "location_name": "Thư viện",
    "timestamp": "2026-11-10T14:30:00Z"
  }
}
```

### 6.2. Response Envelope (`ApiResponse[MatchScoreResult]`)

```json
{
  "success": true,
  "message": "Tính toán điểm tương đồng thành công",
  "data": {
    "total_score": 96.38,
    "level": "HIGH",
    "reasons": [
      "Tên tài sản tương đồng khá cao (89.66%)",
      "Cùng danh mục tài sản (Phụ kiện)",
      "Màu sắc trùng khớp hoàn toàn ('đen' / 'black')",
      "Cùng địa điểm phát hiện/thất lạc (Thư viện)",
      "Thời gian xảy ra rất gần nhau (chênh lệch 4.5 giờ)"
    ],
    "breakdown": {
      "name": {
        "score": 89.66,
        "weight": 0.35,
        "weighted_score": 31.38,
        "reason": "Tên tài sản tương đồng khá cao (89.66%)",
        "details": {
          "normalized_a": "vi da nam pedro",
          "normalized_b": "vi da pedro",
          "levenshtein_ratio": 84.62,
          "token_sort_ratio": 84.62,
          "token_set_ratio": 100.0,
          "length_penalty": 0.9
        }
      },
      "category": {
        "score": 100.0,
        "weight": 0.25,
        "weighted_score": 25.0,
        "reason": "Cùng danh mục tài sản (Phụ kiện)",
        "details": {
          "matched": true,
          "category_id": "c1f72a69-65be-44b4-82f3-324d5ba7b545"
        }
      },
      "color": {
        "score": 100.0,
        "weight": 0.15,
        "weighted_score": 15.0,
        "reason": "Màu sắc trùng khớp hoàn toàn ('đen' / 'black')",
        "details": {
          "normalized_a": "den",
          "normalized_b": "den",
          "fuzzy_score": 100.0
        }
      },
      "location": {
        "score": 100.0,
        "weight": 0.15,
        "weighted_score": 15.0,
        "reason": "Cùng địa điểm phát hiện/thất lạc (Thư viện)",
        "details": {
          "matched": true,
          "location_id": "b3c65c92-3eb4-44aa-9d51-30910f135111"
        }
      },
      "time": {
        "score": 98.66,
        "weight": 0.1,
        "weighted_score": 9.87,
        "reason": "Thời gian xảy ra rất gần nhau (chênh lệch 4.5 giờ)",
        "details": {
          "diff_seconds": 16200.0,
          "diff_hours": 4.5,
          "diff_days": 0.19
        }
      }
    },
    "algorithm_version": "rules-v1"
  }
}
```

---

## 7. Kiểm thử tự động (Testing)

- **Unit tests:** `tests/unit/test_scorer.py` (38 test cases kiểm tra từng tiêu chí độc lập, hằng số, ngưỡng biên, phép tính và mô hình ORM).
- **Integration tests:** `tests/integration/test_matching_api.py` (12 test cases kiểm tra endpoint HTTP, validation schema, các trường hợp High/Medium/Low).

Chạy kiểm thử:
```bash
pytest tests/unit/test_scorer.py tests/integration/test_matching_api.py -v
```

