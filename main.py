"""VEX — Discord-бот для управления Rust-кланом. Весь проект в ОДНОМ файле.

Запуск:  python main.py
Переменные окружения: DISCORD_TOKEN (обязательно), GUILD_ID, DATA_DIR, TIMEZONE.
Библиотека discord.py при первом запуске установится автоматически.

Устройство файла: ниже в словаре _SOURCES лежит исходный код модулей бота (обычный текст,
его можно править прямо здесь — цвета, типы тикетов и домены в блоке vex/config.py).
В самом конце файла — точка входа.
"""
import importlib.abc
import importlib.util
import logging
import subprocess
import sys


def _ensure_dependencies():
    try:
        import discord  # noqa: F401
        return
    except ImportError:
        pass
    print("Устанавливаю discord.py (только при первом запуске)...", flush=True)
    base = [sys.executable, "-m", "pip", "install", "--quiet", "discord.py>=2.4,<3"]
    for extra in ([], ["--break-system-packages"], ["--user"]):
        if subprocess.call(base + extra) == 0:
            break
    else:
        raise SystemExit(
            "Не удалось установить discord.py автоматически. "
            "Добавь на хостинг файл requirements.txt со строкой: discord.py>=2.4,<3"
        )
    importlib.invalidate_caches()


_ensure_dependencies()

_PACKAGES = ['vex', 'vex.cogs']

_SOURCES = {
    'vex': r'''"""VEX — Discord-бот для управления клан-сообществом в Rust."""
''',
    'vex.config': r'''"""Настройки и константы VEX. Всё, что хочется поменять «под себя», — здесь."""
import json
import os
from pathlib import Path

try:  # .env нужен только для локального запуска; на хостинге переменные задаются в панели
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Окружение -------------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = _int("GUILD_ID")  # ID сервера: команды появятся сразу. Пусто = глобальная синхронизация (до часа)
# Здесь лежит база. На bothost постоянные данные хранятся в /app/data — он выбирается сам, если существует.
DATA_DIR = Path(os.getenv("DATA_DIR") or ("/app/data" if Path("/app").is_dir() else "./data"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# --- Сайт-панель -------------------------------------------------------------
# Сайт включается, когда хостинг передаёт порт (переменная PORT, появляется вместе с опцией «Использовать домен»).
WEB_PORT = _int("PORT") or _int("WEB_PORT")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()  # Developer Portal -> OAuth2 -> Client Secret
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "").strip()  # необязательно: по умолчанию берётся ID бота
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")  # необязательно: https://адрес-твоего-бота

# --- Оформление ------------------------------------------------------------
BRAND = "VEX"
FOOTER = "VEX • Clan Control"
COLOR_MAIN = 0x8B5CF6  # фиолетовый
COLOR_DARK = 0x6D28D9  # тёмно-фиолетовый (закрытые события)
COLOR_OK = 0x22C55E
COLOR_ERR = 0xEF4444
COLOR_WARN = 0xF59E0B

# --- Тикеты: типы обращений (меню на панели). Меняй как угодно, до 25 штук. ---
TICKET_TYPES = [
    {"key": "join", "slug": "join", "label": "Вступление в клан", "emoji": "🛡️",
     "description": "Подать заявку на вступление"},
    {"key": "question", "slug": "question", "label": "Вопрос", "emoji": "❓",
     "description": "Задать вопрос администрации"},
    {"key": "report", "slug": "report", "label": "Жалоба", "emoji": "🚨",
     "description": "Жалоба на игрока или участника клана"},
    {"key": "appeal", "slug": "appeal", "label": "Обжалование наказания", "emoji": "⚖️",
     "description": "Оспорить мут, бан или предупреждение"},
    {"key": "other", "slug": "other", "label": "Другое", "emoji": "📨",
     "description": "Всё остальное"},
]

def load_ticket_types(raw):
    """Типы тикетов сервера: из настроек (JSON, их меняют на сайте) или значения по умолчанию."""
    if raw:
        try:
            out = []
            for item in json.loads(raw)[:25]:
                out.append({
                    "key": str(item["key"]),
                    "slug": str(item.get("slug") or "ticket")[:20],
                    "label": str(item["label"])[:100],
                    "emoji": str(item.get("emoji") or ""),
                    "description": str(item.get("description") or "")[:100],
                })
            if out:
                return out
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    return [dict(t) for t in TICKET_TYPES]


# --- Автомодерация: домены, которые разрешены всегда ------------------------
DEFAULT_ALLOWED_DOMAINS = (
    "tenor.com",
    "giphy.com",
    "cdn.discordapp.com",
    "media.discordapp.net",
)

# --- Ключи команд для системы доступа (/perms) -------------------------------
COMMAND_KEYS = {
    "ticket_admin": "Панель и настройка тикетов",
    "ticket_manage": "Работа с тикетами (закрыть, добавить, взять)",
    "role": "Выдача и снятие ролей (/role add, /role remove)",
    "role_admin": "Список ролей, которые можно выдавать (/role allow)",
    "wipe": "Вайп-реакты и /noreact",
    "automod": "Настройка автомодерации",
    "autorole": "Настройка авто-выдачи ролей",
    "say": "Сообщения от имени бота (/say)",
}
''',
    'vex.embeds': r'''"""Единый стиль эмбедов VEX."""
import discord

from . import config


def make(title=None, description=None, color=config.COLOR_MAIN, footer=True):
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=config.FOOTER)
    return embed


def ok(text, title="Готово"):
    return make(f"✅ {title}", text, config.COLOR_OK)


def err(text, title="Ошибка"):
    return make(f"⛔ {title}", text, config.COLOR_ERR)


def warn(text, title="Внимание"):
    return make(f"⚠️ {title}", text, config.COLOR_WARN)


def info(text, title=None):
    return make(title, text)
''',
    'vex.db': r'''"""Небольшая обёртка над SQLite (стандартная библиотека, без доп. зависимостей)."""
import asyncio
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER NOT NULL,
    key      TEXT    NOT NULL,
    value    TEXT    NOT NULL,
    PRIMARY KEY (guild_id, key)
);

-- Универсальное хранилище «ролей и каналов по назначению»:
--   cmd:<ключ>            роли с доступом к команде
--   ticket_support        роли поддержки тикетов
--   manageable            роли, которые модераторы могут выдавать
--   autorole_member       роли для новых участников
--   autorole_bot          роли для новых ботов
--   automod_bypass        роли, которых не трогает автомодерация
--   automod_ignore_channel каналы, где автомодерация выключена
CREATE TABLE IF NOT EXISTS guild_targets (
    guild_id  INTEGER NOT NULL,
    kind      TEXT    NOT NULL,
    target_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, kind, target_id)
);

CREATE TABLE IF NOT EXISTS allowed_domains (
    guild_id INTEGER NOT NULL,
    domain   TEXT    NOT NULL,
    PRIMARY KEY (guild_id, domain)
);

CREATE TABLE IF NOT EXISTS automod_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    link       TEXT    NOT NULL,
    ts         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    channel_id INTEGER NOT NULL DEFAULT 0,
    user_id    INTEGER NOT NULL,
    type       TEXT    NOT NULL,
    reason     TEXT    NOT NULL DEFAULT '',
    claimed_by INTEGER,
    status     TEXT    NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL,
    closed_at  INTEGER
);

CREATE TABLE IF NOT EXISTS wipe_events (
    message_id   INTEGER PRIMARY KEY,
    guild_id     INTEGER NOT NULL,
    channel_id   INTEGER NOT NULL,
    creator_id   INTEGER NOT NULL,
    creator_name TEXT    NOT NULL,
    title        TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    server       TEXT,
    ts           INTEGER NOT NULL,
    ask_reason   INTEGER NOT NULL DEFAULT 0,
    ping_role_id INTEGER,
    closed       INTEGER NOT NULL DEFAULT 0,
    reminded     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wipe_responses (
    message_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    status     TEXT    NOT NULL,
    reason     TEXT,
    PRIMARY KEY (message_id, user_id)
);
"""


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn = None

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # --- низкий уровень (выполняется в потоке, чтобы не блокировать бота) ----
    def _execute(self, sql, params):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.rowcount, cur.lastrowid

    def _fetch(self, sql, params, one):
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone() if one else cur.fetchall()

    def _replace(self, table, guild_id, column, kind, values):
        with self._lock:
            if table == "guild_targets":
                self._conn.execute("DELETE FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind))
                self._conn.executemany(
                    "INSERT OR IGNORE INTO guild_targets(guild_id, kind, target_id) VALUES(?,?,?)",
                    [(guild_id, kind, v) for v in values],
                )
            else:
                self._conn.execute("DELETE FROM allowed_domains WHERE guild_id=?", (guild_id,))
                self._conn.executemany(
                    "INSERT OR IGNORE INTO allowed_domains(guild_id, domain) VALUES(?,?)",
                    [(guild_id, v) for v in values],
                )
            self._conn.commit()

    async def set_targets(self, guild_id, kind, ids):
        """Полностью заменяет список ролей/каналов этого назначения."""
        await asyncio.to_thread(self._replace, "guild_targets", guild_id, None, kind, list(ids))

    async def set_domains(self, guild_id, domains):
        """Полностью заменяет список разрешённых доменов сервера."""
        await asyncio.to_thread(self._replace, "allowed_domains", guild_id, None, None, list(domains))

    async def execute(self, sql, params=()):
        """Выполняет запрос, возвращает число затронутых строк."""
        rowcount, _ = await asyncio.to_thread(self._execute, sql, tuple(params))
        return rowcount

    async def insert(self, sql, params=()):
        """Выполняет INSERT, возвращает id новой строки."""
        _, last_id = await asyncio.to_thread(self._execute, sql, tuple(params))
        return last_id

    async def fetchone(self, sql, params=()):
        return await asyncio.to_thread(self._fetch, sql, tuple(params), True)

    async def fetchall(self, sql, params=()):
        return await asyncio.to_thread(self._fetch, sql, tuple(params), False)

    # --- настройки сервера ---------------------------------------------------
    async def get_setting(self, guild_id, key, default=None):
        row = await self.fetchone(
            "SELECT value FROM settings WHERE guild_id=? AND key=?", (guild_id, key)
        )
        return row["value"] if row else default

    async def set_setting(self, guild_id, key, value):
        await self.execute(
            "INSERT INTO settings(guild_id, key, value) VALUES(?,?,?) "
            "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
            (guild_id, key, str(value)),
        )

    async def del_setting(self, guild_id, key):
        await self.execute("DELETE FROM settings WHERE guild_id=? AND key=?", (guild_id, key))

    # --- роли и каналы по назначению ----------------------------------------
    async def get_targets(self, guild_id, kind):
        rows = await self.fetchall(
            "SELECT target_id FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind)
        )
        return [r["target_id"] for r in rows]

    async def add_target(self, guild_id, kind, target_id):
        """True, если запись добавлена (раньше её не было)."""
        changed = await self.execute(
            "INSERT OR IGNORE INTO guild_targets(guild_id, kind, target_id) VALUES(?,?,?)",
            (guild_id, kind, target_id),
        )
        return changed > 0

    async def remove_target(self, guild_id, kind, target_id):
        """True, если запись была и удалена."""
        changed = await self.execute(
            "DELETE FROM guild_targets WHERE guild_id=? AND kind=? AND target_id=?",
            (guild_id, kind, target_id),
        )
        return changed > 0

    async def clear_targets(self, guild_id, kind):
        await self.execute("DELETE FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind))
''',
    'vex.checks': r'''"""Система доступа: какая роль может пользоваться какой командой.

Правило простое:
  * администраторы и владелец сервера могут всё;
  * остальным нужна роль, которой выдан доступ командой /perms grant;
  * пока доступ никому не выдан, команда доступна только администраторам.
"""
import discord
from discord import app_commands


class NoAccess(app_commands.CheckFailure):
    def __init__(self, key=None, admin_only=False):
        self.key = key
        self.admin_only = admin_only
        super().__init__("Нет доступа к команде")


def is_admin(member):
    return member.guild_permissions.administrator or member.guild.owner_id == member.id


async def member_has_access(bot, member, key):
    if not isinstance(member, discord.Member):
        return False
    if is_admin(member):
        return True
    allowed = await bot.db.get_targets(member.guild.id, f"cmd:{key}")
    return any(role.id in allowed for role in member.roles)


def access(key):
    """Декоратор слеш-команды: доступ по ролям из /perms."""

    async def predicate(interaction):
        if await member_has_access(interaction.client, interaction.user, key):
            return True
        raise NoAccess(key)

    return app_commands.check(predicate)


def admin_only():
    """Декоратор слеш-команды: только администраторы (для /perms и /config)."""

    async def predicate(interaction):
        user = interaction.user
        if isinstance(user, discord.Member) and is_admin(user):
            return True
        raise NoAccess(admin_only=True)

    return app_commands.check(predicate)
''',
    'vex.bot': r'''"""Ядро бота: интенты, загрузка модулей, обработка ошибок команд, логирование на сервер."""
import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import config, embeds
from .checks import NoAccess
from .db import Database
from .web import start_web

log = logging.getLogger("vex")

EXTENSIONS = (
    "vex.cogs.tickets",
    "vex.cogs.wipe",
    "vex.cogs.automod",
    "vex.cogs.roles",
    "vex.cogs.staff",
    "vex.cogs.admin",
)


class VexTree(app_commands.CommandTree):
    async def on_error(self, interaction, error):
        if isinstance(error, NoAccess):
            if error.admin_only:
                text = "Эта команда доступна только администраторам."
            else:
                text = (
                    "У тебя нет доступа к этой команде.\n"
                    "Администратор может выдать его через `/perms grant`."
                )
            message = embeds.err(text, "Нет доступа")
        elif isinstance(error, app_commands.CheckFailure):
            message = embeds.err("Эту команду нельзя использовать здесь.", "Недоступно")
        else:
            log.error("Ошибка в команде %s", getattr(interaction.command, "name", "?"), exc_info=error)
            message = embeds.err("Что-то пошло не так. Подробности записаны в логи бота.")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=message, ephemeral=True)
            else:
                await interaction.response.send_message(embed=message, ephemeral=True)
        except discord.HTTPException:
            pass


class VexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # автороли, поиск не ответивших (включить в Developer Portal)
        intents.message_content = True  # автомодерация ссылок (включить в Developer Portal)
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            tree_cls=VexTree,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
        )
        self.db = Database(config.DATA_DIR / "vex.sqlite3")
        self.web_runner = None

    async def close(self):
        if self.web_runner is not None:
            await self.web_runner.cleanup()
        await super().close()

    async def setup_hook(self):
        self.db.connect()
        log.info("База данных: %s", self.db.path.resolve())
        for extension in EXTENSIONS:
            await self.load_extension(extension)

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Синхронизировано команд: %d", len(synced))
        self.web_runner = await start_web(self)

    async def on_ready(self):
        log.info("VEX запущен как %s (серверов: %d)", self.user, len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="за кланом")
        )

    async def send_log(self, guild, embed, key="mod_log", file=None):
        """Отправляет эмбед в лог-канал сервера. Для тикетов, если нет своего канала, берёт общий."""
        channel_id = await self.db.get_setting(guild.id, key)
        if not channel_id and key != "mod_log":
            channel_id = await self.db.get_setting(guild.id, "mod_log")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            return
        try:
            await channel.send(embed=embed, file=file)
        except discord.HTTPException:
            log.warning("Не удалось отправить лог в канал %s", channel_id)
''',
    'vex.webui': r'''"""Страницы сайта VEX: чистые функции «данные -> HTML». Без зависимостей от discord и aiohttp.

Во всех формах стоит метка __CSRF__ — layout() заменяет её на токен сессии.
"""
import html
import re
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo

FLASH_OK = {
    "saved": "Сохранено.",
    "sent": "Панель отправлена в канал.",
    "deleted": "Удалено.",
    "reminded": "Напоминание отправлено.",
    "noone": "Все уже ответили — напоминать некому.",
}
FLASH_ERR = {
    "denied": "Вход отменён.",
    "state": "Не удалось подтвердить вход. Попробуй ещё раз.",
    "oauth": "Discord не принял вход. Проверь Client Secret и Redirect URI в Developer Portal.",
    "nosecret": "Сайт не настроен: не задана переменная DISCORD_CLIENT_SECRET.",
    "types_empty": "Добавь хотя бы один тип обращения.",
    "types_many": "Типов обращений может быть не больше 25.",
    "channel": "Выбери канал из списка.",
    "noperm": "У VEX нет прав писать в этот канал.",
    "noevent": "Событие не найдено.",
    "nocog": "Модуль бота ещё не загружен, попробуй через минуту.",
}

NAV = [
    ("", "Обзор", "🏠"),
    ("access", "Доступ к командам", "🔐"),
    ("roles", "Роли", "🎭"),
    ("automod", "Автомодерация", "🛡️"),
    ("tickets", "Тикеты", "🎫"),
    ("events", "События", "📝"),
    ("general", "Общие", "⚙️"),
]

CSS = """
:root{color-scheme:dark;--bg:#0e0a1a;--panel:#171124;--panel2:#1e1730;--line:#2d2447;--text:#eee9fb;--muted:#9d93bd;
--brand:#8b5cf6;--brand2:#6d28d9;--ok:#22c55e;--err:#ef4444;--warn:#f59e0b;--r:14px}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;min-height:100vh;color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Arial,sans-serif;
background:radial-gradient(900px 500px at 85% -10%,#2b1b57 0,transparent 60%),radial-gradient(700px 400px at -10% 110%,#1d1240 0,transparent 55%),var(--bg)}
a{color:#c4b5fd;text-decoration:none}a:hover{text-decoration:underline}
code{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:.9em}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}h2{font-size:18px;margin:0 0 4px}h3{font-size:15px;margin:0 0 8px}
.muted,.sub{color:var(--muted)}
.top{display:flex;align-items:center;gap:16px;padding:12px 20px;border-bottom:1px solid var(--line);background:rgba(14,10,26,.75);
backdrop-filter:blur(8px);position:sticky;top:0;z-index:5}
.brand{display:flex;align-items:baseline;gap:10px;color:var(--text)}.brand:hover{text-decoration:none}
.brand b{font-size:20px;letter-spacing:.12em;background:linear-gradient(135deg,#c4b5fd,#8b5cf6);-webkit-background-clip:text;background-clip:text;color:transparent}
.brand small{color:var(--muted);font-size:12px}
.spacer{flex:1}
.user{display:flex;align-items:center;gap:10px}.user img{border-radius:50%}.user form{margin:0}
.link{background:none;border:0;color:#c4b5fd;cursor:pointer;font:inherit;padding:0}.link:hover{text-decoration:underline}
.shell{display:block;max-width:1120px;margin:0 auto;padding:24px 20px 60px}
.shell.has-side{display:grid;grid-template-columns:230px minmax(0,1fr);gap:28px;max-width:1280px}
.side{position:sticky;top:76px;align-self:start}
.guild{display:flex;align-items:center;gap:10px;padding:10px 12px;margin-bottom:12px;background:var(--panel);border:1px solid var(--line);border-radius:var(--r);font-weight:600}
.side nav{display:flex;flex-direction:column;gap:2px}
.side nav a{display:flex;gap:10px;align-items:center;padding:9px 12px;border-radius:10px;color:var(--text)}
.side nav a:hover{background:var(--panel);text-decoration:none}
.side nav a.active{background:linear-gradient(135deg,rgba(139,92,246,.32),rgba(109,40,217,.22));box-shadow:inset 0 0 0 1px rgba(139,92,246,.55)}
.ico{width:32px;height:32px;border-radius:50%;flex:none;object-fit:cover}
.ico.ph{display:grid;place-items:center;background:var(--brand2);font-weight:700}
.head{margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;margin-bottom:16px}
.card>h2{margin-bottom:2px}.card>.sub{margin:0 0 14px}
.block{padding:14px 0;border-top:1px solid var(--line)}.block:first-of-type{border-top:0;padding-top:4px}
.block h3 small{color:var(--muted);font-weight:400;margin-left:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:14px 16px}
.tile b{display:block;font-size:24px;line-height:1.2}.tile span{color:var(--muted);font-size:13px}
.gcard{display:flex;align-items:center;gap:12px;padding:14px 16px;background:var(--panel);border:1px solid var(--line);border-radius:var(--r);color:var(--text)}
.gcard:hover{border-color:var(--brand);text-decoration:none;transform:translateY(-1px)}
.gcard small{display:block;color:var(--muted)}
.field{margin:0 0 16px}.field>label,.field>.lbl{display:block;font-weight:600;margin-bottom:6px}
.hint{color:var(--muted);font-size:13px;margin-top:4px}
input[type=text],input[type=number],select,textarea{width:100%;background:var(--panel2);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit}
input:focus,select:focus,textarea:focus{outline:2px solid rgba(139,92,246,.6);outline-offset:1px;border-color:var(--brand)}
textarea{min-height:110px;resize:vertical}textarea.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13.5px}
input[type=number]{max-width:140px}
.row{display:flex;gap:16px;flex-wrap:wrap}.row .field{flex:1;min-width:170px}
.check{display:flex;align-items:center;gap:10px;cursor:pointer}.check input{width:18px;height:18px;accent-color:var(--brand)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{position:relative}.chip input{position:absolute;opacity:0;inset:0;width:100%;height:100%;cursor:pointer;margin:0}
.chip span{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);color:var(--muted);transition:.12s}
.chip:hover span{border-color:var(--brand);color:var(--text)}
.chip input:checked+span{background:var(--brand2);border-color:var(--brand);color:#fff}
.chip input:focus-visible+span{outline:2px solid #c4b5fd;outline-offset:2px}
.chip.locked{opacity:.45}.chip.locked input{cursor:not-allowed}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.actions{margin-top:6px;display:flex;gap:10px;flex-wrap:wrap}
.btn{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;border:0;border-radius:10px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer}
.btn:hover{filter:brightness(1.1);text-decoration:none}
.btn.ghost{background:var(--panel2);border:1px solid var(--line);color:var(--text)}
.btn.danger{background:#b91c1c}.btn.sm{padding:5px 12px;font-size:13px}
.flash{padding:12px 16px;border-radius:12px;margin-bottom:16px;border:1px solid}
.flash.ok{background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.5)}
.flash.err{background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.55)}
.flash.warn{background:rgba(245,158,11,.12);border-color:rgba(245,158,11,.5)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px 10px;border-top:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:13px;border-top:0}
.tablewrap{overflow-x:auto}
ul.health{list-style:none;margin:0;padding:0}ul.health li{padding:6px 0}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;background:var(--panel2);border:1px solid var(--line)}
.pill.on{background:rgba(34,197,94,.15);border-color:rgba(34,197,94,.5)}.pill.off{background:rgba(239,68,68,.15);border-color:rgba(239,68,68,.5)}
.inline{display:inline-block;margin:0 6px 4px 0}
details summary{cursor:pointer;color:#fca5a5;display:inline-block}
.hero{text-align:center;padding:70px 10px 40px}.hero h1{font-size:40px}.hero p{color:var(--muted);max-width:520px;margin:10px auto 26px}
@media (max-width:860px){
.shell.has-side{grid-template-columns:minmax(0,1fr);gap:14px}
.side{position:static;min-width:0}.side nav{flex-direction:row;overflow-x:auto;padding-bottom:6px}.side nav a{white-space:nowrap}
main{min-width:0}.shell{padding:16px 16px 50px}.card{padding:16px}
.top{padding:10px 14px}.brand small,.user span{display:none}.hero h1{font-size:30px}
}
"""


def esc(value):
    return html.escape(str(value), quote=True)


# --------------------------------------------------------------------------- разбор форм
def is_emoji(text):
    """Грубая проверка «это эмодзи» (Discord отклоняет мусор в SelectOption)."""
    return bool(text) and len(text) <= 8 and all(ord(ch) > 0x2000 for ch in text)


def make_slug(label):
    return re.sub(r"[^\w]+", "-", label.lower()).strip("-")[:20] or "ticket"


def types_to_text(types):
    return "\n".join(f"{t.get('emoji', '')} | {t['label']} | {t.get('description', '')}" for t in types)


def parse_types_text(text, existing):
    """Строки вида «эмодзи | Название | Описание» -> (список типов, код ошибки).

    existing: {название в нижнем регистре: (key, slug)} — чтобы старые тикеты не теряли свой тип.
    """
    types, used = [], set()
    for line in str(text).splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            emoji, label, desc = parts[0], parts[1], " | ".join(parts[2:])
        elif len(parts) == 2:
            if is_emoji(parts[0]):
                emoji, label, desc = parts[0], parts[1], ""
            else:
                emoji, label, desc = "", parts[0], parts[1]
        else:
            emoji, label, desc = "", parts[0], ""
        if not is_emoji(emoji):
            emoji = ""
        label, desc = label[:100], desc[:100]
        if not label:
            continue
        found = existing.get(label.lower())
        key = found[0] if found else f"{zlib.crc32(label.lower().encode('utf-8')):08x}"
        slug = found[1] if found else make_slug(label)
        if key in used:
            continue
        used.add(key)
        types.append({"key": key, "slug": slug, "label": label, "emoji": emoji, "description": desc})
    if not types:
        return None, "types_empty"
    if len(types) > 25:
        return None, "types_many"
    return types, None


def fmt_ts(ts, tz):
    try:
        return datetime.fromtimestamp(int(ts), ZoneInfo(tz)).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(ts)


# --------------------------------------------------------------------------- кирпичики
def icon(url, name, size=32):
    if url:
        return f'<img class="ico" src="{esc(url)}" alt="" width="{size}" height="{size}">'
    letter = esc((name or "?")[:1].upper())
    return f'<span class="ico ph" style="width:{size}px;height:{size}px">{letter}</span>'


def chips(name, items, selected, empty="Ничего не найдено."):
    if not items:
        return f'<p class="muted">{esc(empty)}</p>'
    sel = set(selected)
    out = ['<div class="chips">']
    for it in items:
        locked = bool(it.get("locked"))
        checked = " checked" if (it["id"] in sel and not locked) else ""
        dot = ""
        if "color" in it:
            color = it["color"] or 0x99AAB5
            dot = f'<i class="dot" style="background:#{color:06x}"></i>'
        lock = "🔒 " if locked else ""
        out.append(
            f'<label class="chip{" locked" if locked else ""}"><input type="checkbox" name="{esc(name)}" '
            f'value="{it["id"]}"{checked}{" disabled" if locked else ""}><span>{dot}{lock}{esc(it["name"])}</span></label>'
        )
    out.append("</div>")
    return "".join(out)


def select(name, items, selected, blank="— не выбран —"):
    out = [f'<select name="{esc(name)}"><option value="">{esc(blank)}</option>']
    for it in items:
        sel = " selected" if selected is not None and it["id"] == selected else ""
        out.append(f'<option value="{it["id"]}"{sel}>{esc(it["name"])}</option>')
    out.append("</select>")
    return "".join(out)


def field(label, control, hint=""):
    hint_html = f'<div class="hint">{hint}</div>' if hint else ""
    return f'<div class="field"><span class="lbl">{esc(label)}</span>{control}{hint_html}</div>'


def card(title, inner, sub=""):
    sub_html = f'<p class="sub">{sub}</p>' if sub else ""
    return f'<section class="card"><h2>{esc(title)}</h2>{sub_html}{inner}</section>'


def head(title, sub=""):
    return f'<div class="head"><h1>{esc(title)}</h1><p class="sub">{sub}</p></div>'


def form(action, inner, button="Сохранить"):
    return (
        f'<form method="post" action="{esc(action)}"><input type="hidden" name="csrf" value="__CSRF__">'
        f'{inner}<div class="actions"><button class="btn" type="submit">{esc(button)}</button></div></form>'
    )


def mini_form(action, button, cls="btn ghost sm"):
    return (
        f'<form class="inline" method="post" action="{esc(action)}"><input type="hidden" name="csrf" value="__CSRF__">'
        f'<button class="{cls}" type="submit">{esc(button)}</button></form>'
    )


def tiles(items):
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><b>{esc(v)}</b><span>{esc(l)}</span></div>' for v, l in items
    ) + "</div>"


def layout(title, body, *, user=None, guild=None, section=None, csrf="", ok=None, err=None):
    flash = ""
    if ok:
        flash += f'<div class="flash ok">✅ {esc(FLASH_OK.get(ok, "Готово."))}</div>'
    if err:
        flash += f'<div class="flash err">⛔ {esc(FLASH_ERR.get(err, "Что-то пошло не так."))}</div>'

    side = ""
    switch = ""
    if guild:
        links = []
        for slug, label, emoji in NAV:
            href = f"/g/{guild['id']}" + (f"/{slug}" if slug else "")
            cls = ' class="active"' if slug == (section or "") else ""
            links.append(f'<a{cls} href="{href}"><span>{emoji}</span>{esc(label)}</a>')
        side = (
            f'<aside class="side"><div class="guild">{icon(guild.get("icon"), guild["name"])}'
            f'<span>{esc(guild["name"])}</span></div><nav>{"".join(links)}</nav></aside>'
        )
        switch = '<a href="/">Сменить сервер</a>'

    userbar = ""
    if user:
        userbar = (
            f'<div class="user"><img src="{esc(user["avatar"])}" alt="" width="28" height="28"><span>{esc(user["name"])}</span>'
            '<form method="post" action="/logout"><input type="hidden" name="csrf" value="__CSRF__">'
            '<button class="link" type="submit">Выйти</button></form></div>'
        )

    page = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)} · VEX</title><style>{CSS}</style></head><body>"
        '<header class="top"><a class="brand" href="/"><b>VEX</b><small>панель управления</small></a>'
        f'<span class="spacer"></span>{switch}{userbar}</header>'
        f'<div class="shell{" has-side" if guild else ""}">{side}<main>{flash}{body}</main></div></body></html>'
    )
    return page.replace("__CSRF__", esc(csrf))


# --------------------------------------------------------------------------- страницы
def login_page(configured):
    if configured:
        action = '<a class="btn" href="/login">Войти через Discord</a>'
    else:
        action = (
            '<div class="flash warn">Сайт ещё не настроен: на хостинге не задана переменная '
            "<code>DISCORD_CLIENT_SECRET</code>.</div>"
        )
    return (
        '<section class="hero"><h1>VEX</h1>'
        "<p>Панель управления ботом для клана: доступ к командам, роли, автомодерация, тикеты и события — всё в браузере.</p>"
        f"{action}</section>"
    )


def guilds_page(guilds, invite_url):
    if guilds:
        cards = "".join(
            f'<a class="gcard" href="/g/{g["id"]}">{icon(g.get("icon"), g["name"], 40)}'
            f'<div><b>{esc(g["name"])}</b><small>{esc(g.get("members", ""))} участников</small></div></a>'
            for g in guilds
        )
        body = f'<div class="grid">{cards}</div>'
    else:
        body = (
            '<div class="flash warn">Не нашёл серверов, где ты администратор и где уже есть VEX. '
            "Пригласи бота на свой сервер и обнови страницу.</div>"
        )
    body += f'<p style="margin-top:18px"><a class="btn ghost" href="{esc(invite_url)}">➕ Добавить VEX на сервер</a></p>'
    return head("Твои серверы", "Выбери сервер, которым хочешь управлять.") + body


def overview_page(gid, stats, health, recent):
    t = tiles([
        (stats["open_tickets"], "открытых тикетов"),
        (stats["active_events"], "ближайших событий"),
        ("вкл" if stats["automod_on"] else "выкл", "автомодерация"),
        (stats["members"], "участников"),
    ])
    items = "".join(
        f'<li>{"ℹ️" if ok is None else ("✅" if ok else "⛔")} {esc(text)}</li>' for ok, text in health
    )
    health_card = card("Состояние бота", f'<ul class="health">{items}</ul>')

    if recent:
        rows = "".join(
            f"<tr><td>{esc(r['when'])}</td><td>{esc(r['user'])}</td><td>{esc(r['channel'])}</td>"
            f"<td><code>{esc(r['link'])}</code></td></tr>"
            for r in recent
        )
        table = (
            '<div class="tablewrap"><table><tr><th>Когда</th><th>Кто</th><th>Канал</th><th>Ссылка</th></tr>'
            f"{rows}</table></div>"
        )
    else:
        table = '<p class="muted">Пока нарушений не было.</p>'
    recent_card = card("Последние срабатывания автомодерации", table)

    links = "".join(
        f'<a class="gcard" href="/g/{gid}/{slug}"><span style="font-size:22px">{emoji}</span><b>{esc(label)}</b></a>'
        for slug, label, emoji in NAV[1:]
    )
    return head("Обзор", "Состояние бота и быстрые ссылки.") + t + health_card + recent_card + f'<div class="grid">{links}</div>'


def access_page(gid, roles, selected, keys):
    blocks = "".join(
        f'<div class="block"><h3><code>{esc(key)}</code><small>{esc(desc)}</small></h3>'
        f'{chips("cmd_" + key, roles, selected.get(key, []), "На сервере нет ролей.")}</div>'
        for key, desc in keys.items()
    )
    note = (
        '<div class="flash warn">Администраторы сервера всегда имеют доступ ко всем командам. '
        "Если у группы не выбрано ни одной роли — команды этой группы доступны только администраторам.</div>"
    )
    return (
        head("Доступ к командам", "Какие роли могут пользоваться какими командами бота.")
        + note + card("Группы команд", form(f"/g/{gid}/access", blocks))
    )


def roles_page(gid, assign_roles, manage_roles, member_sel, bot_sel, manageable_sel):
    inner = (
        '<div class="block"><h3>Роли новым участникам<small>выдаются при заходе на сервер</small></h3>'
        + chips("autorole_member", assign_roles, member_sel)
        + '</div><div class="block"><h3>Роли новым ботам<small>выдаются при добавлении бота</small></h3>'
        + chips("autorole_bot", assign_roles, bot_sel)
        + '</div><div class="block"><h3>Роли, которые модераторы могут выдавать<small>через /role add и /role remove</small></h3>'
        + chips("manageable", manage_roles, manageable_sel)
        + '<div class="hint">Если ничего не выбрано — можно выдавать любые роли ниже своей, кроме ролей с опасными правами.</div></div>'
    )
    note = (
        '<div class="flash warn">Роли с замком 🔒 стоят выше роли VEX или управляются интеграцией, поэтому бот не сможет их выдать. '
        "Подними роль VEX выше них в настройках сервера → Роли.</div>"
    )
    return head("Роли", "Авто-выдача при заходе и список ролей для модераторов.") + note + card("Настройки", form(f"/g/{gid}/roles", inner))


def automod_page(gid, s, roles, channels, default_domains):
    switch = (
        f'<label class="check"><input type="checkbox" name="enabled" value="1"{" checked" if s["enabled"] else ""}>'
        "<span>Автомодерация ссылок включена</span></label>"
    )
    punish = (
        '<div class="row">'
        + field("Нарушений до тайм-аута", f'<input type="number" name="strikes" min="1" max="10" value="{s["strikes"]}">',
                "Считаются за последние 10 минут.")
        + field("Тайм-аут, минут", f'<input type="number" name="timeout" min="0" max="1440" value="{s["timeout"]}">',
                "0 — не выдавать, только удалять ссылки.")
        + "</div>"
    )
    defaults = ", ".join(f"<code>{esc(d)}</code>" for d in default_domains)
    domains = field(
        "Разрешённые домены",
        f'<textarea class="mono" name="domains" placeholder="youtube.com&#10;twitch.tv">{esc(s["domains_text"])}</textarea>',
        f"По одному в строке. Поддомены разрешаются сами. Всегда разрешены: {defaults}.",
    )
    bypass = field("Роли, которых автомодерация не проверяет", chips("bypass", roles, s["bypass"]),
                   "Администраторы и модераторы с правом «Управлять сообщениями» не проверяются никогда.")
    ignore = field("Каналы, где ссылки разрешены", chips("ignore", channels, s["ignore"]))
    return head("Автомодерация", "Защита от нежелательных ссылок и инвайтов.") + card(
        "Настройки", form(f"/g/{gid}/automod", switch + "<br><br>" + punish + domains + bypass + ignore)
    )


def tickets_page(gid, t, categories, channels, roles, open_tickets):
    settings = (
        '<div class="row">'
        + field("Категория для тикетов", select("category", categories, t["category"]),
                "Новые тикеты создаются в этой категории.")
        + field("Канал для логов тикетов", select("log_channel", channels, t["log_channel"]),
                "Сюда приходят переписки закрытых тикетов.")
        + field("Тикетов на человека", f'<input type="number" name="max_open" min="1" max="5" value="{t["max_open"]}">')
        + "</div>"
        + field("Роли поддержки", chips("support", roles, t["support"]),
                "Видят все тикеты и могут их вести.")
        + field(
            "Типы обращений (меню на панели)",
            f'<textarea class="mono" name="types" rows="7">{esc(t["types_text"])}</textarea>',
            "По одному в строке: <code>эмодзи | Название | Описание</code>. Не больше 25. "
            "После изменения отправь панель заново — старая панель обновится при ближайшем выборе в меню.",
        )
    )
    panel = (
        '<div class="row">'
        + field("Канал", select("channel", channels, None, "— выбери канал —"))
        + field("Заголовок (необязательно)", '<input type="text" name="title" maxlength="200" placeholder="🎫 Центр поддержки">')
        + "</div>"
        + field("Текст (необязательно)", '<textarea name="description" rows="4" maxlength="2000" '
                'placeholder="Если пусто — стандартный текст со списком типов"></textarea>')
    )
    if open_tickets:
        rows = "".join(
            f"<tr><td>#{x['id']:04d}</td><td>{esc(x['user'])}</td><td>{esc(x['type'])}</td>"
            f"<td>{esc(x['status'])}</td><td>{esc(x['created'])}</td><td><code>#{esc(x['channel'])}</code></td></tr>"
            for x in open_tickets
        )
        table = (
            '<div class="tablewrap"><table><tr><th>№</th><th>Автор</th><th>Тип</th><th>Статус</th><th>Создан</th><th>Канал</th></tr>'
            f"{rows}</table></div>"
        )
    else:
        table = '<p class="muted">Открытых тикетов нет.</p>'
    return (
        head("Тикеты", "Панель обращений, роли поддержки и список открытых тикетов.")
        + card("Настройки", form(f"/g/{gid}/tickets", settings))
        + card("Отправить панель", form(f"/g/{gid}/tickets/panel", panel, "Отправить панель"),
               "Сообщение с меню, через которое участники открывают тикеты.")
        + card("Открытые тикеты", table)
    )


def events_page(gid, events):
    if not events:
        return head("События", "Вайп-реакты, созданные командой /wipereact.") + card(
            "События", '<p class="muted">Событий пока нет. Создай первое командой <code>/wipereact</code> в Discord.</p>'
        )
    rows = []
    for e in events:
        base = f"/g/{gid}/events/{e['message_id']}"
        status = '<span class="pill off">приём закрыт</span>' if e["closed"] else '<span class="pill on">идёт приём</span>'
        actions = (
            mini_form(f"{base}/toggle", "Открыть приём" if e["closed"] else "Закрыть приём")
            + mini_form(f"{base}/remind", "Напомнить не ответившим")
            + f'<details class="inline"><summary>Удалить</summary>{mini_form(f"{base}/delete", "Точно удалить", "btn danger sm")}</details>'
        )
        rows.append(
            f"<tr><td><b>{esc(e['title'])}</b><br><a href=\"{esc(e['url'])}\" target=\"_blank\" rel=\"noopener\">#{esc(e['channel'])}</a></td>"
            f"<td>{esc(e['when'])}</td><td>✅ {e['accepted']} · ❌ {e['declined']} · 🕒 {e['late']}</td><td>{status}</td><td>{actions}</td></tr>"
        )
    table = (
        '<div class="tablewrap"><table><tr><th>Событие</th><th>Когда</th><th>Ответы</th><th>Статус</th><th>Действия</th></tr>'
        + "".join(rows) + "</table></div>"
    )
    return head("События", "Вайп-реакты, созданные командой /wipereact.") + card("Последние события", table)


def general_page(gid, g, channels, timezone):
    inner = (
        field("Лог-канал модерации", select("mod_log", channels, g["mod_log"]),
              "Сюда пишутся действия автомодерации, выдача ролей, сообщения /say, входы и выходы.")
        + field("Канал приветствий", select("welcome_channel", channels, g["welcome_channel"]),
                "Если не выбран — приветствия выключены.")
        + field("Текст приветствия", f'<textarea name="welcome_text" rows="4" maxlength="1500" '
                f'placeholder="{esc(g["welcome_default"])}">{esc(g["welcome_text"])}</textarea>',
                "Можно использовать <code>{user}</code> и <code>{server}</code>. Пусто — стандартный текст.")
    )
    info = f'<p class="muted">Часовой пояс бота: <code>{esc(timezone)}</code> (задаётся переменной <code>TIMEZONE</code> на хостинге).</p>'
    return head("Общие настройки", "Логи и приветствие новых участников.") + card("Настройки", form(f"/g/{gid}/general", inner)) + info


def error_page(text):
    return f'<section class="hero"><h1>Ой</h1><p>{esc(text)}</p><a class="btn" href="/">На главную</a></section>'
''',
    'vex.web': r'''"""Сайт-панель VEX: вход через Discord (OAuth2), настройка бота в браузере.

Работает в том же процессе, что и бот, и пользуется той же базой.
Включается, только если хостинг передал порт (переменная PORT).
"""
import json
import logging
import re
import secrets
import time
from urllib.parse import urlencode

import discord
from aiohttp import ClientSession, ClientTimeout, web

from . import config, webui
from .checks import is_admin
from .cogs.admin import DEFAULT_WELCOME
from .cogs.automod import normalize_domain

log = logging.getLogger("vex.web")

API = "https://discord.com/api/v10"
SESSION_TTL = 12 * 3600
COOKIE = "vex_session"
STATE_COOKIE = "vex_state"
INVITE_PERMISSIONS = 1099780320272
ADMINISTRATOR = 0x8
USER_AGENT = "DiscordBot (https://discord.com, 1.0) VEX-dashboard"

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' https://cdn.discordapp.com data:; style-src 'unsafe-inline'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
}


# --------------------------------------------------------------------------- общие помощники
def base_url(request):
    if config.PUBLIC_URL:
        return config.PUBLIC_URL
    proto = request.headers.get("X-Forwarded-Proto", request.scheme).split(",")[0].strip()
    host = request.headers.get("X-Forwarded-Host", request.host).split(",")[0].strip()
    return f"{proto}://{host}"


def is_https(request):
    return base_url(request).startswith("https://")


def html_response(text, status=200):
    return web.Response(text=text, status=status, content_type="text/html", charset="utf-8")


def current_session(request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    store = request.app["sessions"]
    sess = store.get(token)
    if sess is None:
        return None
    if sess["exp"] < time.time():
        store.pop(token, None)
        return None
    return sess


def authorize(request):
    """Проверяет вход и права на сервер. Возвращает (сессия, сервер) или прерывает запрос."""
    sess = current_session(request)
    if sess is None:
        raise web.HTTPFound("/")
    try:
        gid = int(request.match_info["gid"])
    except (KeyError, ValueError):
        raise web.HTTPNotFound(text="Сервер не найден")
    if gid not in sess["guilds"]:
        raise web.HTTPForbidden(text="Нет доступа к этому серверу")
    guild = request.app["bot"].get_guild(gid)
    if guild is None:
        raise web.HTTPNotFound(text="VEX не добавлен на этот сервер")
    member = guild.get_member(sess["uid"])
    if member is not None and not is_admin(member):  # права могли отозвать после входа
        raise web.HTTPForbidden(text="Ты больше не администратор этого сервера")
    return sess, guild


def check_csrf(sess, data):
    if not secrets.compare_digest(str(data.get("csrf", "")), sess["csrf"]):
        raise web.HTTPForbidden(text="Сессия устарела. Обнови страницу и повтори.")


async def post_context(request):
    sess, guild = authorize(request)
    data = await request.post()
    check_csrf(sess, data)
    return sess, guild, data


def back(gid, section="", ok=None, err=None):
    path = f"/g/{gid}" + (f"/{section}" if section else "")
    if ok:
        path += f"?ok={ok}"
    elif err:
        path += f"?err={err}"
    return web.HTTPSeeOther(path)


def render(request, sess, title, body, guild=None, section=None):
    user = {"name": sess["name"], "avatar": sess["avatar"]} if sess else None
    guild_ctx = None
    if guild is not None:
        guild_ctx = {"id": guild.id, "name": guild.name, "icon": guild.icon.url if guild.icon else None}
    text = webui.layout(
        title, body, user=user, guild=guild_ctx, section=section,
        csrf=sess["csrf"] if sess else "", ok=request.query.get("ok"), err=request.query.get("err"),
    )
    return html_response(text)


def role_items(guild, lock=None):
    me_top = guild.me.top_role
    items = []
    for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if role.is_default():
            continue
        item = {"id": role.id, "name": role.name, "color": role.color.value}
        if lock == "assign" and (role.managed or role >= me_top):
            item["locked"] = True
        elif lock == "managed" and role.managed:
            item["locked"] = True
        items.append(item)
    return items


def channel_items(guild):
    return [{"id": c.id, "name": f"#{c.name}"} for c in guild.text_channels]


def category_items(guild):
    return [{"id": c.id, "name": c.name} for c in guild.categories]


def free_ids(items):
    return {i["id"] for i in items if not i.get("locked")}


def pick_ids(values, valid):
    out = []
    for value in values:
        text = str(value)
        if text.isdigit() and int(text) in valid and int(text) not in out:
            out.append(int(text))
    return out


def pick_one(value, valid):
    text = str(value or "")
    return int(text) if text.isdigit() and int(text) in valid else None


def clamp(value, low, high, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


async def set_or_del(db, gid, key, value):
    if value is None or value == "":
        await db.del_setting(gid, key)
    else:
        await db.set_setting(gid, key, value)


# --------------------------------------------------------------------------- middleware
@web.middleware
async def middleware(request, handler):
    try:
        response = await handler(request)
    except web.HTTPException:
        raise
    except Exception:
        log.exception("Ошибка на странице %s", request.path)
        response = html_response(
            webui.layout("Ошибка", webui.error_page("Внутренняя ошибка. Подробности записаны в логи бота.")), 500
        )
    response.headers.update(SECURITY_HEADERS)
    return response


# --------------------------------------------------------------------------- вход и выход
def avatar_url(user):
    if user.get("avatar"):
        return f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png?size=64"
    return f"https://cdn.discordapp.com/embed/avatars/{(int(user['id']) >> 22) % 6}.png"


def client_id(bot):
    return config.CLIENT_ID or str(bot.user.id)


async def health(request):
    return web.Response(text="ok")


async def index(request):
    bot = request.app["bot"]
    sess = current_session(request)
    if sess is None:
        body = webui.login_page(bool(config.CLIENT_SECRET))
        return html_response(
            webui.layout("Вход", body, ok=request.query.get("ok"), err=request.query.get("err"))
        )
    guilds = []
    for gid in sess["guilds"]:
        guild = bot.get_guild(gid)
        if guild:
            guilds.append({
                "id": gid, "name": guild.name, "members": guild.member_count,
                "icon": guild.icon.url if guild.icon else None,
            })
    invite = (
        "https://discord.com/oauth2/authorize?"
        + urlencode({"client_id": client_id(bot), "scope": "bot applications.commands", "permissions": INVITE_PERMISSIONS})
    )
    return render(request, sess, "Серверы", webui.guilds_page(guilds, invite))


async def login(request):
    if not config.CLIENT_SECRET:
        raise web.HTTPFound("/?err=nosecret")
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id(request.app["bot"]),
        "redirect_uri": base_url(request) + "/callback",
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "none",
    }
    response = web.HTTPFound("https://discord.com/oauth2/authorize?" + urlencode(params))
    response.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, samesite="Lax", secure=is_https(request))
    raise response


async def callback(request):
    bot = request.app["bot"]
    if request.query.get("error"):
        raise web.HTTPFound("/?err=denied")
    code = request.query.get("code")
    state = request.query.get("state")
    expected = request.cookies.get(STATE_COOKIE)
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        raise web.HTTPFound("/?err=state")

    async with ClientSession(timeout=ClientTimeout(total=15), headers={"User-Agent": USER_AGENT}) as http:
        async with http.post(f"{API}/oauth2/token", data={
            "client_id": client_id(bot),
            "client_secret": config.CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": base_url(request) + "/callback",
        }) as resp:
            if resp.status != 200:
                log.warning("OAuth: обмен кода не удался (%s): %s", resp.status, (await resp.text())[:200])
                raise web.HTTPFound("/?err=oauth")
            token = (await resp.json())["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        async with http.get(f"{API}/users/@me", headers=auth) as resp:
            if resp.status != 200:
                raise web.HTTPFound("/?err=oauth")
            user = await resp.json()
        async with http.get(f"{API}/users/@me/guilds", headers=auth) as resp:
            if resp.status != 200:
                raise web.HTTPFound("/?err=oauth")
            guilds = await resp.json()

    admin_guilds = {}
    for item in guilds:
        permissions = int(item.get("permissions") or 0)
        if item.get("owner") or permissions & ADMINISTRATOR:
            admin_guilds[int(item["id"])] = {"name": item["name"]}

    store = request.app["sessions"]
    now = time.time()
    for old in [t for t, s in store.items() if s["exp"] < now]:
        del store[old]
    session_token = secrets.token_urlsafe(32)
    store[session_token] = {
        "uid": int(user["id"]),
        "name": user.get("global_name") or user["username"],
        "avatar": avatar_url(user),
        "guilds": admin_guilds,
        "csrf": secrets.token_urlsafe(24),
        "exp": now + SESSION_TTL,
    }
    response = web.HTTPFound("/")
    response.set_cookie(COOKIE, session_token, max_age=SESSION_TTL, httponly=True, samesite="Lax", secure=is_https(request))
    response.del_cookie(STATE_COOKIE)
    raise response


async def logout(request):
    sess = current_session(request)
    data = await request.post()
    if sess is not None:
        check_csrf(sess, data)
        request.app["sessions"].pop(request.cookies.get(COOKIE), None)
    response = web.HTTPSeeOther("/")
    response.del_cookie(COOKIE)
    raise response


# --------------------------------------------------------------------------- обзор
async def overview(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    gid = guild.id

    open_tickets = (await db.fetchone(
        "SELECT COUNT(*) AS c FROM tickets WHERE guild_id=? AND status='open'", (gid,)))["c"]
    active_events = (await db.fetchone(
        "SELECT COUNT(*) AS c FROM wipe_events WHERE guild_id=? AND closed=0 AND ts>?", (gid, int(time.time()))))["c"]
    automod_on = await db.get_setting(gid, "automod_enabled", "1") != "0"

    recent = []
    for row in await db.fetchall(
        "SELECT user_id, channel_id, link, ts FROM automod_log WHERE guild_id=? ORDER BY id DESC LIMIT 8", (gid,)
    ):
        member = guild.get_member(row["user_id"])
        channel = guild.get_channel(row["channel_id"])
        recent.append({
            "when": webui.fmt_ts(row["ts"], config.TIMEZONE),
            "user": member.display_name if member else str(row["user_id"]),
            "channel": f"#{channel.name}" if channel else "—",
            "link": row["link"][:80],
        })

    me = guild.me
    perms = me.guild_permissions
    above = sum(1 for r in guild.roles if not r.is_default() and r > me.top_role)
    health = [
        (perms.manage_roles, "Право «Управлять ролями» (для /role и авто-ролей)"),
        (perms.manage_channels, "Право «Управлять каналами» (для тикетов)"),
        (perms.manage_messages, "Право «Управлять сообщениями» (для автомодерации)"),
        (perms.moderate_members, "Право «Отправлять участников подумать» (тайм-ауты автомодерации)"),
        (bool(await db.get_setting(gid, "mod_log")), "Задан лог-канал модерации (раздел «Общие»)"),
        (bool(await db.get_setting(gid, "ticket_category")), "Настроена категория тикетов (раздел «Тикеты»)"),
        (None, f"Выше роли VEX стоит ролей: {above}. Их бот выдать не сможет — при необходимости подними роль VEX."),
    ]
    stats = {"open_tickets": open_tickets, "active_events": active_events, "automod_on": automod_on,
             "members": guild.member_count}
    return render(request, sess, "Обзор", webui.overview_page(gid, stats, health, recent), guild, "")


# --------------------------------------------------------------------------- доступ к командам
async def access_get(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    selected = {}
    for key in config.COMMAND_KEYS:
        selected[key] = await db.get_targets(guild.id, f"cmd:{key}")
    body = webui.access_page(guild.id, role_items(guild), selected, config.COMMAND_KEYS)
    return render(request, sess, "Доступ к командам", body, guild, "access")


async def access_post(request):
    sess, guild, data = await post_context(request)
    db = request.app["bot"].db
    valid = {r["id"] for r in role_items(guild)}
    for key in config.COMMAND_KEYS:
        await db.set_targets(guild.id, f"cmd:{key}", pick_ids(data.getall(f"cmd_{key}", []), valid))
    raise back(guild.id, "access", ok="saved")


# --------------------------------------------------------------------------- роли
async def roles_get(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    body = webui.roles_page(
        guild.id, role_items(guild, "assign"), role_items(guild, "managed"),
        await db.get_targets(guild.id, "autorole_member"),
        await db.get_targets(guild.id, "autorole_bot"),
        await db.get_targets(guild.id, "manageable"),
    )
    return render(request, sess, "Роли", body, guild, "roles")


async def roles_post(request):
    sess, guild, data = await post_context(request)
    db = request.app["bot"].db
    assignable = free_ids(role_items(guild, "assign"))
    manageable = free_ids(role_items(guild, "managed"))
    await db.set_targets(guild.id, "autorole_member", pick_ids(data.getall("autorole_member", []), assignable))
    await db.set_targets(guild.id, "autorole_bot", pick_ids(data.getall("autorole_bot", []), assignable))
    await db.set_targets(guild.id, "manageable", pick_ids(data.getall("manageable", []), manageable))
    raise back(guild.id, "roles", ok="saved")


# --------------------------------------------------------------------------- автомодерация
async def automod_get(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    gid = guild.id
    domains = [r["domain"] for r in await db.fetchall(
        "SELECT domain FROM allowed_domains WHERE guild_id=? ORDER BY domain", (gid,))]
    state = {
        "enabled": await db.get_setting(gid, "automod_enabled", "1") != "0",
        "strikes": clamp(await db.get_setting(gid, "automod_strikes", "3"), 1, 10, 3),
        "timeout": clamp(await db.get_setting(gid, "automod_timeout", "10"), 0, 1440, 10),
        "domains_text": "\n".join(domains),
        "bypass": await db.get_targets(gid, "automod_bypass"),
        "ignore": await db.get_targets(gid, "automod_ignore_channel"),
    }
    body = webui.automod_page(gid, state, role_items(guild), channel_items(guild), config.DEFAULT_ALLOWED_DOMAINS)
    return render(request, sess, "Автомодерация", body, guild, "automod")


async def automod_post(request):
    sess, guild, data = await post_context(request)
    db = request.app["bot"].db
    gid = guild.id
    await db.set_setting(gid, "automod_enabled", "1" if data.get("enabled") else "0")
    await db.set_setting(gid, "automod_strikes", clamp(data.get("strikes"), 1, 10, 3))
    await db.set_setting(gid, "automod_timeout", clamp(data.get("timeout"), 0, 1440, 10))

    domains = []
    for item in re.split(r"[\s,;]+", str(data.get("domains", ""))):
        domain = normalize_domain(item) if item else ""
        if domain and "." in domain and len(domain) <= 100 and re.fullmatch(r"[a-z0-9.\-]+", domain) \
                and domain not in domains:
            domains.append(domain)
    await db.set_domains(gid, domains[:200])

    await db.set_targets(gid, "automod_bypass",
                         pick_ids(data.getall("bypass", []), {r["id"] for r in role_items(guild)}))
    await db.set_targets(gid, "automod_ignore_channel",
                         pick_ids(data.getall("ignore", []), {c.id for c in guild.text_channels}))
    raise back(gid, "automod", ok="saved")


# --------------------------------------------------------------------------- тикеты
async def tickets_get(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    gid = guild.id

    def as_int(value):
        return int(value) if value and str(value).isdigit() else None

    types = config.load_ticket_types(await db.get_setting(gid, "ticket_types"))
    labels = {t["key"]: t["label"] for t in types}
    state = {
        "category": as_int(await db.get_setting(gid, "ticket_category")),
        "log_channel": as_int(await db.get_setting(gid, "ticket_log")),
        "max_open": clamp(await db.get_setting(gid, "ticket_max_open", "1"), 1, 5, 1),
        "support": await db.get_targets(gid, "ticket_support"),
        "types_text": webui.types_to_text(types),
    }
    open_tickets = []
    for row in await db.fetchall(
        "SELECT id, user_id, type, claimed_by, created_at, channel_id FROM tickets "
        "WHERE guild_id=? AND status='open' ORDER BY id DESC LIMIT 50", (gid,)
    ):
        member = guild.get_member(row["user_id"])
        channel = guild.get_channel(row["channel_id"])
        claimer = guild.get_member(row["claimed_by"]) if row["claimed_by"] else None
        open_tickets.append({
            "id": row["id"],
            "user": member.display_name if member else str(row["user_id"]),
            "type": labels.get(row["type"], "Обращение"),
            "status": f"В работе — {claimer.display_name}" if claimer else "Ожидает ответа",
            "created": webui.fmt_ts(row["created_at"], config.TIMEZONE),
            "channel": channel.name if channel else "удалён",
        })
    body = webui.tickets_page(gid, state, category_items(guild), channel_items(guild), role_items(guild), open_tickets)
    return render(request, sess, "Тикеты", body, guild, "tickets")


async def tickets_post(request):
    sess, guild, data = await post_context(request)
    db = request.app["bot"].db
    gid = guild.id

    existing = {t["label"].lower(): (t["key"], t["slug"])
                for t in config.load_ticket_types(await db.get_setting(gid, "ticket_types"))}
    types, error = webui.parse_types_text(data.get("types", ""), existing)
    if error:
        raise back(gid, "tickets", err=error)

    await db.set_setting(gid, "ticket_types", json.dumps(types, ensure_ascii=False))
    await set_or_del(db, gid, "ticket_category", pick_one(data.get("category"), {c.id for c in guild.categories}))
    await set_or_del(db, gid, "ticket_log", pick_one(data.get("log_channel"), {c.id for c in guild.text_channels}))
    await db.set_setting(gid, "ticket_max_open", clamp(data.get("max_open"), 1, 5, 1))
    await db.set_targets(gid, "ticket_support",
                         pick_ids(data.getall("support", []), {r["id"] for r in role_items(guild)}))
    raise back(gid, "tickets", ok="saved")


async def tickets_panel(request):
    sess, guild, data = await post_context(request)
    channels = {c.id: c for c in guild.text_channels}
    channel_id = pick_one(data.get("channel"), set(channels))
    if channel_id is None:
        raise back(guild.id, "tickets", err="channel")
    channel = channels[channel_id]
    perms = channel.permissions_for(guild.me)
    if not (perms.send_messages and perms.embed_links):
        raise back(guild.id, "tickets", err="noperm")
    cog = request.app["bot"].get_cog("Tickets")
    if cog is None:
        raise back(guild.id, "tickets", err="nocog")
    title = str(data.get("title", "")).strip()[:200] or None
    description = str(data.get("description", "")).strip()[:2000] or None
    try:
        await cog.send_panel(channel, title, description)
    except discord.HTTPException:
        raise back(guild.id, "tickets", err="noperm")
    raise back(guild.id, "tickets", ok="sent")


# --------------------------------------------------------------------------- события
async def events_get(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    gid = guild.id
    events = []
    for ev in await db.fetchall("SELECT * FROM wipe_events WHERE guild_id=? ORDER BY ts DESC LIMIT 25", (gid,)):
        counts = {"accepted": 0, "declined": 0, "late": 0}
        for row in await db.fetchall(
            "SELECT status, COUNT(*) AS c FROM wipe_responses WHERE message_id=? GROUP BY status", (ev["message_id"],)
        ):
            if row["status"] in counts:
                counts[row["status"]] = row["c"]
        channel = guild.get_channel(ev["channel_id"])
        events.append({
            "message_id": ev["message_id"],
            "title": ev["title"],
            "when": webui.fmt_ts(ev["ts"], config.TIMEZONE),
            "closed": bool(ev["closed"]),
            "channel": channel.name if channel else "удалён",
            "url": f"https://discord.com/channels/{gid}/{ev['channel_id']}/{ev['message_id']}",
            **counts,
        })
    return render(request, sess, "События", webui.events_page(gid, events), guild, "events")


async def event_action(request):
    sess, guild, data = await post_context(request)
    db = request.app["bot"].db
    message_id = request.match_info["mid"]
    action = request.match_info["action"]
    if not message_id.isdigit() or action not in ("toggle", "delete", "remind"):
        raise web.HTTPNotFound()
    ev = await db.fetchone(
        "SELECT * FROM wipe_events WHERE message_id=? AND guild_id=?", (int(message_id), guild.id)
    )
    if ev is None:
        raise back(guild.id, "events", err="noevent")
    cog = request.app["bot"].get_cog("Wipe")
    if cog is None:
        raise back(guild.id, "events", err="nocog")
    if action == "toggle":
        await cog.set_closed(ev["message_id"], not ev["closed"])
        raise back(guild.id, "events", ok="saved")
    if action == "delete":
        await cog.delete_event(ev["message_id"])
        raise back(guild.id, "events", ok="deleted")
    count = await cog.remind_pending(ev["message_id"])
    raise back(guild.id, "events", ok="reminded" if count else "noone")


# --------------------------------------------------------------------------- общие
async def general_get(request):
    sess, guild = authorize(request)
    db = request.app["bot"].db
    gid = guild.id

    def as_int(value):
        return int(value) if value and str(value).isdigit() else None

    state = {
        "mod_log": as_int(await db.get_setting(gid, "mod_log")),
        "welcome_channel": as_int(await db.get_setting(gid, "welcome_channel")),
        "welcome_text": await db.get_setting(gid, "welcome_text", ""),
        "welcome_default": DEFAULT_WELCOME.replace("\n", " "),
    }
    body = webui.general_page(gid, state, channel_items(guild), config.TIMEZONE)
    return render(request, sess, "Общие настройки", body, guild, "general")


async def general_post(request):
    sess, guild, data = await post_context(request)
    db = request.app["bot"].db
    gid = guild.id
    valid = {c.id for c in guild.text_channels}
    await set_or_del(db, gid, "mod_log", pick_one(data.get("mod_log"), valid))
    await set_or_del(db, gid, "welcome_channel", pick_one(data.get("welcome_channel"), valid))
    text = str(data.get("welcome_text", "")).replace("\r\n", "\n").strip()[:1500]
    await set_or_del(db, gid, "welcome_text", text)
    raise back(gid, "general", ok="saved")


# --------------------------------------------------------------------------- запуск
def build_app(bot):
    app = web.Application(middlewares=[middleware])
    app["bot"] = bot
    app["sessions"] = {}
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/login", login)
    app.router.add_get("/callback", callback)
    app.router.add_post("/logout", logout)
    app.router.add_get("/g/{gid}", overview)
    for section, getter, poster in (
        ("access", access_get, access_post),
        ("roles", roles_get, roles_post),
        ("automod", automod_get, automod_post),
        ("tickets", tickets_get, tickets_post),
        ("general", general_get, general_post),
    ):
        app.router.add_get(f"/g/{{gid}}/{section}", getter)
        app.router.add_post(f"/g/{{gid}}/{section}", poster)
    app.router.add_post("/g/{gid}/tickets/panel", tickets_panel)
    app.router.add_get("/g/{gid}/events", events_get)
    app.router.add_post("/g/{gid}/events/{mid}/{action}", event_action)
    return app


async def start_web(bot):
    """Запускает сайт. Возвращает runner (для остановки) или None, если сайт выключен."""
    if not config.WEB_PORT:
        log.info("Сайт выключен: хостинг не передал порт (PORT). Включи опцию «Использовать домен».")
        return None
    try:
        runner = web.AppRunner(build_app(bot))
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", config.WEB_PORT).start()
    except OSError:
        log.exception("Не удалось запустить сайт на порту %s", config.WEB_PORT)
        return None
    log.info("Сайт запущен на порту %s%s", config.WEB_PORT,
             "" if config.CLIENT_SECRET else " (вход не настроен: нет DISCORD_CLIENT_SECRET)")
    return runner
''',
    'vex.cogs': r'''''',
    'vex.cogs.tickets': r'''"""Тикеты: панель с меню, приватные каналы, управление, транскрипты (как в Ticket Tool)."""
import asyncio
import io
from time import time as now_ts
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access, member_has_access

TZ = ZoneInfo(config.TIMEZONE)
FALLBACK_TYPE = {"label": "Обращение", "emoji": "🎫", "slug": "ticket", "description": ""}


# --------------------------------------------------------------------------- эмбеды
def panel_embed(types, title=None, description=None):
    if description:
        text = description
    else:
        listing = "\n".join(
            f"{t['emoji'] or '▫️'} **{t['label']}**" + (f" — {t['description']}" if t["description"] else "")
            for t in types
        )
        text = (
            "Нужна помощь или хочешь вступить в клан?\n"
            "Выбери тип обращения в меню ниже — для тебя создастся приватный канал, "
            "где с тобой свяжется администрация.\n\n" + listing
        )
    embed = embeds.make(title or "🎫 Центр поддержки", text)
    if not description:
        embed.add_field(
            name="ℹ️ Правила",
            value="• Один открытый тикет на человека\n• Пиши по делу и не спамь\n• Не пингуй администрацию без причины",
            inline=False,
        )
    return embed


def ticket_embed(guild, row, types_map):
    t = types_map.get(row["type"], FALLBACK_TYPE)
    embed = embeds.make(f"{t['emoji'] or '🎫'} Тикет #{row['id']:04d} — {t['label']}")
    embed.description = f">>> {row['reason']}"[:4000]
    embed.add_field(name="👤 Автор", value=f"<@{row['user_id']}>", inline=True)
    if row["claimed_by"]:
        status = f"🟡 В работе — <@{row['claimed_by']}>"
    else:
        status = "🟢 Ожидает ответа"
    embed.add_field(name="📌 Статус", value=status, inline=True)
    embed.add_field(name="🕒 Создан", value=f"<t:{row['created_at']}:R>", inline=True)
    member = guild.get_member(row["user_id"])
    if member:
        embed.set_thumbnail(url=member.display_avatar.url)
    return embed


# --------------------------------------------------------------------------- интерфейс
class TicketReasonModal(discord.ui.Modal):
    def __init__(self, cog, type_key, label):
        super().__init__(title=label[:45])
        self.cog = cog
        self.type_key = type_key
        self.reason = discord.ui.TextInput(
            label="Опишите ваш вопрос",
            style=discord.TextStyle.paragraph,
            placeholder="Расскажи подробно: что нужно, ник в игре, возраст, часы в Rust и т.д.",
            max_length=1000,
            required=True,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        await self.cog.create_ticket(interaction, self.type_key, str(self.reason))


class TicketSelect(discord.ui.Select):
    def __init__(self, types):
        options = [
            discord.SelectOption(
                label=t["label"], value=t["key"], description=t["description"] or None, emoji=t["emoji"] or None
            )
            for t in types
        ]
        super().__init__(
            placeholder="Выберите тип обращения…",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="vex:ticket:select",
        )

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Tickets")
        types = await cog.get_types(interaction.guild.id)
        label = next((t["label"] for t in types if t["key"] == self.values[0]), FALLBACK_TYPE["label"])
        await interaction.response.send_modal(TicketReasonModal(cog, self.values[0], label))
        # сбрасываем выбор в меню (и подтягиваем актуальный список типов)
        try:
            await interaction.message.edit(view=TicketPanelView(types))
        except discord.HTTPException:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self, types=None):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(types or config.load_ticket_types(None)))


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть", emoji="🔒", style=discord.ButtonStyle.danger,
                       custom_id="vex:ticket:close")
    async def close_button(self, interaction, button):
        await interaction.client.get_cog("Tickets").on_close_button(interaction)

    @discord.ui.button(label="Взять в работу", emoji="✋", style=discord.ButtonStyle.success,
                       custom_id="vex:ticket:claim")
    async def claim_button(self, interaction, button):
        await interaction.client.get_cog("Tickets").on_claim_button(interaction)


class ConfirmCloseView(discord.ui.View):
    def __init__(self, cog, channel):
        super().__init__(timeout=60)
        self.cog = cog
        self.channel = channel

    @discord.ui.button(label="Да, закрыть", emoji="🔒", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        await interaction.response.edit_message(embed=embeds.warn("Закрываю тикет…"), view=None)
        await self.cog.close_ticket(self.channel, interaction.user)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(embed=embeds.info("Отменено."), view=None)


# --------------------------------------------------------------------------- модуль
class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Система тикетов", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())

    # ---- вспомогательное
    async def get_types(self, guild_id):
        """Типы обращений сервера (настраиваются на сайте)."""
        return config.load_ticket_types(await self.bot.db.get_setting(guild_id, "ticket_types"))

    async def get_types_map(self, guild_id):
        return {t["key"]: t for t in await self.get_types(guild_id)}

    async def send_panel(self, channel, title=None, description=None):
        """Отправляет в канал панель с меню типов. Используется и командой, и сайтом."""
        types = await self.get_types(channel.guild.id)
        return await channel.send(embed=panel_embed(types, title, description), view=TicketPanelView(types))

    async def get_ticket(self, channel_id):
        return await self.bot.db.fetchone(
            "SELECT * FROM tickets WHERE channel_id=? AND status='open'", (channel_id,)
        )

    async def is_staff(self, member):
        if member.guild_permissions.administrator:
            return True
        support = await self.bot.db.get_targets(member.guild.id, "ticket_support")
        if any(role.id in support for role in member.roles):
            return True
        return await member_has_access(self.bot, member, "ticket_manage")

    async def build_transcript(self, channel, row):
        lines = [
            f"Тикет #{row['id']:04d} • {channel.guild.name}",
            f"Автор: {row['user_id']}",
            "-" * 48,
        ]
        async for message in channel.history(limit=None, oldest_first=True):
            stamp = message.created_at.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
            text = message.content or ""
            for embed in message.embeds:
                if embed.title:
                    text += f" [embed: {embed.title}]"
            for attachment in message.attachments:
                text += f" [файл: {attachment.url}]"
            lines.append(f"[{stamp}] {message.author}: {text}")
        return "\n".join(lines).encode("utf-8")

    # ---- создание
    async def create_ticket(self, interaction, type_key, reason):
        guild = interaction.guild
        user = interaction.user
        db = self.bot.db
        await interaction.response.defer(ephemeral=True)

        category_id = await db.get_setting(guild.id, "ticket_category")
        category = guild.get_channel(int(category_id)) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                embed=embeds.err("Тикеты ещё не настроены. Сообщи администрации."), ephemeral=True
            )
            return

        max_open = int(await db.get_setting(guild.id, "ticket_max_open", "1"))
        rows = await db.fetchall(
            "SELECT id, channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            (guild.id, user.id),
        )
        live = []
        for row in rows:
            if guild.get_channel(row["channel_id"]):
                live.append(row)
            else:  # канал удалили вручную
                await db.execute(
                    "UPDATE tickets SET status='closed', closed_at=? WHERE id=?", (int(now_ts()), row["id"])
                )
        if len(live) >= max_open:
            await interaction.followup.send(
                embed=embeds.warn(f"У тебя уже есть открытый тикет: <#{live[0]['channel_id']}>"),
                ephemeral=True,
            )
            return

        support_ids = await db.get_targets(guild.id, "ticket_support")
        support_roles = [r for r in (guild.get_role(i) for i in support_ids) if r]

        ticket_id = await db.insert(
            "INSERT INTO tickets(guild_id, user_id, type, reason, created_at) VALUES(?,?,?,?,?)",
            (guild.id, user.id, type_key, reason, int(now_ts())),
        )

        member_perms = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True,
        )
        staff_perms = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True, manage_messages=True,
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: member_perms,
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True, manage_messages=True,
                embed_links=True, attach_files=True, read_message_history=True,
            ),
        }
        for role in support_roles:
            overwrites[role] = staff_perms

        types_map = await self.get_types_map(guild.id)
        slug = types_map.get(type_key, FALLBACK_TYPE)["slug"]
        try:
            channel = await guild.create_text_channel(
                name=f"{slug}-{ticket_id:04d}",
                category=category,
                overwrites=overwrites,
                topic=f"Тикет #{ticket_id:04d} • {user} ({user.id})",
                reason=f"Тикет от {user}",
            )
        except (discord.Forbidden, discord.HTTPException):
            await db.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
            await interaction.followup.send(
                embed=embeds.err("Не удалось создать канал. Проверь права бота (Manage Channels)."),
                ephemeral=True,
            )
            return

        await db.execute("UPDATE tickets SET channel_id=? WHERE id=?", (channel.id, ticket_id))
        row = await db.fetchone("SELECT * FROM tickets WHERE id=?", (ticket_id,))

        pings = " ".join([user.mention] + [r.mention for r in support_roles])
        await channel.send(
            content=pings,
            embed=ticket_embed(guild, row, types_map),
            view=TicketControlView(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )
        await interaction.followup.send(
            embed=embeds.ok(f"Тикет создан: {channel.mention}", "Обращение открыто"), ephemeral=True
        )

    # ---- кнопки внутри тикета
    async def on_close_button(self, interaction):
        row = await self.get_ticket(interaction.channel.id)
        if row is None:
            await interaction.response.send_message(
                embed=embeds.err("Этот канал не является открытым тикетом."), ephemeral=True
            )
            return
        if not (interaction.user.id == row["user_id"] or await self.is_staff(interaction.user)):
            await interaction.response.send_message(
                embed=embeds.err("Закрыть тикет может его автор или поддержка."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=embeds.warn("Закрыть этот тикет? Переписка сохранится файлом в лог-канале."),
            view=ConfirmCloseView(self, interaction.channel),
            ephemeral=True,
        )

    async def on_claim_button(self, interaction):
        row = await self.get_ticket(interaction.channel.id)
        if row is None:
            await interaction.response.send_message(
                embed=embeds.err("Этот канал не является открытым тикетом."), ephemeral=True
            )
            return
        if not await self.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=embeds.err("Брать тикеты в работу может только поддержка."), ephemeral=True
            )
            return
        if row["claimed_by"]:
            await interaction.response.send_message(
                embed=embeds.warn(f"Тикет уже ведёт <@{row['claimed_by']}>."), ephemeral=True
            )
            return
        await self.bot.db.execute(
            "UPDATE tickets SET claimed_by=? WHERE id=?", (interaction.user.id, row["id"])
        )
        row = await self.bot.db.fetchone("SELECT * FROM tickets WHERE id=?", (row["id"],))
        await interaction.response.edit_message(
            embed=ticket_embed(interaction.guild, row, await self.get_types_map(interaction.guild.id)),
            view=TicketControlView(),
        )
        await interaction.channel.send(
            embed=embeds.info(f"✋ {interaction.user.mention} взял(а) тикет в работу."),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # ---- закрытие
    async def close_ticket(self, channel, closer):
        row = await self.get_ticket(channel.id)
        if row is None:
            return
        guild = channel.guild
        await self.bot.db.execute(
            "UPDATE tickets SET status='closed', closed_at=? WHERE id=?", (int(now_ts()), row["id"])
        )
        data = await self.build_transcript(channel, row)
        filename = f"ticket-{row['id']:04d}.txt"

        log = embeds.make(f"🔒 Тикет #{row['id']:04d} закрыт")
        log.add_field(name="Автор", value=f"<@{row['user_id']}>", inline=True)
        log.add_field(name="Закрыл", value=closer.mention, inline=True)
        if row["claimed_by"]:
            log.add_field(name="Вёл", value=f"<@{row['claimed_by']}>", inline=True)
        log.add_field(name="Открыт", value=f"<t:{row['created_at']}:f>", inline=True)
        await self.bot.send_log(
            guild, log, key="ticket_log", file=discord.File(io.BytesIO(data), filename=filename)
        )

        author = guild.get_member(row["user_id"])
        if author:
            try:
                dm = embeds.make(f"🔒 Твой тикет #{row['id']:04d} закрыт", f"Сервер: **{guild.name}**")
                await author.send(embed=dm, file=discord.File(io.BytesIO(data), filename=filename))
            except discord.HTTPException:
                pass  # личные сообщения закрыты

        try:
            await channel.send(embed=embeds.warn("Тикет закрыт. Канал будет удалён через 5 секунд."))
        except discord.HTTPException:
            pass
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Тикет закрыт: {closer}")
        except discord.HTTPException:
            pass

    # ---- команды администрации
    @ticket.command(name="panel", description="Отправить панель создания тикетов")
    @app_commands.describe(
        channel="Куда отправить панель (по умолчанию — текущий канал)",
        title="Свой заголовок панели",
        description="Свой текст панели (\\n — перенос строки)",
    )
    @access("ticket_admin")
    async def panel(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None,
                    title: str | None = None, description: str | None = None):
        channel = channel or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=embeds.err("Панель можно отправить только в текстовый канал."), ephemeral=True
            )
            return
        text = description.replace("\\n", "\n") if description else None
        try:
            await self.send_panel(channel, title, text)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=embeds.err(f"У меня нет прав писать в {channel.mention}."), ephemeral=True
            )
            return
        note = f"Панель отправлена в {channel.mention}."
        if not await self.bot.db.get_setting(interaction.guild.id, "ticket_category"):
            note += "\n⚠️ Категория для тикетов ещё не задана — выполни `/ticket setup`."
        await interaction.response.send_message(embed=embeds.ok(note), ephemeral=True)

    @ticket.command(name="setup", description="Настроить категорию, лог-канал и лимит тикетов")
    @app_commands.describe(
        category="Категория, где будут создаваться тикеты",
        log_channel="Канал для транскриптов закрытых тикетов",
        max_open="Сколько тикетов одновременно может быть у одного человека",
    )
    @access("ticket_admin")
    async def setup_cmd(self, interaction: discord.Interaction, category: discord.CategoryChannel,
                        log_channel: discord.TextChannel | None = None,
                        max_open: app_commands.Range[int, 1, 5] = 1):
        gid = interaction.guild.id
        await self.bot.db.set_setting(gid, "ticket_category", category.id)
        await self.bot.db.set_setting(gid, "ticket_max_open", max_open)
        lines = [f"Категория: **{category.name}**", f"Лимит открытых тикетов: **{max_open}**"]
        if log_channel:
            await self.bot.db.set_setting(gid, "ticket_log", log_channel.id)
            lines.append(f"Лог тикетов: {log_channel.mention}")
        await interaction.response.send_message(embed=embeds.ok("\n".join(lines), "Тикеты настроены"),
                                                ephemeral=True)

    @ticket.command(name="support_add", description="Добавить роль поддержки (видит и ведёт все тикеты)")
    @app_commands.describe(role="Роль модераторов/поддержки")
    @access("ticket_admin")
    async def support_add(self, interaction: discord.Interaction, role: discord.Role):
        added = await self.bot.db.add_target(interaction.guild.id, "ticket_support", role.id)
        text = f"{role.mention} теперь видит новые тикеты." if added else f"{role.mention} уже в списке."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @ticket.command(name="support_remove", description="Убрать роль поддержки")
    @app_commands.describe(role="Роль, которую нужно убрать")
    @access("ticket_admin")
    async def support_remove(self, interaction: discord.Interaction, role: discord.Role):
        removed = await self.bot.db.remove_target(interaction.guild.id, "ticket_support", role.id)
        text = f"{role.mention} убрана из поддержки." if removed else f"{role.mention} не была в списке."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @ticket.command(name="support_list", description="Показать роли поддержки")
    @access("ticket_admin")
    async def support_list(self, interaction: discord.Interaction):
        ids = await self.bot.db.get_targets(interaction.guild.id, "ticket_support")
        text = "\n".join(f"• <@&{i}>" for i in ids) or "Роли не заданы — тикеты видят только администраторы."
        await interaction.response.send_message(embed=embeds.info(text, "🛠️ Роли поддержки"), ephemeral=True)

    # ---- команды внутри тикета
    async def _staff_ticket(self, interaction):
        """Возвращает строку тикета, если команда вызвана поддержкой в открытом тикете."""
        row = await self.get_ticket(interaction.channel.id)
        if row is None:
            await interaction.response.send_message(
                embed=embeds.err("Эту команду нужно вызывать внутри открытого тикета."), ephemeral=True
            )
            return None
        if not await self.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=embeds.err("Команда доступна только поддержке."), ephemeral=True
            )
            return None
        return row

    @ticket.command(name="add", description="Добавить участника в этот тикет")
    @app_commands.describe(user="Кого добавить")
    async def add(self, interaction: discord.Interaction, user: discord.Member):
        if await self._staff_ticket(interaction) is None:
            return
        await interaction.channel.set_permissions(
            user, view_channel=True, send_messages=True, read_message_history=True, attach_files=True
        )
        await interaction.response.send_message(embed=embeds.ok(f"{user.mention} добавлен(а) в тикет."))

    @ticket.command(name="remove", description="Убрать участника из этого тикета")
    @app_commands.describe(user="Кого убрать")
    async def remove(self, interaction: discord.Interaction, user: discord.Member):
        row = await self._staff_ticket(interaction)
        if row is None:
            return
        if user.id == row["user_id"]:
            await interaction.response.send_message(
                embed=embeds.err("Автора тикета убрать нельзя — закрой тикет."), ephemeral=True
            )
            return
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=embeds.ok(f"{user.mention} убран(а) из тикета."))

    @ticket.command(name="rename", description="Переименовать канал тикета")
    @app_commands.describe(name="Новое название")
    async def rename(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 80]):
        if await self._staff_ticket(interaction) is None:
            return
        await interaction.channel.edit(name=name)
        await interaction.response.send_message(embed=embeds.ok("Канал переименован."), ephemeral=True)

    @ticket.command(name="close", description="Закрыть этот тикет")
    async def close(self, interaction: discord.Interaction):
        row = await self.get_ticket(interaction.channel.id)
        if row is None:
            await interaction.response.send_message(
                embed=embeds.err("Эту команду нужно вызывать внутри открытого тикета."), ephemeral=True
            )
            return
        if not (interaction.user.id == row["user_id"] or await self.is_staff(interaction.user)):
            await interaction.response.send_message(
                embed=embeds.err("Закрыть тикет может его автор или поддержка."), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=embeds.warn("Закрываю тикет…"), ephemeral=True)
        await self.close_ticket(interaction.channel, interaction.user)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
''',
    'vex.cogs.wipe': r'''"""Вайп-реакты: событие с кнопками «Приду / Не приду / Опоздаю» и /noreact."""
import re
from datetime import datetime
from time import time as now_ts
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config, embeds
from ..checks import access, member_has_access

TZ = ZoneInfo(config.TIMEZONE)
LINK_RE = re.compile(r"channels/(?:\d+|@me)/(\d+)/(\d+)")
STATUSES = {
    "accepted": ("✅", "Придут"),
    "declined": ("❌", "Не придут"),
    "late": ("🕒", "Опоздают"),
}
REMIND_BEFORE = 15 * 60  # за сколько секунд напоминать участникам


# --------------------------------------------------------------------------- утилиты
def parse_datetime(date_s, time_s):
    """'25.11.2026' или '25.11' + '19:00' -> datetime в часовом поясе бота (или None)."""
    now = datetime.now(TZ)
    try:
        parts = [int(p) for p in re.split(r"[./-]", date_s.strip())]
        hour, minute = [int(p) for p in re.split(r"[:.]", time_s.strip())]
        if len(parts) == 2:
            day, month = parts
            dt = datetime(now.year, month, day, hour, minute, tzinfo=TZ)
            if dt < now:
                dt = dt.replace(year=now.year + 1)
        elif len(parts) == 3:
            day, month, year = parts
            if year < 100:
                year += 2000
            dt = datetime(year, month, day, hour, minute, tzinfo=TZ)
        else:
            return None
    except ValueError:
        return None
    return dt


def render_list(rows, status):
    lines = []
    for row in rows:
        if row["status"] != status:
            continue
        line = f"<@{row['user_id']}>"
        if row["reason"]:
            line += f" — {discord.utils.escape_markdown(row['reason'])}"
        lines.append(line)
    text = ""
    shown = 0
    for line in lines:
        if len(text) + len(line) + 1 > 1000:
            text += f"\n…и ещё {len(lines) - shown}"
            break
        text += ("\n" if text else "") + line
        shown += 1
    return len(lines), text or "—"


def build_embed(ev, rows):
    closed = bool(ev["closed"])
    embed = embeds.make(
        title=f"{'🔒' if closed else '📝'} {ev['title']}",
        description=ev["description"] or None,
        color=config.COLOR_DARK if closed else config.COLOR_MAIN,
        footer=False,
    )
    ts = int(ev["ts"])
    embed.add_field(
        name="📅 Дата и время",
        value=f"<t:{ts}:F>\n<t:{ts}:R>\n*(указано по {config.TIMEZONE})*",
        inline=False,
    )
    embed.add_field(name="🗺️ Сервер", value=ev["server"] or "—", inline=False)
    for status, (emoji, label) in STATUSES.items():
        count, text = render_list(rows, status)
        embed.add_field(name=f"{emoji} {label} ({count})", value=text, inline=True)
    note = " • приём ответов закрыт" if closed else ""
    embed.set_footer(text=f"Создал: {ev['creator_name']} • {config.BRAND}{note}")
    return embed


def chunk_mentions(members, limit=1800):
    chunks, current = [], ""
    for member in members:
        piece = member.mention + " "
        if len(current) + len(piece) > limit:
            chunks.append(current.strip())
            current = ""
        current += piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


# --------------------------------------------------------------------------- интерфейс
class ReasonModal(discord.ui.Modal):
    def __init__(self, cog, ev, status, message):
        super().__init__(title="Укажи причину" if status == "declined" else "Во сколько будешь?")
        self.cog = cog
        self.ev_id = ev["message_id"]
        self.status = status
        self.message = message
        self.reason = discord.ui.TextInput(
            label="Причина" if status == "declined" else "Комментарий",
            placeholder="Например: работа / нет интернета / буду к 20:00",
            required=False,
            max_length=100,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        await self.cog.save_response(self.ev_id, interaction.user.id, self.status, str(self.reason).strip())
        await interaction.response.defer()
        await self.cog.refresh_message(self.message, self.ev_id)


class EditModal(discord.ui.Modal):
    def __init__(self, cog, ev, message):
        super().__init__(title="Редактировать событие")
        self.cog = cog
        self.ev_id = ev["message_id"]
        self.message = message
        dt = datetime.fromtimestamp(ev["ts"], TZ)
        self.title_in = discord.ui.TextInput(label="Название", default=ev["title"], max_length=100)
        self.desc_in = discord.ui.TextInput(
            label="Описание", default=ev["description"] or "", style=discord.TextStyle.paragraph,
            required=False, max_length=1000,
        )
        self.date_in = discord.ui.TextInput(label="Дата (ДД.ММ.ГГГГ)", default=dt.strftime("%d.%m.%Y"),
                                            max_length=10)
        self.time_in = discord.ui.TextInput(label="Время (ЧЧ:ММ)", default=dt.strftime("%H:%M"), max_length=5)
        for item in (self.title_in, self.desc_in, self.date_in, self.time_in):
            self.add_item(item)

    async def on_submit(self, interaction):
        dt = parse_datetime(str(self.date_in), str(self.time_in))
        if dt is None:
            await interaction.response.send_message(
                embed=embeds.err("Не понял дату или время. Формат: `25.11.2026` и `19:00`."), ephemeral=True
            )
            return
        await self.cog.bot.db.execute(
            "UPDATE wipe_events SET title=?, description=?, ts=?, reminded=0 WHERE message_id=?",
            (str(self.title_in), str(self.desc_in), int(dt.timestamp()), self.ev_id),
        )
        await interaction.response.defer()
        await self.cog.refresh_message(self.message, self.ev_id)


class WipeView(discord.ui.View):
    def __init__(self, closed=False):
        super().__init__(timeout=None)
        if closed:
            for child in self.children:
                if getattr(child, "custom_id", None) != "vex:wipe:settings":
                    child.disabled = True

    @discord.ui.button(label="Приду", emoji="✅", style=discord.ButtonStyle.success, custom_id="vex:wipe:accepted")
    async def accept(self, interaction, button):
        await interaction.client.get_cog("Wipe").handle_response(interaction, "accepted")

    @discord.ui.button(label="Не приду", emoji="❌", style=discord.ButtonStyle.danger, custom_id="vex:wipe:declined")
    async def decline(self, interaction, button):
        await interaction.client.get_cog("Wipe").handle_response(interaction, "declined")

    @discord.ui.button(label="Опоздаю", emoji="🕒", style=discord.ButtonStyle.secondary, custom_id="vex:wipe:late")
    async def late(self, interaction, button):
        await interaction.client.get_cog("Wipe").handle_response(interaction, "late")

    @discord.ui.button(emoji="📝", style=discord.ButtonStyle.secondary, custom_id="vex:wipe:edit")
    async def edit(self, interaction, button):
        await interaction.client.get_cog("Wipe").handle_edit(interaction)

    @discord.ui.button(emoji="⚙️", style=discord.ButtonStyle.primary, custom_id="vex:wipe:settings")
    async def settings(self, interaction, button):
        await interaction.client.get_cog("Wipe").handle_settings(interaction)


class SettingsView(discord.ui.View):
    def __init__(self, cog, ev_id, message):
        super().__init__(timeout=120)
        self.cog = cog
        self.ev_id = ev_id
        self.message = message

    @discord.ui.button(label="Закрыть / открыть приём", emoji="🔒", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction, button):
        ev = await self.cog.get_event(self.ev_id)
        new_state = 0 if ev["closed"] else 1
        await self.cog.bot.db.execute("UPDATE wipe_events SET closed=? WHERE message_id=?",
                                      (new_state, self.ev_id))
        await self.cog.refresh_message(self.message, self.ev_id)
        text = "Приём ответов закрыт." if new_state else "Приём ответов снова открыт."
        await interaction.response.edit_message(embed=embeds.ok(text), view=None)

    @discord.ui.button(label="Напомнить не ответившим", emoji="🔔", style=discord.ButtonStyle.primary)
    async def remind(self, interaction, button):
        ev = await self.cog.get_event(self.ev_id)
        pending = await self.cog.pending_members(interaction.guild, self.message.channel, ev)
        if not pending:
            await interaction.response.edit_message(embed=embeds.ok("Все уже ответили."), view=None)
            return
        await interaction.response.edit_message(
            embed=embeds.ok(f"Напоминаю {len(pending)} участникам."), view=None
        )
        for chunk in chunk_mentions(pending):
            await self.message.reply(
                f"🔔 Отметьтесь, пожалуйста, под событием!\n{chunk}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )

    @discord.ui.button(label="Удалить событие", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        db = self.cog.bot.db
        await db.execute("DELETE FROM wipe_responses WHERE message_id=?", (self.ev_id,))
        await db.execute("DELETE FROM wipe_events WHERE message_id=?", (self.ev_id,))
        try:
            await self.message.delete()
        except discord.HTTPException:
            pass
        await interaction.response.edit_message(embed=embeds.ok("Событие удалено."), view=None)


# --------------------------------------------------------------------------- модуль
class Wipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(WipeView())
        self.reminder_loop.start()

    async def cog_unload(self):
        self.reminder_loop.cancel()

    # ---- данные
    async def get_event(self, message_id):
        return await self.bot.db.fetchone("SELECT * FROM wipe_events WHERE message_id=?", (message_id,))

    async def get_rows(self, message_id):
        return await self.bot.db.fetchall(
            "SELECT user_id, status, reason FROM wipe_responses WHERE message_id=? ORDER BY rowid",
            (message_id,),
        )

    async def save_response(self, message_id, user_id, status, reason):
        await self.bot.db.execute(
            "INSERT INTO wipe_responses(message_id, user_id, status, reason) VALUES(?,?,?,?) "
            "ON CONFLICT(message_id, user_id) DO UPDATE SET status=excluded.status, reason=excluded.reason",
            (message_id, user_id, status, reason or None),
        )

    async def refresh_message(self, message, message_id):
        ev = await self.get_event(message_id)
        if ev is None:
            return
        rows = await self.get_rows(message_id)
        try:
            await message.edit(embed=build_embed(ev, rows), view=WipeView(closed=bool(ev["closed"])))
        except discord.HTTPException:
            pass

    # ---- действия для сайта
    async def fetch_event_message(self, ev):
        channel = self.bot.get_channel(ev["channel_id"])
        if channel is None:
            return None
        try:
            return await channel.fetch_message(ev["message_id"])
        except discord.HTTPException:
            return None

    async def set_closed(self, message_id, closed):
        await self.bot.db.execute("UPDATE wipe_events SET closed=? WHERE message_id=?", (int(closed), message_id))
        ev = await self.get_event(message_id)
        message = await self.fetch_event_message(ev) if ev else None
        if message:
            await self.refresh_message(message, message_id)

    async def delete_event(self, message_id):
        ev = await self.get_event(message_id)
        message = await self.fetch_event_message(ev) if ev else None
        await self.bot.db.execute("DELETE FROM wipe_responses WHERE message_id=?", (message_id,))
        await self.bot.db.execute("DELETE FROM wipe_events WHERE message_id=?", (message_id,))
        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

    async def remind_pending(self, message_id):
        """Упоминает не ответивших под событием. Возвращает, скольким напомнили."""
        ev = await self.get_event(message_id)
        message = await self.fetch_event_message(ev) if ev else None
        if message is None:
            return 0
        pending = await self.pending_members(message.guild, message.channel, ev)
        for chunk in chunk_mentions(pending):
            await message.reply(
                f"🔔 Отметьтесь, пожалуйста, под событием!\n{chunk}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        return len(pending)

    async def can_manage(self, member, ev):
        return member.id == ev["creator_id"] or await member_has_access(self.bot, member, "wipe")

    async def pending_members(self, guild, channel, ev, role=None):
        rows = await self.get_rows(ev["message_id"]) if ev else []
        responded = {r["user_id"] for r in rows}
        if role is None and ev and ev["ping_role_id"]:
            role = guild.get_role(ev["ping_role_id"])
        base = role.members if role else channel.members
        return [m for m in base if not m.bot and m.id not in responded]

    # ---- кнопки
    async def handle_response(self, interaction, status):
        ev = await self.get_event(interaction.message.id)
        if ev is None:
            await interaction.response.send_message(
                embed=embeds.err("Это событие уже не отслеживается."), ephemeral=True
            )
            return
        if ev["closed"]:
            await interaction.response.send_message(
                embed=embeds.warn("Приём ответов закрыт."), ephemeral=True
            )
            return

        existing = await self.bot.db.fetchone(
            "SELECT status FROM wipe_responses WHERE message_id=? AND user_id=?",
            (ev["message_id"], interaction.user.id),
        )
        if existing and existing["status"] == status:  # повторное нажатие снимает ответ
            await self.bot.db.execute(
                "DELETE FROM wipe_responses WHERE message_id=? AND user_id=?",
                (ev["message_id"], interaction.user.id),
            )
        elif status != "accepted" and ev["ask_reason"]:
            await interaction.response.send_modal(ReasonModal(self, ev, status, interaction.message))
            return
        else:
            await self.save_response(ev["message_id"], interaction.user.id, status, None)

        rows = await self.get_rows(ev["message_id"])
        await interaction.response.edit_message(embed=build_embed(ev, rows), view=WipeView())

    async def handle_edit(self, interaction):
        ev = await self.get_event(interaction.message.id)
        if ev is None:
            await interaction.response.send_message(embed=embeds.err("Событие не найдено."), ephemeral=True)
            return
        if not await self.can_manage(interaction.user, ev):
            await interaction.response.send_message(
                embed=embeds.err("Редактировать может автор события или модерация."), ephemeral=True
            )
            return
        await interaction.response.send_modal(EditModal(self, ev, interaction.message))

    async def handle_settings(self, interaction):
        ev = await self.get_event(interaction.message.id)
        if ev is None:
            await interaction.response.send_message(embed=embeds.err("Событие не найдено."), ephemeral=True)
            return
        if not await self.can_manage(interaction.user, ev):
            await interaction.response.send_message(
                embed=embeds.err("Настройки доступны автору события и модерации."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=embeds.info("Что сделать с событием?", "⚙️ Настройки события"),
            view=SettingsView(self, ev["message_id"], interaction.message),
            ephemeral=True,
        )

    # ---- напоминание за 15 минут
    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        try:
            now = int(now_ts())
            events = await self.bot.db.fetchall(
                "SELECT * FROM wipe_events WHERE closed=0 AND reminded=0 AND ts > ? AND ts <= ?",
                (now, now + REMIND_BEFORE),
            )
            for ev in events:
                await self.bot.db.execute(
                    "UPDATE wipe_events SET reminded=1 WHERE message_id=?", (ev["message_id"],)
                )
                channel = self.bot.get_channel(ev["channel_id"])
                if channel is None:
                    continue
                rows = await self.get_rows(ev["message_id"])
                ids = [r["user_id"] for r in rows if r["status"] in ("accepted", "late")]
                if not ids:
                    continue
                embed = embeds.make(
                    f"⏰ Скоро начало: {ev['title']}",
                    f"Старт <t:{ev['ts']}:R>. Все, кто отметился, — на связь!",
                )
                mentions = " ".join(f"<@{i}>" for i in ids)[:1900]
                await channel.send(
                    content=mentions, embed=embed, allowed_mentions=discord.AllowedMentions(users=True)
                )
        except Exception:  # цикл не должен умирать из-за одной ошибки
            import logging

            logging.getLogger("vex").exception("Ошибка в цикле напоминаний")

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    # ---- команды
    @app_commands.command(name="wipereact", description="Создать событие с реакциями (вайп, рейд, сбор)")
    @app_commands.describe(
        title="Название события",
        description="Описание (\\n — перенос строки)",
        date="Дата: ДД.ММ.ГГГГ или ДД.ММ",
        time="Время: ЧЧ:ММ",
        ask_for_reason="Спрашивать причину при «Не приду» и «Опоздаю»",
        server="Сервер Rust / IP (необязательно)",
        ping_role="Роль, которую упомянуть в сообщении (необязательно)",
    )
    @app_commands.guild_only()
    @access("wipe")
    async def wipereact(self, interaction: discord.Interaction,
                        title: app_commands.Range[str, 1, 100],
                        description: str,
                        date: str, time: str,
                        ask_for_reason: bool = False,
                        server: str | None = None,
                        ping_role: discord.Role | None = None):
        dt = parse_datetime(date, time)
        if dt is None:
            await interaction.response.send_message(
                embed=embeds.err("Не понял дату или время. Пример: дата `25.11.2026`, время `19:00`."),
                ephemeral=True,
            )
            return
        if dt < datetime.now(TZ):
            await interaction.response.send_message(
                embed=embeds.err("Эта дата уже в прошлом."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        ev = {
            "title": title,
            "description": description.replace("\\n", "\n")[:1000],
            "server": server[:200] if server else None,
            "ts": int(dt.timestamp()),
            "closed": 0,
            "creator_name": interaction.user.display_name,
        }
        try:
            message = await interaction.channel.send(
                content=ping_role.mention if ping_role else None,
                embed=build_embed(ev, []),
                view=WipeView(),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=embeds.err("У меня нет прав писать в этот канал."), ephemeral=True
            )
            return

        await self.bot.db.execute(
            "INSERT INTO wipe_events(message_id, guild_id, channel_id, creator_id, creator_name, title, "
            "description, server, ts, ask_reason, ping_role_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (message.id, interaction.guild.id, message.channel.id, interaction.user.id,
             ev["creator_name"], ev["title"], ev["description"], ev["server"], ev["ts"],
             int(ask_for_reason), ping_role.id if ping_role else None),
        )
        await interaction.followup.send(embed=embeds.ok("Событие создано."), ephemeral=True)

    @app_commands.command(name="noreact", description="Показать, кто не отреагировал на сообщение")
    @app_commands.describe(
        message="Ссылка на сообщение или его ID",
        role="Проверять только участников этой роли (по умолчанию — все, кто видит канал)",
        ping="Сразу упомянуть всех не ответивших",
    )
    @app_commands.guild_only()
    @access("wipe")
    async def noreact(self, interaction: discord.Interaction, message: str,
                      role: discord.Role | None = None, ping: bool = False):
        guild = interaction.guild
        match = LINK_RE.search(message)
        if match:
            channel_id, message_id = int(match.group(1)), int(match.group(2))
        elif message.strip().isdigit():
            channel_id, message_id = None, int(message.strip())
        else:
            await interaction.response.send_message(
                embed=embeds.err("Пришли ссылку на сообщение или его ID."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=not ping)

        ev = await self.get_event(message_id)
        if channel_id is None:
            channel_id = ev["channel_id"] if ev else interaction.channel.id
        channel = guild.get_channel_or_thread(channel_id)
        if channel is None:
            await interaction.followup.send(embed=embeds.err("Не нашёл такой канал."), ephemeral=True)
            return
        try:
            target = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden):
            await interaction.followup.send(
                embed=embeds.err("Не нашёл сообщение. Если оно в другом канале — пришли ссылку."),
                ephemeral=True,
            )
            return

        if ev:
            missing = await self.pending_members(guild, channel, ev, role)
        else:
            responded = set()
            for reaction in target.reactions:
                async for user in reaction.users():
                    responded.add(user.id)
            base = role.members if role else channel.members
            missing = [m for m in base if not m.bot and m.id not in responded]

        if not missing:
            await interaction.followup.send(embed=embeds.ok("Все уже отреагировали 🎉"))
            return

        if ping:
            chunks = chunk_mentions(missing)
            await interaction.followup.send(
                content=f"🔔 Не отреагировали ({len(missing)}) — отметьтесь здесь: {target.jump_url}\n{chunks[0]}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            for chunk in chunks[1:]:
                await interaction.followup.send(
                    content=chunk, allowed_mentions=discord.AllowedMentions(users=True)
                )
            return

        listing = ""
        shown = 0
        for member in missing:
            piece = member.mention + "\n"
            if len(listing) + len(piece) > 3800:
                listing += f"…и ещё {len(missing) - shown}"
                break
            listing += piece
            shown += 1
        embed = embeds.make(f"🔍 Не отреагировали ({len(missing)})", listing)
        embed.add_field(name="Сообщение", value=f"[Перейти]({target.jump_url})", inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Wipe(bot))
''',
    'vex.cogs.automod': r'''"""Автомодерация: защита от нежелательных ссылок и инвайтов."""
import logging
import re
from datetime import timedelta
from time import time as now_ts

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access

log = logging.getLogger("vex")

TLDS = (
    "com|net|org|ru|su|ua|by|kz|gg|io|me|tv|xyz|ly|cc|info|biz|pro|club|online|site|link|"
    "store|shop|app|dev|fun|top|vip|ws|gl|gd"
)
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>()\[\]]+"
    r"|(?:discord\.gg|discord(?:app)?\.com/invite)/[^\s<>()\[\]]+"
    r"|\b(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+(?:" + TLDS + r")\b(?:/[^\s<>()\[\]]*)?",
    re.IGNORECASE,
)
STRIKE_WINDOW = 10 * 60  # секунд: сколько «живёт» нарушение


def extract_host(link):
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", link.strip().lower())
    host = host.split("/")[0].split("?")[0].split("#")[0]
    host = host.split("@")[-1].split(":")[0]
    return host


def normalize_domain(text):
    return extract_host(text).strip(".")


def find_violation(content, allowed):
    """Возвращает первую запрещённую ссылку в тексте или None."""
    for match in URL_RE.finditer(content):
        raw = match.group(0)
        host = extract_host(raw)
        if not host:
            continue
        if host in ("discord.com", "discordapp.com") and "/channels/" in raw.lower():
            continue  # ссылки на сообщения Discord
        if any(host == d or host.endswith("." + d) for d in allowed):
            continue
        return raw
    return None


class AutoMod(commands.Cog):
    automod = app_commands.Group(
        name="automod", description="Автомодерация ссылок", guild_only=True
    )

    def __init__(self, bot):
        self.bot = bot
        self.strikes = {}  # (guild_id, user_id) -> [timestamps]

    # ---- данные
    async def allowed_domains(self, guild_id):
        rows = await self.bot.db.fetchall("SELECT domain FROM allowed_domains WHERE guild_id=?", (guild_id,))
        return set(config.DEFAULT_ALLOWED_DOMAINS) | {r["domain"] for r in rows}

    async def is_exempt(self, message):
        member = message.author
        perms = member.guild_permissions
        if perms.administrator or perms.manage_messages:
            return True
        guild_id = message.guild.id
        bypass = await self.bot.db.get_targets(guild_id, "automod_bypass")
        if any(role.id in bypass for role in member.roles):
            return True
        ignored = await self.bot.db.get_targets(guild_id, "automod_ignore_channel")
        return message.channel.id in ignored

    # ---- проверка сообщений
    async def check_message(self, message):
        if message.guild is None or message.author.bot or not message.content:
            return
        if not isinstance(message.author, discord.Member):
            return
        if not URL_RE.search(message.content):
            return  # дёшево отсекаем почти все сообщения без обращения к базе

        guild_id = message.guild.id
        if await self.bot.db.get_setting(guild_id, "automod_enabled", "1") == "0":
            return
        if await self.is_exempt(message):
            return
        link = find_violation(message.content, await self.allowed_domains(guild_id))
        if link is None:
            return
        await self.punish(message, link)

    async def punish(self, message, link):
        guild = message.guild
        member = message.author
        db = self.bot.db

        deleted = True
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            deleted = False

        max_strikes = int(await db.get_setting(guild.id, "automod_strikes", "3"))
        timeout_minutes = int(await db.get_setting(guild.id, "automod_timeout", "10"))
        key = (guild.id, member.id)
        now = now_ts()
        history = [t for t in self.strikes.get(key, []) if now - t < STRIKE_WINDOW] + [now]
        self.strikes[key] = history

        await db.execute(
            "INSERT INTO automod_log(guild_id, user_id, channel_id, link, ts) VALUES(?,?,?,?,?)",
            (guild.id, member.id, message.channel.id, link[:200], int(now)),
        )
        await db.execute(  # храним последние 200 записей на сервер
            "DELETE FROM automod_log WHERE guild_id=? AND id NOT IN "
            "(SELECT id FROM automod_log WHERE guild_id=? ORDER BY id DESC LIMIT 200)",
            (guild.id, guild.id),
        )

        action = "Сообщение удалено" if deleted else "❗ Не удалось удалить (нет прав Manage Messages)"
        timed_out = False
        if len(history) >= max_strikes and timeout_minutes > 0:
            try:
                await member.timeout(timedelta(minutes=timeout_minutes), reason="VEX AutoMod: ссылки")
                timed_out = True
                self.strikes.pop(key, None)
                action += f" • тайм-аут на {timeout_minutes} мин."
            except (discord.Forbidden, discord.HTTPException):
                action += " • тайм-аут выдать не удалось (роль бота ниже участника)"

        try:
            warning = embeds.warn(
                f"{member.mention}, отправка ссылок здесь запрещена.\n"
                "Если ссылка нужна — напиши модераторам или открой тикет.",
                "Ссылка удалена",
            )
            if timed_out:
                warning.add_field(name="Наказание", value=f"Тайм-аут на {timeout_minutes} мин.")
            await message.channel.send(embed=warning, delete_after=10)
        except discord.HTTPException:
            pass

        log_embed = embeds.make("🛡️ AutoMod: нежелательная ссылка", color=config.COLOR_WARN)
        log_embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Канал", value=message.channel.mention, inline=True)
        log_embed.add_field(name="Ссылка", value=f"`{link[:200]}`", inline=False)
        log_embed.add_field(name="Действие", value=action, inline=False)
        log_embed.add_field(name="Нарушений за 10 мин", value=str(len(history)), inline=True)
        await self.bot.send_log(guild, log_embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.check_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await self.check_message(after)

    # ---- команды
    @automod.command(name="status", description="Текущие настройки автомодерации")
    @access("automod")
    async def status(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        db = self.bot.db
        enabled = await db.get_setting(gid, "automod_enabled", "1") != "0"
        strikes = await db.get_setting(gid, "automod_strikes", "3")
        timeout = await db.get_setting(gid, "automod_timeout", "10")
        domains = sorted(await self.allowed_domains(gid))
        bypass = await db.get_targets(gid, "automod_bypass")
        ignored = await db.get_targets(gid, "automod_ignore_channel")
        embed = embeds.make("🛡️ Автомодерация ссылок")
        embed.add_field(name="Состояние", value="🟢 Включена" if enabled else "🔴 Выключена", inline=True)
        embed.add_field(name="Тайм-аут", value=f"после {strikes} нарушений • {timeout} мин.", inline=True)
        embed.add_field(name="Разрешённые домены", value="\n".join(f"`{d}`" for d in domains)[:1000] or "—",
                        inline=False)
        embed.add_field(name="Игнорируемые роли",
                        value=" ".join(f"<@&{r}>" for r in bypass) or "— (модераторы с Manage Messages и админы не проверяются)",
                        inline=False)
        embed.add_field(name="Игнорируемые каналы", value=" ".join(f"<#{c}>" for c in ignored) or "—",
                        inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod.command(name="toggle", description="Включить или выключить автомодерацию")
    @app_commands.describe(enabled="True — включить, False — выключить")
    @access("automod")
    async def toggle(self, interaction: discord.Interaction, enabled: bool):
        await self.bot.db.set_setting(interaction.guild.id, "automod_enabled", "1" if enabled else "0")
        text = "Автомодерация включена." if enabled else "Автомодерация выключена."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @automod.command(name="allow", description="Разрешить домен (например youtube.com)")
    @app_commands.describe(domain="Домен или ссылка")
    @access("automod")
    async def allow(self, interaction: discord.Interaction, domain: str):
        domain = normalize_domain(domain)
        if "." not in domain:
            await interaction.response.send_message(embed=embeds.err("Это не похоже на домен."), ephemeral=True)
            return
        changed = await self.bot.db.execute(
            "INSERT OR IGNORE INTO allowed_domains(guild_id, domain) VALUES(?,?)", (interaction.guild.id, domain)
        )
        text = f"`{domain}` разрешён (вместе с поддоменами)." if changed else f"`{domain}` уже разрешён."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @automod.command(name="disallow", description="Убрать домен из разрешённых")
    @app_commands.describe(domain="Домен или ссылка")
    @access("automod")
    async def disallow(self, interaction: discord.Interaction, domain: str):
        domain = normalize_domain(domain)
        changed = await self.bot.db.execute(
            "DELETE FROM allowed_domains WHERE guild_id=? AND domain=?", (interaction.guild.id, domain)
        )
        if changed:
            text = f"`{domain}` больше не разрешён."
        elif domain in config.DEFAULT_ALLOWED_DOMAINS:
            text = f"`{domain}` — встроенный домен, его можно изменить только в `vex/config.py`."
        else:
            text = f"`{domain}` не был в списке."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @automod.command(name="bypass", description="Роль, которую автомодерация не проверяет")
    @app_commands.describe(role="Роль", enabled="True — не проверять, False — снова проверять")
    @access("automod")
    async def bypass(self, interaction: discord.Interaction, role: discord.Role, enabled: bool = True):
        gid = interaction.guild.id
        if enabled:
            await self.bot.db.add_target(gid, "automod_bypass", role.id)
            text = f"{role.mention} теперь не проверяется."
        else:
            await self.bot.db.remove_target(gid, "automod_bypass", role.id)
            text = f"{role.mention} снова проверяется."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @automod.command(name="ignore_channel", description="Канал, где ссылки разрешены")
    @app_commands.describe(channel="Канал", enabled="True — разрешить ссылки, False — снова проверять")
    @access("automod")
    async def ignore_channel(self, interaction: discord.Interaction, channel: discord.TextChannel,
                             enabled: bool = True):
        gid = interaction.guild.id
        if enabled:
            await self.bot.db.add_target(gid, "automod_ignore_channel", channel.id)
            text = f"В {channel.mention} ссылки разрешены."
        else:
            await self.bot.db.remove_target(gid, "automod_ignore_channel", channel.id)
            text = f"В {channel.mention} ссылки снова проверяются."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @automod.command(name="punishment", description="Сколько нарушений до тайм-аута и на сколько минут")
    @app_commands.describe(strikes="Нарушений за 10 минут до тайм-аута",
                           timeout_minutes="Длительность тайм-аута в минутах (0 — не выдавать)")
    @access("automod")
    async def punishment(self, interaction: discord.Interaction, strikes: app_commands.Range[int, 1, 10],
                         timeout_minutes: app_commands.Range[int, 0, 1440]):
        gid = interaction.guild.id
        await self.bot.db.set_setting(gid, "automod_strikes", strikes)
        await self.bot.db.set_setting(gid, "automod_timeout", timeout_minutes)
        text = (f"После **{strikes}** нарушений за 10 минут — тайм-аут на **{timeout_minutes}** мин."
                if timeout_minutes else "Тайм-ауты отключены, ссылки только удаляются.")
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
''',
    'vex.cogs.roles': r'''"""Роли: выдача/снятие командой с проверкой иерархии и авто-выдача при заходе."""
import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access, is_admin

TARGET_CHOICES = [
    app_commands.Choice(name="Участники", value="member"),
    app_commands.Choice(name="Боты", value="bot"),
]


class RoleTools(commands.Cog):
    role = app_commands.Group(name="role", description="Управление ролями", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

    async def check_assignable(self, interaction, member, role):
        """Текст ошибки или None, если менять эту роль можно."""
        guild = interaction.guild
        invoker = interaction.user
        if role.is_default():
            return "Роль @everyone менять нельзя."
        if role.managed:
            return "Эта роль управляется интеграцией (ботом или бустом) — вручную её не выдать."
        if role >= guild.me.top_role:
            return f"Роль {role.mention} выше моей высшей роли или равна ей. Подними роль VEX в настройках сервера."
        if is_admin(invoker):
            return None
        if role >= invoker.top_role:
            return "Эта роль не ниже твоей высшей роли — выдавать её нельзя."
        if member.id != invoker.id and member.top_role >= invoker.top_role:
            return "Нельзя менять роли участника, который не ниже тебя по иерархии."
        perms = role.permissions
        if perms.administrator or perms.manage_roles or perms.manage_guild:
            return "Роли с опасными правами может выдавать только администратор."
        allowed = await self.bot.db.get_targets(guild.id, "manageable")
        if allowed and role.id not in allowed:
            return "Эта роль не входит в список ролей, которые разрешено выдавать (`/role allowed`)."
        return None

    async def _change(self, interaction, member, role, reason, give):
        error = await self.check_assignable(interaction, member, role)
        if error:
            await interaction.response.send_message(embed=embeds.err(error), ephemeral=True)
            return
        has_role = role in member.roles
        if give and has_role:
            await interaction.response.send_message(
                embed=embeds.info(f"У {member.mention} уже есть {role.mention}."), ephemeral=True
            )
            return
        if not give and not has_role:
            await interaction.response.send_message(
                embed=embeds.info(f"У {member.mention} нет роли {role.mention}."), ephemeral=True
            )
            return

        audit = f"{interaction.user} через VEX" + (f": {reason}" if reason else "")
        try:
            if give:
                await member.add_roles(role, reason=audit)
            else:
                await member.remove_roles(role, reason=audit)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=embeds.err("У меня не хватает прав (Manage Roles) или роль выше моей."), ephemeral=True
            )
            return

        verb = "выдана" if give else "снята"
        text = f"Роль {role.mention} {verb}: {member.mention}"
        await interaction.response.send_message(
            embed=embeds.ok(text), allowed_mentions=discord.AllowedMentions.none()
        )

        log = embeds.make(f"🎭 Роль {verb}", color=config.COLOR_MAIN)
        log.add_field(name="Участник", value=member.mention, inline=True)
        log.add_field(name="Роль", value=role.mention, inline=True)
        log.add_field(name="Кто", value=interaction.user.mention, inline=True)
        if reason:
            log.add_field(name="Причина", value=reason[:500], inline=False)
        await self.bot.send_log(interaction.guild, log)

    @role.command(name="add", description="Выдать роль участнику")
    @app_commands.describe(member="Кому", role="Какую роль", reason="Причина (попадёт в журнал аудита)")
    @access("role")
    async def add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role,
                  reason: str | None = None):
        await self._change(interaction, member, role, reason, give=True)

    @role.command(name="remove", description="Снять роль с участника")
    @app_commands.describe(member="С кого", role="Какую роль", reason="Причина (попадёт в журнал аудита)")
    @access("role")
    async def remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role,
                     reason: str | None = None):
        await self._change(interaction, member, role, reason, give=False)

    @role.command(name="allow", description="Разрешить модераторам выдавать эту роль")
    @app_commands.describe(role="Роль")
    @access("role_admin")
    async def allow(self, interaction: discord.Interaction, role: discord.Role):
        added = await self.bot.db.add_target(interaction.guild.id, "manageable", role.id)
        text = f"{role.mention} добавлена в список выдаваемых." if added else f"{role.mention} уже в списке."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @role.command(name="deny", description="Убрать роль из списка выдаваемых")
    @app_commands.describe(role="Роль")
    @access("role_admin")
    async def deny(self, interaction: discord.Interaction, role: discord.Role):
        removed = await self.bot.db.remove_target(interaction.guild.id, "manageable", role.id)
        text = f"{role.mention} убрана из списка." if removed else f"{role.mention} не была в списке."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @role.command(name="allowed", description="Список ролей, которые разрешено выдавать")
    @access("role_admin")
    async def allowed(self, interaction: discord.Interaction):
        ids = await self.bot.db.get_targets(interaction.guild.id, "manageable")
        if ids:
            text = "\n".join(f"• <@&{i}>" for i in ids)
        else:
            text = ("Список пуст — модераторы могут выдавать любые роли ниже своей "
                    "(кроме ролей с опасными правами).")
        await interaction.response.send_message(embed=embeds.info(text, "🎭 Выдаваемые роли"), ephemeral=True)


class AutoRole(commands.Cog):
    autorole = app_commands.Group(name="autorole", description="Авто-выдача ролей при заходе", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

    async def apply(self, member):
        kind = "autorole_bot" if member.bot else "autorole_member"
        ids = await self.bot.db.get_targets(member.guild.id, kind)
        me = member.guild.me
        roles = []
        for role_id in ids:
            role = member.guild.get_role(role_id)
            if role and not role.managed and role < me.top_role and role not in member.roles:
                roles.append(role)
        if not roles:
            return
        try:
            await member.add_roles(*roles, reason="VEX: авто-выдача ролей")
        except discord.HTTPException:
            return
        log = embeds.make("🎭 Авто-роль выдана", color=config.COLOR_MAIN)
        log.add_field(name="Участник", value=member.mention, inline=True)
        log.add_field(name="Роли", value=" ".join(r.mention for r in roles), inline=True)
        await self.bot.send_log(member.guild, log)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.pending:  # если включена проверка (screening) — ждём её завершения
            await self.apply(member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.pending and not after.pending:
            await self.apply(after)

    @autorole.command(name="add", description="Добавить роль, выдаваемую при заходе")
    @app_commands.describe(role="Роль", target="Кому выдавать")
    @app_commands.choices(target=TARGET_CHOICES)
    @access("autorole")
    async def add(self, interaction: discord.Interaction, role: discord.Role,
                  target: app_commands.Choice[str]):
        if role.managed or role.is_default() or role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                embed=embeds.err("Эту роль я выдать не смогу: она выше моей, управляется интеграцией или это @everyone."),
                ephemeral=True,
            )
            return
        kind = "autorole_bot" if target.value == "bot" else "autorole_member"
        added = await self.bot.db.add_target(interaction.guild.id, kind, role.id)
        text = (f"{role.mention} будет выдаваться при заходе ({target.name.lower()})."
                if added else f"{role.mention} уже в списке.")
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @autorole.command(name="remove", description="Убрать роль из авто-выдачи")
    @app_commands.describe(role="Роль", target="Кому выдавалась")
    @app_commands.choices(target=TARGET_CHOICES)
    @access("autorole")
    async def remove(self, interaction: discord.Interaction, role: discord.Role,
                     target: app_commands.Choice[str]):
        kind = "autorole_bot" if target.value == "bot" else "autorole_member"
        removed = await self.bot.db.remove_target(interaction.guild.id, kind, role.id)
        text = f"{role.mention} убрана из авто-выдачи." if removed else f"{role.mention} не была в списке."
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @autorole.command(name="list", description="Какие роли выдаются при заходе")
    @access("autorole")
    async def list_roles(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        members = await self.bot.db.get_targets(gid, "autorole_member")
        bots = await self.bot.db.get_targets(gid, "autorole_bot")
        embed = embeds.make("🎭 Авто-выдача ролей")
        embed.add_field(name="Участникам", value=" ".join(f"<@&{i}>" for i in members) or "—", inline=False)
        embed.add_field(name="Ботам", value=" ".join(f"<@&{i}>" for i in bots) or "—", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(RoleTools(bot))
    await bot.add_cog(AutoRole(bot))
''',
    'vex.cogs.staff': r'''"""Сообщения от имени бота (анонимно для участников)."""
import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access


class SayModal(discord.ui.Modal):
    def __init__(self, cog, channel, use_embed, reply_to, attachment):
        super().__init__(title="Сообщение от имени VEX")
        self.cog = cog
        self.channel = channel
        self.use_embed = use_embed
        self.reply_to = reply_to
        self.attachment = attachment
        self.heading = None
        if use_embed:
            self.heading = discord.ui.TextInput(
                label="Заголовок (необязательно)", required=False, max_length=256
            )
            self.add_item(self.heading)
        self.body = discord.ui.TextInput(
            label="Текст сообщения",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000 if use_embed else 2000,
        )
        self.add_item(self.body)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        text = str(self.body)

        file = None
        if self.attachment is not None:
            try:
                file = await self.attachment.to_file()
            except discord.HTTPException:
                file = None

        reference = None
        if self.reply_to:
            try:
                reference = await self.channel.fetch_message(self.reply_to)
            except (discord.NotFound, discord.Forbidden):
                reference = None

        mentions = discord.AllowedMentions(users=True, roles=True, everyone=False, replied_user=False)
        try:
            if self.use_embed:
                # без подписи и футера — выглядит как официальное сообщение от бота
                embed = discord.Embed(description=text, color=config.COLOR_MAIN)
                heading = str(self.heading) if self.heading else ""
                if heading:
                    embed.title = heading
                if file is not None and (self.attachment.content_type or "").startswith("image/"):
                    embed.set_image(url=f"attachment://{file.filename}")
                sent = await self.channel.send(
                    embed=embed, file=file, reference=reference, allowed_mentions=mentions
                )
            else:
                sent = await self.channel.send(
                    content=text, file=file, reference=reference, allowed_mentions=mentions
                )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=embeds.err(f"У меня нет прав писать в {self.channel.mention}."), ephemeral=True
            )
            return

        # Для участников сообщение анонимно, но в закрытый лог-канал модерации записывается, кто его отправил.
        log = embeds.make("🕵️ Сообщение от имени бота", color=config.COLOR_MAIN)
        log.add_field(name="Отправил", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        log.add_field(name="Канал", value=self.channel.mention, inline=True)
        log.add_field(name="Сообщение", value=f"[Перейти]({sent.jump_url})", inline=True)
        log.add_field(name="Текст", value=text[:1000], inline=False)
        await self.cog.bot.send_log(interaction.guild, log)

        await interaction.followup.send(
            embed=embeds.ok(f"Отправлено в {self.channel.mention}."), ephemeral=True
        )


class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="say", description="Отправить сообщение от имени бота")
    @app_commands.describe(
        channel="Куда отправить (по умолчанию — текущий канал)",
        embed="Оформить красивым эмбедом",
        reply_to="ID сообщения, на которое ответить",
        attachment="Прикрепить файл или картинку",
    )
    @app_commands.guild_only()
    @access("say")
    async def say(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None,
                  embed: bool = False, reply_to: str | None = None,
                  attachment: discord.Attachment | None = None):
        channel = channel or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=embeds.err("Писать можно только в текстовые каналы."), ephemeral=True
            )
            return
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                embed=embeds.err(f"У меня нет прав писать в {channel.mention}."), ephemeral=True
            )
            return
        reply_id = None
        if reply_to:
            if not reply_to.strip().isdigit():
                await interaction.response.send_message(
                    embed=embeds.err("`reply_to` — это числовой ID сообщения."), ephemeral=True
                )
                return
            reply_id = int(reply_to.strip())
        await interaction.response.send_modal(SayModal(self, channel, embed, reply_id, attachment))


async def setup(bot):
    await bot.add_cog(Staff(bot))
''',
    'vex.cogs.admin': r'''"""Администрирование: доступ к командам по ролям (/perms), настройки (/config), логи, приветствие, /help."""
import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import admin_only

KEY_CHOICES = [
    app_commands.Choice(name=f"{key} — {desc}"[:100], value=key)
    for key, desc in config.COMMAND_KEYS.items()
]

DEFAULT_WELCOME = (
    "Привет, {user}! Добро пожаловать на **{server}**.\n"
    "Загляни в правила, а если хочешь вступить в клан — открой тикет."
)


class Permissions(commands.Cog):
    perms = app_commands.Group(
        name="perms",
        description="Какие роли имеют доступ к каким командам бота",
        guild_only=True,
        default_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot):
        self.bot = bot

    @perms.command(name="grant", description="Дать роли доступ к группе команд")
    @app_commands.describe(command="Группа команд", role="Роль")
    @app_commands.choices(command=KEY_CHOICES)
    @admin_only()
    async def grant(self, interaction: discord.Interaction, command: app_commands.Choice[str],
                    role: discord.Role):
        added = await self.bot.db.add_target(interaction.guild.id, f"cmd:{command.value}", role.id)
        text = (f"{role.mention} теперь имеет доступ: **{command.value}**."
                if added else f"{role.mention} уже имеет доступ к **{command.value}**.")
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @perms.command(name="revoke", description="Забрать у роли доступ к группе команд")
    @app_commands.describe(command="Группа команд", role="Роль")
    @app_commands.choices(command=KEY_CHOICES)
    @admin_only()
    async def revoke(self, interaction: discord.Interaction, command: app_commands.Choice[str],
                     role: discord.Role):
        removed = await self.bot.db.remove_target(interaction.guild.id, f"cmd:{command.value}", role.id)
        text = (f"У {role.mention} больше нет доступа к **{command.value}**."
                if removed else f"У {role.mention} и не было доступа к **{command.value}**.")
        await interaction.response.send_message(embed=embeds.ok(text), ephemeral=True)

    @perms.command(name="reset", description="Сбросить доступ группы команд (останутся только администраторы)")
    @app_commands.describe(command="Группа команд")
    @app_commands.choices(command=KEY_CHOICES)
    @admin_only()
    async def reset(self, interaction: discord.Interaction, command: app_commands.Choice[str]):
        await self.bot.db.clear_targets(interaction.guild.id, f"cmd:{command.value}")
        await interaction.response.send_message(
            embed=embeds.ok(f"Доступ к **{command.value}** сброшен — только администраторы."), ephemeral=True
        )

    @perms.command(name="list", description="Показать, кто к чему имеет доступ")
    @admin_only()
    async def list_perms(self, interaction: discord.Interaction):
        embed = embeds.make("🔐 Доступ к командам", "Администраторы имеют доступ ко всему.")
        for key, desc in config.COMMAND_KEYS.items():
            ids = await self.bot.db.get_targets(interaction.guild.id, f"cmd:{key}")
            roles = " ".join(f"<@&{i}>" for i in ids) or "*только администраторы*"
            embed.add_field(name=f"`{key}`", value=f"{desc}\n└ {roles}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ServerConfig(commands.Cog):
    config_group = app_commands.Group(
        name="config",
        description="Настройки бота на сервере",
        guild_only=True,
        default_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot):
        self.bot = bot

    # ---- команды
    @config_group.command(name="log_channel", description="Канал для логов модерации и действий бота")
    @app_commands.describe(channel="Приватный канал для модераторов")
    @admin_only()
    async def log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.db.set_setting(interaction.guild.id, "mod_log", channel.id)
        await interaction.response.send_message(
            embed=embeds.ok(f"Логи будут приходить в {channel.mention}."), ephemeral=True
        )

    @config_group.command(name="welcome", description="Включить приветствие новых участников")
    @app_commands.describe(channel="Канал приветствий",
                           text="Текст. Можно {user}, {server}. Пусто — стандартный")
    @admin_only()
    async def welcome(self, interaction: discord.Interaction, channel: discord.TextChannel,
                      text: str | None = None):
        gid = interaction.guild.id
        await self.bot.db.set_setting(gid, "welcome_channel", channel.id)
        if text:
            await self.bot.db.set_setting(gid, "welcome_text", text.replace("\\n", "\n"))
        else:
            await self.bot.db.del_setting(gid, "welcome_text")
        await interaction.response.send_message(
            embed=embeds.ok(f"Приветствия включены в {channel.mention}."), ephemeral=True
        )

    @config_group.command(name="welcome_off", description="Выключить приветствие")
    @admin_only()
    async def welcome_off(self, interaction: discord.Interaction):
        await self.bot.db.del_setting(interaction.guild.id, "welcome_channel")
        await interaction.response.send_message(embed=embeds.ok("Приветствия выключены."), ephemeral=True)

    @config_group.command(name="show", description="Показать текущие настройки")
    @admin_only()
    async def show(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        db = self.bot.db

        async def channel_of(key):
            value = await db.get_setting(gid, key)
            return f"<#{value}>" if value else "—"

        category = await db.get_setting(gid, "ticket_category")
        embed = embeds.make("⚙️ Настройки VEX")
        embed.add_field(name="Лог модерации", value=await channel_of("mod_log"), inline=True)
        embed.add_field(name="Лог тикетов", value=await channel_of("ticket_log"), inline=True)
        embed.add_field(name="Приветствия", value=await channel_of("welcome_channel"), inline=True)
        embed.add_field(name="Категория тикетов", value=f"<#{category}>" if category else "—", inline=True)
        embed.add_field(name="Часовой пояс", value=config.TIMEZONE, inline=True)
        embed.add_field(name="База данных", value=f"`{self.bot.db.path}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- события: приветствие и журнал входов/выходов
    @commands.Cog.listener()
    async def on_member_join(self, member):
        gid = member.guild.id
        log = embeds.make("📥 Участник зашёл", color=config.COLOR_OK)
        log.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)", inline=True)
        log.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        log.set_thumbnail(url=member.display_avatar.url)
        await self.bot.send_log(member.guild, log)

        channel_id = await self.bot.db.get_setting(gid, "welcome_channel")
        if not channel_id or member.bot:
            return
        channel = member.guild.get_channel(int(channel_id))
        if channel is None:
            return
        template = await self.bot.db.get_setting(gid, "welcome_text", DEFAULT_WELCOME)
        text = template.replace("{user}", member.mention).replace("{server}", member.guild.name)
        embed = embeds.make("👋 Добро пожаловать!", text)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Участник №", value=str(member.guild.member_count), inline=True)
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log = embeds.make("📤 Участник вышел", color=config.COLOR_ERR)
        log.add_field(name="Участник", value=f"{member} (`{member.id}`)", inline=True)
        roles = [r.mention for r in member.roles if not r.is_default()]
        log.add_field(name="Роли", value=" ".join(roles)[:1000] or "—", inline=False)
        await self.bot.send_log(member.guild, log)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Что умеет VEX")
    async def help(self, interaction: discord.Interaction):
        embed = embeds.make(
            "🟣 VEX — управление кланом",
            "Бот для организации клана: тикеты, события, роли и защита сервера.",
        )
        embed.add_field(
            name="🎫 Тикеты",
            value="`/ticket panel` `/ticket setup` `/ticket support_add`\n"
                  "Внутри тикета: `/ticket add` `remove` `rename` `close`",
            inline=False,
        )
        embed.add_field(name="📝 События", value="`/wipereact` — сбор с кнопками • `/noreact` — кто не ответил",
                        inline=False)
        embed.add_field(name="🎭 Роли", value="`/role add` `/role remove` • `/autorole add` `remove` `list`",
                        inline=False)
        embed.add_field(name="🛡️ Автомодерация", value="`/automod status` `toggle` `allow` `bypass` `punishment`",
                        inline=False)
        embed.add_field(name="📣 Сообщения", value="`/say` — от имени бота", inline=False)
        embed.add_field(name="🔐 Администрирование", value="`/perms` — доступ ролей • `/config` — настройки",
                        inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Permissions(bot))
    await bot.add_cog(ServerConfig(bot))
    await bot.add_cog(Help(bot))
''',
}


class _EmbeddedFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Отдаёт модули vex.* прямо из словаря _SOURCES, без файлов на диске."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in _SOURCES:
            return None
        return importlib.util.spec_from_loader(fullname, self, is_package=fullname in _PACKAGES)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__spec__.name
        filename = name.replace(".", "/") + (".py" if name not in _PACKAGES else "/__init__.py")
        exec(compile(_SOURCES[name], filename, "exec"), module.__dict__)

    def get_source(self, fullname):  # чтобы в ошибках были видны строки кода
        return _SOURCES[fullname]


sys.meta_path.insert(0, _EmbeddedFinder())


def main():
    from vex import config
    from vex.bot import VexBot

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not config.TOKEN:
        raise SystemExit("Не задана переменная окружения DISCORD_TOKEN")
    VexBot().run(config.TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
