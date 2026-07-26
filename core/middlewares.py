"""
Middlewares:
1. AuthMiddleware   — tolak semua request dari chat_id selain CHAT_ID
2. ThrottleMiddleware — anti-spam: 1 request per user per detik
3. AutoDeleteMiddleware — hapus pesan command user otomatis
"""
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from core.config import CHAT_ID


class AuthMiddleware(BaseMiddleware):
    """Hanya terima update dari CHAT_ID yang terdaftar."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id if event.message else None

        if chat_id != CHAT_ID:
            # Diam saja — jangan kasih info apapun ke orang lain
            return
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Batasi 1 request per detik per user untuk callback query."""

    def __init__(self) -> None:
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            uid = event.from_user.id
            now = time.monotonic()
            if now - self._last.get(uid, 0) < 1.0:
                await event.answer("⏳ Terlalu cepat, tunggu sebentar.")
                return
            self._last[uid] = now
        return await handler(event, data)


class AutoDeleteMiddleware(BaseMiddleware):
    """Hapus pesan command user (misal /start) supaya chat tetap bersih."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            try:
                await event.delete()
            except Exception:
                pass
        return result
