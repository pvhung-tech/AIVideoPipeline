# BOOTSTRAP.md

Version: 1.0

Project: AI Video Pipeline Studio

Purpose: AI Project Bootstrap Guide

---

# Welcome

Bạn đang tham gia phát triển **AI Video Pipeline Studio**.

Đây là một dự án phần mềm thương mại, hướng tới xây dựng một ứng dụng Desktop tự động tạo video bằng AI.

Mục tiêu của bạn không phải là viết mã nhanh nhất, mà là xây dựng một hệ thống ổn định, có thể mở rộng và dễ bảo trì.

---

# Before Writing Any Code

Đọc các tài liệu theo đúng thứ tự sau:

1. AGENTS.md
2. RULES.md
3. PROJECT.md
4. ARCHITECTURE.md
5. IMPLEMENTATION_PLAN.md

Không bỏ qua bước này.

Nếu có xung đột giữa các tài liệu, ưu tiên theo đúng thứ tự trên.

---

# Project Goal

Xây dựng ứng dụng Desktop cho phép người dùng:

* Tạo Project.
* Nhập Script hoặc Subtitle.
* AI phân tích nội dung.
* Tìm kiếm tư liệu minh họa.
* Ghép Avatar.
* Ghép phụ đề.
* Thêm nhạc nền.
* Render video MP4.

Ứng dụng phải hướng tới khả năng sản xuất video hàng loạt.

---

# Repository Layout

```text
AI-Video-Pipeline/
│
├── AGENTS.md
├── RULES.md
├── PROJECT.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── BOOTSTRAP.md
├── README.md
│
├── backend/
│   ├── app/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── shared/
├── assets/
├── scripts/
├── configs/
└── docs/
```

---

# Phase 0 Checklist

Hoàn thành các công việc sau trước khi phát triển tính năng:

## Repository

* Khởi tạo Git.
* Tạo cấu trúc thư mục.
* Thiết lập `.gitignore`.

## Backend

* Khởi tạo FastAPI.
* Tạo cấu trúc Clean Architecture.
* Cấu hình Logging.
* Thiết lập Dependency Injection.

## Frontend

* Khởi tạo React + TypeScript + Tauri.
* Thiết lập Routing.
* Thiết lập State Management.

## Quality

* Cấu hình Formatter.
* Cấu hình Linter.
* Thiết lập Unit Test.
* Thiết lập CI cơ bản.

---

# Coding Workflow

Đối với mỗi tính năng:

1. Xác nhận Feature thuộc Phase hiện tại.
2. Kiểm tra tài liệu liên quan.
3. Thiết kế Interface.
4. Viết Unit Test.
5. Viết mã nguồn.
6. Chạy kiểm thử.
7. Cập nhật tài liệu nếu cần.

Không bỏ qua bước kiểm thử.

---

# Architectural Guardrails

Không được:

* Thay đổi cấu trúc thư mục.
* Đổi tên Public API.
* Thay đổi Database Schema mà không có Migration.
* Thêm Dependency mới nếu chưa đánh giá.
* Trộn Business Logic vào UI.

Mọi thay đổi lớn phải phù hợp với ARCHITECTURE.md.

---

# Communication Format

Sau mỗi nhiệm vụ, báo cáo theo mẫu:

## Summary

Mô tả ngắn gọn những gì đã thực hiện.

## Files Changed

Liệt kê các file đã tạo hoặc sửa.

## Tests

Các bài kiểm thử đã chạy.

## Risks

Các rủi ro còn tồn tại.

## Next Step

Đề xuất bước tiếp theo theo IMPLEMENTATION_PLAN.md.

---

# Build Quality Checklist

Trước khi kết thúc một nhiệm vụ:

* Build thành công.
* Không có lỗi lint.
* Unit Test đạt yêu cầu.
* Không tạo phụ thuộc vòng.
* Không có TODO quan trọng chưa xử lý.
* Tài liệu được cập nhật nếu cần.

---

# Definition of Success

Repository được coi là sẵn sàng cho Sprint tiếp theo khi:

* Kiến trúc không bị vi phạm.
* Tính năng mới hoạt động đúng.
* Không làm hỏng chức năng hiện có.
* Tài liệu luôn phản ánh đúng trạng thái mã nguồn.

---

# AI Agent Responsibilities

AI Coding Agent phải:

* Tuân thủ AGENTS.md.
* Tuân thủ RULES.md.
* Không vượt phạm vi Phase hiện tại.
* Ưu tiên giải pháp đơn giản và dễ bảo trì.
* Ghi nhận các đề xuất cải tiến thay vì tự ý triển khai.

---

# Bootstrap Complete

Nếu tất cả các bước trên đã hoàn thành, AI có thể bắt đầu triển khai Phase 0 trong IMPLEMENTATION_PLAN.md.

Mọi phát triển tiếp theo phải bám sát tài liệu dự án và cập nhật tài liệu khi có thay đổi.

# End of File
