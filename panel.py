"""Единая админ-панель /panel. Кладётся рядом с main.py и подхватывается автоматически."""
import json
from datetime import datetime
from time import time as now_ts
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from vex import config, embeds
from vex.checks import is_admin

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

    @discord.ui.button(label="Назад", emoji="⬅️", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction, button):
        await self.cog.show_main(interaction)

    @discord.ui.button(label="Закрыть", emoji="✖️", style=discord.ButtonStyle.danger, row=4)
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


# --------------------------------------------------------------------------- роли
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


# --------------------------------------------------------------------------- тикеты
class ChannelSelect(discord.ui.Select):
    def __init__(self, kind, items, selected, placeholder, max_values=1):
        options = [
            discord.SelectOption(label=item.name[:100], value=str(item.id), default=(item.id == selected) if max_values == 1 else (item.id in selected))
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


# --------------------------------------------------------------------------- события
class EventsSectionView(BackView):
    def __init__(self, cog, events):
        super().__init__(cog)
        self.events = events
        for index, event in enumerate(events[:15]):
            self.add_item(EventButton(cog, event, index % 3))

    @discord.ui.button(label="Назад", emoji="⬅️", style=discord.ButtonStyle.secondary, row=3)
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


# --------------------------------------------------------------------------- общие
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


# --------------------------------------------------------------------------- ког
class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="panel", description="Единая панель управления VEX (только админы)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        if not (isinstance(interaction.user, discord.Member) and is_admin(interaction.user)):
            await interaction.response.send_message(embed=embeds.err("Только администраторы."), ephemeral=True)
            return
        await self.show_main(interaction)

    # ---- переходы
    async def show_main(self, interaction):
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
        if interaction.response.is_done():
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
                "SELECT * FROM wipe_events WHERE guild_id=? ORDER BY ts DESC LIMIT 15", (guild.id,)
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

    # ---- сохранения
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

    # ---- модалки
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

    # ---- события
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
