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
from CommonClient import get_base_parser, gui_enabled, logger, server_loop
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


class TsfpContext(CommonContext):
    game = game_data.GAME_NAME
    items_handling = 0b111  # the server sends us every item, including our own

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_status: str = NOT_CONNECTED
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
        self.final_level_logged: Optional[bool] = None    # last "Future Perfect open?" written to the log
        self.misc_logged: tuple = ()                        # last Miscellaneous multiplier state logged
        self.score_logged: tuple = ()                       # last score multiplier state written to the log
        self.buffs_shown: Optional[list] = None             # weapon buffs last shown in the Weapon Buffs tab
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
        self.death_pending: bool = False                    # a Death Link has arrived and not been dealt with
        self.death_hook_logged: str = ""
        self.objective_tracker = game_state.ObjectiveTracker()
        self.objectives_found: set[int] = set()
        self.objectives_seed: Optional[str] = None

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

    def make_gui(self):
        """The normal client window (or Universal Tracker's), plus a Weapon Buffs tab."""
        base = super().make_gui()
        try:
            from . import gui
            return gui.make_gui(base)
        except Exception:
            logger.warning("Could not add the Weapon Buffs tab; the rest of the client is unaffected.")
            logger.debug(traceback.format_exc())
            return base

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            self.connected_at = time.monotonic()
            slot_data = args.get("slot_data", {})
            self.story_mode = int(slot_data.get("story_mode", game_data.STORY_INDIVIDUAL))
            self.goal = int(slot_data.get("goal", game_data.GOAL_FUTURE_PERFECT))
            self.story_levels_required = int(slot_data.get("story_levels_required", 0))
            self.trophy_grade = int(slot_data.get("trophy_grade", 1))
            self.final_level_logged = None
            self.buffs_shown = None
            self.streamer_mode = bool(slot_data.get("streamer_mode", 0))
            self.easier_trophies = {option: bool(slot_data.get(option, 0)) for option in game_data.EASIER_TROPHIES}
            Utils.async_start(self.update_death_link(bool(slot_data.get("death_link", 0))))
            seed_version = str(slot_data.get("world_version", "unknown"))
            if seed_version == game_data.WORLD_VERSION:
                logger.info(f"This game was generated with apworld {seed_version}, the same as this client.")
            else:
                logger.warning(f"This game was generated with apworld {seed_version}, but this client is "
                               f"{game_data.WORLD_VERSION}. Items added since {seed_version} are not in this game; "
                               "generate a new one to get them.")
            seed = f"{self.seed_name}/{self.slot}"
            if self.objectives_seed not in (None, seed):   # a different game: forget the old one's objectives
                self.objectives_found = set()
            self.objectives_seed = seed
        elif cmd == "ReceivedItems":
            self.items_synced = True
        super().on_package(cmd, args)      # Universal Tracker listens to the same messages


async def check_locations(ctx: TsfpContext, levels: dict[str, int], story: set[int]) -> None:
    found = (game_state.earned_location_ids(levels) | game_state.milestone_location_ids(levels)
             | story | ctx.objectives_found)
    found &= set(ctx.server_locations)       # only locations that exist in this seed
    new = found - set(ctx.checked_locations) - ctx.reported_locations
    if new:
        ctx.reported_locations |= new
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])

    if ctx.goal == game_data.GOAL_ALL_TROPHIES:
        goal = game_state.trophy_goal_reached(levels, ctx.trophy_grade)
    else:
        goal = game_state.story_goal_reached(dolphin)
    if not ctx.victory_sent and goal:
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
        ctx.victory_sent = True


def show_weapon_buffs(ctx: TsfpContext, item_list: list[int]) -> None:
    """Keep the Weapon Buffs tab showing the buffs received so far."""
    levels = game_state.weapon_buff_levels(item_list)
    if levels == ctx.buffs_shown:
        return
    ctx.buffs_shown = levels
    if ctx.ui and hasattr(ctx.ui, "update_weapon_buffs"):
        ctx.ui.update_weapon_buffs(levels)


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
        logger.info(f"Behead The Undead points are now x{multiplier}.")


async def death_link(ctx: TsfpContext) -> None:
    """Send a Death Link when a mission fails; fail the mission being played when one arrives."""
    failed = ctx.mission_failure.poll(dolphin)
    enabled = ctx.slot is not None and "DeathLink" in ctx.tags
    if not enabled:
        ctx.death_pending = False
        return
    state = game_state.ensure_death_hook(dolphin)
    if state != ctx.death_hook_logged:
        ctx.death_hook_logged = state
        if state == "busy":
            logger.error("Death Link can be sent but NOT received: the memory it needs is in use. Turn off "
                         "Gecko/cheat codes in Dolphin (Config > General > Enable Cheats) and restart the game.")
        elif state == "unknown":
            logger.error("Death Link can be sent but NOT received: the game's data is not what the client expects.")
    if failed:
        name = ctx.player_names.get(ctx.slot, "A player")
        logger.info(f"You failed {failed}: Death Link sent.")
        await ctx.send_death(f"{name} failed {failed}.")
    if ctx.death_pending:
        ctx.death_pending = False
        target = ctx.mission_failure.fail(dolphin)
        logger.info(f"Death Link received: {target} failed." if target
                    else "Death Link received, but you are not in a mission, so nothing happened.")


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
        logger.info(f"Miscellaneous Challenges points are now x{multiplier}.")


def story_mask_for(ctx: TsfpContext) -> int:
    """Which story levels are open right now: your items, plus the Future Perfect requirement."""
    final_open = True
    if ctx.goal == game_data.GOAL_FUTURE_PERFECT and ctx.story_levels_required > 0:
        beaten = game_state.story_levels_beaten(dolphin)
        final_open = beaten >= ctx.story_levels_required
        if final_open != ctx.final_level_logged:
            ctx.final_level_logged = final_open
            name = game_data.STORY_LEVELS[game_data.FINAL_STORY_LEVEL]
            if final_open:
                logger.info(f"{ctx.story_levels_required} story levels beaten: {name} opens once you have it.")
            else:
                logger.info(f"{name} needs {ctx.story_levels_required} other story levels beaten.")
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
                            logger.info(f"Starting armour is now {armour_level * 25}% "
                                        f"({armour_level} of {game_data.STARTING_ARMOUR_COPIES}).")
                ctx.starting_armour.poll(dolphin, armour_level)
                await death_link(ctx)
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
                    received = {item.item for item in ctx.items_received}
                    if ctx.conditions_ok:
                        game_state.enforce_unlocks(dolphin, received)
                        item_list = [item.item for item in ctx.items_received]
                        enforce_score(ctx, game_state.score_multiplier(item_list))
                        enforce_misc_score(ctx, game_state.misc_multiplier(item_list))
                        skipped = game_state.enforce_weapon_buffs(dolphin, item_list)
                        if skipped != ctx.buffs_skipped:
                            ctx.buffs_skipped = skipped
                            if skipped:
                                logger.warning("These weapon buffs are NOT applied because the game's value is not "
                                               "one the client recognises (restart the game to reset it): "
                                               + ", ".join(skipped))
                        show_weapon_buffs(ctx, item_list)
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
