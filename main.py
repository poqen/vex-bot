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
                    "Администратор может выдать его через `/panel` → «Доступ»."
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

    @discord.ui.button(label="Назад", emoji="⬅️", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction, button):
        await self.cog.show_main(interaction)

    @discord.ui.button(label="Закрыть", emoji="✖️", style=discord.ButtonStyle.danger, row=4)
    async def close(self, interaction, button):
        await interaction.response.edit_message(embed=embeds.info("Панель закрыта."), view=None)


class AccessRoleSelect(discord.ui.Select):
    def __init__(self, key, roles, selected):
        options = [
            discord.SelectOption(label=role.name[:100], value=str(role.id), default=role.id in selected)
            for role in roles[:25]
        ]
        super().__init__(
            placeholder=f"Роли для «{config.COMMAND_KEYS[key]}»"[:100],
            options=options or [discord.SelectOption(label="На сервере нет ролей", value="0")],
            min_values=0,
            max_values=len(options) or 1,
            disabled=not options,
        )
        self.key = key

    async def callback(self, interaction):
        pass


class AccessSectionView(BackView):
    def __init__(self, cog, roles, selected):
        super().__init__(cog)
        self.roles = roles
        for key in config.COMMAND_KEYS:
            if len(self.children) >= 20:
                break
            self.add_item(AccessRoleSelect(key, roles, set(selected.get(key, []))))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, AccessRoleSelect):
                out[child.key] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=3)
    async def save(self, interaction, button):
        await self.cog.save_access(interaction, self._selected_map())


class RoleSelect(discord.ui.Select):
    def __init__(self, kind, roles, selected, placeholder):
        options = [
            discord.SelectOption(label=role.name[:100], value=str(role.id), default=role.id in selected)
            for role in roles[:25]
        ]
        super().__init__(
            placeholder=placeholder[:100],
            options=options or [discord.SelectOption(label="На сервере нет ролей", value="0")],
            min_values=0,
            max_values=len(options) or 1,
            disabled=not options,
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

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=3)
    async def save(self, interaction, button):
        await self.cog.save_roles(interaction, self._selected_map())


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
            placeholder=placeholder[:100],
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

    @discord.ui.button(label="Параметры", emoji="🛠️", style=discord.ButtonStyle.primary, row=2)
    async def params(self, interaction, button):
        await self.cog.open_automod_modal(interaction)

    @discord.ui.button(label="Сохранить списки", emoji="💾", style=discord.ButtonStyle.success, row=3)
    async def save(self, interaction, button):
        await self.cog.save_automod_lists(interaction, self._selected_map())


class ChannelSelect(discord.ui.Select):
    def __init__(self, kind, items, selected, placeholder, max_values=1):
        options = [
            discord.SelectOption(
                label=item.name[:100],
                value=str(item.id),
                default=(item.id == selected) if max_values == 1 else (item.id in selected),
            )
            for item in items[:25]
        ]
        super().__init__(
            placeholder=placeholder[:100],
            options=options or [discord.SelectOption(label="Нет вариантов", value="0")],
            min_values=0,
            max_values=max(1, min(max_values, len(options))) if options else 1,
            disabled=not options,
        )
        self.kind = kind

    async def callback(self, interaction):
        pass


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
            await interaction.response.send_message(embed=embeds.err("Нужен хотя бы один тип обращения."), ephemeral=True)
            return
        await self.cog.save_tickets_modal(interaction, max_open, types)


class TicketsSectionView(BackView):
    def __init__(self, cog, categories, channels, roles, category_sel, log_sel, support_sel):
        super().__init__(cog)
        self.add_item(ChannelSelect("ticket_category", categories, category_sel, "Категория для тикетов", 1))
        self.add_item(ChannelSelect("ticket_log", channels, log_sel, "Лог-канал тикетов", 1))
        self.add_item(AutomodSelect("ticket_support", roles, set(support_sel), "Роли поддержки"))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, (ChannelSelect, AutomodSelect)):
                out[child.kind] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Лимит и типы", emoji="🛠️", style=discord.ButtonStyle.primary, row=2)
    async def modal(self, interaction, button):
        await self.cog.open_tickets_modal(interaction)

    @discord.ui.button(label="Отправить панель", emoji="📨", style=discord.ButtonStyle.primary, row=2)
    async def send_panel(self, interaction, button):
        await self.cog.send_ticket_panel(interaction)

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=3)
    async def save(self, interaction, button):
        await self.cog.save_tickets(interaction, self._selected_map())


class EventsSectionView(BackView):
    def __init__(self, cog, events):
        super().__init__(cog)
        self.events = events
        for index, event in enumerate(events[:12]):
            self.add_item(EventButton(cog, event, index % 3))

    @discord.ui.button(label="Назад", emoji="⬅️", style=discord.ButtonStyle.secondary, row=4)
    async def back2(self, interaction, button):
        await self.cog.show_main(interaction)


class EventButton(discord.ui.Button):
    def __init__(self, cog, event, row):
        label = (event["title"] or "Событие")[:60]
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.cog = cog
        self.event = event

    async def callback(self, interaction):
        await self.cog.open_event(interaction, self.event)


class EventActionView(discord.ui.View):
    def __init__(self, cog, event):
        super().__init__(timeout=300)
        self.cog = cog
        self.event = event

    @discord.ui.button(label="Закрыть/открыть приём", emoji="🔒", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction, button):
        await self.cog.toggle_event(interaction, self.event)

    @discord.ui.button(label="Напомнить", emoji="🔔", style=discord.ButtonStyle.primary)
    async def remind(self, interaction, button):
        await self.cog.remind_event(interaction, self.event)

    @discord.ui.button(label="Удалить", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        await self.cog.delete_event(interaction, self.event)

    @discord.ui.button(label="Назад", emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await self.cog.show_section(interaction, "events")


class GeneralModal(discord.ui.Modal):
    def __init__(self, cog, welcome_text):
        super().__init__(title="Общие: текст приветствия")
        self.cog = cog
        self.welcome = discord.ui.TextInput(
            label="Текст приветствия ({user}, {server})",
            style=discord.TextStyle.paragraph,
            default=welcome_text,
            required=False,
            max_length=1500,
        )
        self.add_item(self.welcome)

    async def on_submit(self, interaction):
        await self.cog.save_welcome_text(interaction, str(self.welcome).strip())


class GeneralSectionView(BackView):
    def __init__(self, cog, channels, mod_log_sel, welcome_sel):
        super().__init__(cog)
        self.add_item(ChannelSelect("mod_log", channels, mod_log_sel, "Лог-канал модерации", 1))
        self.add_item(ChannelSelect("welcome_channel", channels, welcome_sel, "Канал приветствий", 1))

    def _selected_map(self):
        out = {}
        for child in self.children:
            if isinstance(child, ChannelSelect):
                out[child.kind] = [int(v) for v in child.values if v.isdigit()]
        return out

    @discord.ui.button(label="Текст приветствия", emoji="✏️", style=discord.ButtonStyle.primary, row=2)
    async def modal(self, interaction, button):
        await self.cog.open_general_modal(interaction)

    @discord.ui.button(label="Сохранить", emoji="💾", style=discord.ButtonStyle.success, row=3)
    async def save(self, interaction, button):
        await self.cog.save_general(interaction, self._selected_map())


class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="panel", description="Единая панель управления VEX (только админы)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not (isinstance(interaction.user, discord.Member) and is_admin(interaction.user)):
            await interaction.followup.send(embed=embeds.err("Только администраторы."), ephemeral=True)
            return
        await self.show_main(interaction, initial=True)

    async def show_main(self, interaction, initial=False):
        embed = embeds.make(
            "🟣 VEX — панель управления",
            "Всё управление ботом в одном месте. Выбери раздел:",
        )
        embed.add_field(
            name="Разделы",
            value="🔐 Доступ • 🎭 Роли • 🛡️ Автомод • 🎫 Тикеты\n📝 События • ⚙️ Общие • ❓ Помощь",
            inline=False,
        )
        view = MainView(self)
        if initial:
            await interaction.edit_original_response(embed=embed, view=view)
        elif interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

    async def show_section(self, interaction, key):
        guild = interaction.guild
        if key == "access":
            selected = {k: await self.bot.db.get_targets(guild.id, f"cmd:{k}") for k in config.COMMAND_KEYS}
            view = AccessSectionView(self, [r for r in guild.roles if not r.is_default()], selected)
            embed = embeds.make("🔐 Доступ к командам", "Кто из ролей может пользоваться какими командами. Администраторы всегда имеют доступ.")
        elif key == "roles":
            member_sel = await self.bot.db.get_targets(guild.id, "autorole_member")
            bot_sel = await self.bot.db.get_targets(guild.id, "autorole_bot")
            manageable_sel = await self.bot.db.get_targets(guild.id, "manageable")
            view = RolesSectionView(self, [r for r in guild.roles if not r.is_default()], member_sel, bot_sel, manageable_sel)
            embed = embeds.make("🎭 Роли", "Авто-выдача и список ролей, которые можно выдавать.")
        elif key == "automod":
            bypass = await self.bot.db.get_targets(guild.id, "automod_bypass")
            ignore = await self.bot.db.get_targets(guild.id, "automod_ignore_channel")
            view = AutomodSectionView(self, [r for r in guild.roles if not r.is_default()], list(guild.text_channels), bypass, ignore)
            embed = embeds.make("🛡️ Автомодерация", "Настройки фильтра ссылок и списки исключений.")
        elif key == "tickets":
            cats = [c for c in guild.categories]
            channels = list(guild.text_channels)
            roles = [r for r in guild.roles if not r.is_default()]
            cat_sel = pick_one(await self.bot.db.get_setting(guild.id, "ticket_category"), {c.id for c in cats})
            log_sel = pick_one(await self.bot.db.get_setting(guild.id, "ticket_log"), {c.id for c in channels})
            support_sel = await self.bot.db.get_targets(guild.id, "ticket_support")
            view = TicketsSectionView(self, cats, channels, roles, cat_sel, log_sel, support_sel)
            embed = embeds.make("🎫 Тикеты", "Настройки тикетов и отправка панели.")
        elif key == "events":
            rows = await self.bot.db.fetchall(
                "SELECT * FROM wipe_events WHERE guild_id=? ORDER BY ts DESC LIMIT 12", (guild.id,)
            )
            events = [{"message_id": r["message_id"], "title": r["title"], "ts": r["ts"], "closed": r["closed"]} for r in rows]
            view = EventsSectionView(self, events)
            embed = embeds.make("📝 События", "Нажми на событие для управления (закрыть/напомнить/удалить).")
        elif key == "general":
            channels = list(guild.text_channels)
            mod_log_sel = pick_one(await self.bot.db.get_setting(guild.id, "mod_log"), {c.id for c in channels})
            welcome_sel = pick_one(await self.bot.db.get_setting(guild.id, "welcome_channel"), {c.id for c in channels})
            view = GeneralSectionView(self, channels, mod_log_sel, welcome_sel)
            embed = embeds.make("⚙️ Общие", "Логи модерации и приветствия.")
        elif key == "help":
            embed = embeds.make("❓ Помощь", "Панель дублирует слэш-команды. Команды остаются доступными.")
            embed.add_field(name="Тикеты", value="`/ticket ...`", inline=True)
            embed.add_field(name="События", value="`/wipereact`, `/noreact`", inline=True)
            embed.add_field(name="Роли", value="`/role`, `/autorole`", inline=True)
            embed.add_field(name="Автомод", value="`/automod ...`", inline=True)
            embed.add_field(name="Прочее", value="`/say`, `/perms`, `/config`", inline=True)
            view = BackView(self)
        else:
            await self.show_main(interaction)
            return

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

    async def save_access(self, interaction, selected):
        guild = interaction.guild
        for key, ids in selected.items():
            await self.bot.db.set_targets(guild.id, f"cmd:{key}", ids)
        await interaction.response.send_message(embed=embeds.ok("Доступ обновлён."), ephemeral=True)

    async def save_roles(self, interaction, selected):
        guild = interaction.guild
        for kind, ids in selected.items():
            await self.bot.db.set_targets(guild.id, kind, ids)
        await interaction.response.send_message(embed=embeds.ok("Роли обновлены."), ephemeral=True)

    async def save_automod_lists(self, interaction, selected):
        guild = interaction.guild
        for kind, ids in selected.items():
            await self.bot.db.set_targets(guild.id, kind, ids)
        await interaction.response.send_message(embed=embeds.ok("Списки исключений обновлены."), ephemeral=True)

    async def save_automod(self, interaction, enabled, strikes, timeout, domains):
        gid = interaction.guild.id
        await self.bot.db.set_setting(gid, "automod_enabled", "1" if enabled else "0")
        await self.bot.db.set_setting(gid, "automod_strikes", strikes)
        await self.bot.db.set_setting(gid, "automod_timeout", timeout)
        await self.bot.db.set_domains(gid, domains)
        await interaction.response.send_message(embed=embeds.ok("Параметры автомодерации сохранены."), ephemeral=True)

    async def save_tickets(self, interaction, selected):
        gid = interaction.guild.id
        cat = selected.get("ticket_category", [])
        log = selected.get("ticket_log", [])
        support = selected.get("ticket_support", [])
        if cat:
            await self.bot.db.set_setting(gid, "ticket_category", cat[0])
        else:
            await self.bot.db.del_setting(gid, "ticket_category")
        if log:
            await self.bot.db.set_setting(gid, "ticket_log", log[0])
        else:
            await self.bot.db.del_setting(gid, "ticket_log")
        await self.bot.db.set_targets(gid, "ticket_support", support)
        await interaction.response.send_message(embed=embeds.ok("Настройки тикетов сохранены."), ephemeral=True)

    async def save_tickets_modal(self, interaction, max_open, types):
        gid = interaction.guild.id
        await self.bot.db.set_setting(gid, "ticket_max_open", max_open)
        await self.bot.db.set_setting(gid, "ticket_types", json.dumps(types, ensure_ascii=False))
        await interaction.response.send_message(embed=embeds.ok("Лимит и типы тикетов сохранены."), ephemeral=True)

    async def save_welcome_text(self, interaction, text):
        gid = interaction.guild.id
        if text:
            await self.bot.db.set_setting(gid, "welcome_text", text)
        else:
            await self.bot.db.del_setting(gid, "welcome_text")
        await interaction.response.send_message(embed=embeds.ok("Текст приветствия сохранён."), ephemeral=True)

    async def save_general(self, interaction, selected):
        gid = interaction.guild.id
        mod_log = selected.get("mod_log", [])
        welcome = selected.get("welcome_channel", [])
        if mod_log:
            await self.bot.db.set_setting(gid, "mod_log", mod_log[0])
        else:
            await self.bot.db.del_setting(gid, "mod_log")
        if welcome:
            await self.bot.db.set_setting(gid, "welcome_channel", welcome[0])
        else:
            await self.bot.db.del_setting(gid, "welcome_channel")
        await interaction.response.send_message(embed=embeds.ok("Общие настройки сохранены."), ephemeral=True)

    async def open_automod_modal(self, interaction):
        gid = interaction.guild.id
        enabled = await self.bot.db.get_setting(gid, "automod_enabled", "1") != "0"
        strikes = clamp(await self.bot.db.get_setting(gid, "automod_strikes", "3"), 1, 10, 3)
        timeout = clamp(await self.bot.db.get_setting(gid, "automod_timeout", "10"), 0, 1440, 10)
        rows = await self.bot.db.fetchall("SELECT domain FROM allowed_domains WHERE guild_id=?", (gid,))
        domains_text = "\n".join(r["domain"] for r in rows)
        await interaction.response.send_modal(AutomodModal(self, enabled, strikes, timeout, domains_text))

    async def open_tickets_modal(self, interaction):
        gid = interaction.guild.id
        max_open = clamp(await self.bot.db.get_setting(gid, "ticket_max_open", "1"), 1, 5, 1)
        raw = await self.bot.db.get_setting(gid, "ticket_types")
        if raw:
            try:
                types = json.loads(raw)
                types_text = "\n".join(
                    f"{t.get('emoji', '')} | {t['label']} | {t.get('description', '')}" for t in types
                )
            except (ValueError, KeyError, TypeError):
                types_text = ""
        else:
            types_text = "\n".join(
                f"{t['emoji']} | {t['label']} | {t['description']}" for t in config.TICKET_TYPES
            )
        await interaction.response.send_modal(TicketsModal(self, max_open, types_text))

    async def open_general_modal(self, interaction):
        text = await self.bot.db.get_setting(interaction.guild.id, "welcome_text", "")
        await interaction.response.send_modal(GeneralModal(self, text or "Привет, {user}! Добро пожаловать на **{server}**."))

    async def send_ticket_panel(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(embed=embeds.err("Только в текстовый канал."), ephemeral=True)
            return
        cog = self.bot.get_cog("Tickets")
        if cog is None:
            await interaction.followup.send(embed=embeds.err("Модуль тикетов не загружен."), ephemeral=True)
            return
        try:
            await channel.send(embed=cog.panel_embed(), view=cog.TicketPanelView())
        except discord.Forbidden:
            await interaction.followup.send(embed=embeds.err("Нет прав писать в этот канал."), ephemeral=True)
            return
        await interaction.followup.send(embed=embeds.ok(f"Панель отправлена в {channel.mention}."), ephemeral=True)

    async def open_event(self, interaction, event):
        await interaction.response.send_message(
            embed=embeds.make(
                f"📝 {event['title']}",
                f"Когда: {fmt_ts(event['ts'])}\nПриём: {'закрыт' if event['closed'] else 'открыт'}",
            ),
            view=EventActionView(self, event),
            ephemeral=True,
        )

    async def _event_message(self, event):
        row = await self.bot.db.fetchone("SELECT * FROM wipe_events WHERE message_id=?", (event["message_id"],))
        if not row:
            return None
        channel = self.bot.get_channel(row["channel_id"])
        if not channel:
            return None
        try:
            return await channel.fetch_message(row["message_id"])
        except discord.HTTPException:
            return None

    async def toggle_event(self, interaction, event):
        row = await self.bot.db.fetchone("SELECT closed FROM wipe_events WHERE message_id=?", (event["message_id"],))
        if not row:
            await interaction.response.send_message(embed=embeds.err("Событие не найдено."), ephemeral=True)
            return
        new_state = 0 if row["closed"] else 1
        await self.bot.db.execute("UPDATE wipe_events SET closed=? WHERE message_id=?", (new_state, event["message_id"]))
        event["closed"] = new_state
        await interaction.response.send_message(
            embed=embeds.ok("Приём закрыт." if new_state else "Приём открыт."), ephemeral=True
        )

    async def remind_event(self, interaction, event):
        message = await self._event_message(event)
        if message is None:
            await interaction.response.send_message(embed=embeds.err("Сообщение события не найдено."), ephemeral=True)
            return
        responded = {r["user_id"] for r in await self.bot.db.fetchall(
            "SELECT user_id FROM wipe_responses WHERE message_id=?", (event["message_id"],))}
        members = [m for m in message.channel.members if not m.bot and m.id not in responded]
        if not members:
            await interaction.response.send_message(embed=embeds.ok("Все уже ответили."), ephemeral=True)
            return
        await message.reply(
            "🔔 Отметьтесь, пожалуйста, под событием!\n" + " ".join(m.mention for m in members)[:1800],
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        await interaction.response.send_message(embed=embeds.ok(f"Напомнил {len(members)} участникам."), ephemeral=True)

    async def delete_event(self, interaction, event):
        message = await self._event_message(event)
        await self.bot.db.execute("DELETE FROM wipe_responses WHERE message_id=?", (event["message_id"],))
        await self.bot.db.execute("DELETE FROM wipe_events WHERE message_id=?", (event["message_id"],))
        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        await interaction.response.send_message(embed=embeds.ok("Событие удалено."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Panel(bot))
''',
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

TYPE_MAP = {t["key"]: t for t in config.TICKET_TYPES}
TZ = ZoneInfo(config.TIMEZONE)


def panel_embed(title=None, description=None):
    if description:
        text = description
    else:
        types = "\n".join(
            f"{t['emoji']} **{t['label']}** — {t['description']}" for t in config.TICKET_TYPES
        )
        text = (
            "Нужна помощь или хочешь вступить в клан?\n"
            "Выбери тип обращения в меню ниже — для тебя создастся приватный канал, "
            "где с тобой свяжется администрация.\n\n" + types
        )
    embed = embeds.make(title or "🎫 Центр поддержки", text)
    if not description:
        embed.add_field(
            name="ℹ️ Правила",
            value="• Один открытый тикет на человека\n• Пиши по делу и не спамь\n• Не пингуй администрацию без причины",
            inline=False,
        )
    return embed


def ticket_embed(guild, row):
    t = TYPE_MAP.get(row["type"], {"label": "Обращение", "emoji": "🎫"})
    embed = embeds.make(f"{t['emoji']} Тикет #{row['id']:04d} — {t['label']}")
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


class TicketReasonModal(discord.ui.Modal):
    def __init__(self, cog, type_key):
        label = TYPE_MAP[type_key]["label"]
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
    def __init__(self):
        options = [
            discord.SelectOption(
                label=t["label"], value=t["key"], description=t["description"][:100], emoji=t["emoji"]
            )
            for t in config.TICKET_TYPES
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
        await interaction.response.send_modal(TicketReasonModal(cog, self.values[0]))
        try:
            await interaction.message.edit(view=TicketPanelView())
        except discord.HTTPException:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


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


class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Система тикетов", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())

    def panel_embed(self, title=None, description=None):
        return panel_embed(title, description)

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
            else:
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

        slug = TYPE_MAP[type_key]["slug"]
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
            embed=ticket_embed(guild, row),
            view=TicketControlView(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )
        await interaction.followup.send(
            embed=embeds.ok(f"Тикет создан: {channel.mention}", "Обращение открыто"), ephemeral=True
        )

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
            embed=ticket_embed(interaction.guild, row), view=TicketControlView()
        )
        await interaction.channel.send(
            embed=embeds.info(f"✋ {interaction.user.mention} взял(а) тикет в работу."),
            allowed_mentions=discord.AllowedMentions.none(),
        )

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
                pass

        try:
            await channel.send(embed=embeds.warn("Тикет закрыт. Канал будет удалён через 5 секунд."))
        except discord.HTTPException:
            pass
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Тикет закрыт: {closer}")
        except discord.HTTPException:
            pass

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
            await channel.send(embed=panel_embed(title, text), view=TicketPanelView())
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

    async def _staff_ticket(self, interaction):
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
REMIND_BEFORE = 15 * 60


def parse_datetime(date_s, time_s):
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


class Wipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(WipeView())
        self.reminder_loop.start()

    async def cog_unload(self):
        self.reminder_loop.cancel()

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

    async def can_manage(self, member, ev):
        return member.id == ev["creator_id"] or await member_has_access(self.bot, member, "wipe")

    async def pending_members(self, guild, channel, ev, role=None):
        rows = await self.get_rows(ev["message_id"]) if ev else []
        responded = {r["user_id"] for r in rows}
        if role is None and ev and ev["ping_role_id"]:
            role = guild.get_role(ev["ping_role_id"])
        base = role.members if role else channel.members
        return [m for m in base if not m.bot and m.id not in responded]

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
        if existing and existing["status"] == status:
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
        except Exception:
            import logging

            logging.getLogger("vex").exception("Ошибка в цикле напоминаний")

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

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
STRIKE_WINDOW = 10 * 60


def extract_host(link):
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", link.strip().lower())
    host = host.split("/")[0].split("?")[0].split("#")[0]
    host = host.split("@")[-1].split(":")[0]
    return host


def normalize_domain(text):
    return extract_host(text).strip(".")


def find_violation(content, allowed):
    for match in URL_RE.finditer(content):
        raw = match.group(0)
        host = extract_host(raw)
        if not host:
            continue
        if host in ("discord.com", "discordapp.com") and "/channels/" in raw.lower():
            continue
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
        self.strikes = {}

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

    async def check_message(self, message):
        if message.guild is None or message.author.bot or not message.content:
            return
        if not isinstance(message.author, discord.Member):
            return
        if not URL_RE.search(message.content):
            return

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
        if not member.pending:
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
        embed.add_field(name="🔐 Администрирование", value="`/panel` — единая панель • `/perms` • `/config`",
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

    def get_source(self, fullname):
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
