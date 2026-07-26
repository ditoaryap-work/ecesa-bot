"""
Helper send/edit/delete message — semua interaksi Telegram lewat sini.
"""
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from core.config import CHAT_ID


async def send(bot: Bot, text: str, keyboard: InlineKeyboardMarkup | None = None) -> int | None:
    """Kirim pesan baru, return message_id."""
    try:
        msg = await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return msg.message_id
    except TelegramBadRequest as e:
        print(f"[messaging.send] error: {e}")
        return None


async def edit(bot: Bot, message_id: int | None, text: str, keyboard: InlineKeyboardMarkup | None = None) -> bool:
    if message_id is None:
        return False
    """Edit pesan yang sudah ada (main menu pattern — edit in place)."""
    try:
        await bot.edit_message_text(
            chat_id=CHAT_ID,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return True
    except TelegramBadRequest as e:
        # pesan sudah terlalu lama / tidak berubah — tidak perlu panic
        if "message is not modified" not in str(e).lower():
            print(f"[messaging.edit] error: {e}")
        return False


async def delete(bot: Bot, message_id: int | None) -> bool:
    if message_id is None:
        return False
    """Hapus pesan."""
    try:
        await bot.delete_message(chat_id=CHAT_ID, message_id=message_id)
        return True
    except TelegramBadRequest:
        return False


async def alert(bot: Bot, text: str) -> None:
    """Kirim alert push — tidak ada keyboard, tidak edit in place."""
    from core.db import is_muted
    muted, _ = await is_muted()
    if muted:
        return
    await send(bot, text)
