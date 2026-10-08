"""
Reading and writing the game's memory.

Every function takes `mem`, an object with read_byte(address), read_bytes(address, n) and
write_word(address, value). In the real client that is the dolphin_memory_engine module.
Keeping Dolphin out of this file means the logic can be tested without Dolphin running.
"""
import struct

from . import game_data


def _read_word(mem, address: int) -> int:
    return struct.unpack(">I", mem.read_bytes(address, 4))[0]


def read_trophy_levels(mem) -> dict[str, int]:
    """Best trophy per mission: 0 = none, 1 = Bronze ... 4 = Platinum."""
    levels: dict[str, int] = {}
    for mission in game_data.MISSIONS:
        value = mem.read_byte(mission.trophy_address)
        # Anything outside 0-4 is garbage (e.g. the wrong save is loaded): ignore it.
        levels[mission.item_name] = value if 0 <= value <= len(game_data.TIERS) else 0
    return levels


def earned_location_ids(levels: dict[str, int]) -> set[int]:
    """A Silver also counts as the Bronze, a Platinum as all four, and so on."""
    found: set[int] = set()
    for mission in game_data.MISSIONS:
        for tier in range(1, levels.get(mission.item_name, 0) + 1):
            found.add(game_data.location_id(mission.index, tier))
    return found


def milestone_location_ids(levels: dict[str, int]) -> set[int]:
    """Group and league milestones: a Bronze or better on every one of their missions."""
    return {
        location_id for _name, location_id, missions, _kind in game_data.MILESTONES
        if all(levels.get(m.item_name, 0) >= game_data.MILESTONE_TROPHY for m in missions)
    }


def trophy_goal_reached(levels: dict[str, int], grade: int, hunt: int = game_data.HUNT_ALL) -> bool:
    """Trophy Hunt goal: at least `grade` (1 Bronze ... 4 Platinum) on every hunted mission."""
    return all(levels.get(m.item_name, 0) >= grade for m in game_data.hunted_missions(hunt))


def trophies_at_grade(levels: dict[str, int], grade: int) -> int:
    """How many missions have at least `grade`."""
    return sum(1 for m in game_data.MISSIONS if levels.get(m.item_name, 0) >= grade)


def check_conditions(mem) -> list[str]:
    """
    Make sure every condition address really is a condition in this copy of the game, before
    anything is written. Returns a list of problems (empty = all good).
    """
    problems = []
    for mission in game_data.MISSIONS:
        a = mission.condition_address
        before = (_read_word(mem, a - 8), _read_word(mem, a - 4))
        kind = _read_word(mem, a)
        if before != game_data.CONDITION_MARKER or kind > 8:
            problems.append(f"{mission.item_name}: no condition at {a:08X}")
    for league, a in game_data.LEAGUE_CONDITIONS.items():
        kind, previous_league = _read_word(mem, a), _read_word(mem, a + 4)
        if kind > 8 or previous_league > 2:
            problems.append(f"{league} league: no condition at {a:08X}")
    for name, a, *_ in game_data.CHARACTERS + game_data.CHEATS:
        if _read_word(mem, a) > 8:
            problems.append(f"{name}: no condition at {a:08X}")
    for name, _weapon, single, double in game_data.WEAPONS:
        for a in (single, double):
            if a is not None and _read_word(mem, a) > 8:
                problems.append(f"{name}: no condition at {a:08X}")
    return problems


def _set_condition(mem, address: int, value: int) -> None:
    if _read_word(mem, address) != value:
        mem.write_word(address, value)


def enforce_unlocks(mem, received_item_ids: set[int]) -> None:
    """
    Every mission, character, cheat and weapon is unlocked exactly when its item has been received, and
    both leagues are open. Safe to call many times a second: it only writes when something
    needs to change.
    """
    def apply(address: int, item_name: str) -> None:
        owned = game_data.ITEM_NAME_TO_ID[item_name] in received_item_ids
        _set_condition(mem, address, game_data.CONDITION_UNLOCKED if owned else game_data.CONDITION_LOCKED)

    for name, address, _ in game_data.CHEATS:
        apply(address, game_data.cheat_item_name(name))
    for name, address, *_ in game_data.CHARACTERS:
        apply(address, game_data.character_item_name(name))
    for name, _weapon, single, double in game_data.WEAPONS:
        apply(single, game_data.weapon_item_name(name))
        if double is not None:                   # the (x2) version comes with the weapon
            apply(double, game_data.weapon_item_name(name))
    for mission in game_data.MISSIONS:
        apply(mission.condition_address, mission.item_name)
    for address in game_data.LEAGUE_CONDITIONS.values():
        _set_condition(mem, address, game_data.CONDITION_UNLOCKED)


# ---- Story Mode ----

def story_location_ids(mem) -> set[int]:
    """Story levels completed in single player, per difficulty (read from the save data)."""
    found: set[int] = set()
    for d, address in enumerate(game_data.STORY_PROGRESS_WORDS):
        bits = _read_word(mem, address)
        for level in range(len(game_data.STORY_LEVELS)):
            if bits >> level & 1:
                found.add(game_data.story_location_id(level, d))
    return found


def story_patch_state(mem) -> str:
    """'patched', 'original' (safe to patch) or 'unknown' (not the code we expect: leave it alone)."""
    first = tuple(_read_word(mem, game_data.STORY_FUNCTION + 4 * k) for k in range(len(game_data.STORY_PATCH)))
    if first == game_data.STORY_PATCH:
        return "patched"
    original = tuple(_read_word(mem, game_data.STORY_FUNCTION + 4 * k) for k in range(len(game_data.STORY_ORIGINAL)))
    return "original" if original == game_data.STORY_ORIGINAL else "unknown"


def apply_story_patch(mem, mask: int) -> None:
    """Install the story-level patch. Only call this when story_patch_state() is 'original'."""
    mem.write_word(game_data.STORY_MASK_ADDRESS, mask)
    # Write the instructions last to first, so the function only changes behaviour at the very
    # end, when the first instruction (the entry point) is replaced.
    for k in reversed(range(len(game_data.STORY_PATCH))):
        mem.write_word(game_data.STORY_FUNCTION + 4 * k, game_data.STORY_PATCH[k])


def story_levels_beaten(mem) -> int:
    """How many story levels other than Future Perfect are complete (on any difficulty)."""
    bits = _read_word(mem, game_data.STORY_PROGRESS_WORDS[0])   # Easy is set by every difficulty
    return bin(bits & ((1 << game_data.FINAL_STORY_LEVEL) - 1)).count("1")


def story_goal_reached(mem) -> bool:
    """Future Perfect goal: the final level complete on any difficulty."""
    return bool(_read_word(mem, game_data.STORY_PROGRESS_WORDS[0]) >> game_data.FINAL_STORY_LEVEL & 1)


def story_mask(received_items: list[int], progressive: bool = False, final_level_open: bool = True) -> int:
    """
    Bit N = story level N is available. received_items is the full list of received item IDs
    (with repeats, which is what makes Progressive Story Level work). final_level_open is False
    while Future Perfect is still held back by the "story levels required" setting.
    """
    if progressive:
        count = received_items.count(game_data.ITEM_NAME_TO_ID[game_data.PROGRESSIVE_STORY_ITEM_NAME])
        mask = (1 << min(count, len(game_data.STORY_LEVELS))) - 1
    else:
        owned = set(received_items)
        mask = 0
        for level, name in enumerate(game_data.STORY_ITEM_NAMES):
            if game_data.ITEM_NAME_TO_ID[name] in owned:
                mask |= 1 << level
    if not final_level_open:
        mask &= ~(1 << game_data.FINAL_STORY_LEVEL)
    return mask


def _ensure_story_hooks(mem) -> str:
    """
    Install the "don't roll into a level you don't own" hooks. Only call this once the
    0x801C0C30 patch is in, because the hooks' code lives in that function's unused tail.
    Returns 'patched', 'installed' or 'unknown'.
    """
    result = "patched"
    for hook, original, jump, cave, code in game_data.STORY_HOOKS:
        current = _read_word(mem, hook)
        if current == jump:
            if tuple(_read_word(mem, cave + 4 * k) for k in range(len(code))) == code:
                continue
        elif current != original:
            return "unknown"
        for k, value in enumerate(code):      # the code first...
            mem.write_word(cave + 4 * k, value)
        mem.write_word(hook, jump)            # ...then the jump to it
        result = "installed"
    return result


def enforce_story(mem, mask: int) -> str:
    """
    Keep both story patches installed (the game restores its code when it is reset) and the
    mask (from story_mask) up to date. Returns the state for logging: 'patched', 'installed'
    or 'unknown'.
    """
    state = story_patch_state(mem)
    if state == "unknown":
        return "unknown"
    if state == "original":
        # If only the level-select patch was undone, the jumps would land in the old code, so
        # take them out before anything else.
        for hook, original, jump, _cave, _code in game_data.STORY_HOOKS:
            if _read_word(mem, hook) == jump:
                mem.write_word(hook, original)
        apply_story_patch(mem, mask)
        state = "installed"
    else:
        _set_condition(mem, game_data.STORY_MASK_ADDRESS, mask)
    flow = _ensure_story_hooks(mem)
    if flow == "unknown":
        return "unknown"
    return "installed" if "installed" in (state, flow) else "patched"


# ---- Story objectives ----

def read_objective_states(mem):
    """
    None when no story level is running (or its objective list isn't ready), otherwise
    (key, {slot: state}). The key changes whenever a different level, difficulty or list is loaded.
    """
    map_id = mem.read_byte(game_data.SETUP_MAP_ID)
    difficulty = mem.read_byte(game_data.SETUP_DIFFICULTY)
    if (mem.read_byte(game_data.SETUP_GAME_MODE) != game_data.GAME_MODE_STORY
            or map_id not in game_data.STORY_MAP_IDS or difficulty >= len(game_data.STORY_DIFFICULTIES)):
        return None
    level = game_data.STORY_MAP_IDS.index(map_id)
    pointer = _read_word(mem, game_data.OBJECTIVES_POINTER)
    size = game_data.OBJECTIVE_RECORD_SIZE
    if not game_data.RAM_START <= pointer <= game_data.RAM_END - size * game_data.OBJECTIVE_RECORD_COUNT:
        return None
    data = mem.read_bytes(pointer, size * game_data.OBJECTIVE_RECORD_COUNT)
    states: dict[int, int] = {}
    for slot in range(game_data.OBJECTIVE_RECORD_COUNT):
        state = data[slot * size + game_data.OBJECTIVE_STATE_OFFSET]
        if state == 0:
            continue
        # A real record holds its own slot number and a state of 1-5. Anything else means the
        # list is still being built (or belongs to something else): ignore all of it.
        if state > game_data.OBJECTIVE_COMPLETED or struct.unpack_from(">H", data, slot * size)[0] != slot:
            return None
        states[slot] = state
    return (level, difficulty, pointer), states


class ObjectiveTracker:
    """
    Reports an objective only when it is SEEN to change to "completed" while its level is running.
    Objectives that already read "completed" the first time a list is seen are not reported: at
    that moment the list could still be the previous level's.
    """

    def __init__(self) -> None:
        self.key = None
        self.last: dict[int, int] = {}

    def poll(self, mem) -> set[int]:
        seen = read_objective_states(mem)
        if seen is None:
            self.key = None
            return set()
        key, states = seen
        found: set[int] = set()
        if key == self.key:
            wanted = {slot for slot, _name, _hidden in game_data.STORY_OBJECTIVES.get(key[0], ())}
            for slot, state in states.items():
                if (state == game_data.OBJECTIVE_COMPLETED and slot in wanted
                        and self.last.get(slot) in (1, 2, 3)):
                    found.add(game_data.objective_location_id(key[0], slot))
        self.key, self.last = key, states
        return found


# ---- Behead The Undead score multiplier ----

def score_multiplier(received_items: list[int]) -> int:
    """1 (normal) to 4, from how many Progressive Score Multipliers have been received."""
    count = received_items.count(game_data.ITEM_NAME_TO_ID[game_data.SCORE_MULTIPLIER_ITEM_NAME])
    return 1 + min(count, game_data.SCORE_MULTIPLIER_COPIES)


def misc_multiplier(received_items: list[int]) -> int:
    """1 (normal) to 4, from how many Progressive Miscellaneous Challenges Score Multipliers you have."""
    count = received_items.count(game_data.ITEM_NAME_TO_ID[game_data.MISC_MULTIPLIER_ITEM_NAME])
    return 1 + min(count, game_data.MISC_MULTIPLIER_COPIES)


def enforce_score_multiplier(mem, multiplier: int) -> str:
    """Behead The Undead: see _enforce_points_patch."""
    return _enforce_points_patch(
        mem, game_data.SCORE_TABLE, game_data.SCORE_CAVES, game_data.SCORE_HOOKS, game_data.SCORE_CAVE_CODE,
        game_data.score_table_words(multiplier),
        {game_data.score_table_words(m) for m in range(1, game_data.SCORE_MULTIPLIER_COPIES + 2)})


def enforce_misc_multiplier(mem, multiplier: int) -> str:
    """Miscellaneous Challenges: see _enforce_points_patch."""
    return _enforce_points_patch(
        mem, game_data.MISC_TABLE, game_data.MISC_CAVES, game_data.MISC_HOOKS, game_data.MISC_CAVE_CODE,
        game_data.misc_table_words(multiplier),
        {game_data.misc_table_words(m) for m in range(1, game_data.MISC_MULTIPLIER_COPIES + 2)})


def _enforce_points_patch(mem, table_address, caves, all_hooks, code, table, valid_tables) -> str:
    """
    Keep a points table at the wanted values and the scoring code reading from it. Returns
    'patched', 'installed', 'busy' (the memory it needs is in use, e.g. by Dolphin's Gecko
    cheats: nothing is changed) or 'unknown' (the scoring code is not what we expect).
    """
    current_table = tuple(_read_word(mem, table_address + 4 * k) for k in range(len(table)))
    current_code = tuple(_read_word(mem, caves + 4 * k) for k in range(len(code)))
    padding = _read_word(mem, table_address + 4 * len(table))
    ours = current_table in valid_tables and current_code == code
    empty = not any(current_table) and not any(current_code) and padding == 0
    hooks = [(a, original, jump, _read_word(mem, a)) for a, original, jump in all_hooks]
    if any(now not in (original, jump) for _a, original, jump, now in hooks):
        return "unknown"
    # A jump must never exist without the table and code it leads to.
    if not ours and any(now == jump for _a, _o, jump, now in hooks):
        for address, original, jump, now in hooks:
            if now == jump:
                mem.write_word(address, original)
        hooks = [(a, original, jump, original) for a, original, jump, _now in hooks]
    if not ours and not empty:
        return "busy"

    result = "patched"
    for k, value in enumerate(table):                       # the table first...
        if current_table[k] != value:
            mem.write_word(table_address + 4 * k, value)
    if current_code != code:                                # ...then the code that reads it...
        for k, value in enumerate(code):
            mem.write_word(caves + 4 * k, value)
        result = "installed"
    for address, _original, jump, now in hooks:             # ...then the jumps to that code
        if now != jump:
            mem.write_word(address, jump)
            result = "installed"
    return result


# ---- Weapon buffs ----

def weapon_buff_levels(received_items: list[int]) -> list[tuple[str, int, int, int, int]]:
    """
    One entry per weapon buff you have at least one copy of, in alphabetical order:
    (item name, copies counted, most copies that count, normal value, value now).
    """
    rows = []
    for weapon, stat, _address, normal, change, copies, _priority in game_data.WEAPON_BUFFS:
        name = game_data.weapon_buff_item_name(weapon, stat, change)
        have = min(received_items.count(game_data.ITEM_NAME_TO_ID[name]), copies)
        if have:
            rows.append((name, have, copies, normal, game_data.weapon_buff_value(normal, change, have)))
    return sorted(rows)


def enforce_weapon_buffs(mem, received_items: list[int]) -> list[str]:
    """
    Make every buffed stat match the copies you have. A stat is only written while it holds its
    normal value or one of its own buff steps; anything else (another cheat, a different game
    version) is left alone and its item name is returned.
    """
    skipped = []
    for weapon, stat, address, normal, change, copies, _priority in game_data.WEAPON_BUFFS:
        name = game_data.weapon_buff_item_name(weapon, stat, change)
        have = min(received_items.count(game_data.ITEM_NAME_TO_ID[name]), copies)
        target = game_data.weapon_buff_value(normal, change, have)
        current = _read_word(mem, address)
        if current == target:
            continue
        if current not in {game_data.weapon_buff_value(normal, change, k) for k in range(copies + 1)}:
            skipped.append(name)
            continue
        mem.write_word(address, target)
    return skipped


# ---- Which mission is running ----

def current_mission(mem):
    """
    What is being played, from the game's setup: ("story", level), ("mission", Mission) for an
    Arcade League mission or Challenge, or None for anything else (menus, custom Arcade matches,
    cutscenes).
    """
    map_id = mem.read_byte(game_data.SETUP_MAP_ID)
    if _read_word(mem, game_data.SETUP_FLAGS_54) & game_data.SETUP_MISSION_FLAG:
        index = _read_word(mem, game_data.SETUP_MISSION_INDEX)
        if index < len(game_data.MISSIONS):
            return "mission", game_data.MISSIONS[index]
        return None
    if mem.read_byte(game_data.SETUP_GAME_MODE) == game_data.GAME_MODE_STORY and map_id in game_data.STORY_MAP_IDS:
        return "story", game_data.STORY_MAP_IDS.index(map_id)
    return None


# ---- Easier trophy requirements ----

def enforce_easier_trophies(mem, enabled: dict[str, bool]) -> dict[str, str]:
    """
    Set each mission's trophy requirements to the easier values (option on) or the normal ones.
    Returns, per option, 'easier', 'normal' or 'unknown' (a value is neither: nothing is changed
    for that mission).
    """
    result = {}
    for option, rules in game_data.EASIER_TROPHIES.items():
        on = bool(enabled.get(option))
        current = [_read_word(mem, address) for address, _normal, _easier in rules]
        if any(now not in (normal, easier) for now, (_a, normal, easier) in zip(current, rules)):
            result[option] = "unknown"
            continue
        for now, (address, normal, easier) in zip(current, rules):
            wanted = easier if on else normal
            if now != wanted:
                mem.write_word(address, wanted)
        result[option] = "easier" if on else "normal"
    return result


# ---- Streamer Mode ----

def enforce_streamer_mode(mem, enabled: bool) -> str:
    """
    Make the Disco music slot play the replacement track (enabled) or the real one. Returns
    'replaced', 'original' or 'unknown' (the slot holds something we do not recognise: left alone).
    """
    wanted = game_data.MUSIC_REPLACEMENT_NAME if enabled else game_data.MUSIC_DISCO_NAME
    current = _read_word(mem, game_data.MUSIC_DISCO_ENTRY)
    if current not in (game_data.MUSIC_DISCO_NAME, game_data.MUSIC_REPLACEMENT_NAME):
        return "unknown"
    if current != wanted:
        mem.write_word(game_data.MUSIC_DISCO_ENTRY, wanted)
    return "replaced" if enabled else "original"


# ---- Death Link ----

def mission_name(mission) -> str:
    kind, what = mission
    return game_data.STORY_LEVELS[what] if kind == "story" else what.name


def ensure_death_hook(mem) -> str:
    """
    Make the game able to fail the current mission on request. Returns 'ready', 'busy' (the
    memory it needs is in use, e.g. by Dolphin's Gecko cheats) or 'unknown' (the game's data is
    not what we expect). Nothing is changed unless the result is 'ready'.
    """
    code = game_data.DEATH_CAVE_CODE
    entry = _read_word(mem, game_data.STATE_TABLE_PLAYING)
    if entry not in (game_data.STATE_PLAYING_HANDLER, game_data.DEATH_CAVE):
        return "unknown"
    current = tuple(_read_word(mem, game_data.DEATH_CAVE + 4 * k) for k in range(len(code)))
    trigger = _read_word(mem, game_data.DEATH_TRIGGER)
    if current == code and trigger in (0, 1):
        if entry != game_data.DEATH_CAVE:
            mem.write_word(game_data.STATE_TABLE_PLAYING, game_data.DEATH_CAVE)
        return "ready"
    if entry == game_data.DEATH_CAVE:              # never leave the game pointed at something else
        mem.write_word(game_data.STATE_TABLE_PLAYING, game_data.STATE_PLAYING_HANDLER)
    if any(current) or trigger:
        return "busy"
    for k, value in enumerate(code):
        mem.write_word(game_data.DEATH_CAVE + 4 * k, value)
    mem.write_word(game_data.STATE_TABLE_PLAYING, game_data.DEATH_CAVE)
    return "ready"


class MissionFailure:
    """Notices the game failing a mission, and can make it fail the one being played."""

    def __init__(self) -> None:
        self.armed = False        # a mission is being played and has not failed yet
        self.caused = False       # the next failure is one we asked for
        self.waiting = 0          # polls left for the game to act on our request

    def poll(self, mem):
        """Call every 0.25 s. Returns the mission's name when it has just failed by itself."""
        if self.waiting:
            self.waiting -= 1
            if not self.waiting and _read_word(mem, game_data.DEATH_TRIGGER):   # the game never took it
                mem.write_word(game_data.DEATH_TRIGGER, 0)
                self.caused = False
        mission = current_mission(mem)
        if mission is None:
            self.armed = False
            return None
        failed = _read_word(mem, game_data.SETUP_FLAGS_54) & game_data.SETUP_FAILED_FLAG
        if not failed:
            if _read_word(mem, game_data.GAME_STATE) == game_data.GAME_STATE_PLAYING:
                self.armed = True
            return None
        if not self.armed:
            return None
        self.armed = False
        if self.caused:
            self.caused = False
            return None
        return mission_name(mission)

    def fail(self, mem):
        """Fail the mission being played. Returns its name, or None when there is nothing to fail."""
        mission = current_mission(mem)
        if (mission is None or not self.armed or self.caused
                or _read_word(mem, game_data.GAME_STATE) != game_data.GAME_STATE_PLAYING
                or ensure_death_hook(mem) != "ready"):
            return None
        mem.write_word(game_data.DEATH_TRIGGER, 1)
        self.caused = True
        self.waiting = game_data.DEATH_TRIGGER_POLLS
        return mission_name(mission)


# ---- Progressive Starting Armour ----

def starting_armour_level(received_items: list[int]) -> int:
    """0 to 4: how many Progressive Starting Armour items count."""
    count = received_items.count(game_data.ITEM_NAME_TO_ID[game_data.STARTING_ARMOUR_ITEM_NAME])
    return min(count, game_data.STARTING_ARMOUR_COPIES)


def starting_armour_applies(mem) -> bool:
    """Story, Arcade League, Behead The Undead and TimeSplitters 'Story' Classic only."""
    playing = current_mission(mem)
    if playing is None:
        return False
    kind, what = playing
    if kind == "story":
        return True
    return what.prefix != "Challenge" or what.group in game_data.STARTING_ARMOUR_CHALLENGE_GROUPS


def _float(word: int) -> float:
    return struct.unpack(">f", struct.pack(">I", word))[0]


class StartingArmour:
    """
    Gives armour once at the start of each life. A new life is: a level that has just loaded (a
    mission start, or a restart from a checkpoint or the pause menu), or the player coming back
    after dying (a respawn in Arcade). It only ever raises armour, and never during a life.
    """

    def __init__(self) -> None:
        self.state = 0            # address of the player state last seen (0 = none)
        self.loading = False      # a level load has been seen since armour was last given
        self.dead = False
        self.pending = 0          # polls left before armour is given; 0 = nothing to give

    def poll(self, mem, level: int):
        """Call every 0.25 s. Returns the armour written (a number) when it gives some, else None."""
        game = _read_word(mem, game_data.GAME_STATE)
        if game == game_data.GAME_STATE_LOADING:
            self.loading = True
        pointer = _read_word(mem, game_data.PLAYER_STATE_POINTER)
        if not game_data.RAM_START <= pointer < game_data.RAM_END - 0x100:
            self.state, self.pending = 0, 0
            return None
        if game != game_data.GAME_STATE_PLAYING:
            return None
        life = _read_word(mem, pointer + game_data.PLAYER_LIFE_OFFSET)
        if life == game_data.PLAYER_DEAD:
            self.dead, self.pending = True, 0
            return None
        if life != game_data.PLAYER_ALIVE:                 # not set up yet
            return None
        if pointer != self.state or self.loading or self.dead:
            self.state, self.loading, self.dead = pointer, False, False
            self.pending = game_data.STARTING_ARMOUR_SETTLE_POLLS
        if not self.pending:
            return None
        self.pending -= 1
        if self.pending or level <= 0 or not starting_armour_applies(mem):
            return None
        full = _float(_read_word(mem, pointer + game_data.PLAYER_FULL_BAR_OFFSET))
        armour = _float(_read_word(mem, pointer + game_data.PLAYER_ARMOUR_OFFSET))
        if not 0.0 < full <= 1000.0:
            return None
        target = full * level / game_data.STARTING_ARMOUR_COPIES
        if not 0.0 <= armour < target:                     # already has that much (or isn't sane)
            return None
        mem.write_word(pointer + game_data.PLAYER_ARMOUR_OFFSET, struct.unpack(">I", struct.pack(">f", target))[0])
        return target
