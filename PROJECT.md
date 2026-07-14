# PROJECT.md

Version: 1.0

Project: AI Video Pipeline Studio

Status: Active Development

---

# 1. Project Overview

## Purpose

AI Video Pipeline Studio là ứng dụng Desktop giúp tự động tạo video từ nội dung văn bản bằng AI.

Ứng dụng hướng đến việc thay thế quy trình dựng video thủ công bằng một pipeline tự động có khả năng:

* Phân tích nội dung.
* Tìm kiếm tư liệu minh họa.
* Ghép avatar.
* Đồng bộ phụ đề.
* Thêm nhạc nền.
* Xuất video hoàn chỉnh.

Mục tiêu là giúp một người vận hành có thể sản xuất hàng trăm hoặc hàng nghìn video mỗi tháng.

---

# 2. Vision

Xây dựng nền tảng tạo video AI có khả năng mở rộng lâu dài, tương tự một "AI Premiere Pro", nhưng tập trung vào tự động hóa thay vì chỉnh sửa thủ công.

---

# 3. Product Goals

## Business Goals

* Giảm ít nhất 90% thời gian dựng video.
* Chuẩn hóa quy trình sản xuất.
* Hỗ trợ sản xuất hàng loạt (Batch Processing).
* Hỗ trợ nhiều loại nội dung.

## Technical Goals

* Cross-platform (Windows, macOS, Linux).
* Kiến trúc mô-đun.
* Dễ mở rộng.
* Dễ bảo trì.
* Plugin-ready.

---

# 4. Target Users

## Primary

* YouTube Creators
* MCN / Network
* Media Agencies
* News Organizations

## Secondary

* Marketing Teams
* Educational Organizations
* Businesses
* Independent Creators

---

# 5. Supported Content Types

Version 1 tập trung vào:

* News
* Documentary
* History
* Education
* Podcast

Kids Content is outside the active Version 1 product scope.

Kiến trúc phải cho phép mở rộng sang các loại nội dung khác.

---

# 6. User Workflow

Quy trình chuẩn:

1. Tạo Project.
2. Nhập Script hoặc SRT.
3. Chọn giọng đọc hoặc Avatar.
4. AI phân tích nội dung và sinh từ khóa.
5. Tìm kiếm media minh họa.
6. Tải và lưu media.
7. Ghép video, phụ đề và nhạc nền.
8. Render.
9. Kiểm tra kết quả.
10. Xuất MP4.

---

# 7. MVP Scope

Phiên bản đầu tiên phải hoàn thành các chức năng sau:

## Project Management

* Tạo Project.
* Mở Project.
* Lưu Project.
* Đóng Project.

## Script Import

* TXT
* SRT

## AI Analysis

* Tách cảnh.
* Sinh từ khóa.
* Phân loại cảnh.

## Media Search

* Pixabay
* Pexels
* DVIDS Hub
* commons.wikimedia.org
* Local Library

## Media Management

* Download.
* Cache.
* Kiểm tra trùng lặp.

## Video Composer

* Scene Timeline Editor.

* Ghép Avatar.
* Ghép B-roll.
* Ghép Subtitle.
* Ghép Logo.
* Ghép Background Music.

## Rendering

* MP4 (H.264).
* 1080p.
* 30 FPS.

---

# 8. Out of Scope

Không triển khai trong MVP:

* Cloud Rendering.
* Multi-user Collaboration.
* Marketplace.
* Mobile Application.
* Live Streaming.

Các tính năng này sẽ được xem xét sau khi hoàn thành MVP.

---

# 9. Functional Requirements

## FR-001

Người dùng có thể tạo Project mới.

## FR-002

Người dùng có thể mở Project hiện có.

## FR-003

Ứng dụng tự động lưu Project.

## FR-004

Import Script dạng TXT.

## FR-005

Import Subtitle dạng SRT.

## FR-006

AI phân tích nội dung thành các Scene.

## FR-007

Sinh từ khóa cho từng Scene.

## FR-008

Tìm media theo từ khóa.

## FR-009

Tải media và lưu vào cache.

## FR-010

Ghép media theo đúng thời lượng Scene.

## FR-011

Ghép phụ đề.

## FR-012

Ghép avatar (nếu có).

## FR-013

Ghép nhạc nền.

## FR-014

Render thành video MP4.

## FR-015

Xuất file hoàn chỉnh.

---

# 10. Non-Functional Requirements

## Performance

* Khởi động ứng dụng dưới 5 giây.
* Render video 5 phút trong thời gian mục tiêu dưới 10 phút trên cấu hình khuyến nghị.

## Reliability

* Không làm hỏng Project khi xảy ra lỗi.
* Có thể tiếp tục từ bước gần nhất.

## Maintainability

* Clean Architecture.
* SOLID.
* Modular Design.

## Security

* Không lưu API Key trong mã nguồn.
* Không ghi Secret vào log.

---

# 11. Technology Stack

Frontend

* React
* TypeScript
* Tauri

Backend

* Python
* FastAPI

Video

* FFmpeg

AI

* Gemini
* OpenAI
* Ollama (tùy chọn)

Database

* SQLite

Cache

* File System

---

# 12. Project Structure

```text
AI-Video-Pipeline/
│
├── backend/
├── frontend/
├── shared/
├── tests/
├── assets/
├── docs/
│
├── AGENTS.md
├── RULES.md
├── PROJECT.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
└── BOOTSTRAP.md
```

---

# 13. Success Criteria

MVP được coi là hoàn thành khi:

* Tạo được Project.
* Import được TXT và SRT.
* AI sinh từ khóa cho từng Scene.
* Tìm và tải media tự động.
* Ghép video, avatar, phụ đề và nhạc nền.
* Render thành công MP4.
* Không có lỗi nghiêm trọng trong quy trình chuẩn.

---

# 14. Future Roadmap

## Version 1.1

* Timeline Preview.
* Render Queue.

## Version 2.0

* Plugin System.
* AI Layout Engine.
* AI Scene Selection.

## Version 3.0

* Cloud Rendering.
* Team Collaboration.
* Asset Marketplace.

---

# 15. Definition of Done

Một tính năng được coi là hoàn thành khi:

* Đáp ứng Functional Requirements.
* Không vi phạm RULES.md.
* Không phá vỡ kiến trúc.
* Có Unit Test phù hợp.
* Cập nhật tài liệu liên quan.
* Được đánh dấu hoàn thành trong IMPLEMENTATION_PLAN.md.

---

# 16. Guiding Principles

* Ưu tiên tính đúng đắn hơn tốc độ.
* Ưu tiên kiến trúc hơn giải pháp tạm thời.
* Ưu tiên mở rộng hơn tối ưu sớm.
* Mọi thay đổi phải giữ cho hệ thống đơn giản, nhất quán và dễ bảo trì.

# End of File
