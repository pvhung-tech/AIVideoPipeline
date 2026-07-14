# RULES.md

Version: 1.0

# AI Video Pipeline Studio

---

# 1. Purpose

Tài liệu này định nghĩa các quy tắc kỹ thuật bắt buộc áp dụng cho toàn bộ dự án.

Mọi AI Coding Agent và lập trình viên phải tuân thủ tài liệu này.

Nếu có mâu thuẫn giữa các tài liệu:

```
AGENTS.md
    ↓
RULES.md
    ↓
ARCHITECTURE.md
    ↓
PROJECT.md
    ↓
IMPLEMENTATION_PLAN.md
```

---

# 2. General Principles

## 2.1 Clean Architecture

Luôn áp dụng Clean Architecture.

Không được đưa Business Logic vào UI.

Luồng phụ thuộc:

```
UI
    ↓
Application
    ↓
Domain
    ↓
Infrastructure
```

Không được phụ thuộc ngược.

---

## 2.2 SOLID

Tất cả class phải tuân thủ SOLID.

Đặc biệt:

* Single Responsibility
* Dependency Inversion

---

## 2.3 Modular Design

Mỗi module chỉ có một nhiệm vụ.

Ví dụ:

Sai

```
media.py

- download
- render
- subtitle
- search
```

Đúng

```
media/

download.py

search.py

cache.py

validator.py
```

---

# 3. Folder Structure

```
backend/

frontend/

shared/

tests/

assets/

scripts/

configs/
```

Không tự ý tạo thư mục mới nếu chưa có lý do.

---

# 4. File Size Rules

Giới hạn khuyến nghị:

Python

≤ 500 dòng

TypeScript

≤ 500 dòng

Function

≤ 40 dòng

Class

≤ 300 dòng

Nếu vượt quá:

→ Tách module.

---

# 5. Naming Convention

Class

PascalCase

```
ProjectService
```

Function

camelCase

```
createProject()
```

Variable

camelCase

```
projectId
```

Constant

```
MAX_RENDER_QUEUE
```

File

snake_case

```
render_engine.py
```

---

# 6. Python Rules

Version

Python 3.12+

Formatter

Black

Linter

Ruff

Type Checking

Mypy

Không dùng

```
print()
```

Sử dụng

```
logging
```

---

# 7. TypeScript Rules

Strict Mode

Bật.

Không sử dụng

```
any
```

Nếu bắt buộc phải dùng:

Giải thích bằng comment.

---

# 8. React Rules

Chỉ sử dụng

Functional Component

Hook

Không dùng

Class Component.

State Management

Ưu tiên

Zustand

Không dùng Redux nếu chưa có nhu cầu rõ ràng.

---

# 9. FastAPI Rules

Router chỉ làm nhiệm vụ:

* Validate
* Parse Request
* Return Response

Không chứa Business Logic.

Luồng chuẩn:

```
Router

↓

Service

↓

Repository

↓

Database
```

---

# 10. Database Rules

Không viết SQL trong UI.

Không truy cập Database trực tiếp từ Service.

Bắt buộc dùng Repository Pattern.

---

# 11. Dependency Rules

Không import vòng.

Sai

```
A → B

B → A
```

Đúng

```
A

↓

Interface

↑

B
```

---

# 12. Logging Rules

Không dùng

```
print()
```

Bắt buộc dùng logging.

Mọi log gồm:

* Timestamp
* Level
* Module
* Message

Ví dụ:

```
INFO

MediaSearch

Downloaded 15 videos.
```

---

# 13. Error Handling

Không được

```
except:
    pass
```

Mọi Exception phải:

* Ghi log
* Có Error Code
* Có Message rõ ràng

Ví dụ:

```
MEDIA_DOWNLOAD_FAILED
```

---

# 14. Configuration

Không hard-code.

Mọi cấu hình nằm trong:

```
.env

configs/
```

Ví dụ:

```
OPENAI_API_KEY

PIXABAY_API_KEY

FFMPEG_PATH
```

---

# 15. API Rules

Response chuẩn

```json
{
  "success": true,
  "data": {},
  "message": "",
  "error": null
}
```

Lỗi

```json
{
  "success": false,
  "error": {
      "code":"MEDIA_NOT_FOUND",
      "message":"..."
  }
}
```

---

# 16. Testing Rules

Mọi Service phải có Unit Test.

Không merge nếu:

* Test Fail
* Lint Fail

---

# 17. Git Rules

Branch

```
feature/

bugfix/

hotfix/
```

Commit

```
feat:

fix:

refactor:

docs:

test:
```

Ví dụ

```
feat(media): add pixabay downloader
```

---

# 18. Performance Rules

Không load toàn bộ video vào RAM.

Ưu tiên:

* Streaming
* Chunk Processing
* Lazy Loading

---

# 19. Security Rules

Không commit:

* API Key
* Password
* Token
* Secret

Không ghi Secret vào log.

---

# 20. Documentation Rules

Mọi module mới phải cập nhật:

* README.md (nếu thay đổi cách sử dụng)
* ARCHITECTURE.md (nếu thay đổi kiến trúc)
* PROJECT.md (nếu thay đổi phạm vi)
* IMPLEMENTATION_PLAN.md (đánh dấu hoàn thành)

---

# 21. AI Coding Rules

Trước khi viết code:

1. Đọc AGENTS.md.
2. Đọc RULES.md.
3. Đọc ARCHITECTURE.md.
4. Đọc PROJECT.md.
5. Đọc IMPLEMENTATION_PLAN.md.

Chỉ triển khai đúng Task hiện tại.

Không tự ý thêm tính năng ngoài phạm vi.

---

# 22. Definition of Done

Một nhiệm vụ chỉ được coi là hoàn thành khi:

* Code chạy được.
* Không có lỗi lint.
* Unit Test pass.
* Không tạo nợ kỹ thuật mới.
* Cập nhật tài liệu liên quan.
* Đã tự rà soát mã nguồn.

---

# 23. Forbidden Actions

AI Coding Agent không được phép:

* Thay đổi kiến trúc khi chưa được yêu cầu.
* Đổi tên API công khai.
* Đổi schema cơ sở dữ liệu mà không có migration.
* Xóa module đang được sử dụng.
* Viết mã trùng lặp nếu có thể tái sử dụng.
* Thêm dependency mới mà không nêu lý do.

---

# 24. Guiding Principle

Ưu tiên:

1. Tính đúng đắn.
2. Khả năng bảo trì.
3. Khả năng mở rộng.
4. Hiệu năng.
5. Tốc độ phát triển.

Không hy sinh kiến trúc chỉ để hoàn thành nhanh một tính năng.

---

# End of Document
