"""Dispatcher backends that drive the coder. The orchestrator core is backend-
agnostic; only this package knows about the SDK vs the GitHub Action."""

from .base import Dispatcher, build_prompt
from .sdk_dispatcher import SdkDispatcher


def get_dispatcher(backend: str, **kwargs) -> Dispatcher:
    if backend == "sdk":
        return SdkDispatcher(**kwargs)
    if backend == "action":
        from .action_dispatcher import ActionDispatcher
        return ActionDispatcher(**kwargs)
    raise ValueError(f"Unknown dispatch backend: {backend!r} (expected sdk|action)")


__all__ = ["Dispatcher", "SdkDispatcher", "get_dispatcher", "build_prompt"]
