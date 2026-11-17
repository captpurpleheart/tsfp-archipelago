"""
Archipelago client for TimeSplitters: Future Perfect running in Dolphin.

Modelled on the Mario Kart Double Dash client. Every 0.25 s it:
  1. reads trophies, story completions and story objectives and reports new ones as checks, and
  2. makes the game's unlocks match the items the player has received.
"""
import asyncio
import time
import traceback
from typing import Any, Optional

import Utils
from CommonClient import ClientCommandProcessor, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

import dolphin_memory_engine as dolphin

from . import game_data, game_state

# Universal Tracker, when it is installed, provides the tracker tab and in-logic checks. Its
# context is a drop-in replacement for the normal one.
tracker_loaded = False
try:
    from worlds.tracker.TrackerClient import TrackerGameContext as CommonContext
    tracker_loaded = True
except ImportError:
    from CommonClient import CommonContext

CONNECTED = "Dolphin connected successfully."
NOT_CONNECTED = "Dolphin connection has not been initiated."
LOST = "Dolphin connection was lost. Start Dolphin and the game, then wait."
WRONG_GAME = "Dolphin is running a different game. Load TimeSplitters: Future Perfect."


ANNOUNCE_SETTINGS = ("received", "sent", "found", "deathlink", "filler")
ANNOUNCE_DEFAULTS = {"on": True, **{name: True for name in ANNOUNCE_SETTINGS}}


class TsfpCommandProcessor(getattr(CommonContext, "command_processor", ClientCommandProcessor)):
    def _cmd_announce(self, setting: str = "", value: str = "") -> bool:
        """In-game announcements. /announce shows the settings. /announce on or /announce off switches
        them all. /announce received|sent|found|deathlink|filler on|off switches one kind
        (filler: announcements of filler items)."""
        ctx = self.ctx
        setting, value = setting.lower(), value.lower()
        if setting in ("on", "off") and not value:
            setting, value = "on", setting
        if setting and (setting not in ("on",) + ANNOUNCE_SETTINGS or value not in ("on", "off")):
            self.output("Use /announce on|off, or /announce received|sent|found|deathlink|filler on|off.")
            return False
        if setting:
            ctx.announce[setting] = value == "on"
            try:
                Utils.persistent_store("timesplitters_future_perfect", "announce", dict(ctx.announce))
            except Exception:
                pass
        self.output("In-game announcements: " + ("ON" if ctx.announce["on"] else "OFF") + " ("
                    + ", ".join(f"{name} {'on' if ctx.announce[name] else 'off'}" for name in ANNOUNCE_SETTINGS)
                    + ")")
        return True


class TsfpContext(CommonContext):
    game = game_data.GAME_NAME
    items_handling = 0b111  # the server sends us every item, including our own
    command_processor = TsfpCommandProcessor

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_status: str = NOT_CONNECTED
        self.announcer = game_state.Announcer()
        self.announce: dict[str, bool] = dict(ANNOUNCE_DEFAULTS)
        try:
            saved = Utils.persistent_load().get("timesplitters_future_perfect", {}).get("announce", {})
            self.announce.update({k: bool(v) for k, v in saved.items() if k in ANNOUNCE_DEFAULTS})
        except Exception:
            pass
        self.frame_hook_logged: str = ""
        self.award_screen = game_state.AwardScreen()
        self.award_hook_logged: str = ""
        self.award_items_seen: Optional[int] = None         # items_received already looked at
        self.last_played = None                             # ("mission", Mission) / ("story", level)
        self.dolphin_sync_task: Optional[asyncio.Task] = None
        self.reported_locations: set[int] = set()  # sent already, server may not have confirmed yet
        self.items_synced: bool = False             # True once the server has sent our item list
        self.connected_at: Optional[float] = None   # when the server accepted our login
        self.victory_sent: bool = False
        self.conditions_ok: bool = False            # unlock data checked for this game session
        self.story_state_logged: str = ""           # last story patch state written to the log
        # From slot_data:
        self.story_mode: int = game_data.STORY_INDIVIDUAL
        self.goal: int = game_data.GOAL_FUTURE_PERFECT
        self.story_levels_required: int = 0
        self.trophy_grade: int = 1
        self.trophies_required: int = 0
        self.trophies_required_grade: int = 1
        self.trophy_hunt_setting: int = game_data.HUNT_ALL
        self.final_level_logged: Optional[bool] = None    # last "Future Perfect open?" written to the log
        self.misc_logged: tuple = ()                        # last Miscellaneous multiplier state logged
        self.resistances: bool = False                      # this seed has damage resistances
        self.resist_logged: tuple = ()                      # last damage resistance state logged
        self.score_logged: tuple = ()                       # last score multiplier state written to the log
        self.buffs_shown: Optional[str] = None              # the Inventory tab's text last shown
        self.buffs_skipped: list[str] = []                  # weapon buffs last reported as not applied
        # Story objectives are only visible at the moment they complete, so they are remembered
        # here until the server has them.
        self.starting_armour = game_state.StartingArmour()
        self.mission_failure = game_state.MissionFailure()
        self.streamer_mode: bool = False                    # from slot_data
        self.streamer_logged: str = ""
        self.easier_trophies: dict[str, bool] = {}          # from slot_data
        self.easier_logged: dict[str, str] = {}
        self.armour_logged: int = 0                         # starting armour level last written to the log
        self.arcade_deaths = game_state.ArcadeDeaths()
        self.death_link_amnesty: int = 0                    # 0 = Arcade League deaths don't count
        self.death_pending: bool = False                    # a Death Link has arrived and not been dealt with
        self.death_hook_logged: str = ""
        self.objective_tracker = game_state.ObjectiveTracker()
        self.objectives_found: set[int] = set()
        self.objectives_seed: Optional[str] = None
        # Archipelago Shop (slot data, and the server's data storage for kills and points spent)
        self.shop_size: int = 0
        self.shop_prices: list[int] = []
        self.shop_kills: Optional[int] = None       # None until the server has told us
        self.shop_spent: Optional[int] = None
        self.shop_kills_pending: int = 0            # kills not yet added on the server
        self.shop_bought: set[int] = set()          # bought here, perhaps not yet confirmed by the server
        self.shop_hinted: set[int] = set()
        self.shop_hint_rows: set[int] = set()       # rows whose item to hint
        self.shop_hints: int = game_data.SHOP_HINTS_ALL
        self.award_hide: set[int] = set()           # bought characters, weapons and cheats to keep off the award screen
        self.shop_menu = game_state.ShopMenu()
        self.kill_counter = game_state.KillCounter()
        self.shop_state_logged: str = ""
        self.shop_earned: dict[str, int] = {"trophies": 0, "story": 0}   # last read from the profile
        self.shop_notice: Optional[tuple[str, float]] = None              # (title, until) e.g. not enough points
        self.shop_list: tuple = (None, [])          # the shop's points and rows, for the Inventory tab

    def items_ready(self) -> bool:
        """
        True once it is safe to touch the game. The server only sends a
        ReceivedItems packet when we own at least one item, so a player with no
        items yet would wait forever. If none arrives within 3 seconds of
        logging in, we assume there are none.
        """
        if self.items_synced:
            return True
        return self.connected_at is not None and time.monotonic() - self.connected_at >= 3.0

    def reset_server_state(self) -> None:
        self.reported_locations = set()
        self.items_synced = False
        self.connected_at = None
        self.victory_sent = False
        super().reset_server_state()

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_deathlink(self, data: dict[str, Any]) -> None:
        super().on_deathlink(data)
        self.death_pending = True
        if self.announce["on"] and self.announce["deathlink"]:
            cause = str(data.get("cause") or "") or f"Death Link from {data.get('source', 'someone')}"
            self.announcer.add(cause, game_data.MESSAGE_STYLE_BIG)

    def announce_item_send(self, args: dict[str, Any]) -> None:
        """Queue an in-game line for an item that concerns us (received, sent or found)."""
        if not self.announce["on"] or self.slot is None:
            return
        item, receiving = args.get("item"), args.get("receiving")
        if item is None or receiving is None:
            return
        if isinstance(item, dict):
            item_id, sender, flags = item.get("item"), item.get("player"), item.get("flags", 0)
        else:
            item_id, sender, flags = item.item, item.player, item.flags
        if not flags and not self.announce["filler"]:
            return
        try:
            name = self.item_names.lookup_in_slot(item_id, receiving)
        except Exception:
            name = f"item {item_id}"
        players = self.player_names
        if receiving == self.slot and sender == self.slot:
            kind, text = "found", f"Found {name}"
        elif receiving == self.slot:
            kind, text = "received", f"Received {name} from {players.get(sender, 'someone')}"
        elif sender == self.slot:
            kind, text = "sent", f"Sent {name} to {players.get(receiving, 'someone')}"
        else:
            return
        if self.announce[kind]:
            self.announcer.add(text, game_data.MESSAGE_STYLE_LINE)

    def make_gui(self):
        """The normal client window (or Universal Tracker's), plus an Inventory tab."""
        base = super().make_gui()
        try:
            from . import gui
            return gui.make_gui(base)
        except Exception:
            logger.warning("Could not add the Inventory tab; the rest of the client is unaffected.")
            logger.debug(traceback.format_exc())
            return base

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            self.connected_at = time.monotonic()
            self.award_items_seen = None       # items already received are not news
            slot_data = args.get("slot_data", {})
            self.story_mode = int(slot_data.get("story_mode", game_data.STORY_INDIVIDUAL))
            self.goal = int(slot_data.get("goal", game_data.GOAL_FUTURE_PERFECT))
            self.story_levels_required = int(slot_data.get("story_levels_required", 0))
            self.trophy_grade = int(slot_data.get("trophy_grade", 1))
            self.trophies_required = int(slot_data.get("trophies_required", 0))
            self.trophies_required_grade = int(slot_data.get("trophies_required_grade", 1))
            self.trophy_hunt_setting = int(slot_data.get("trophy_hunt_setting", game_data.HUNT_ALL))
            self.final_level_logged = None
            self.buffs_shown = None
            self.streamer_mode = bool(slot_data.get("streamer_mode", 0))
            self.easier_trophies = {option: bool(slot_data.get(option, 0)) for option in game_data.EASIER_TROPHIES}
            Utils.async_start(self.update_death_link(bool(slot_data.get("death_link", 0))))
            self.death_link_amnesty = int(slot_data.get("death_link_amnesty", 0))   # 0: seeds before 1.3.0
            self.resistances = bool(slot_data.get("include_damage_resistances", 0))  # 0: seeds before 1.4.0
            self.shop_size = int(slot_data.get("shop_locations", 0)) if slot_data.get("include_archipelago_shop") else 0
            self.shop_prices = list(slot_data.get("shop_prices", []))
            self.shop_kills = self.shop_spent = None
            self.shop_bought = set()
            self.shop_hinted = set()
            self.shop_hint_rows = set()
            self.shop_hints = int(slot_data.get("shop_hints", game_data.SHOP_HINTS_ALL))   # all: older seeds
            if self.shop_size:
                Utils.async_start(self.send_msgs([{"cmd": "Get", "keys": [self.shop_kills_key, self.shop_spent_key]}]))
            logger.info("In-game announcements are " + ("on" if self.announce["on"] else "off")
                        + ". Type /announce to see or change them.")
            seed_version = str(slot_data.get("world_version", "unknown"))
            if seed_version == game_data.WORLD_VERSION:
                logger.info(f"This game was generated with apworld {seed_version}, the same as this client.")
            elif seed_version.split(".")[:2] == game_data.WORLD_VERSION.split(".")[:2]:
                logger.info(f"This game was generated with apworld {seed_version}; this client is "
                            f"{game_data.WORLD_VERSION}, a fix for the same version, so nothing is missing.")
            else:
                logger.warning(f"This game was generated with apworld {seed_version}, but this client is "
                               f"{game_data.WORLD_VERSION}. Items added since {seed_version} are not in this game; "
                               "generate a new one to get them.")
            # What is at each of our locations, so the award screen can name what was just found.
            missing = sorted(args.get("missing_locations", []))
            if missing:
                Utils.async_start(self.send_msgs([{"cmd": "LocationScouts", "locations": missing,
                                                   "create_as_hint": 0}]))
            seed = f"{self.seed_name}/{self.slot}"
            if self.objectives_seed not in (None, seed):   # a different game: forget the old one's objectives
                self.objectives_found = set()
            self.objectives_seed = seed
        elif cmd == "ReceivedItems":
            self.items_synced = True
        elif cmd == "PrintJSON" and args.get("type") in ("ItemSend", "ItemCheat"):
            self.announce_item_send(args)
        elif cmd == "Retrieved":
            keys = args.get("keys", {})
            if self.shop_kills_key in keys:
                self.shop_kills = int(keys[self.shop_kills_key] or 0)
            if self.shop_spent_key in keys:
                self.shop_spent = int(keys[self.shop_spent_key] or 0)
        super().on_package(cmd, args)      # Universal Tracker listens to the same messages

    @property
    def shop_kills_key(self) -> str:
        return f"tsfp_shop_kills_{self.team}_{self.slot}"

    @property
    def shop_spent_key(self) -> str:
        return f"tsfp_shop_spent_{self.team}_{self.slot}"


async def check_locations(ctx: TsfpContext, levels: dict[str, int], story: set[int]) -> None:
    found = (game_state.earned_location_ids(levels) | game_state.milestone_location_ids(levels)
             | story | ctx.objectives_found)
    found &= set(ctx.server_locations)       # only locations that exist in this seed
    new = found - set(ctx.checked_locations) - ctx.reported_locations
    if new:
        ctx.reported_locations |= new
        ctx.award_screen.found.extend(sorted(new))
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])

    if ctx.goal == game_data.GOAL_ALL_TROPHIES:
        goal = game_state.trophy_goal_reached(levels, ctx.trophy_grade, ctx.trophy_hunt_setting)
    else:
        goal = game_state.story_goal_reached(dolphin)
    if not ctx.victory_sent and goal:
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
        ctx.victory_sent = True


def show_inventory(ctx: TsfpContext, item_list: list[int]) -> None:
    """Keep the Inventory tab showing the shop's points and rows, and the bonus items received."""
    from . import gui
    shop = ctx.shop_list if ctx.shop_size else None
    levels = game_state.resistance_levels(item_list)
    resistances = [(award.removesuffix(" Damage"), levels[name], game_data.RESISTANCE_COPIES,
                    round(levels[name] * game_data.RESISTANCE_STEP * 100))
                   for name, award, _types in game_data.RESISTANCES if levels[name]]
    buffs = []
    for weapon, stat, _address, normal, change, copies, _always in sorted(game_data.WEAPON_BUFFS):
        have = min(item_list.count(game_data.ITEM_NAME_TO_ID[game_data.weapon_buff_item_name(weapon, stat, change)]),
                   copies)
        if have:
            buffs.append((weapon, stat, round(change * have * 100), normal,
                          game_data.weapon_buff_value(normal, change, have), have, copies))
    multipliers = []
    for name, (display, copies) in _SCORE_ITEMS.items():
        have = min(item_list.count(game_data.ITEM_NAME_TO_ID[name]), copies)
        if have:
            multipliers.append((display, have + 1, have, copies))
    other = []
    armour = game_state.starting_armour_level(item_list)
    if armour:
        other.append(("Starting Armour", armour * 100 // game_data.STARTING_ARMOUR_COPIES, armour,
                      game_data.STARTING_ARMOUR_COPIES))
    text = gui.inventory_text(shop, resistances, buffs, multipliers, other)
    if text == ctx.buffs_shown:
        return
    ctx.buffs_shown = text
    if ctx.ui and hasattr(ctx.ui, "update_inventory"):
        ctx.ui.update_inventory(text)


def enforce_score(ctx: TsfpContext, multiplier: int) -> None:
    """Keep the Behead The Undead points at the multiplier you have, and say so when it changes."""
    state = game_state.enforce_score_multiplier(dolphin, multiplier)
    logged = (state in ("patched", "installed"), multiplier)
    if logged == ctx.score_logged:
        return
    ctx.score_logged = logged
    if state == "busy":
        logger.error("Behead The Undead score multipliers are NOT active: the memory they need is in use. "
                     "Turn off Gecko/cheat codes in Dolphin (Config > General > Enable Cheats) and restart the game.")
    elif state == "unknown":
        logger.error("Behead The Undead score multipliers are NOT active: the scoring code is not what "
                     "the client expects.")
    elif multiplier > 1:
        logger.debug(f"Behead The Undead points are now x{multiplier}.")


_ITEM_ID_TO_NAME = {code: name for name, code in game_data.ITEM_NAME_TO_ID.items()}
_MISSIONS_BY_ITEM = {m.item_name: m for m in game_data.MISSIONS}
_BUFFS_BY_ITEM = {game_data.weapon_buff_item_name(b[0], b[1], b[4]): b for b in game_data.WEAPON_BUFFS}
_RESISTANCES_BY_ITEM = {r[0]: r for r in game_data.RESISTANCES}
_SCORE_ITEMS = {game_data.SCORE_MULTIPLIER_ITEM_NAME: ("Behead The Undead", game_data.SCORE_MULTIPLIER_COPIES),
                game_data.MISC_MULTIPLIER_ITEM_NAME: ("Miscellaneous Challenges", game_data.MISC_MULTIPLIER_COPIES)}
_NATIVE_AWARDS = (set(game_data.CHARACTER_ITEM_NAMES) | set(game_data.CHEAT_ITEM_NAMES)
                  | set(game_data.WEAPON_ITEM_NAMES) | {game_data.FILLER_ITEM_NAME})

# Where each kind of entry goes on the award screen: (0, n) before the game's own entries
# (characters, weapons, cheats, ...), (1, n) after them.
_STORY, _MISSION, _CHALLENGE = (0, 0), (0, 1), (0, 2)
_ARMOUR, _SCORE, _RESISTANCE, _BUFF, _OTHER_PLAYER = (1, 0), (1, 1), (1, 2), (1, 3), (1, 4)


def _other_player_rank(flags: int) -> int:
    """Progression, then useful, then traps, then filler."""
    if flags & 0b001:
        return 0
    if flags & 0b010:
        return 1
    if flags & 0b100:
        return 2
    return 3


def _award_line(name: str, held: int) -> tuple[str, str]:
    """The line for one of our progressive items, when you hold `held` copies of it with this one."""
    if name == game_data.PROGRESSIVE_STORY_ITEM_NAME:
        return game_data.AWARD_STORY, game_data.STORY_LEVELS[held - 1]
    if name in _BUFFS_BY_ITEM:
        weapon, stat, _address, _normal, change, _copies, _always = _BUFFS_BY_ITEM[name]
        return game_data.AWARD_BUFF.format(stat=stat.upper()), f"{weapon} {round(change * 100 * held)}%"
    if name in _SCORE_ITEMS:
        return game_data.AWARD_SCORE, f"{_SCORE_ITEMS[name][0]} x{held + 1}"
    _item, award_name, _types = _RESISTANCES_BY_ITEM[name]
    return game_data.AWARD_RESISTANCE, f"{award_name} {round(game_data.RESISTANCE_STEP * 100 * held)}%"


def _most_copies(name: str) -> int:
    if name == game_data.PROGRESSIVE_STORY_ITEM_NAME:
        return len(game_data.STORY_LEVELS)
    if name in _BUFFS_BY_ITEM:
        return _BUFFS_BY_ITEM[name][5]
    if name in _SCORE_ITEMS:
        return _SCORE_ITEMS[name][1]
    return game_data.RESISTANCE_COPIES


def award_entries(ctx: TsfpContext) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """The award screen lines for the items found or received since the last award screen, as
    (lines before the game's own entries, lines after them). Characters, cheats and weapons are left
    out: the game lists those itself once they unlock."""
    entries: list = []                   # [line or None, sort key]
    progressive: dict[str, list[int]] = {}    # item name: positions of its entries, for the totals
    for order, found in enumerate(ctx.award_screen.found):
        if isinstance(found, int):          # one of our locations: what is there
            item = ctx.locations_info.get(found)
            if item is None:
                continue
            receiver = item.player          # a NetworkItem for a location names who it is for
        else:                               # an item another player sent us
            item, receiver = found, ctx.slot
        if receiver != ctx.slot:
            name = display_item_name(ctx, item.item, item.player)
            player = ctx.player_names.get(item.player, "Someone")
            entries.append([(game_data.AWARD_OTHER_PLAYER.format(player=player), name),
                            (*_OTHER_PLAYER, _other_player_rank(item.flags), order)])
            continue
        name = _ITEM_ID_TO_NAME.get(item.item, "")
        if not name or name in _NATIVE_AWARDS:
            continue
        if name in game_data.STORY_ITEM_NAMES:
            level = game_data.STORY_ITEM_NAMES.index(name)
            if ctx.last_played == ("story", level):
                continue                    # you have just played it, so you know you have it
            entries.append([(game_data.AWARD_STORY, game_data.STORY_LEVELS[level]), (*_STORY, 0, order)])
        elif name in _MISSIONS_BY_ITEM:
            mission = _MISSIONS_BY_ITEM[name]
            if ctx.last_played == ("mission", mission):
                continue
            if mission.prefix == "Challenge":
                entries.append([(game_data.AWARD_CHALLENGE, mission.name), (*_CHALLENGE, 0, order)])
            else:
                entries.append([(game_data.AWARD_MISSION, mission.name), (*_MISSION, 0, order)])
        elif (name == game_data.PROGRESSIVE_STORY_ITEM_NAME or name in _BUFFS_BY_ITEM
              or name in _SCORE_ITEMS or name in _RESISTANCES_BY_ITEM):
            kind = (_STORY if name == game_data.PROGRESSIVE_STORY_ITEM_NAME else _BUFF if name in _BUFFS_BY_ITEM
                    else _SCORE if name in _SCORE_ITEMS else _RESISTANCE)
            progressive.setdefault(name, []).append(len(entries))
            entries.append([None, (*kind, 0, order)])
        else:
            entries.append([(game_data.AWARD_ITEM, name), (*_ARMOUR, 0, order)])
    # Progressive items show what you hold with each one: the last ones received, counting the
    # ones still on their way.
    received = [item.item for item in ctx.items_received]
    for name, positions in progressive.items():
        count = received.count(game_data.ITEM_NAME_TO_ID[name])
        for k, position in enumerate(positions):
            held = min(max(count - len(positions) + k + 1, 1), _most_copies(name))
            line = _award_line(name, held)
            if name == game_data.PROGRESSIVE_STORY_ITEM_NAME and ctx.last_played == ("story", held - 1):
                line = None
            entries[position][0] = line
    entries = [entry for entry in entries if entry[0] is not None]
    entries.sort(key=lambda entry: entry[1])
    front = [line for line, key in entries if key[0] == 0]
    back = [line for line, key in entries if key[0] == 1]
    return front, back


def note_received_items(ctx: TsfpContext) -> None:
    """Add items other players have sent since the last look to the award list. Items already
    received when the client connects are not listed; our own items come with our locations."""
    if ctx.slot is None or not ctx.items_ready():
        return
    count = len(ctx.items_received)
    if ctx.award_items_seen is None or count < ctx.award_items_seen:
        ctx.award_items_seen = count
        return
    for item in ctx.items_received[ctx.award_items_seen:]:
        if item.player != ctx.slot:
            ctx.award_screen.found.append(item)
    ctx.award_items_seen = count


def award_hook(ctx: TsfpContext) -> bool:
    """Install the award screen hook as early as possible; True when ready."""
    state = game_state.ensure_award_hook(dolphin)
    if state != ctx.award_hook_logged:
        ctx.award_hook_logged = state
        if state == "busy":
            logger.error("Archipelago items will NOT show on the award screen: the memory they need is in "
                         "use. Turn off Gecko/cheat codes in Dolphin (Config > General > Enable Cheats) and "
                         "restart the game.")
        elif state == "unknown":
            logger.error("Archipelago items will NOT show on the award screen: the game's code is not what "
                         "the client expects.")
    return state == "ready"


_SHOP_RESTOCK_ID = game_data.ITEM_NAME_TO_ID[game_data.SHOP_RESTOCK_ITEM_NAME]
SHOP_NOTICE_SECONDS = 1.5
_TROPHY_FILLER_POINTS = {game_data.ITEM_NAME_TO_ID[name]: points
                         for name, points in game_data.TROPHY_FILLER_POINTS.items()}


def shop_points(ctx: TsfpContext) -> Optional[int]:
    """Points to spend, or None until the server has said how many were earned by kills and spent."""
    if ctx.shop_kills is None or ctx.shop_spent is None:
        return None
    filler = sum(_TROPHY_FILLER_POINTS.get(item.item, 0) for item in ctx.items_received)
    return (ctx.shop_earned["trophies"] + ctx.shop_earned["story"] + ctx.shop_kills + ctx.shop_kills_pending
            + filler - ctx.shop_spent)


def shop_display_name(name: str) -> str:
    """A Future Perfect item as the shop shows it, as on the award screen: a mission or story level
    by its own name, a weapon buff as "<weapon> <buff>" (e.g. "Plasma Autorifle +25% Reserve Ammo")."""
    if name in _MISSIONS_BY_ITEM:
        return _MISSIONS_BY_ITEM[name].name
    if name in game_data.STORY_ITEM_NAMES:
        return game_data.STORY_LEVELS[game_data.STORY_ITEM_NAMES.index(name)]
    return game_data.short_item_name(game_data.GAME_NAME, name)


def display_item_name(ctx: TsfpContext, item_id: int, player: int) -> str:
    """An item's name as the award screen and the shop show it: Future Perfect and TimeSplitters 2
    items shortened (missions by their own name and so on), anything else as it is."""
    try:
        name = ctx.item_names.lookup_in_slot(item_id, player)
    except Exception:
        return "Unknown item"
    slot_info = getattr(ctx, "slot_info", {}).get(player)
    game = game_data.GAME_NAME if player == ctx.slot else getattr(slot_info, "game", None)
    if game == game_data.GAME_NAME:
        return shop_display_name(name)
    return game_data.short_item_name(game, name)


def _shop_item_text(ctx: TsfpContext, location: int, price: int) -> Optional[str]:
    info = ctx.locations_info.get(location)
    if info is None:
        return None
    name = display_item_name(ctx, info.item, info.player)
    owner = "You" if info.player == ctx.slot else ctx.player_names.get(info.player, "Someone")
    return f"{name} ({owner}) - {price} Points"


def shop_rows(ctx: TsfpContext) -> tuple[list[str], list[Optional[int]]]:
    """What each row shows, and the location each row is selling (None when it shows "Purchased")."""
    size = ctx.shop_size
    total = size // game_data.SHOP_ROWS
    restocks = sum(1 for item in ctx.items_received if item.item == _SHOP_RESTOCK_ID)
    batches = min(restocks + 1, total)
    done = set(ctx.checked_locations) | ctx.shop_bought
    rows, selling = [], []
    for k in range(game_data.SHOP_ROWS):
        c = 0
        while c < total and game_data.shop_location_id(c * game_data.SHOP_ROWS + k) in done:
            c += 1
        if c >= batches:
            rows.append("Purchased")
            selling.append(None)
            continue
        index = c * game_data.SHOP_ROWS + k
        price = ctx.shop_prices[index] if index < len(ctx.shop_prices) else 0
        location = game_data.shop_location_id(index)
        rows.append(_shop_item_text(ctx, location, price) or "Loading...")
        selling.append(location)
    return rows, selling


async def run_shop(ctx: TsfpContext, levels: dict[str, int]) -> None:
    """Count points, keep the shop menu up to date and handle what is bought there."""
    new = ctx.kill_counter.poll(dolphin)
    if new:
        ctx.shop_kills_pending += new * game_data.KILL_POINTS
    if ctx.shop_kills_pending and ctx.shop_kills is not None and ctx.server is not None:
        added, ctx.shop_kills_pending = ctx.shop_kills_pending, 0
        ctx.shop_kills += added
        await ctx.send_msgs([{"cmd": "Set", "key": ctx.shop_kills_key, "default": 0, "want_reply": False,
                              "operations": [{"operation": "add", "value": added}]}])
    story = game_state.story_points(dolphin)
    if story is not None:                       # a profile is loaded
        ctx.shop_earned["trophies"] = game_state.trophy_points(levels)
        ctx.shop_earned["story"] = story
    if ctx.award_hide:
        received = {item.item for item in ctx.items_received}
        ctx.award_hide -= {item for item in ctx.award_hide
                           if item in received and game_state.hide_from_award_screen(dolphin, item)}
    state = ctx.shop_menu.install(dolphin)
    if state != ctx.shop_state_logged:
        ctx.shop_state_logged = state
        if state == "installed":
            logger.info("The Archipelago Shop is in Extras & Shop > Archipelago Shop (the old View Movies).")
        elif state == "busy":
            logger.error("The Archipelago Shop is NOT available: the memory it needs is in use. Turn off "
                         "Gecko/cheat codes in Dolphin (Config > General > Enable Cheats), close any test tools, "
                         "and restart the game.")
        elif state == "unknown":
            logger.error("The Archipelago Shop is NOT available: the game's code is not what the client expects.")
    if state != "installed":
        return
    points = shop_points(ctx)
    rows, selling = shop_rows(ctx)
    ctx.shop_list = (points, rows)
    title = "Archipelago Shop\n" + ("Connecting..." if points is None else f"{points} Points")
    if ctx.shop_notice and time.monotonic() < ctx.shop_notice[1]:
        title = ctx.shop_notice[0]
    # Seeing an item in the shop sends a hint for it: the rows shown when the shop is opened, and a
    # row's next item once buying it brings that up.
    if ctx.server is not None and ctx.shop_hint_rows:
        unhinted = sorted({selling[k] for k in ctx.shop_hint_rows} - {None} - ctx.shop_hinted
                          - set(ctx.checked_locations))
        unhinted = [location for location in unhinted if location in ctx.locations_info
                    and (ctx.shop_hints == game_data.SHOP_HINTS_ALL
                         or ctx.shop_hints == game_data.SHOP_HINTS_PROGRESSION
                         and ctx.locations_info[location].flags & 0b001)]
        ctx.shop_hint_rows = set()
        if unhinted:
            ctx.shop_hinted.update(unhinted)
            await ctx.send_msgs([{"cmd": "LocationScouts", "locations": unhinted, "create_as_hint": 2}])
    picks = ctx.shop_menu.update(dolphin, title, rows)
    if ctx.shop_menu.just_opened:
        ctx.shop_hint_rows = set(range(game_data.SHOP_ROWS))
    for k in picks:
        location = selling[k]
        if location is None:
            continue
        index = location - game_data.shop_location_id(0)
        price = ctx.shop_prices[index] if index < len(ctx.shop_prices) else 0
        if points is None or ctx.server is None or location not in ctx.locations_info:
            logger.info("The shop can't sell anything until the client is connected to the server.")
            continue
        if price > points:
            logger.debug(f"Not enough points for that: it costs {price}, you have {points}.")
            ctx.shop_notice = (f"Not Enough Points!\n{points} Points", time.monotonic() + SHOP_NOTICE_SECONDS)
            continue
        ctx.shop_bought.add(location)
        ctx.shop_hint_rows.add(k)                  # its next item, if a restock has brought one
        ctx.shop_spent = (ctx.shop_spent or 0) + price
        points -= price
        logger.debug(f"Bought {rows[k]} ({points} points left).")
        info = ctx.locations_info[location]
        if info.player == ctx.slot and info.item in game_data.AWARD_SNAPSHOT_ITEMS:
            ctx.award_hide.add(info.item)          # bought here: not news on the award screen
        ctx.reported_locations.add(location)
        await ctx.send_msgs([{"cmd": "Set", "key": ctx.shop_spent_key, "default": 0, "want_reply": False,
                              "operations": [{"operation": "add", "value": price}]},
                             {"cmd": "LocationChecks", "locations": [location]}])


def frame_hook(ctx: TsfpContext) -> bool:
    """Install the once-a-frame hook (announcements and receiving Death Links); True when ready."""
    state = game_state.ensure_frame_hook(dolphin)
    if state != ctx.frame_hook_logged:
        ctx.frame_hook_logged = state
        if state == "busy":
            logger.error("In-game announcements and receiving Death Links are NOT available: the memory they "
                         "need is in use. Turn off Gecko/cheat codes in Dolphin (Config > General > Enable "
                         "Cheats) and restart the game.")
        elif state == "unknown":
            logger.error("In-game announcements and receiving Death Links are NOT available: the game's data "
                         "is not what the client expects.")
    return state == "ready"


async def death_link(ctx: TsfpContext, hook_ready: bool) -> None:
    """Send a Death Link when a mission fails; fail the mission being played when one arrives."""
    failed = ctx.mission_failure.poll(dolphin)
    died = ctx.arcade_deaths.poll(dolphin)
    if ctx.death_link_amnesty <= 0 or ctx.mission_failure.caused or ctx.mission_failure.waiting:
        died = None                     # off for this seed, or the death came from a Death Link we received
    enabled = ctx.slot is not None and "DeathLink" in ctx.tags
    if not enabled:
        ctx.death_pending = False
        return
    if died and not failed and died[1] % ctx.death_link_amnesty == 0:
        mission, deaths = died
        name = ctx.player_names.get(ctx.slot, "A player")
        if ctx.death_link_amnesty == 1:
            logger.info(f"You died in {mission}: Death Link sent.")
            await ctx.send_death(f"{name} died in {mission}.")
        else:
            logger.info(f"You died {deaths} times in {mission}: Death Link sent.")
            await ctx.send_death(f"{name} died {deaths} times in {mission}.")
    elif died:
        left = ctx.death_link_amnesty - died[1] % ctx.death_link_amnesty
        logger.info(f"You died in {died[0]}: {left} more death{'s' if left != 1 else ''} until a Death Link is sent.")
    if failed:
        name = ctx.player_names.get(ctx.slot, "A player")
        logger.info(f"You failed {failed}: Death Link sent.")
        await ctx.send_death(f"{name} failed {failed}.")
    if ctx.death_pending:
        ctx.death_pending = False
        target = ctx.mission_failure.fail(dolphin) if hook_ready else None
        logger.info(f"Death Link received: you died in {target}." if target
                    else "Death Link received, but you are not playing a mission, so nothing happened.")


def enforce_resistances(ctx: TsfpContext, item_list: list[int], frame_hook_ready: bool) -> None:
    """Keep player 1's damage resistances at the items held, and say so when they change."""
    levels = game_state.resistance_levels(item_list)
    state = game_state.enforce_resistances(dolphin, levels, frame_hook_ready)
    logged = (state, tuple(sorted(levels.items())))
    if logged == ctx.resist_logged:
        return
    ctx.resist_logged = logged
    if state == "busy":
        logger.error("Damage resistances are NOT active: the memory they need is in use. Turn off Gecko/cheat "
                     "codes in Dolphin (Config > General > Enable Cheats), close any test tools, and restart the "
                     "game.")
    elif state == "unknown":
        logger.error("Damage resistances are NOT active: the game's damage code is not what the client expects.")
    elif state == "ready":
        held = [f"{award} {round(game_data.RESISTANCE_STEP * 100 * levels[name])}%"
                for name, award, _types in game_data.RESISTANCES if levels[name]]
        if held:
            logger.debug("Damage resistances: " + ", ".join(held) + ".")


def enforce_misc_score(ctx: TsfpContext, multiplier: int) -> None:
    """Keep the Miscellaneous Challenges points at the multiplier you have, and say so when it changes."""
    state = game_state.enforce_misc_multiplier(dolphin, multiplier)
    logged = (state in ("patched", "installed"), multiplier)
    if logged == ctx.misc_logged:
        return
    ctx.misc_logged = logged
    if state == "busy":
        logger.error("Miscellaneous Challenges score multipliers are NOT active: the memory they need is in "
                     "use. Turn off Gecko/cheat codes in Dolphin (Config > General > Enable Cheats) and restart "
                     "the game.")
    elif state == "unknown":
        logger.error("Miscellaneous Challenges score multipliers are NOT active: the scoring code is not "
                     "what the client expects.")
    elif multiplier > 1:
        logger.debug(f"Miscellaneous Challenges points are now x{multiplier}.")


def story_mask_for(ctx: TsfpContext) -> int:
    """Which story levels are open right now: your items, plus the 1924 Future Perfect requirements."""
    final_open = True
    if ctx.goal == game_data.GOAL_FUTURE_PERFECT and (ctx.story_levels_required or ctx.trophies_required):
        levels_ok = game_state.story_levels_beaten(dolphin) >= ctx.story_levels_required
        trophies = game_state.trophies_at_grade(game_state.read_trophy_levels(dolphin), ctx.trophies_required_grade)
        trophies_ok = trophies >= ctx.trophies_required
        final_open = levels_ok and trophies_ok
        if final_open != ctx.final_level_logged:
            ctx.final_level_logged = final_open
            name = game_data.STORY_LEVELS[game_data.FINAL_STORY_LEVEL]
            needs = []
            if ctx.story_levels_required:
                needs.append(f"{ctx.story_levels_required} other story levels beaten")
            if ctx.trophies_required:
                grade = game_data.TIERS[ctx.trophies_required_grade - 1]
                needs.append(f"{ctx.trophies_required} Arcade League missions or Challenges with {grade} or better")
            if final_open:
                logger.info(f"Requirements met: {name} opens once you have it.")
            else:
                logger.info(f"{name} needs " + " and ".join(needs) + ".")
    received = [item.item for item in ctx.items_received]
    return game_state.story_mask(received, ctx.story_mode == game_data.STORY_PROGRESSIVE, final_open)


async def dolphin_sync_task(ctx: TsfpContext) -> None:
    logger.info("Starting Dolphin connector.")
    while not ctx.exit_event.is_set():
        try:
            if dolphin.is_hooked() and ctx.dolphin_status == CONNECTED:
                # Starting armour is given at the start of each life, so the player is watched
                # all the time; nothing is given until your items are known.
                armour_level = 0
                if ctx.slot is not None and ctx.items_ready() and ctx.conditions_ok:
                    armour_level = game_state.starting_armour_level([item.item for item in ctx.items_received])
                    if armour_level != ctx.armour_logged:      # said once, when the amount changes
                        ctx.armour_logged = armour_level
                        if armour_level:
                            logger.debug(f"Starting armour is now {armour_level * 25}% "
                                         f"({armour_level} of {game_data.STARTING_ARMOUR_COPIES}).")
                ctx.starting_armour.poll(dolphin, armour_level)
                hook_ready = ctx.slot is not None and frame_hook(ctx)
                ctx.announcer.poll(dolphin, hook_ready)
                note_received_items(ctx)
                if game_state._read_word(dolphin, game_data.GAME_STATE) == game_data.GAME_STATE_PLAYING:
                    ctx.last_played = game_state.current_mission(dolphin) or ctx.last_played
                ctx.award_screen.poll(dolphin, award_hook(ctx), *(award_entries(ctx) if ctx.slot is not None else ([], [])))
                await death_link(ctx, hook_ready)
                # Objectives can only be seen at the moment they complete, so watch them even
                # while the server connection is down; they are sent as soon as it is back.
                ctx.objectives_found |= ctx.objective_tracker.poll(dolphin)
                # Only act once we are logged in AND our item list has had time to
                # arrive, otherwise we'd briefly relock things the player really owns.
                if ctx.slot is not None and ctx.items_ready():
                    music = game_state.enforce_streamer_mode(dolphin, ctx.streamer_mode)
                    if music != ctx.streamer_logged:
                        ctx.streamer_logged = music
                        if music == "replaced":
                            logger.info("Streamer Mode: the Disco and credits music is replaced with Like A Monkey.")
                        elif music == "unknown" and ctx.streamer_mode:
                            logger.error("Streamer Mode is NOT active: the game's music list is not what the "
                                         "client expects. The Disco and credits music is unchanged.")
                    easier = game_state.enforce_easier_trophies(dolphin, ctx.easier_trophies)
                    if easier != ctx.easier_logged:
                        for option, state in easier.items():
                            if state == ctx.easier_logged.get(option):
                                continue
                            name = game_data.EASIER_TROPHY_NAMES[option]
                            if state == "easier":
                                logger.info(f"{name}: easier trophy requirements are active.")
                            elif state == "unknown" and ctx.easier_trophies.get(option):
                                logger.error(f"{name}: easier trophy requirements are NOT active (the game's "
                                             "values are not what the client expects).")
                        ctx.easier_logged = easier
                    levels = game_state.read_trophy_levels(dolphin)
                    await check_locations(ctx, levels, game_state.story_location_ids(dolphin))
                    if ctx.shop_size:
                        await run_shop(ctx, levels)
                    received = {item.item for item in ctx.items_received}
                    if ctx.conditions_ok:
                        game_state.enforce_unlocks(dolphin, received)
                        item_list = [item.item for item in ctx.items_received]
                        enforce_score(ctx, game_state.score_multiplier(item_list))
                        enforce_misc_score(ctx, game_state.misc_multiplier(item_list))
                        if ctx.resistances:
                            enforce_resistances(ctx, item_list, hook_ready)
                        skipped = game_state.enforce_weapon_buffs(dolphin, item_list)
                        if skipped != ctx.buffs_skipped:
                            ctx.buffs_skipped = skipped
                            if skipped:
                                logger.warning("These weapon buffs are NOT applied because the game's value is not "
                                               "one the client recognises (restart the game to reset it): "
                                               + ", ".join(skipped))
                        show_inventory(ctx, item_list)
                        story_state = game_state.enforce_story(dolphin, story_mask_for(ctx))
                        if story_state != ctx.story_state_logged:
                            ctx.story_state_logged = story_state
                            if story_state == "installed":
                                logger.info("Story level patch installed. Story levels are now controlled by your items.")
                            elif story_state == "unknown":
                                logger.error("The story level code is not what the client expects, so story "
                                             "levels will NOT be locked (story checks still work).")
                await asyncio.sleep(0.25)
            else:
                if ctx.dolphin_status == CONNECTED:
                    logger.warning(LOST)
                    ctx.dolphin_status = LOST
                logger.info("Attempting to connect to Dolphin...")
                dolphin.hook()
                if dolphin.is_hooked():
                    game_id = dolphin.read_bytes(game_data.GAME_ID_ADDRESS, 6)
                    if game_data.GAME_ID is not None and game_id != game_data.GAME_ID:
                        logger.info(f"{WRONG_GAME} (found {game_id!r})")
                        ctx.dolphin_status = WRONG_GAME
                        dolphin.un_hook()
                        await asyncio.sleep(5)
                    else:
                        logger.info(f"{CONNECTED} Game ID: {game_id!r}")
                        problems = game_state.check_conditions(dolphin)
                        ctx.conditions_ok = not problems
                        if problems:
                            logger.error("Unlock data does not look right, so missions will NOT be locked or "
                                         "unlocked (checks still work). First problems: " + "; ".join(problems[:3]))
                        else:
                            logger.info("Unlock data found. Missions are now controlled by your items.")
                        # Install the story patches straight away, before the game gets a chance to
                        # run (and Dolphin to compile) the code they change. Until the server sends
                        # your items, every story level stays locked.
                        early = game_state.enforce_story(
                            dolphin, story_mask_for(ctx) if ctx.slot is not None and ctx.items_ready() else 0)
                        ctx.story_state_logged = early
                        if early == "unknown":
                            logger.info("Story patches not installed yet (the game may still be loading); "
                                        "the client will try again once you connect to the server.")
                        else:
                            logger.info("Story patches are in place.")
                        if not problems:
                            # Same for the scoring code: in place before a challenge first runs.
                            enforce_score(ctx, 1)
                        ctx.dolphin_status = CONNECTED
                else:
                    logger.info("Dolphin not found, trying again in 5 seconds...")
                    ctx.dolphin_status = LOST
                    await asyncio.sleep(5)
        except Exception:
            dolphin.un_hook()
            logger.warning("Lost connection to Dolphin or hit an error; retrying in 5 seconds.")
            logger.debug(traceback.format_exc())
            ctx.dolphin_status = LOST
            await asyncio.sleep(5)


def main(*args) -> None:
    Utils.init_logging("TimeSplitters Future Perfect Client")

    async def _main(connect: Optional[str], password: Optional[str]) -> None:
        ctx = TsfpContext(connect, password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        if tracker_loaded:
            ctx.run_generator()            # Universal Tracker's own copy of the world, for logic
            ctx.tags.remove("Tracker")     # this is a real game client, not a tracker-only one
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        await asyncio.sleep(1)

        ctx.dolphin_sync_task = asyncio.create_task(dolphin_sync_task(ctx), name="DolphinSync")
        await ctx.exit_event.wait()
        ctx.server_address = None
        await ctx.shutdown()
        if ctx.dolphin_sync_task:
            await asyncio.sleep(3)
            await ctx.dolphin_sync_task

    parser = get_base_parser(description="TimeSplitters Future Perfect Client.")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url")
    parsed = parser.parse_args(args)

    from CommonClient import handle_url_arg
    parsed = handle_url_arg(parsed, parser=parser)

    import colorama
    colorama.init()
    asyncio.run(_main(parsed.connect, parsed.password))
    colorama.deinit()


if __name__ == "__main__":
    main()
