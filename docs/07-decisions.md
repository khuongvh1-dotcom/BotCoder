# 07 — Decision Log

Nhật ký quyết định kiến trúc (ADR rút gọn). Mỗi mục: **quyết định**, **vì sao**,
**đánh đổi**. Đọc để hiểu *tại sao* code như hiện tại trước khi đổi.

---

## D1 — Bot điều phối, KHÔNG tự viết coding agent
**Quyết định**: Bot chỉ orchestrate; việc sửa code giao cho Claude qua `claude-agent-sdk`.
**Vì sao**: Coding agent đã có sẵn và mạnh; giá trị nằm ở quy trình (queue, gate, CI, audit).
**Đánh đổi**: Phụ thuộc SDK/CLI Anthropic.

## D2 — Backend SDK headless cho MVP (sau interface Dispatcher)
**Quyết định**: MVP dùng `SdkDispatcher` (local, đồng bộ). GitHub Action backend để stub.
**Vì sao**: Bot chạy local cần **kiểm soát đồng bộ** vòng dispatch→PR→CI→fix; `query()` block tới khi xong, workspace local dễ debug, rẻ. GitHub Action là bất đồng bộ (hợp khi bot sống trong Actions — v0.2).
**Đánh đổi**: Phải tự lo git/PR (đã làm trong `git_ops`). Đổi backend dễ nhờ interface.

## D3 — Auth qua subscription, không bắt buộc API key
**Quyết định**: Hỗ trợ cả 3: ANTHROPIC_API_KEY > CLAUDE_CODE_OAUTH_TOKEN > login CLI sẵn có.
**Vì sao**: Người dùng dùng **gói Pro/Max**, không API key. Thực tế đã test: SDK **kế thừa login Claude Code CLI** → không cần env var nào.
**Đánh đổi**: Usage tính vào giới hạn gói (có thể throttle khi song song). ToS cho automation headless chưa rõ — cần kiểm tra nếu scale lớn.

## D4 — Classifier rule-based ở MVP
**Quyết định**: `task_classifier` dùng keyword/path, không LLM. Ưu tiên Risk khai trong plan, nhưng upgrade declared-safe nếu chạm high-risk.
**Vì sao**: Rẻ, tất định, dễ test; đủ cho MVP. LLM classifier để v0.2.
**Đánh đổi**: Kém tinh tế hơn LLM với task mơ hồ → rơi vào `medium_risk`.

## D5 — Không auto-merge; dừng ở HUMAN_REVIEW
**Quyết định**: MVP luôn dừng ở `HUMAN_REVIEW`; `merge.auto_merge=false`.
**Vì sao**: An toàn cho công cụ dùng nội bộ nhiều repo; con người duyệt vùng rủi ro.
**Đánh đổi**: Không hoàn toàn tự động — đúng chủ đích (AI-first ≠ AI-only).

## D6 — Security gate trước commit (path_guard + secret_scanner)
**Quyết định**: Quét path + secret trên file thay đổi **trước** khi commit; vi phạm → BLOCKED.
**Vì sao**: Bot chạy code tự động → nguy cơ sửa nhầm vùng cấm / lộ secret là thật. Cần cho đa repo.
**Đánh đổi**: Có thể chặn nhầm (false positive) → cần lọc artifact (`__pycache__`) và pattern đủ chính xác.

## D7 — Enum/config/format khai đủ từ đầu (forward-compatible)
**Quyết định**: `TaskStatus`, `Task` (parallel/depends_on/conflict_group/agent_type), `rules.execution/locks/plans`, state `version:2` khai đủ ngay; MVP dùng một phần.
**Vì sao**: Tránh đập đi làm lại khi lên song song (v0.3) / multi-agent (v0.4) / nhiều plan (v0.2).
**Đánh đổi**: Có field/stub "chưa dùng" — chấp nhận để ổn định lâu dài.

## D8 — state.json (JSON atomic), không DB
**Quyết định**: Lưu state bằng 1 file JSON, ghi atomic.
**Vì sao**: MVP nhỏ; đủ cho idempotency + resume; không thêm phụ thuộc.
**Đánh đổi**: Không hợp khi số task rất lớn / truy vấn phức tạp → chuyển SQLite sau (giữ interface).

## D9 — Workspace cô lập per-task
**Quyết định**: Mỗi task clone riêng `workspace/task-NNN/`.
**Vì sao**: Không nhiễu file giữa task; nền cho song song v0.3.
**Đánh đổi**: Tốn disk/thời gian clone hơn dùng chung — chấp nhận để an toàn.

## D10 — git/gh CLI qua subprocess, không GitPython
**Quyết định**: `git_ops` gọi `git` + `gh` qua subprocess.
**Vì sao**: `gh pr create` một dòng, auth sẵn từ `gh`; ít phụ thuộc.
**Đánh đổi**: Phụ thuộc CLI cài sẵn (đã có). PyGithub vẫn dùng cho API đọc (issue/checks).

## D11 — Idempotency dựa state.json là chính, marker là phụ
**Quyết định**: Chống tạo trùng issue/PR chủ yếu bằng `state.json`; marker issue + `find_pr_for_branch` là lớp phụ.
**Vì sao**: List API GitHub có **độ trễ index** → marker không đảm bảo ở lần tạo liên tiếp. State local thì tức thời.
**Đánh đổi**: Mất `state.json` + chạy lại ngay có thể tạo trùng (hiếm) — chấp nhận.

## D12 — Dispatcher không raise trong async generator
**Quyết định**: `SdkDispatcher._run` thu lỗi rồi return `(summary, error)`, không raise trong `async for`.
**Vì sao**: Raise giữa generator gây `aclose(): async generator already running`. Ngoài ra coder có thể đã sửa file dù result báo lỗi (vd "max turns") — không nên vứt bỏ.
**Đánh đổi**: `main` phải tự quyết: FAILED chỉ khi error **và** không có file đổi.
