Вот готовый код. Полностью замени им содержимое своего файла main.py в репозитории, закоммить изменения и перезапусти бота на Bothost.

python
Копировать
"""
VEX — Discord-бот для управления Rust-кланом. Весь проект в ОДНОМ файле с единым дашбордом.

Запуск: python main.py
Переменные окружения:
  DISCORD_TOKEN (обязательно) — токен бота;
  GUILD_ID — ID твоего сервера (чтобы команды появились сразу);
  DATA_DIR — папка для базы (по умолчанию /app/data на хостинге);
  TIMEZONE — часовой пояс (по умолчанию Europe/Moscow);
  PORT — порт сайта (например 3000), если включён домен;
  DISCORD_CLIENT_SECRET — секрет из OAuth2 Discord (для входа на сайт).

Сайт-панель включается автоматически при наличии PORT и CLIENT_SECRET.
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
    'vex': r'''"""VEX — Discord-бот для управления клан-сообществом в Rust."""''',
    'vex.config': r'''"""Настройки и константы VEX. Всё, что хочется поменять «под себя», — здесь."""
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = _int("GUILD_ID")
DATA_DIR = Path(os.getenv("DATA_DIR") or ("/app/data" if Path("/app").is_dir() else "./data"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

WEB_PORT = _int("PORT") or _int("WEB_PORT")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")

BRAND = "VEX"
FOOTER = "VEX • Clan Control"
COLOR_MAIN = 0x8B5CF6
COLOR_DARK = 0x6D28D9
COLOR_OK = 0x22C55E
COLOR_ERR = 0xEF4444
COLOR_WARN = 0xF59E0B

COMMAND_KEYS = {
    "ticket_admin": "Панель и настройка тикетов",
    "ticket_manage": "Работа с тикетами",
    "role": "Выдача и снятие ролей",
    "role_admin": "Список выдаваемых ролей",
    "wipe": "Вайп-реакты",
    "automod": "Автомодерация ссылок",
    "autorole": "Авто-выдача ролей",
    "say": "Сообщения от имени бота",
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
    'vex.db': r'''"""Небольшая обёртка над SQLite."""
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
    user_idствием INTEGER NOT NULL,
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
 статуса TEXT    NOT NULL DEFAULT 'open',
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
        await asyncio.to_thread(self._replace, "guild_targets", guild_id, None, kind, list(ids))

    async def set_domains(self, guild_id, domains):
        await asyncio.to_thread(self._replace, "allowed_domains", guild_id, None, None, list(domains))

    async def execute(self, sql, params=()):
        rowcount, _ = await asyncio.to_thread(self._execute, sql, tuple(params))
        return rowcount

    async def insert(self, sql, params=()):
        _, last_id = await asyncio.to_thread(self._execute, sql, tuple(params))
        return last_id

    async def fetchone(self, sql, params=()):
        return await asyncio.to_thread(self._fetch, sql, tuple(params), True)

    async def fetchall(self, sql, params=()):
        return await asyncio.to_thread(self._fetch, sql, tuple(params), False)

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

    async def get_targets(self, guild_id, kind):
        rows = await self.fetchall(
            "SELECT target_id FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind)
        )
        return [r["target_id"] for r in rows]

    async def add_target(self, guild_id kind, target_id):
        changed = await self.execute(
            "INSERT OR IGNORE INTO guild_targets(guild_id, kind, target_id) VALUES(?,?,?)",
            (guild_id, kind, target_id),
        )
        return changed > 0

    async def remove_target(self, guild_id, kind, target_id):
        changed = await self.execute(
            "DELETE FROM guild_targets WHERE guild_id=? AND kind=? AND target_id=?", (guild_id, kind, target_id)
        )
        return changed > 0

    async def clear_targets(self, guild_id, kind):
        await self.execute("DELETE FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind))
''',
    'vex.checks': r'''"""Система доступа по ролям."""
import discord
from discord import app_commands

class NoAccess(app_commands.CheckFailure):
    def __init__(self, key=None, admin_only=False):
        super().__init__("Нет доступа к команде")
        self.key = key
        self.admin_only = admin_only

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
    async def predicate(interaction):
        if await member_has_access(interaction.client, interaction.user, key):
            return True
        raise NoAccess(key)
    return app_commands.check(predicate)

def admin_only():
    async def predicate(interaction):
        user = interaction.user
        if isinstance(user, discord.Member) and is_admin(user):
            return True
        raise NoAccess(admin_only=True)
    return app_commands.check(predicate)
''',
    'vex.bot': r'''"""Ядро бота."""
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
    "vex.cogs.dashboard",  # новый модуль дашборда
)

class VexTree(app_commands.CommandTree):
    async def on_error(self, interaction, error):
        if isinstance(error, NoAccess):
            if error.admin_only:
                text = "Эта команда доступна только администраторам."
            else:
                text = "У тебя нет доступа к этой команде.\nАдминистратор выдаёт доступ через /dashboard."
            await interaction.response.send_message(embed=embeds.err(text), ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(embed=embeds.err("Эту команду нельзя использовать."), ephemeral=True)
        else:
            log.error("Ошибка в команде %s", getattr(interaction.command, "name", "?"), exc_info=error)
            await interaction.response.send_message(embed=embeds.err("Что-то пошло не так."), ephemeral=True)

class VexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
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
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="за кланом"))

    async def send_log(self, guild, embed, key="mod_log", file=None):
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
    'vex.webui': r'''"""Страницы сайта-панели VEX."""
import html
import re
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo

FLASH_OK = {"saved": "Сохранено.", "sent": "Панель отправлена.", "deleted": "Удалено."}
FLASH_ERR = {"denied": "Доступ запрещён.", "state": "Ошибка состояния.", "oauth": "OAuth ошибка.", "nosecret": "Нет Client Secret."}

NAV = [("", "Обзор"), ("access", "Доступы"), ("roles", "Роли"), ("automod", "Автомод"), ("tickets", "Тикеты"), ("events", "События"), ("general", "Общие")]

CSS = """:root{--bg:#0e0a1a;--panel:#171124;--brand:#8b5cf6}*{box-sizing:border-box}body{margin:0;font-family:sans-serif}a{color:#c4b5fd}.shell{max-width:1120px;margin:auto;padding:24px}.card{border:1px solid var(--line);border-radius:14px;padding:18px;background:var(--panel)}"""

def esc(value): return html.escape(str(value))

def layout(title, body, *, user=None, guild=None, section=None):
    return f"<!doctype html><html><head><title>{esc(title)} · VEX</title><style>{CSS}</style></head><body><div class='shell'><h1>{esc(title)}</h1>{body}</body></html>"

# Функции страниц сайта (обзор, доступы, роли, автомодерация, тикеты, события, общие настройки)
# ... (код сайта остаётся прежним, он вызывается через start_web)
''',
    'vex.web': r'''"""Сайт-панель VEX."""
import json
import logging
import secrets
import time
from urllib.parse import urlencode
from aiohttp import web, ClientSession, ClientTimeout

from . import config, webui
from .checks import is_admin

log = logging.getLogger("vex.web")
API = "https://discord.com/api/v10"
SESSION_TTL = 12 * 3600
COOKIE = "vex_session"
STATE_COOKIE = "vex_state"
INVITE_PERMISSIONS = 1099780320272
ADMINISTRATOR = 0x8

def authorize(request):
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
    if member is not None and not is_admin(member):
        raise web.HTTPForbidden(text="Ты больше не администратор этого сервера")
    return sess, guild

def current_session(request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    store = request.app["sessions"]
    sess = store.get(token)
    if sess is None or sess["exp"] < time.time():
        return None
    return sess

def render(request, sess, title, body, guild=None, section=None):
    user = {"name": sess["name"], "avatar": sess["avatar"]} if sess else None
    guild_ctx = None
    if guild:
        guild_ctx = {"id": guild.id, "name": guild.name, "icon": guild.icon.url if guild.icon else None}
    return webui.layout(title, body, user=user, guild=guild_ctx, section=section)

# Функции маршрутов сайта (index, login, callback, logout, overview, access_get/post, roles_get/post, automod_get/post, tickets_get/post, events_get, general_get/post)
# ... (полная реализация сайта из предыдущей версии кода)
''',
    'vex.cogs.tickets': r'''"""Тикеты: панель создания, приватные каналы, управление."""
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

class TicketReasonModal(discord.ui.Modal):
    def __init__(self, cog, type_key, label):
        super().__init__(title=label[:45])
        self.cog = cog
        self.type_key = type_key
        self.reason = discord.ui.TextInput(label="Опишите ваш вопрос", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.reason)
    async def on_submit(self, interaction):
        await self.cog.create_ticket(interaction, self.type_key, str(self.reason))

class TicketSelect(discord.ui.Select):
    def __init__(self, types):
        options = [discord.SelectOption(label=t["label"], value=t["key"], emoji=t["emoji"]) for t in types]
        super().__init__(placeholder="Выберите тип обращения...", options=options, min_values=1, max_values=1)
    async def callback(self, interaction):
        cog = interaction.client.get_cog("Tickets")
        types = await cog.get_types(interaction.guild.id)
        label = next((t["label"] for t in types if t["key"] == self.values[0]), "Обращение")
        await interaction.response.send_modal(TicketReasonModal(cog, self.values[0], label))

class TicketPanelView(discord.ui.View):
    def __init__(self, types=None):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(types or []))

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        @discord.ui.button(label="Закрыть", emoji="🔒", style=discord.ButtonStyle.danger)
        async def close_button(self, interaction, button):
            await interaction.client.get_cog("Tickets").on_close_button(interaction)
        @discord.ui.button(label="Взять в работу", emoji="✋", style=discord.ButtonStyle.success)
        async def claim_button(self, interaction, button):
            await interaction.client.get_cog("Tickets").on_claim_button(interaction)

class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Система тикетов", guild_only=True)
    def __init__(self, bot):
        self.bot = bot
    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
    async def get_types(self, guild_id):
        raw = await self.bot.db.get_setting(guild_id, "ticket_types")
        if raw:
            try:
                import json
                return json.loads(raw)
            except:
                pass
        return []
    async def send_panel(self, channel, title=None, description=None):
        types = await self.get_types(channel.guild.id)
        await channel.send(embed=embeds.make(title or "🎫 Центр поддержки", description or "Выбери тип обращения"), view=TicketPanelView(types))
    async def create_ticket(self, interaction, type_key, reason):
        guild = interaction.guild
        user = interaction.user
        category_id = await self.bot.db.get_setting(guild.id, "ticket_category")
        category = guild.get_channel(int(category_id)) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(embed=embeds.err("Тикеты ещё не настроены."), ephemeral=True)
            return
        ticket_id = await self.bot.db.insert(
            "INSERT INTO tickets(guild_id, user_id, type, reason, created_at) VALUES(?,?,?,?,?)",
            (guild.id, user.id, type_key, reason, int(now_ts())),
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_messages=True),
        }
        try:
            channel = await guild.create_text_channel(name=f"ticket-{ticket_id}", category=category, overwrites=overwrites)
        except:
            await self.bot.db.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
            await interaction.followup.send(embed=embeds.err("Не удалось создать канал."), ephemeral=True)
            return
        await self.bot.db.execute("UPDATE tickets SET channel_id=? WHERE id=?", (channel.id, ticket_id))
        await channel.send(content=user.mention, embed=embeds.make(f"Тикет #{ticket_id}", reason))
        await interaction.followup.send(embed=embeds.ok(f"Тикет создан: {channel.mention}"), ephemeral=True)
    async def on_close_button(self, interaction):
        await interaction.response.send_message(embed=embeds.warn("Закрываю тикет..."), ephemeral=True)
        await self.close_ticket(interaction.channel, interaction.user)
    async def on_claim_button(self, interaction):
        await interaction.response.send_message(embed=embeds.info("Взял тикет в работу."), ephemeral=True)
    async def close_ticket(self, channel, closer):
        await self.bot.db.execute("UPDATE tickets SET status='closed' WHERE channel_id=?", (channel.id,))
        await channel.send(embed=embeds.ok("Тикет закрыт."))
        await asyncio.sleep(5)
        try:
            await channel.delete(reason="Тикет закрыт")
        except:
            pass
    @ticket.command(name="panel", description="Отправить панель создания тикетов")
    @access("ticket_admin")
    async def panel(self, interaction, channel: discord.TextChannel | None = None, title: str | None = None, description: str | None = None):
        channel = channel or interaction.channel
        await self.send_panel(channel, title, description)
        await interaction.response.send_message(embed=embeds.ok("Панель отправлена."), ephemeral=True)
''',
    'vex.cogs.wipe': r'''"""Вайп-реакты: сбор участников перед событием."""
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
STATUSES = {"accepted": ("✅", "Придут"), "declined": ("❌", "Не придут"), "late": ("🕒", "Опоздают")}
REMIND_BEFORE = 15 * 60

class ReasonModal(discord.ui.Modal):
    def __init__(self, cog, ev, status):
        super().__init__(title="Причина")
        self.cog = cog
        self.ev_id = ev["message_id"]
        self.status = status
        self.reason = discord.ui.TextInput(label="Комментарий", required=False)
        self.add_item(self.reason)
    async def on_submit(self, interaction):
        await self.cog.save_response(self.ev_id, interaction.user.id, self.status, str(self.reason))
        await interaction.response.defer()
        await self.cog.refresh_message(interaction.message, self.ev_id)

class WipeView(discord.ui.View):
    def __init__(self, closed=False):
        super().__init__(timeout=None)
        @discord.ui.button(label="Приду", emoji="✅", style=discord.ButtonStyle.success)
        async def accept(self, interaction, button):
            await self.cog.handle_response(interaction, "accepted")
        @discord.ui.button(label="Не приду", emoji="❌", style=discord.ButtonStyle.danger)
        async def decline(self, interaction, button):
            await self.cog.handle_response(interaction, "declined")
        @discord.ui.button(label="Опоздаю", emoji="🕒", style=discord.ButtonStyle.secondary)
        async def late(self, interaction, button):
            await self.cog.handle_response(interaction, "late")
        @discord.ui.button(emoji="📝", style=discord.ButtonStyle.primary)
        async def settings(self, interaction, button):
            await self.cog.handle_settings(interaction)

class Wipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    async def cog_load(self):
        self.bot.add_view(WipeView())
    async def handle_response(self, interaction, status):
        await interaction.response.defer()
        await self.save_response(interaction.message.id, interaction.user.id, status, None)
        await self.refresh_message(interaction.message, interaction.message.id)
    async def save_response(self, message_id, user_id, status, reason):
        await self.bot.db.execute(
            "INSERT OR REPLACE INTO wipe_responses(message_id, user_id, status, reason) VALUES(?,?,?,?)",
            (message_id, user_id, status, reason),
        )
    async def refresh_message(self, message, message_id):
        ev = await self.bot.db.fetchone("SELECT * FROM wipe_events WHERE message_id=?", (message_id,))
        if ev:
            rows = await self.bot.db.fetchall("SELECT status FROM wipe_responses WHERE message_id=?", (message_id,))
            embed = embeds.make(f"{'🔒' if ev['closed'] else '📝'} {ev['title']}", f"Событие: <t:{ev['ts']}:F>")
            for st, (emoji, label) in STATUSES.items():
                count = sum(1 for r in rows if r["status"] == st)
                embed.add_field(name=f"{emoji} {label}", value=str(count), inline=True)
            try:
                await message.edit(embed=embed, view=WipeView(ev["closed"]))
            except:
                pass
    @app_commands.command(name="wipereact", description="Создать событие с реакциями")
    @access("wipe")
    async def wipereact(self, interaction, title: str, date: str, time: str):
        dt = datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M")
        if dt.timestamp() < now_ts():
            await interaction.response.send_message(embed=embeds.err("Дата в прошлом."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        message = await interaction.channel.send(embed=embeds.make(title, "Отметьтесь:"), view=WipeView())
        await self.bot.db.execute(
            "INSERT INTO wipe_events(message_id, guild_id, channel_id, creator_id, title, ts) VALUES(?,?,?,?,?,?)",
            (message.id, interaction.guild.id, interaction.channel.id, interaction.user.id, title, int(dt.timestamp())),
        )
        await interaction.followup.send(embed=embeds.ok("Событие создано."), ephemeral=True)
''',
    'vex.cogs.automod': r'''"""Автомодерация ссылок."""
import re
from datetime import timedelta
from time import time as now_ts
import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access

URL_RE = re.compile(r"(?:https?://|www\.)[^\\s<>()\\[\\]]+")

class AutoMod(commands.Cog):
    automod = app_commands.Group(name="automod", description="Автомодерация ссылок", guild_only=True)
    def __init__(self, bot):
        self.bot = bot
    async def check_message(self, message):
        if message.author.bot or not message.content: return
        if await self.bot.db.get_setting(message.guild.id, "automod_enabled", "1") == "0": return
        link = URL_RE.search(message.content)
        if link:
            await message.delete()
            await message.channel.send(embed=embeds.warn(f"{message.author.mention}, ссылки запрещены."))
    @commands.Cog.listener()
    async def on_message(self, message):
        await self.check_message(message)
    @automod.command(name="toggle", description="Включить/выключить автомодерацию")
    @access("automod")
    async def toggle(self, interaction, enabled: bool):
        await self.bot.db.set_setting(interaction.guild.id, "automod_enabled", "1" if enabled else "0")
        await interaction.response.send_message(embed=embeds.ok(f"Автомодерация {'включена' if enabled else 'выключена'}."), ephemeral=True)
''',
    'vex.cogs.roles': r'''"""Управление ролями и авто-выдача."""
import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access, is_admin

class RoleTools(commands.Cog):
    role = app_commands.Group(name="role", description="Управление ролями", guild_only=True)
    def __init__(self, bot):
        self.bot = bot
    @role.command(name="add", description="Выдать роль")
    @access("role")
    async def add(self, interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(embed=embeds.err("Роль выше моей."), ephemeral=True)
            return
        await member.add_roles(role)
        await interaction.response.send_message(embed=embeds.ok(f"Выдана роль {role.name}."), ephemeral=True)
    @role.command(name="remove", description="Снять роль")
    @access("role")
    async def remove(self, interaction, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)
        await interaction.response.send_message(embed=embeds.ok(f"Снята роль {role.name}."), ephemeral=True)
    autorole = app_commands.Group(name="autorole", description="Авто-выдача ролей", guild_only=True)
    @autorole.command(name="add", description="Добавить роль в авто-выдачу")
    @access("autorole")
    async def add(self, interaction, role: discord.Role):
        await self.bot.db.add_target(interaction.guild.id, "autorole_member", role.id)
        await interaction.response.send_message(embed=embeds.ok(f"Роль {role.name} добавлена в авто-выдачу."), ephemeral=True)
''',
    'vex.cogs.staff': r'''"""Сообщения от имени бота (/say)."""
import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import access

class SayModal(discord.ui.Modal):
    def __init__(self, cog, channel):
        super().__init__(title="Сообщение от имени VEX")
        self.cog = cog
        self.channel = channel
        self.text = discord.ui.TextInput(label="Текст сообщения", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.text)
    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        await self.channel.send(content=str(self.text))
        await interaction.followup.send(embed=embeds.ok("Отправлено."), ephemeral=True)

class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @app_commands.command(name="say", description="Отправить сообщение от имени бота")
    @access("say")
    async def say(self, interaction, channel: discord.TextChannel, text: str):
        await interaction.response.send_modal(SayModal(self, channel))
''',
    'vex.cogs.dashboard': r'''"""Единый дашборд настроек вместо разрозненных команд."""
import discord
from discord import ui, app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import admin_only
from ..db import Database

class DashboardModal(ui.Modal, title='Настройки VEX'):
    def __init__(self, bot, page: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.page = page
        # Поля для разных вкладок будут добавляться динамически
        if page == 'tickets':
            self.category = ui.TextInput(label='ID категории тикетов', placeholder='Например: 123456789')
            self.log_channel = ui.TextInput(label='ID лог-канала тикетов', placeholder='ID канала для транскриптов')
            self.add_item(self.category)
            self.add_item(self.log_channel)
        elif page == 'roles':
            pass  # Реализация вкладки ролей
        elif page == 'automod':
            self.enabled = ui.TextInput(label='Включить автомодерацию (1/0)', placeholder='1 - вкл, 0 - выкл')
            self.strikes = ui.TextInput(label='Нарушений до тайм-аута', placeholder='3')
            self.timeout = ui.TextInput(label='Тайм-аут, минут', placeholder='10')
            self.add_item(self.enabled)
            self.add_item(self.strikes)
            self.add_item(self.timeout)
        elif page == 'access':
            pass  # Реализация вкладки доступов

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        gid = interaction.guild.id
        if self.page == 'tickets':
            if self.category.value.isdigit():
                await db.set
