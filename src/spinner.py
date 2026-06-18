"""Spinner dòng trạng thái cho terminal — dấu chấm nhảy + nhãn 'Claude đang làm gì'.

Mục đích: khi Claude đang chạy (chờ giữa các message), in một dòng động kiểu

    ⠹ Claude đang sửa map_view.dart .

với ký tự quay + dấu chấm nhảy, để người dùng biết tool vẫn còn sống. Khi có
bước mới thì đổi nhãn (set_label); khi xong thì stop() và xóa dòng spinner.

Spinner chạy ở một luồng nền riêng và chỉ bật khi stdout là TTY thật (terminal),
nên khi chạy qua pipe/redirect (test, CI) nó tự tắt — log không bị bẩn ký tự \r.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time

# Các khung quay (braille) — mượt và gọn trên đa số terminal hiện đại.
_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Spinner:
    def __init__(self, label: str = "Claude đang làm việc", interval: float = 0.12):
        # Nhãn hiện tại (đổi runtime qua set_label) — mô tả Claude đang làm gì.
        self._label = label
        # Khoảng thời gian giữa 2 khung (giây).
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Chỉ bật spinner khi xuất ra terminal thật; tránh làm bẩn log khi pipe.
        self._enabled = bool(getattr(sys.stdout, "isatty", lambda: False)())
        self._lock = threading.Lock()
        # Độ dài dòng đã in lần trước, để xóa sạch khi cập nhật/đổi nhãn.
        self._last_len = 0

    def set_label(self, label: str) -> None:
        """Đổi nội dung 'đang làm gì' mà spinner đang hiển thị."""
        with self._lock:
            self._label = label

    def _render(self, frame: str) -> None:
        # Số dấu chấm nhảy theo thời gian (0..3) tạo cảm giác 'đang gõ'.
        dots = "." * (int(time.monotonic() * 2) % 4)
        with self._lock:
            text = f"\r{frame} {self._label} {dots}"
        # Đệm khoảng trắng để xóa phần dư của dòng cũ (nhãn ngắn hơn lần trước).
        pad = max(0, self._last_len - len(text))
        sys.stdout.write(text + " " * pad)
        sys.stdout.flush()
        self._last_len = len(text)

    def _spin(self) -> None:
        for frame in itertools.cycle(_FRAMES):
            if self._stop.is_set():
                break
            self._render(frame)
            time.sleep(self._interval)

    def _clear_line(self) -> None:
        # Xóa hẳn dòng spinner (ghi đè bằng khoảng trắng rồi về đầu dòng).
        if self._last_len:
            sys.stdout.write("\r" + " " * self._last_len + "\r")
            sys.stdout.flush()
            self._last_len = 0

    def start(self) -> "Spinner":
        if not self._enabled:
            return self
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if not self._enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._clear_line()

    def __enter__(self) -> "Spinner":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
