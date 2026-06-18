# AI Dev Orchestrator — Documentation

Tài liệu kỹ thuật cho **AI Dev Orchestrator** (BotCoder): bot Python điều phối
Claude tự động code theo plan qua GitHub Issues / PRs / Actions CI.

> Trạng thái hiện tại: **MVP v0.1.1 hoàn thành**, đã chạy end-to-end thật trên
> repo sandbox (`khuongvh1-dotcom/ai-sandbox`). 45 unit test pass.

## Mục lục

| # | Tài liệu | Nội dung |
|---|----------|----------|
| ⭐ | [USAGE (HDSD tiếng Việt)](USAGE.md) | **Bắt đầu ở đây**: trỏ bot vào repo, viết plan, chạy, duyệt PR |
| 01 | [Architecture](01-architecture.md) | Triết lý, sơ đồ thành phần, luồng orchestration, state machine |
| 02 | [Modules](02-modules.md) | Chi tiết từng module trong `src/`: trách nhiệm, hàm chính, luồng gọi |
| 03 | [Configuration](03-configuration.md) | Project profile, rules.yaml, plan format, auth (subscription/API key) |
| 04 | [State & Data](04-state-and-data.md) | `state.json` schema, models, audit trail trong `runs/` |
| 05 | [Development](05-development.md) | Cài đặt, chạy, test, các lỗi đã gặp & cách xử lý |
| 06 | [Roadmap & Extension Points](06-roadmap.md) | v0.2/v0.3/v0.4 và các điểm cắm để nâng cấp |
| 07 | [Decision Log](07-decisions.md) | Nhật ký quyết định kiến trúc (vì sao chọn thế này) |

## Đọc nhanh theo nhu cầu

- **Muốn dùng ngay (trỏ repo, chạy plan)** → [USAGE](USAGE.md) ⭐
- **Muốn hiểu hệ thống làm gì** → [01-architecture](01-architecture.md)
- **Muốn sửa/thêm code** → [02-modules](02-modules.md) + [06-roadmap](06-roadmap.md)
- **Muốn chạy thử** → [05-development](05-development.md)
- **Muốn đổi cấu hình / thêm repo mới** → [03-configuration](03-configuration.md)
- **Muốn hiểu vì sao thiết kế thế này** → [07-decisions](07-decisions.md)

## Tóm tắt một câu

Đọc `plans/plan.md` → tách task → phân loại rủi ro → tạo GitHub Issue → Claude
(qua `claude-agent-sdk`) sửa code trong workspace cô lập → quét path/secret →
commit + tạo PR → đọc CI → fix-loop nếu fail → **dừng ở human review** (không
auto-merge). State lưu `state.json` (atomic, resumable), audit ghi `runs/`.
