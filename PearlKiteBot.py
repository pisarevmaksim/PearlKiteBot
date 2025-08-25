# -*- coding: utf-8 -*-
# bot.py
import os
import re
from pathlib import Path
from datetime import datetime
from telegram import Update, User
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

EVENTS_PATH = Path("dbs") / "events"

# Parse helpers: supports Cyrillic key "кайт" + from/to (quotes supported)
_PARAM_RE = re.compile(
    r'''(?:^|\s)(кайт|from|to)\s*=\s*(?:"([^"]+)"|'([^']+)'|([^\s]+))''',
    re.IGNORECASE,
)

def parse_params(s: str) -> dict:
    """Parse кайт=..., from=..., to=... (supports quotes)."""
    params = {}
    for key, v1, v2, v3 in _PARAM_RE.findall(s or ""):
        val = (v1 or v2 or v3 or "").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        params[key.lower()] = val
    return params

def ensure_events_file() -> None:
    """Ensure dbs/events file exists."""
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EVENTS_PATH.exists():
        EVENTS_PATH.touch()

def real_user_name(u: User | None) -> str:
    """Best-effort real display name from Telegram profile."""
    if not u:
        return ""
    name = (getattr(u, "full_name", None) or "").strip()
    if not name:
        parts = [getattr(u, "first_name", "") or "", getattr(u, "last_name", "") or ""]
        name = " ".join(p for p in parts if p).strip()
    if not name and getattr(u, "username", None):
        name = f"@{u.username}"
    if not name:
        name = str(u.id)
    return name.replace("\n", " ").replace("\r", " ").replace("\t", " ")

def tail_lines(path: Path, n: int) -> list[str]:
    """Return last n lines of a UTF-8 text file without loading full file."""
    if not path.exists():
        return []
    n = max(1, n)
    chunk = 8192
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        buf = b""
        pos = f.tell()
        lines = []
        while pos > 0 and (len(lines) <= n):
            read = chunk if pos >= chunk else pos
            pos -= read
            f.seek(pos)
            buf = f.read(read) + buf
            lines = buf.splitlines()
        tail = lines[-n:]
        return [b.decode("utf-8", errors="replace") for b in tail]

# ---------- commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    text = (
        "Команды:\n"
        "/go_kite кайт=\"core 13.5\" from=10:00 to=12:00 — добавить запись (имя из профиля)\n"
        "/иду_кататься кайт=\"core 13.5\" from=10:00 to=12:00 — то же (русская форма)\n"
        "/list [N] — показать последние N (по умолчанию 10)"
    )
    if msg:
        await msg.reply_text(text)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

async def ride_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Use effective_message to support channels, groups, captions
    msg = update.effective_message
    chat = update.effective_chat

    full_text = ""
    if msg and msg.text:
        full_text = msg.text
    elif msg and msg.caption:
        full_text = msg.caption

    raw = full_text.partition(" ")[2] if full_text else ""
    p = parse_params(raw)

    missing = [k for k in ("кайт", "from", "to") if not p.get(k)]
    if missing:
        help_text = (
            "Формат:\n"
            "/go_kite кайт=\"core 13.5\" from=10:00 to=12:00\n"
            "Можно в кавычках: /go_kite кайт=\"core 13.51\" from=\"11:01\" to=\"12:00\"\n"
            f"Не хватает: {', '.join(missing)}"
        )
        if msg:
            await msg.reply_text(help_text)
        else:
            await context.bot.send_message(chat_id=chat.id, text=help_text)
        return

    ensure_events_file()
    ts = datetime.now().isoformat(timespec="seconds")
    chat_id = chat.id if chat else ""
    user_id = update.effective_user.id if update.effective_user else ""
    name = real_user_name(update.effective_user)
    kite = p["кайт"]

    # TSV: ts\tchat_id\tuser_id\tname\tкайт\tfrom\tto
    line = f"{ts}\t{chat_id}\t{user_id}\t{name}\t{kite}\t{p['from']}\t{p['to']}"
    with EVENTS_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")

    ok = f"Сохранено: {name} | [{kite}] | {p['from']} → {p['to']}\n→ {EVENTS_PATH}"
    if msg:
        await msg.reply_text(ok)
    else:
        await context.bot.send_message(chat_id=chat_id, text=ok)

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    arg = ""
    if msg and msg.text:
        parts = msg.text.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
    elif msg and msg.caption:
        parts = msg.caption.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

    try:
        n = int(arg) if arg else 10
    except ValueError:
        n = 10
    n = max(1, min(n, 50))

    lines = tail_lines(EVENTS_PATH, n)
    if not lines:
        txt = "Пока нет записей."
        if msg:
            await msg.reply_text(txt)
        else:
            await context.bot.send_message(chat_id=chat.id, text=txt)
        return

    items = []
    for ln in lines:
        parts = ln.rstrip("\n").split("\t")
        ts   = parts[0] if len(parts) > 0 else ""
        name = parts[3] if len(parts) > 3 else ""
        kite = parts[4] if len(parts) > 4 else ""
        frm  = parts[5] if len(parts) > 5 else ""
        to   = parts[6] if len(parts) > 6 else ""
        items.append(f"{ts} | {name} | [{kite}] | {frm} → {to}")

    out = "Последние записи:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(items))
    if msg:
        await msg.reply_text(out)
    else:
        await context.bot.send_message(chat_id=chat.id, text=out)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg and msg.text:
        await msg.reply_text(msg.text)

def main():
    token = os.getenv("BOT_PearlKiteBot") or os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_PearlKiteBot (or BOT_TOKEN) env var first")
    app = Application.builder().token(token).build()

    # Canonical command
    app.add_handler(CommandHandler("go_kite", ride_cmd))
    # Optional aliases for compatibility
    app.add_handler(CommandHandler("idu_katatsya", ride_cmd))
    app.add_handler(MessageHandler(filters.Regex(r"^/\s*иду_кататься(?:@\w+)?(?:\s|$)"), ride_cmd))

    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()

if __name__ == "__main__":
    main()
