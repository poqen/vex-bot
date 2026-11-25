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

    def _execute(self, sql, params):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.rowcount, cur.lastrowid

    def _fetch(self, sql, params, one):
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone() if one else cur.fetchall()

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

    async def add_target(self, guild_id, kind, target_id):
        changed = await self.execute(
            "INSERT OR IGNORE INTO guild_targets(guild_id, kind, target_id) VALUES(?,?,?)",
            (guild_id, kind, target_id),
        )
        return changed > 0

    async def remove_target(self, guild_id, kind, target_id):
        changed = await self.execute(
            "DELETE FROM guild_targets WHERE guild_id=? AND kind=? AND target_id=?",
            (guild_id, kind, target_id),
        )
        return changed > 0

    async def clear_targets(self, guild_id, kind):
        await self.execute("DELETE FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind))

    async def set_targets(self, guild_id, kind, ids):
        await self.execute("DELETE FROM guild_targets WHERE guild_id=? AND kind=?", (guild_id, kind))
        for target_id in ids:
            await self.add_target(guild_id, kind, target_id)

    async def set_domains(self, guild_id, domains):
        await self.execute("DELETE FROM allowed_domains WHERE guild_id=?", (guild_id,))
        for domain in domains:
            await self.execute(
                "INSERT OR IGNORE INTO allowed_domains(guild_id, domain) VALUES(?,?)",
                (guild_id, domain),
            )
''',
    'vex.checks': r'''"""Система доступа: какая роль может пользоваться какой командой."""
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
    'vex.bot': r'''"""Ядро бота: интенты, загрузка модулей, обработка ошибок команд, логирование на сервер."""
import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import config, embeds
from .checks import NoAccess
from .db import Database

log = logging.getLogger("vex")

EXTENSIONS = (
    "vex.cogs.panel",
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
                    "Администратор может выдать его через `/panel` → «Доступ к командам»."
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

    async def on_ready(self):
        log.info("VEX запущен как %s (серверов: %d)", self.user, len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="за кланом")
        )

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
    'vex.cogs': r'''''',
    'vex.cogs.panel': r'''"""Единая админ-панель /panel: всё управление ботом в одном месте, кнопками."""
import json
from datetime import datetime
from time import time as now_ts
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, embeds
from ..checks import is_admin

TZ = ZoneInfo(config.TIMEZONE)

SECTIONS = [
    ("access", "Доступ к командам", "🔐"),
    ("roles", "Роли", "🎭"),
    ("automod", "Автомодерация", "🛡️"),
    ("tickets", "Тикеты", "🎫"),
    ("events", "События", "📝"),
    ("general", "Общие", "⚙️"),
    ("help", "Помощь", "❓"),
]


def fmt_ts(ts):
    try:
        return datetime.fromtimestamp(int(ts), TZ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(ts)


def clamp(value, low, high, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def pick_one(value, valid):
    text = str(value or "")
    return int(text) if text.isdigit() and int(text) in valid else None


# --------------------------------------------------------------------------- главное меню
class MainView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog

    async def open_section(self, interaction, key):
        await self.cog.show_section(interaction, key)

    @discord.ui.button(label="Доступ", emoji="🔐", style=discord.ButtonStyle.primary, row=0)
    async def b_access(self, interaction, button):
        await self.open_section(interaction, "access")

    @discord.ui.button(label="Роли", emoji="🎭", style=discord.ButtonStyle.primary, row=0)
    async def b_roles(self, interaction, button):
        await self.open_section(interaction, "roles")

    @discord.ui.button(label="Автомод", emoji="🛡️", style=discord.ButtonStyle.primary, row=0)
    async def b_automod(self, interaction, button):
        await self.open_section(interaction, "automod")

    @discord.ui.button(label="Тикеты", emoji="🎫", style=discord.ButtonStyle.primary, row=1)
    async def b_tickets(self, interaction, button):
        await self.open_section(interaction, "tickets")

    @discord.ui.button(label="События", emoji="📝", style=discord.ButtonStyle.primary, row=1)
    async def b_events(self, interaction, button):
        await self.open_section(interaction, "events")

    @discord.ui.button(label="Общие", emoji="⚙️", style=discord.ButtonStyle.primary, row=1)
    async def b_general(self, interaction, button):
        await self.open_section(interaction, "general")

    @discord.ui.button(label="Помощь", emoji="❓", style=discord.ButtonStyle.secondary, row=2)
    async def b_help(self, interaction, button):
        await self.open_section(interaction, "help")

    @discord.ui.button(label="Закрыть", emoji="✖️", style=discord.ButtonStyle.danger, row=2)
    async def b_close(self, interaction, button):
        await interaction.response.edit_message(embed=embeds.info("Панель закрыта."), view=None)


class BackView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="Назад", emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await self.cog.show_main(interaction)

    @discord.ui.button(label="Закрыть", emoji="✖️", style=discord.ButtonStyle.danger)
    async def close(self, interaction, button):
        await interaction.response.edit_message(embed=embeds.info("Панель закрыта."), view=None)


# --------------------------------------------------------------------------- доступ
class AccessRoleSelect(discord.ui.Select):
    def __init__(self, key, roles, selected):
        options = [
            discord.SelectOption(label=role.name[:100], value=str(role.id), default=role.id in selected)
            for role in roles[:25]
        ]
        super().__init__(
            placeholder=f"Роли для «{config.COMMAND_KEYS[key]}»",
            options=options or [discord.SelectOption(label="На сервере нет ролей", value="0")],
            min_values=0,
            max_values=len(options) or 1,
            disabled=not options,
        )
        self.key = key

    async def callback(self, interaction):
        pass  # состояние собираем при сохранении


class AccessSectionView(BackView):
    def __init__(self, cog, roles, selected):
        super().__init__(cog)
        self.roles = roles
        self.selected = selected
        for key in config.COMMAND_KEYS:
            if len(self.children) >= 24:
                break
            self.add_item(AccessRoleSelect(key, roles, set(selected.get(key, []))))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, AccessRoleSelect):
                out[child.key] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=4)
    async def save(self, interaction, button):
        await self.cog.save_access(interaction, self._selected_map())


# --------------------------------------------------------------------------- роли
class RoleSelect(discord.ui.Select):
    def __init__(self, kind, roles, selected, placeholder):
        options = [
            discord.SelectOption(label=role.name[:100], value=str(role.id), default=role.id in selected)
            for role in roles[:25]
        ]
        super().__init__(
            placeholder=placeholder,
            options=options or [discord.SelectOption(label="На сервере нет ролей", value="0")],
            min_values=0,
            max_values=len(options) or 1,
            disabled=not options,
            row=None,
        )
        self.kind = kind

    async def callback(self, interaction):
        pass


class RolesSectionView(BackView):
    def __init__(self, cog, roles, member_sel, bot_sel, manageable_sel):
        super().__init__(cog)
        self.add_item(RoleSelect("autorole_member", roles, set(member_sel), "Роли новым участникам"))
        self.add_item(RoleSelect("autorole_bot", roles, set(bot_sel), "Роли новым ботам"))
        self.add_item(RoleSelect("manageable", roles, set(manageable_sel), "Роли, которые можно выдавать"))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, RoleSelect):
                out[child.kind] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=4)
    async def save(self, interaction, button):
        await self.cog.save_roles(interaction, self._selected_map())


# --------------------------------------------------------------------------- автомодерация
class AutomodModal(discord.ui.Modal):
    def __init__(self, cog, enabled, strikes, timeout, domains_text):
        super().__init__(title="Автомодерация: параметры")
        self.cog = cog
        self.enabled = discord.ui.TextInput(label="Включена (да/нет)", default="да" if enabled else "нет", max_length=3)
        self.strikes = discord.ui.TextInput(label="Нарушений до тайм-аута (1-10)", default=str(strikes), max_length=2)
        self.timeout = discord.ui.TextInput(label="Тайм-аут, мин (0-1440)", default=str(timeout), max_length=4)
        self.domains = discord.ui.TextInput(
            label="Разрешённые домены (по одному в строке)",
            style=discord.TextStyle.paragraph,
            default=domains_text,
            required=False,
            max_length=2000,
        )
        for item in (self.enabled, self.strikes, self.timeout, self.domains):
            self.add_item(item)

    async def on_submit(self, interaction):
        enabled = str(self.enabled).strip().lower() in ("да", "yes", "1", "true", "вкл")
        strikes = clamp(str(self.strikes), 1, 10, 3)
        timeout = clamp(str(self.timeout), 0, 1440, 10)
        domains = [d.strip().lower() for d in str(self.domains).splitlines() if d.strip()][:200]
        await self.cog.save_automod(interaction, enabled, strikes, timeout, domains)


class AutomodSelect(discord.ui.Select):
    def __init__(self, kind, items, selected, placeholder):
        options = [
            discord.SelectOption(label=item.name[:100], value=str(item.id), default=item.id in selected)
            for item in items[:25]
        ]
        super().__init__(
            placeholder=placeholder,
            options=options or [discord.SelectOption(label="Нет вариантов", value="0")],
            min_values=0,
            max_values=len(options) or 1,
            disabled=not options,
        )
        self.kind = kind

    async def callback(self, interaction):
        pass


class AutomodSectionView(BackView):
    def __init__(self, cog, roles, channels, bypass, ignore):
        super().__init__(cog)
        self.add_item(AutomodSelect("automod_bypass", roles, set(bypass), "Роли без проверки"))
        self.add_item(AutomodSelect("automod_ignore_channel", channels, set(ignore), "Каналы без проверки"))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, AutomodSelect):
                out[child.kind] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Параметры", emoji="🛠️", style=discord.ButtonStyle.primary, row=3)
    async def params(self, interaction, button):
        await self.cog.open_automod_modal(interaction)

    @discord.ui.button(label="Сохранить списки", emoji="💾", style=discord.ButtonStyle.success, row=4)
    async def save(self, interaction, button):
        await self.cog.save_automod_lists(interaction, self._selected_map())


# --------------------------------------------------------------------------- тикеты
class TicketsModal(discord.ui.Modal):
    def __init__(self, cog, max_open, types_text):
        super().__init__(title="Тикеты: лимит и типы")
        self.cog = cog
        self.max_open = discord.ui.TextInput(label="Тикетов на человека (1-5)", default=str(max_open), max_length=1)
        self.types = discord.ui.TextInput(
            label="Типы: эмодзи | Название | Описание",
            style=discord.TextStyle.paragraph,
            default=types_text,
            max_length=4000,
        )
        self.add_item(self.max_open)
        self.add_item(self.types)

    async def on_submit(self, interaction):
        max_open = clamp(str(self.max_open), 1, 5, 1)
        types = []
        for line in str(self.types).splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                emoji, label = parts[0], parts[1]
                desc = " | ".join(parts[2:]) if len(parts) > 2 else ""
            else:
                emoji, label, desc = "", parts[0], ""
            if not label:
                continue
            types.append({
                "key": f"t{len(types)}",
                "slug": "ticket",
                "label": label[:100],
                "emoji": emoji[:8],
                "description": desc[:100],
            })
            if len(types) >= 25:
                break
        if not types:
            await interaction.response.send_message(
                embed=embeds.err("Нужен хотя бы один тип обращения."), ephemeral=True
            )
            return
        await self.cog.save_tickets_modal(interaction, max_open, types)


class TicketsSectionView(BackView):
    def __init__(self, cog, categories, channels, roles, category_sel, log_sel, support_sel):
        super().__init__(cog)
        self.add_item(ChannelSelect("ticket_category", categories, category_sel, "Категория для тикетов"))
        self.add_item(ChannelSelect("ticket_log", channels, log_sel, "Лог-канал тикетов"))
        self.add_item(AutomodSelect("ticket_support", roles, set(support_sel), "Роли поддержки"))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, (ChannelSelect, AutomodSelect)):
                out[child.kind] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Лимит и типы", emoji="🛠️", style=discord.ButtonStyle.primary, row=3)
    async def modal(self, interaction, button):
        await self.cog.open_tickets_modal(interaction)

    @discord.ui.button(label="Отправить панель", emoji="📨", style=discord.ButtonStyle.primary, row=3)
    async def send_panel(self, interaction, button):
        await self.cog.send_ticket_panel(interaction)

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=4)
    async def save(self, interaction, button):
        await self.cog.save_tickets(interaction, self._selected_map())


class ChannelSelect(discord.ui.Select):
    def __init__(self, kind, items, selected, placeholder):
        options = [
            discord.SelectOption(label=item.name[:100], value=str(item.id), default=item.id == selected)
            for item in items[:25]
        ]
        super().__init__(
            placeholder=placeholder,
            options=options or [discord.SelectOption(label="Нет вариантов", value="0")],
            min_values=0,
            max_values=1,
            disabled=not options,
        )
        self.kind = kind

    async def callback(self, interaction):
        pass


# --------------------------------------------------------------------------- события
class EventsSectionView(BackView):
    def __init__(self, cog, events):
        super().__init__(cog)
        self.events = events
        for index, event in enumerate(events[:20]):
            self.add_item(EventButton(cog, event, index))


class EventButton(discord.ui.Button):
    def __init__(self, cog, event, index):
        label = (event["title"] or "Событие")[:60]
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=index // 5)
        self.cog = cog
        self.event = event

    async def callback(self, interaction):
        await self.cog.open_event(interaction, self.event)


class EventActionView(discord.ui.View):
    def __init__(self, cog, event):
        super().__init__(timeout=300)
        self.cog = cog
        self.event = event

    @discord.ui.button(label="
