"""
Game facts for TimeSplitters: Future Perfect (GameCube, NTSC-U "G3FE69", played through Dolphin).

Everything learned with Dolphin Memory Engine and the debugger goes in THIS file, so the world
(generation side) and the client (game side) always agree.

Scope: all 27 Arcade League missions and 21 Challenges (48 in total), the 13 story levels and
their objectives, all 150 characters, the 13 cheats and the 34 arcade weapons.

TROPHIES    One 4-byte value per mission, 0x18 apart, starting at 0x80502D34. The LAST byte of
            each value is read (0 = none, 1 = Bronze ... 4 = Platinum).

UNLOCKS     The game decides whether something is unlocked by evaluating a small "condition"
            (5 words) with the function at 0x801C1024. Word 0 is the condition's type:
                0 = always locked   1 = always unlocked   5 = one reward flag   8 = whole league ...
            Every mission has its own condition inside its mission definition (the two words just
            before it are always 2 and 0xBF800000). The client simply writes 1 (unlocked) or
            0 (locked) into word 0, so the save data and reward flags are never touched.
            These conditions are part of the game's own data and go back to normal whenever the
            game is restarted.
            Honorary and Elite League have their own conditions; the client sets them to 1 so both
            leagues are open from the start.
"""
from dataclasses import dataclass

GAME_NAME = "TimeSplitters Future Perfect"
WORLD_VERSION = "1.1.0"     # keep in step with archipelago.json

# The first 6 bytes of emulated memory (0x80000000) are the disc's game ID.
GAME_ID_ADDRESS = 0x80000000
GAME_ID: bytes | None = b"G3FE69"

# Archipelago item/location IDs must be unique within this game. IDs come from the
# position in GROUPS, so don't reorder it once seeds exist.
BASE_ID = 7_620_000

TIERS = ("Bronze", "Silver", "Gold", "Platinum")   # trophy byte values 1-4
TROPHY_BASE_ADDRESS = 0x80502D37   # last byte of the first challenge's 4-byte trophy value
TROPHY_STRIDE = 0x18

CONDITION_UNLOCKED = 1
CONDITION_LOCKED = 0
CONDITION_MARKER = (2, 0xBF800000)   # the two words just before every mission condition

# League conditions ("previous league complete"). Writing 1 opens the league from the start.
LEAGUE_CONDITIONS = {"HL": 0x8047629C, "EL": 0x804762B0}

# (prefix, group, ((mission, condition address), ...) in unlock order)
# Condition addresses were found in the game's mission definitions. Two openers could not be told
# apart from the data alone; they are marked CHECK. Test: write 0 to 0x80463D00 and see whether
# Vamping In Venice locks. If I Like Dead People locks instead, swap the two CHECK addresses.
GROUPS: tuple[tuple[str, str, tuple[tuple[str, int], ...]], ...] = (
    ("Challenge", "Behead The Undead", (("Brain Drain", 0x8045F728), ("Rare Or Well Done?", 0x8045F878), ("Boxing Clever", 0x8045F9E8))),
    ("Challenge", "Cut-Out Shoot-Out", (("Hart Attack", 0x8045FCE0), ("Come Hell Or High Water", 0x8045FB50), ("Balls Of Steel", 0x8045FE5C))),
    ("Challenge", "Cat Driving", (("The Cat's Out Of The Bag", 0x804601F8), ("Lap It Up", 0x80460354), ("The Cat's Pajamas", 0x804604B0))),
    ("Challenge", "Super Smashing Great", (("Avec Le Brique", 0x8046082C), ("Absolutely Potty", 0x804609FC), ("Don't Lose Your Bottle", 0x8046069C))),
    ("Challenge", "TimeSplitters 'Story' Classic", (("Queen Of Harts", 0x80460DDC), ("Sammy Hammy Namby Pamby", 0x80460E98), ("Glimpse Of Stocking", 0x80460F54))),
    ("Challenge", "Monkeying Around", (("Electro Chimp Discomatic", 0x804611BC), ("Melon Heist", 0x804613A4), ("Brass Monkeys", 0x804616B4))),
    ("Challenge", "Miscellaneous Challenges", (("Cortez Can't Jump!", 0x804619C4), ("TSUG: TimeSplitters Underground", 0x80461C48), ("Plainly Off His Rocker", 0x8046181C))),
    ("AL", "One Gun Fun", (("Rockets 101", 0x80463394), ("Big Game Hunt", 0x8046357C), ("Divine Immolation", 0x80463730))),
    ("AL", "Nightstick", (("Commuting Will Kill You", 0x80462E14), ("Toy Soldiers", 0x80462FE8), ("Dam Cold Out Here!", 0x804631D0))),
    ("AL", "On The Take", (("Vamping In Venice", 0x80463D00), ("Pirate Gold", 0x80463918), ("Virtual Brutality", 0x80464AF0))),  # CHECK opener
    ("HL", "Dead Weight", (("A Pox Of Mox", 0x8046226C), ("Rumble In The Jungle", 0x8046247C), ("Freak Unique", 0x80462644))),
    ("HL", "Fever Pitch", (("Outbreak Hotel", 0x80463EB4), ("Missile Bunker", 0x80464078), ("Bag Slag", 0x80464218))),
    ("HL", "Mode Madness", (("I Like Dead People", 0x804648FC), ("Zany Zeppelin", 0x80463B0C), ("Lip Up Fatty", 0x80464CD4))),  # CHECK opener
    ("EL", "Smash 'N Grab", (("Screw Loose", 0x8046280C), ("Oh Shoal-O-Mio", 0x804629F4), ("Astro Jocks", 0x80462C04))),
    ("EL", "Group Therapy", (("Zone Control", 0x80464400), ("Front Loaded", 0x80464578), ("Old Blaggers", 0x80464738))),
    ("EL", "Retro Chique", (("The Dead, The Bad And The Silly", 0x80464E6C), ("Ninja Garden", 0x80465030), ("Sock It To Them", 0x80465204))),
)


@dataclass(frozen=True)
class Mission:
    index: int                 # position in MISSIONS; IDs and trophy slots derive from it
    name: str
    prefix: str                # "AL", "HL", "EL" or "Challenge"
    group: str
    slot: int                  # 0 = group opener, 1 = second mission, 2 = third mission
    trophy_address: int
    condition_address: int     # word 0 = condition type: client writes 1 (unlocked) or 0 (locked)

    @property
    def item_name(self) -> str:
        return f"{self.prefix} - {self.group} - {self.name}"


MISSIONS: tuple[Mission, ...] = tuple(
    Mission(
        index=3 * g + slot, name=name, prefix=prefix, group=group, slot=slot,
        trophy_address=TROPHY_BASE_ADDRESS + TROPHY_STRIDE * (3 * g + slot),
        condition_address=condition,
    )
    for g, (prefix, group, missions) in enumerate(GROUPS)
    for slot, (name, condition) in enumerate(missions)
)

# ---- Characters ----
# The character roster is a table of 150 entries, 0x30 bytes apart from 0x80474690, and each
# entry starts with that character's unlock condition (same types as the missions).
# Every character (including the 67 that are normally open from the
# start) is an item named just after the character, and stays locked until received.
# Names from your corrected list. (name, condition address, roster entry, open by default).
# The comment is how the character normally unlocks.
CHARACTERS: tuple[tuple[str, int, int, bool], ...] = (
    ("Cortez", 0x80474690, 0, True),  # unlocked by default
    ("Henchman Cortez", 0x804746C0, 1, False),  # Story: The Russian Connection on Normal
    ("Dr. Cortez", 0x804746F0, 2, False),  # Story: You Genius, You Genix on Normal
    ("Time Assassin Cortez", 0x80474720, 3, False),  # Story: You Take the High Road on Normal
    ("Captain Ash", 0x80474750, 4, True),  # unlocked by default
    ("Harry Tipper", 0x80474780, 5, True),  # unlocked by default
    ("Swinging Tipper", 0x804747B0, 6, False),  # Story: The Russian Connection on Easy
    ("Jo-Beth Casey", 0x804747E0, 7, True),  # unlocked by default
    ("Amy Chen", 0x80474810, 8, True),  # unlocked by default
    ("Dr. Amy", 0x80474840, 9, False),  # Story: You Genius, You Genix on Easy
    ("R-110", 0x80474870, 10, True),  # unlocked by default
    ("Victorian Crow", 0x804748A0, 11, False),  # Story: Future Perfect (final level) on Normal
    ("Karma Crow", 0x804748D0, 12, False),  # Story: Future Perfect (final level) on Hard
    ("Jacob Crow", 0x80474900, 13, False),  # Story: Future Perfect (final level) on Easy
    ("Mad Old Crow", 0x80474930, 14, False),  # Story: Future Perfect (final level) on Easy
    ("Anya", 0x80474960, 15, False),  # Story: Time To Split on Normal
    ("Captain Fitzgerald", 0x80474990, 16, True),  # unlocked by default
    ("Nobby Peters", 0x804749C0, 17, False),  # Toy Soldiers earned (Bronze trophy)
    ("Sapper Johnson", 0x804749F0, 18, False),  # Sammy Hammy Namby Pamby earned (Bronze trophy)
    ("Tommy Jenkins", 0x80474A20, 19, False),  # every mission in Elite League with Bronze or better
    ("Ivor Baddic", 0x80474A50, 20, True),  # unlocked by default
    ("Pulov Yuran", 0x80474A80, 21, False),  # Plainly Off His Rocker earned (Bronze trophy)
    ("Comrade Papadov", 0x80474AB0, 22, False),  # Lap It Up earned (Bronze trophy)
    ("Warrant Officer Cain", 0x80474AE0, 23, False),  # Story: Scotland the Brave on Normal
    ("Warrant Officer Keely", 0x80474B10, 24, False),  # every mission in Honorary League with Silver or better
    ("Deep Diver", 0x80474B40, 25, False),  # Oh Shoal-O-Mio earned (Bronze trophy)
    ("The Jungle Queen", 0x80474B70, 26, False),  # Story: Scotland the Brave on Easy
    ("Robot Louis Stevenson", 0x80474BA0, 27, False),  # Story: You Take the High Road on Easy
    ("John Smith", 0x80474BD0, 28, True),  # unlocked by default
    ("Jim Smith", 0x80474C00, 29, False),  # Story: Future Perfect (final level) on Easy (co-op?)
    ("Fergal Stack", 0x80474C30, 30, False),  # every mission in Amateur League with Bronze or better
    ("Khallos", 0x80474C60, 31, True),  # unlocked by default
    ("Booty Guard", 0x80474C90, 32, False),  # Zany Zeppelin earned (Bronze trophy)
    ("Kitten Celeste", 0x80474CC0, 33, False),  # Story: The Khallos Express on Easy
    ("Henchwoman", 0x80474CF0, 34, True),  # unlocked by default
    ("Elite Henchwoman", 0x80474D20, 35, False),  # Story: The Khallos Express on Normal
    ("Henchman", 0x80474D50, 36, True),  # unlocked by default
    ("Elite Henchman", 0x80474D80, 37, False),  # Melon Heist earned (Bronze trophy)
    ("Vlad the Installer", 0x80474DB0, 38, False),  # Big Game Hunt earned (Bronze trophy)
    ("Leonid", 0x80474DE0, 39, False),  # Commuting Will Kill You earned (Bronze trophy)
    ("Oleg", 0x80474E10, 40, False),  # TSUG: TimeSplitters Underground earned (Bronze trophy)
    ("Dr. Peabody", 0x80474E40, 41, False),  # every mission in Amateur League with Gold or better
    ("Nurse Gulag", 0x80474E70, 42, True),  # unlocked by default
    ("The Deerhaunter", 0x80474EA0, 43, True),  # unlocked by default
    ("Carrion Carcass", 0x80474ED0, 44, False),  # Rare Or Well Done? earned (Bronze trophy)
    ("Headsprouter", 0x80474F00, 45, True),  # unlocked by default
    ("Mr. Fleshcage", 0x80474F30, 46, False),  # 7 challenge groups complete with Bronze or better
    ("Clip Clamp", 0x80474F60, 47, True),  # unlocked by default
    ("Crispin", 0x80474F90, 48, True),  # unlocked by default
    ("Gideon Gout", 0x80474FC0, 49, False),  # every mission in Amateur League with Silver or better
    ("Daisy Dismay", 0x80474FF0, 50, False),  # Story: Future Perfect (final level) on Easy (co-op?)
    ("Jed", 0x80475020, 51, False),  # 7 challenge groups complete with Gold or better
    ("Arthur Aching", 0x80475050, 52, False),  # Story: Mansion of Madness on Easy
    ("Gilbert Gastric", 0x80475080, 53, False),  # The Cat's Pajamas earned (Bronze trophy)
    ("Jo-Barf Creepy", 0x804750B0, 54, False),  # Story: What Lies Below on Normal
    ("Gladstone", 0x804750E0, 55, True),  # unlocked by default
    ("Blanche Deadwood", 0x80475110, 56, True),  # unlocked by default
    ("Gaston Boucher", 0x80475140, 57, False),  # Story: Mansion of Madness on Normal
    ("Dr. Lancet", 0x80475170, 58, False),  # Story: What Lies Below on Easy
    ("Dr. Pustule", 0x804751A0, 59, True),  # unlocked by default
    ("Nurse Tourniquet", 0x804751D0, 60, True),  # unlocked by default
    ("Nurse Sputum", 0x80475200, 61, False),  # Missile Bunker earned (Bronze trophy)
    ("Lenny Oldburn", 0x80475230, 62, True),  # unlocked by default
    ("Edwina", 0x80475260, 63, True),  # unlocked by default
    ("Deadwina", 0x80475290, 64, False),  # I Like Dead People earned (Bronze trophy)
    ("Brother Bartholomew", 0x804752C0, 65, True),  # unlocked by default
    ("Sister Faith", 0x804752F0, 66, False),  # every mission in Elite League with Silver or better
    ("Envirosuit", 0x80475320, 67, True),  # unlocked by default
    ("Neophyte Lucian", 0x80475350, 68, False),  # Zone Control earned (Bronze trophy)
    ("Neophyte Constance", 0x80475380, 69, False),  # every mission in Honorary League with Bronze or better
    ("Security", 0x804753B0, 70, True),  # unlocked by default
    ("Jack Sprocket", 0x804753E0, 71, False),  # Story: Breaking and Entering on Normal
    ("Inceptor", 0x80475410, 72, False),  # Story: Breaking and Entering on Easy
    ("Inceptress", 0x80475440, 73, True),  # unlocked by default
    ("The Freak", 0x80475470, 74, True),  # unlocked by default
    ("Tin-Legs Tommy", 0x804754A0, 75, False),  # Boxing Clever earned (Bronze trophy)
    ("SecuriDroid XP", 0x804754D0, 76, True),  # unlocked by default
    ("The General", 0x80475500, 77, False),  # Story: Time To Split on Easy
    ("Private Hicks", 0x80475530, 78, True),  # unlocked by default
    ("Private Jones", 0x80475560, 79, False),  # Story: Something to Crow About on Normal
    ("Lazarus Mumble", 0x80475590, 80, True),  # unlocked by default
    ("Mordecai Jones", 0x804755C0, 81, False),  # Story: Machine Wars on Easy
    ("Ghengis Kant", 0x804755F0, 82, False),  # Story: Machine Wars on Normal
    ("Angel Forge", 0x80475620, 83, True),  # unlocked by default
    ("Prison Officer", 0x80475650, 84, False),  # Screw Loose earned (Bronze trophy)
    ("Lt. Black", 0x80475680, 85, True),  # unlocked by default
    ("INSETICK SD/12", 0x804756B0, 86, True),  # unlocked by default
    ("INSETICK SK/10", 0x804756E0, 87, False),  # every mission in Elite League with Gold or better
    ("PROMETHEUS SD/7", 0x80475710, 88, True),  # unlocked by default
    ("PROMETHEUS SD/8", 0x80475740, 89, False),  # Virtual Brutality earned (Bronze trophy)
    ("GOLIATH SD/9", 0x80475770, 90, False),  # Story: Something to Crow About on Easy
    ("Med-Unit 6", 0x804757A0, 91, True),  # unlocked by default
    ("Time Assassin", 0x804757D0, 92, False),  # Story: The Hooded Man on Normal
    ("Berserker Splitter", 0x80475800, 93, False),  # Story: The Hooded Man on Easy
    ("Monkey", 0x80475830, 94, True),  # unlocked by default
    ("Cyborg Chimp", 0x80475860, 95, True),  # unlocked by default
    ("Brains", 0x80475890, 96, False),  # Brain Drain earned (Bronze trophy)
    ("Ninja Monkey", 0x804758C0, 97, True),  # unlocked by default
    ("Renzo", 0x804758F0, 98, True),  # unlocked by default
    ("Goddard", 0x80475920, 99, False),  # Come Hell Or High Water earned (Bronze trophy)
    ("Schmidt", 0x80475950, 100, True),  # unlocked by default
    ("Jacque De La Morte", 0x80475980, 101, False),  # Vamping In Venice earned (Bronze trophy)
    ("Viola", 0x804759B0, 102, False),  # Hart Attack earned (Bronze trophy)
    ("Mr. Underwood", 0x804759E0, 103, False),  # Glimpse Of Stocking earned (Bronze trophy)
    ("Sewer Zombie", 0x80475A10, 104, False),  # 7 challenge groups complete with Silver or better
    ("Undead Priest", 0x80475A40, 105, True),  # unlocked by default
    ("Crypt Zombie", 0x80475A70, 106, True),  # unlocked by default
    ("Maiden", 0x80475AA0, 107, True),  # unlocked by default
    ("Changeling", 0x80475AD0, 108, False),  # every mission in Honorary League with Gold or better
    ("The Cropolite", 0x80475B00, 109, True),  # unlocked by default
    ("Jared Slim", 0x80475B30, 110, False),  # The Dead, The Bad And The Silly earned (Bronze trophy)
    ("Venus", 0x80475B60, 111, False),  # Bag Slag earned (Bronze trophy)
    ("Chastity", 0x80475B90, 112, True),  # unlocked by default
    ("Ghost", 0x80475BC0, 113, True),  # unlocked by default
    ("The Master", 0x80475BF0, 114, False),  # Divine Immolation earned (Bronze trophy)
    ("Riot Officer", 0x80475C20, 115, True),  # unlocked by default
    ("Mischief", 0x80475C50, 116, False),  # Brass Monkeys earned (Bronze trophy)
    ("Mr. Giggles", 0x80475C80, 117, True),  # unlocked by default
    ("Leo Krupps", 0x80475CB0, 118, False),  # Rumble In The Jungle earned (Bronze trophy)
    ("Stumpy", 0x80475CE0, 119, False),  # Front Loaded earned (Bronze trophy)
    ("Bear", 0x80475D10, 120, True),  # unlocked by default
    ("Kypriss", 0x80475D40, 121, True),  # unlocked by default
    ("Stone Golem", 0x80475D70, 122, True),  # unlocked by default
    ("Aztec Warrior", 0x80475DA0, 123, False),  # Avec Le Brique earned (Bronze trophy)
    ("High Priest", 0x80475DD0, 124, True),  # unlocked by default
    ("Dinosaur", 0x80475E00, 125, True),  # unlocked by default
    ("Braces", 0x80475E30, 126, False),  # Old Blaggers earned (Bronze trophy)
    ("Handyman", 0x80475E60, 127, True),  # unlocked by default
    ("Candi Skyler", 0x80475E90, 128, False),  # Screw Loose earned (Bronze trophy)
    ("R One-Oh-Seven", 0x80475EC0, 129, True),  # unlocked by default
    ("Calamari", 0x80475EF0, 130, True),  # unlocked by default
    ("Corporal Hart", 0x80475F20, 131, False),  # Story: Future Perfect (final level) on Normal
    ("Badass Cyborg", 0x80475F50, 132, False),  # Balls Of Steel earned (Bronze trophy)
    ("Snowman", 0x80475F80, 133, False),  # Dam Cold Out Here! earned (Bronze trophy)
    ("Robofish", 0x80475FB0, 134, True),  # unlocked by default
    ("Chinese Chef", 0x80475FE0, 135, False),  # Ninja Garden earned (Bronze trophy)
    ("Gingerbread Man", 0x80476010, 136, True),  # unlocked by default
    ("Duckman Drake", 0x80476040, 137, True),  # unlocked by default
    ("Koozer Mox", 0x80476070, 138, False),  # A Pox Of Mox earned (Bronze trophy)
    ("Teeth Mummy", 0x804760A0, 139, True),  # unlocked by default
    ("Captain Ed Shivers", 0x804760D0, 140, False),  # Pirate Gold earned (Bronze trophy)
    ("Gretel", 0x80476100, 141, True),  # unlocked by default
    ("Arial DaVinci", 0x80476130, 142, True),  # unlocked by default
    ("Dozer", 0x80476160, 143, False),  # Lip Up Fatty earned (Bronze trophy)
    ("Sheriff Skullface", 0x80476190, 144, True),  # unlocked by default
    ("The Shoal", 0x804761C0, 145, True),  # unlocked by default
    ("Hans", 0x804761F0, 146, False),  # Freak Unique earned (Bronze trophy)
    ("Mr. Socky", 0x80476220, 147, False),  # Sock It To Them earned (Bronze trophy)
    ("Lt. Christine Malone", 0x80476250, 148, True),  # unlocked by default
    ("Eli Scrubs", 0x80476280, 149, True),  # unlocked by default
)


def character_item_name(name: str) -> str:
    return name


CHARACTER_ITEM_NAMES: tuple[str, ...] = tuple(character_item_name(c[0]) for c in CHARACTERS)

# ---- Cheats ----
# 16 cheat entries, 0x1C bytes apart from 0x8044EE14, each with its unlock condition 8 bytes in
# (same condition types as the missions). Only the 13 cheats used in the normal game are items;
# the 3 unused ones (Infinite Ammo, Skating and one that isn't in the menu) are never touched.
# Names from your corrected list. (name, condition address, cheat entry). The comment is how the
# cheat normally unlocks; in Archipelago only the item ("<name> Unlock") unlocks it.
CHEATS: tuple[tuple[str, int, int], ...] = (
    ("Big Heads", 0x8044EE1C, 0),  # Outbreak Hotel with Bronze or better
    ("Small Heads", 0x8044EE38, 1),  # A Pox Of Mox with Bronze or better
    ("Human Gun Sounds", 0x8044EE54, 2),  # The Cat's Out Of The Bag with Bronze or better
    ("Big Hands", 0x8044EE70, 3),  # Cortez Can't Jump! with Bronze or better
    ("Paintball", 0x8044EEA8, 5),  # Absolutely Potty with Bronze or better
    ("Fat Characters", 0x8044EEC4, 6),  # Commuting Will Kill You with Bronze or better
    ("All Characters Cloaked", 0x8044EEFC, 8),  # Queen Of Harts with Bronze or better
    ("Slow Motion Deaths", 0x8044EF18, 9),  # Rockets 101 with Bronze or better
    ("Cardboard Characters", 0x8044EF34, 10),  # Hart Attack with Bronze or better
    ("Rotating Heads", 0x8044EF50, 11),  # Brain Drain with Bronze or better
    ("Old Film", 0x8044EF88, 13),  # I Like Dead People with Bronze or better
    ("8-Bit", 0x8044EFA4, 14),  # Screw Loose with Bronze or better
    ("Cascade", 0x8044EFC0, 15),  # Zone Control with Bronze or better
)

# ---- Story Mode ----
# The 13 story levels in order, as (year, name). Bit k of each progress word below is
# "level k completed".
STORY_LEVEL_DATA: tuple[tuple[int, str], ...] = (
    (2401, "Time To Split"), (1924, "Scotland the Brave"), (1969, "The Russian Connection"),
    (1969, "The Khallos Express"), (1994, "Mansion of Madness"), (1994, "What Lies Below"),
    (2052, "Breaking and Entering"), (2052, "You Genius, U Genix"), (2243, "Machine Wars"),
    (2243, "Something to Crow About"), (1924, "You Take The High Road"), (2401, "The Hooded Man"),
    (1924, "Future Perfect"),
)
STORY_LEVELS: tuple[str, ...] = tuple(f"{year} {name}" for year, name in STORY_LEVEL_DATA)
FINAL_STORY_LEVEL = len(STORY_LEVELS) - 1      # 1924 Future Perfect
STORY_DIFFICULTIES = ("Easy", "Normal", "Hard")
# Single-player completion words in the save data, one per difficulty (finishing on Hard also
# sets Normal and Easy). Only ever READ by the client: they are the story locations.
STORY_PROGRESS_WORDS = (0x8050348C, 0x80503490, 0x80503494)

# The game's setup for whatever is being played right now.
SETUP_MAP_ID = 0x805015BC          # 101 and 102 are the menus
SETUP_GAME_MODE = 0x805015BD       # 10 = story
SETUP_DIFFICULTY = 0x805015BF      # 0 Easy, 1 Normal, 2 Hard
# Map ID of each story level, in order (the game's own table at 0x803F2918, used by its
# "which story level is this map" function at 0x8002F130).
STORY_MAP_IDS = (2, 4, 18, 11, 1, 17, 6, 22, 5, 14, 9, 26, 81)
GAME_MODE_STORY = 10

# ---- Story objectives ----
# While a story level runs, 0x806128AC points at the game's list of 45 objective records, 0x4C
# bytes each: +0x00 slot number (2 bytes), +0x02 text ID (2 bytes), +0x08 type, +0x0B state.
# States: 0 unused, 1 not given yet, 2 active, 3 completing, 4 failed, 5 completed (the game's
# own "is it complete" test at 0x80220F30 is state == 5).
OBJECTIVES_POINTER = 0x806128AC
OBJECTIVE_RECORD_SIZE = 0x4C
OBJECTIVE_RECORD_COUNT = 45
OBJECTIVE_STATE_OFFSET = 0x0B
OBJECTIVE_COMPLETED = 5
RAM_START, RAM_END = 0x80000000, 0x81800000

# level -> ((slot, name, hidden), ...). Slots and names recorded by playing through every level.
# "hidden" objectives never appear on screen; you named them after what completes them. They are
# the ones to remove first if any turn out to misbehave.
STORY_OBJECTIVES: dict[int, tuple[tuple[int, str, bool], ...]] = {
    0: ((0, "Reach the Rebel Base", False),
        (1, "Use the Gun Emplacement to Defend against the TimeSplitter Attack", False),
        (2, "Help Defend the Rebel Base", False),
        (3, "Eliminate the Time Assassins in the Battlements", True),
        (4, "Reach the Bridge", True)),
    1: ((1, "Infiltrate the Castle", False),
        (2, "Locate the Time Crystal Mining Site", False),
        (3, "Gain Entry to the Meeting Hall", False),
        (4, "Access the Underground areas of the Island", False),
        (5, "Destroy the Enemy Tank", False),
        (6, "Protect Captain Ash", False),
        (7, "Help Captain Ash rescue his assistant", False),
        (10, "Escape the Trap", False),
        (12, "Eliminate Mounted Gunner at Castle Entrance", True),
        (14, "Disable the Ship Turret", True)),
    2: ((0, "Find Time Traveler", False),
        (1, "Deactivate the Electricity", False),
        (2, "Protect Harry Tipper", False),
        (3, "Gain access to Sector 3", False),
        (4, "Restore Main Power", False),
        (5, "Activate Starter Motor", False),
        (6, "Restore Water Pressure", False),
        (7, "Locate Khallos' Train", False),
        (9, "Rendezvous at the Water Tower", False),
        (10, "Destroy the Blast Door", True)),
    3: ((0, "Destroy the Helicopter", False),
        (1, "Find Khallos", False),
        (2, "Deactivate the Gas Trap", False),
        (3, "Prevent the Missile Launch", False),
        (4, "Defeat Khallos", False),
        (5, "Stop the Train", False),
        (6, "Protect Future Cortez from Henchmen", True),
        (24, "Use SAM to take out the Helicopter", True),
        (26, "Play the Slot Machine", True),
        (30, "Reach the Second Train", True)),
    4: ((0, "Investigate the Mansion", False),
        (1, "Rescue the Scientist", False),
        (2, "Locate the Lab Entrance", False),
        (3, "Defeat the Creature", False),
        (4, "Investigate the Attic", False),
        (9, "Eliminate the Bugs", True),
        (10, "Clear out the Zombies in the Dining Hall", True),
        (11, "Eliminate the Ghosts", True)),
    5: ((0, "Uncover the Identity of the Mystery Time Traveler", False),
        (1, "Protect Jo-Beth from the Zombie Horde", False),
        (2, "Eliminate Princess", False),
        (3, "Escape from the Catacombs", False),
        (10, "Unlock Security Door A", True)),
    6: ((0, "Locate Crow's Office", False),
        (1, "Penetrate Rooftop Security", False),
        (2, "Protect the Intruder", False),
        (3, "Activate Fire Suppression System", False),
        (4, "Help Amy Gain Access to Crow's Floor", False),
        (5, "Access Crow's Terminal", False),
        (6, "Return to the Lift", False)),
    7: ((0, "Find Jacob Crow", False),
        (1, "Obtain an Employee's ID Card", False),
        (2, "Pass through the Security Area with Amy", False),
        (3, "Pass through the Sterilization Sensors", False),
        (5, "Destroy Crow's Security Droids", False),
        (6, "Clear the Area of Hostiles", False),
        (14, "Decode first Security Terminal", False),
        (15, "Decode Phase Two of First Security Terminal", False),
        (16, "Destroy the Railbots", False),
        (18, "Decode Second Security Terminal", False),
        (19, "Destroy the Spiderbots", False)),
    8: ((0, "Reach the Battle Tank", False),
        (1, "Gain Access to the Processing Facility", False),
        (2, "Obtain a Cybernetic Security Implant", False),
        (3, "Locate the UltraNet Secret Laboratory", False),
        (4, "Destroy the Fighters with the GOLIATH", True),
        (5, "Activate the GOLIATH", True),
        (7, "Reach the GOLIATH", True)),
    9: ((0, "Terminate Crow", False),
        (1, "Deactivate the Central Power Core", False),
        (2, "Defeat the Battle Mech", False),
        (3, "Destroy the TimeSplitters Life Support System", False),
        (4, "Eliminate the Creature", False),
        (5, "Destroy First Security Droid", True),
        (6, "Destroy Second Security Droid", True),
        (8, "Activate the Power Node", True),
        (10, "Destroy the Electric Wall", True),
        (11, "Learn about Crow's TimeSplitter Army", True)),
    10: ((0, "Activate the Drilling Machine", False),),
    11: ((0, "Protect your Past Self from the Time Assassins", False),
         (1, "Destroy the TimeSplitter Mothership", False)),
}

# The game asks the function at 0x801C0C30 "is story level N available?" (from the level select
# and the difficulty select). It normally answers "level 0 always, otherwise if level N-1 was
# completed on Easy". The client replaces its first five instructions with:
#     lis   r4, 0x801C
#     lwz   r4, 0x0C44(r4)      # read a 32-bit mask the client keeps up to date
#     srw   r4, r4, r3          # shift by the level number
#     rlwinm r3, r4, 0, 31, 31  # keep bit 0: 1 = available
#     blr
# and stores the mask (bit N = you have that level's item) at 0x801C0C44, inside the old body.
STORY_FUNCTION = 0x801C0C30
STORY_ORIGINAL = (0x9421FFD0, 0x7C0802A6, 0x90010034, 0x93E1002C, 0x7CBF2B78, 0x93C10028)
STORY_PATCH = (0x3C80801C, 0x80840C44, 0x7C841C30, 0x548307FE, 0x4E800020)
STORY_MASK_ADDRESS = 0x801C0C44


# After a story level is beaten, the game's story flow (function at 0x80031FE8) moves on to the
# next level by itself. A second, tiny patch stops that when you don't have the next level:
# the instruction at 0x80032284 (where the flow is about to start a level) jumps to a few
# instructions placed in the now-unused rest of the 0x801C0C30 function:
#     lwz   r0, 0x30(r31)       # the instruction we replaced (story flow state)
#     cmpwi r0, 0 / bne back    # only act when a level is about to start
#     lwz   r3, 0x28(r31)       # the level it's about to start
#     check the same mask       # owned -> back, start it as normal
#     li r4, 101 / stb r4, 0x4c(r30) / b end   # not owned -> load the front end (menus) instead,
#                                              # exactly as the game does when you quit a level
#     back: b 0x80032288
STORY_FLOW_HOOK = 0x80032284
STORY_FLOW_ORIGINAL = 0x801F0030
STORY_FLOW_HOOK_WORD = 0x4818E9C4            # b 0x801C0C48
STORY_FLOW_CAVE = 0x801C0C48
STORY_FLOW_CAVE_CODE = (
    0x801F0030, 0x2C000000, 0x40820028, 0x807F0028, 0x3C80801C, 0x80840C44, 0x7C841C30,
    0x548407FF, 0x40820010, 0x38800065, 0x989E004C, 0x4BE717B8, 0x4BE71610,
)

# Three levels have no ending cutscene (The Russian Connection, Mansion of Madness, Machine Wars).
# For those the flow moves to the next level straight from the save screen, at 0x8003209C,
# and sending the game to the menus from the hook above froze it (see below).
# So a third patch catches that case earlier: the instruction at 0x8003209C (level + 1) jumps to
#     addi r4, r3, 1            # the next level
#     check the same mask       # owned -> do the replaced instruction and carry on as normal
#     li r0, 0 / stw r0, 0x4c(r30) / stw r0, 0x50(r30) / stb r0, 0x93(r30)
#     b 0x8003203C              # not owned -> the game's own "back to the menus" branch
# The three stores matter: here the flow is called by the save screen with a setup that still
# holds what the level's intro cutscene was launched with (flags 0x20000000 = "cutscene"), and
# loading the menus with that flag froze the game. A level or cutscene launch overwrites those
# fields itself; the menus branch does not, so the patch clears them.
STORY_SKIP_HOOK = 0x8003209C
STORY_SKIP_ORIGINAL = 0x38030001
STORY_SKIP_HOOK_WORD = 0x4818EBE0            # b 0x801C0C7C
STORY_SKIP_CAVE = 0x801C0C7C
STORY_SKIP_CAVE_CODE = (
    0x38830001, 0x3CC0801C, 0x80C60C44, 0x7CC62430, 0x54C607FF, 0x4182000C, 0x38030001,
    0x4BE71408, 0x38000000, 0x901E004C, 0x901E0050, 0x981E0093, 0x4BE71390,
)
# (hook address, original instruction, jump, cave address, cave code)
STORY_HOOKS = (
    (STORY_FLOW_HOOK, STORY_FLOW_ORIGINAL, STORY_FLOW_HOOK_WORD, STORY_FLOW_CAVE, STORY_FLOW_CAVE_CODE),
    (STORY_SKIP_HOOK, STORY_SKIP_ORIGINAL, STORY_SKIP_HOOK_WORD, STORY_SKIP_CAVE, STORY_SKIP_CAVE_CODE),
)

def story_item_name(level: int) -> str:
    return STORY_LEVELS[level]


def story_location_name(level: int, difficulty: int) -> str:
    return f"{STORY_LEVELS[level]} Completed ({STORY_DIFFICULTIES[difficulty]})"


def story_location_id(level: int, difficulty: int) -> int:
    return BASE_ID + 500 + level * len(STORY_DIFFICULTIES) + difficulty


def objective_location_name(level: int, name: str) -> str:
    return f"{STORY_LEVELS[level]} - {name}"


def objective_location_id(level: int, slot: int) -> int:
    return BASE_ID + 600 + level * OBJECTIVE_RECORD_COUNT + slot


STORY_ITEM_NAMES: tuple[str, ...] = tuple(story_item_name(k) for k in range(len(STORY_LEVELS)))
PROGRESSIVE_STORY_ITEM_NAME = "Progressive Story Level"


def cheat_item_name(name: str) -> str:
    return f"{name} Unlock"


CHEAT_ITEM_NAMES: tuple[str, ...] = tuple(cheat_item_name(c[0]) for c in CHEATS)
MISSION_ITEM_NAMES: tuple[str, ...] = tuple(m.item_name for m in MISSIONS)
ARCADE_ITEM_NAMES: tuple[str, ...] = tuple(m.item_name for m in MISSIONS if m.prefix != "Challenge")
CHALLENGE_ITEM_NAMES: tuple[str, ...] = tuple(m.item_name for m in MISSIONS if m.prefix == "Challenge")
MISSION_NAMES: tuple[str, ...] = tuple(m.name for m in MISSIONS)

# ---- Arcade weapons ----
# The weapon table has 70 entries, 0x3C bytes apart from 0x8043E22C, each with its unlock
# condition 0x1C bytes in (same condition types as the missions). The custom weapon set menu
# lists the weapons whose condition passes. Each weapon below is one item ("<name> Unlock");
# owning it also unlocks its dual-wield (x2) version where there is one.
# Left alone: Unarmed (always available) and the weapons the game never offers (Temporal Uplink,
# Monkey Gun (x2), TNT, Time Disrupter Grenades).
# (name, weapon id, condition address, (x2) condition address or None)
WEAPONS: tuple[tuple[str, int, int, int | None], ...] = (
    ("Baseball Bat", 54, 0x8043EEF0, None),
    ("Brick", 55, 0x8043EF2C, None),            # normally a reward (flag 11)
    ("Pistol 9mm", 2, 0x8043E2C0, 0x8043E338),
    ("Kruger 9mm", 5, 0x8043E374, 0x8043E3EC),
    ("LX-18", 8, 0x8043E428, 0x8043E4A0),
    ("Scifi Handgun", 25, 0x8043E824, 0x8043E89C),
    ("Revolver", 11, 0x8043E4DC, None),
    ("Injector", 58, 0x8043EFE0, None),
    ("Mag-Charger", 36, 0x8043EAB8, None),
    ("Flamethrower", 20, 0x8043E6F8, None),
    ("Machine Gun", 51, 0x8043EE3C, 0x8043EE78),
    ("K-SMG", 48, 0x8043ED88, 0x8043EE00),
    ("Shotgun", 53, 0x8043EEB4, None),
    ("Dispersion Gun", 15, 0x8043E5CC, None),
    ("Tactical 12-Gauge", 14, 0x8043E590, None),
    ("Soviet Rifle", 22, 0x8043E770, None),
    ("Harpoon Gun", 21, 0x8043E734, None),
    ("ElectroTool", 23, 0x8043E7AC, None),
    ("Plasma Autorifle", 35, 0x8043EA7C, None),
    ("SBP500", 59, 0x8043F01C, None),
    ("Monkey Gun", 38, 0x8043EB30, None),       # normally a reward (flag 15)
    ("Minigun", 16, 0x8043E608, None),
    ("Rocket Launcher", 30, 0x8043E950, None),
    ("Heatseeker", 29, 0x8043E914, None),
    ("Ghost Gun", 34, 0x8043EA40, None),
    ("Scifi Sniper", 32, 0x8043E9C8, None),
    ("Vintage Rifle", 19, 0x8043E6BC, None),
    ("Sniper Rifle", 18, 0x8043E680, None),
    ("Flare Gun", 12, 0x8043E518, 0x8043E554),
    ("Proximity Mines", 43, 0x8043EC5C, None),
    ("Remote Mines", 44, 0x8043EC98, None),
    ("Timed Mines", 46, 0x8043ED10, None),
    ("Grenades", 40, 0x8043EBA8, None),
    ("Plasma Grenades", 42, 0x8043EC20, None),
)


def weapon_item_name(name: str) -> str:
    return f"{name} Unlock"


WEAPON_ITEM_NAMES: tuple[str, ...] = tuple(weapon_item_name(w[0]) for w in WEAPONS)

# ---- Weapon buffs ----
# Whole-number weapon stats the client can raise: clip size and bullets per shot in the weapon
# table (0x29C bytes per weapon from 0x80432D7C; found with Ralf's weapon modifier codes on
# GC-Forever), and the most ammo you can carry (0xE0 bytes per ammo type from 0x8042E318).
# These are plain data: a change applies on the next reload, survives loading a level and resets
# when the game restarts. The dual-wield (x2) weapons use the same records, so they get the
# same buffs. Fire rate, accuracy and damage are left out on purpose: they would apply to
# enemies carrying the weapon as well.
# Each row is one progressive item: every copy adds `change` of the normal value, up to `copies`.
# The table comes from TSFP_Weapon_Buffs.xlsx (see docs/). The position of a row decides its item
# ID, so only ever add rows at the end.
# (weapon, stat, address, normal value, change per copy, copies, always in the pool)
WEAPON_BUFFS: tuple[tuple[str, str, int, int, float, int, bool], ...] = (
    ("Pistol 9mm", "Clip Size", 0x80432D7C, 8, 0.25, 3, False),
    ("Kruger 9mm", "Clip Size", 0x80433018, 8, 0.25, 3, False),
    ("LX-18", "Clip Size", 0x804332B4, 18, 0.25, 3, False),
    ("Revolver", "Clip Size", 0x80433550, 6, 0.25, 3, False),
    ("Tactical 12-Gauge", "Clip Size", 0x80433A88, 8, 0.25, 3, False),
    ("Dispersion Gun", "Bullets Per Shot", 0x80433D7C, 3, 0.25, 2, True),
    ("Sniper Rifle", "Clip Size", 0x8043425C, 5, 0.25, 3, False),
    ("Vintage Rifle", "Clip Size", 0x804344F8, 8, 0.25, 3, False),
    ("Harpoon Gun", "Clip Size", 0x80434A30, 12, 0.25, 3, False),
    ("Soviet Rifle", "Clip Size", 0x80434CCC, 30, 0.25, 3, False),
    ("Scifi Handgun", "Clip Size", 0x80435204, 16, 0.25, 3, False),
    ("Rocket Launcher", "Clip Size", 0x8043573C, 6, 0.25, 3, False),
    ("Scifi Sniper", "Clip Size", 0x804359D8, 8, 0.25, 3, False),
    ("Mag-Charger", "Clip Size", 0x804361AC, 12, 0.25, 3, False),
    ("Monkey Gun", "Clip Size", 0x80436448, 64, 0.25, 3, False),
    ("K-SMG", "Clip Size", 0x80437BC4, 32, 0.25, 3, False),
    ("Machine Gun", "Clip Size", 0x80437E60, 32, 0.25, 3, False),
    ("Injector", "Clip Size", 0x804390A4, 8, 0.25, 3, True),
    ("SBP500", "Clip Size", 0x80439340, 64, 0.25, 3, False),
    ("Pistol 9mm", "Reserve Ammo", 0x8042E318, 60, 0.25, 3, False),
    ("Kruger 9mm", "Reserve Ammo", 0x8042E3F8, 60, 0.25, 3, False),
    ("LX-18", "Reserve Ammo", 0x8042E4D8, 60, 0.25, 3, False),
    ("Minigun", "Reserve Ammo", 0x8042E5B8, 400, 0.25, 3, False),
    ("Sniper Rifle", "Reserve Ammo", 0x8042E698, 40, 0.25, 3, False),
    ("Vintage Rifle", "Reserve Ammo", 0x8042E778, 40, 0.25, 3, False),
    ("Scifi Sniper", "Reserve Ammo", 0x8042E858, 40, 0.25, 3, False),
    ("Soviet Rifle", "Reserve Ammo", 0x8042E938, 200, 0.25, 3, False),
    ("Shotgun", "Reserve Ammo", 0x8042EA18, 40, 0.25, 3, False),
    ("Tactical 12-Gauge", "Reserve Ammo", 0x8042EAF8, 40, 0.25, 3, False),
    ("Dispersion Gun", "Reserve Ammo", 0x8042EBD8, 40, 0.25, 3, False),
    ("Revolver", "Reserve Ammo", 0x8042ECB8, 80, 0.25, 3, False),
    ("Machine Gun", "Reserve Ammo", 0x8042ED98, 256, 0.25, 3, False),
    ("SBP500", "Reserve Ammo", 0x8042EE78, 256, 0.25, 3, False),
    ("K-SMG", "Reserve Ammo", 0x8042EF58, 200, 0.25, 3, False),
    ("K-SMG", "Reserve Grenades", 0x8042F038, 5, 0.25, 3, False),
    ("Plasma Autorifle", "Reserve Ammo", 0x8042F118, 400, 0.25, 3, False),
    ("Scifi Handgun", "Reserve Ammo", 0x8042F1F8, 200, 0.25, 3, False),
    ("Rocket Launcher", "Reserve Ammo", 0x8042F2D8, 12, 0.25, 3, False),
    ("Heatseeker", "Reserve Ammo", 0x8042F3B8, 6, 0.25, 3, False),
    ("Grenades", "Reserve Ammo", 0x8042F578, 5, 0.25, 3, False),
    ("Time Disrupter Grenades", "Reserve Ammo", 0x8042F658, 5, 0.25, 3, False),
    ("Brick", "Reserve Ammo", 0x8042F738, 40, 0.25, 3, False),
    ("Remote Mines", "Reserve Ammo", 0x8042F818, 10, 0.25, 3, False),
    ("Timed Mines", "Reserve Ammo", 0x8042F8F8, 10, 0.25, 3, False),
    ("Proximity Mines", "Reserve Ammo", 0x8042F9D8, 10, 0.25, 3, False),
    ("ElectroTool", "Reserve Ammo", 0x8042FB98, 1800, 0.25, 3, False),
    ("Ghost Gun", "Reserve Ammo", 0x8042FC78, 960, 0.25, 3, False),
    ("Flamethrower", "Reserve Ammo", 0x8042FD58, 1500, 0.25, 3, False),
    ("Harpoon Gun", "Reserve Ammo", 0x8042FE38, 48, 0.25, 3, False),
    ("Injector", "Reserve Ammo", 0x8042FF18, 48, 0.25, 3, True),
    ("Plasma Grenades", "Reserve Ammo", 0x8042FFF8, 5, 0.25, 3, False),
    ("Flare Gun", "Reserve Ammo", 0x80430298, 10, 0.25, 3, False),
    ("Mag-Charger", "Reserve Ammo", 0x80430618, 40, 0.25, 3, False),
    ("Monkey Gun", "Reserve Ammo", 0x804307D8, 256, 0.25, 3, False),
)


def weapon_buff_item_name(weapon: str, stat: str, change: float) -> str:
    return f"Weapon Buff - {weapon} - +{round(change * 100)}% {stat}"


def weapon_buff_value(normal: int, change: float, copies: int) -> int:
    """The stat's value with this many copies (halves round up, so 3.75 -> 4 and 4.5 -> 5)."""
    return int(normal * (1 + change * copies) + 0.5)


WEAPON_BUFF_ITEM_NAMES: tuple[str, ...] = tuple(weapon_buff_item_name(b[0], b[1], b[4]) for b in WEAPON_BUFFS)

# ---- Which mission is running ----
# For Arcade League missions and Challenges the game's setup holds a "this is a set mission" flag
# and the mission's number, which is the same numbering as MISSIONS (0 = Brain Drain ... 47).
# A custom Arcade match leaves the old number behind but has the flag clear. (Found by comparing
# the setup in twelve different missions.)
SETUP_FLAGS_54 = 0x805015C4
SETUP_MISSION_FLAG = 0x4000
SETUP_MISSION_INDEX = 0x805015D8

# ---- Progressive Starting Armour ----
# 0x80611D90 points at the player's state for the current level (0 when there is none). Armour is
# the decimal number 0x78 bytes in, and the number after it is the size of a full bar: 11 in Story and Behead The Undead, 20 in TimeSplitters 'Story' Classic, 1.6 in Arcade.
STARTING_ARMOUR_ITEM_NAME = "Progressive Starting Armour"
STARTING_ARMOUR_COPIES = 4                   # 25%, 50%, 75%, 100%
PLAYER_STATE_POINTER = 0x80611D90
PLAYER_LIFE_OFFSET = 0x24          # 1 while alive, 8 once dead (until the respawn or restart)
PLAYER_ALIVE, PLAYER_DEAD = 1, 8
PLAYER_ARMOUR_OFFSET = 0x78
PLAYER_FULL_BAR_OFFSET = 0x7C      # what a full armour bar is in this mode
# The game's overall state: 7 while playing, 12 while a level is loading (a mission start, or a
# restart from a checkpoint or the pause menu), 8 once the level is over.
GAME_STATE = 0x80611934
GAME_STATE_PLAYING, GAME_STATE_LOADING = 7, 12
# Where starting armour applies: Story, Arcade League, and these two Challenge groups.
STARTING_ARMOUR_CHALLENGE_GROUPS = ("Behead The Undead", "TimeSplitters 'Story' Classic")
# ---- Easier trophy requirements ----
# Each mission record points (at +0x1C) at a list of rules, 5 words each, the last word being the
# number a trophy needs. The game reads them
# when the mission loads. Per option: (address, normal value, easier value), in seconds or points.
EASIER_TROPHIES: dict[str, tuple[tuple[int, int, int], ...]] = {
    # Astro Jocks: finish in this time or less. Silver, Gold, Platinum.
    "easier_astro_jocks": ((0x80462B1C, 150, 180), (0x80462B30, 135, 150), (0x80462B44, 120, 135)),
    # Rumble In The Jungle: finish in this time or less. Silver and Gold keep their normal times.
    "easier_rumble_in_the_jungle": ((0x80462394, 240, 240), (0x804623A8, 210, 210), (0x804623BC, 170, 195)),
    # Cut-Out Shoot-Out: Platinum scores for Hart Attack, Come Hell Or High Water, Balls Of Steel.
    "easier_cut_out_shoot_out": ((0x8045FBEC, 1800, 1775), (0x8045FA70, 1800, 1700), (0x8045FD68, 1250, 1200)),
    # Electro Chimp Discomatic: last this long or more. Bronze, Silver, Gold, Platinum.
    "quicker_electro_chimp_discomatic": ((0x80460FB0, 180, 60), (0x80460FC4, 240, 120),
                                         (0x80460FD8, 270, 180), (0x80460FEC, 360, 240)),
}
EASIER_TROPHY_NAMES = {
    "easier_astro_jocks": "Astro Jocks",
    "easier_rumble_in_the_jungle": "Rumble In The Jungle",
    "easier_cut_out_shoot_out": "Cut-Out Shoot-Out",
    "quicker_electro_chimp_discomatic": "Electro Chimp Discomatic",
}

# ---- Streamer Mode ----
# The game has a list of 201 music tracks at 0x80488D58: one address per track, pointing at the
# track's file name. The Disco map and the credits both play track 185, a licensed song. Streamer
# Mode points that entry at another track's file name, so that track plays in its place.
MUSIC_TABLE = 0x80488D58
MUSIC_DISCO_TRACK = 185
MUSIC_DISCO_ENTRY = MUSIC_TABLE + 4 * MUSIC_DISCO_TRACK
MUSIC_DISCO_NAME = 0x80488B8C          # "music/ts3_disco44fx.ogg"
MUSIC_REPLACEMENT_NAME = 0x80488C84    # "music/ts3_like_a_monkey32fx.ogg" (track 195)

# ---- Death Link ----
# The game fails a mission by setting this bit in the setup flags and calling its "end the level"
# routine. Every failure goes through it: dying in Story, a failed objective, a failed Challenge.
SETUP_FAILED_FLAG = 0x10000
# To fail the mission from outside, the game's own once-a-frame routine (0x8003286C) is used: it
# picks what to do from a table of addresses, one per game state. The entry for "playing" is
# pointed at a few new instructions that fail the mission when DEATH_TRIGGER is not zero and
# otherwise carry on as normal. Only data the game re-reads every frame is changed, so it works
# no matter how long the game has been running.
STATE_TABLE_PLAYING = 0x803F37AC + 4 * 7     # table entry for game state 7
STATE_PLAYING_HANDLER = 0x8003305C           # what that entry normally holds
STATE_HANDLER_EXIT = 0x80033374
END_LEVEL_ROUTINE = 0x80030160
DEATH_TRIGGER = 0x80002EFC
DEATH_CAVE = 0x80002F00


def _build_death_cave() -> tuple[int, ...]:
    def branch(index: int, target: int, link: int = 0) -> int:
        return 0x48000000 | ((target - (DEATH_CAVE + 4 * index)) & 0x03FFFFFC) | link
    low = DEATH_TRIGGER & 0xFFFF
    return (
        0x3D800000 | (DEATH_TRIGGER >> 16),    # lis r12, 0x8000
        0x800C0000 | low,                      # lwz r0, trigger(r12)
        0x2C000000,                            # cmpwi r0, 0
        0x4182002C,                            # beq -> carry on as normal
        0x38000000,                            # li r0, 0
        0x900C0000 | low,                      # stw r0, trigger(r12)
        0x3C808050,                            # lis r4, 0x8050
        0x38841570,                            # addi r4, r4, 0x1570        (the setup)
        0x80040054,                            # lwz r0, 0x54(r4)
        0x64000001,                            # oris r0, r0, 1             (failed)
        0x90040054,                            # stw r0, 0x54(r4)
        0x38600000,                            # li r3, 0
        branch(12, END_LEVEL_ROUTINE, 1),      # bl end the level
        branch(13, STATE_HANDLER_EXIT),
        branch(14, STATE_PLAYING_HANDLER),
    )


DEATH_CAVE_CODE = _build_death_cave()
DEATH_TRIGGER_POLLS = 8                      # polls to wait for the game to act on the trigger

STARTING_ARMOUR_SETTLE_POLLS = 4             # polls (0.25 s each) to wait after a new life begins

# ---- Behead The Undead score multiplier ----
# The points for a kill in the three Behead The Undead challenges are numbers built into the
# game's code (found with Ralf's "Points Per Kill Modifier" code and confirmed in game):
#     Brain Drain          zombie 75 (0x80222AC0), ghost 50 (0x8022297C, 0x80222990, 0x802229A0)
#     Rare Or Well Done?   cow 50 (0x80222AEC)
#     Boxing Clever        100 or 75 by enemy type (0x80222964, 0x8022296C), then its combo
# Dolphin doesn't notice code that changes after it has run, so the client can't just rewrite
# those numbers when a multiplier arrives. Instead, once at startup, each of those instructions
# is replaced by a jump to a few instructions that read the number from a small table, and the
# client changes the table (plain data) whenever it likes.
# The table and the new instructions live at 0x80002E00, in the low memory the game leaves
# empty. Dolphin's own Gecko cheat handler uses that area when cheats are enabled, so the client
# only installs this when the area is empty.
SCORE_MULTIPLIER_ITEM_NAME = "Progressive Behead The Undead Score Multiplier"
SCORE_MULTIPLIER_COPIES = 3                  # x2, x3, x4
SCORE_TABLE = 0x80002E00
SCORE_BASE_POINTS = (50, 75, 50, 100, 75)    # ghost, zombie, cow, Boxing Clever high, Boxing Clever low
SCORE_CAVES = 0x80002E10
# (address, original instruction, table entry, kind, where to go back to)
#   kind "li": load the number into the register the original used; "add": r0 = that register +
#   number; "return": load into r3 and return (the original was followed by blr); "multiply":
#   r3 = r0 x number and return (the original was "mr r3, r0" followed by blr).
_SCORE_SITES = (
    (0x8022297C, 0x38800032, 0, ("li", 4)),
    (0x80222990, 0x38030032, 0, ("add", 3)),
    (0x802229A0, 0x38030032, 0, ("add", 3)),
    (0x80222AC0, 0x3BC0004B, 1, ("li", 30)),
    (0x80222AEC, 0x3BC00032, 2, ("li", 30)),
    (0x80222964, 0x38600064, 3, ("return", 3)),
    (0x8022296C, 0x3860004B, 4, ("return", 3)),
)


def _branch(source: int, target: int) -> int:
    return 0x48000000 | ((target - source) & 0x03FFFFFC)


def _build_score_patch(sites, table_address: int, caves: int):
    hooks, code = [], []
    for address, original, entry, (kind, register) in sites:
        cave = caves + 4 * len(code)
        offset = (table_address & 0xFFFF) + 2 * entry
        code.append(0x3D800000 | (table_address >> 16))                  # lis r12, 0x8000
        if kind == "add":
            code.append(0xA18C0000 | offset)                             # lhz r12, entry(r12)
            code.append(0x7C006214 | (register << 16))                   # add r0, rN, r12
        elif kind == "multiply":
            code.append(0xA18C0000 | offset)                             # lhz r12, entry(r12)
            code.append(0x7C6061D6)                                      # mullw r3, r0, r12
        else:
            code.append(0xA00C0000 | (register << 21) | offset)          # lhz rN, entry(r12)
        if kind in ("return", "multiply"):
            code.append(0x4E800020)                                      # blr
        else:
            code.append(_branch(caves + 4 * len(code), address + 4))
        hooks.append((address, original, _branch(address, cave)))
    return tuple(hooks), tuple(code)


def _table_words(points: tuple[int, ...], multiplier: int) -> tuple[int, ...]:
    values = [p * multiplier for p in points] + [0] * (len(points) % 2)
    return tuple((values[k] << 16) | values[k + 1] for k in range(0, len(values), 2))


# SCORE_HOOKS: (address, original instruction, jump). SCORE_CAVE_CODE: the words at SCORE_CAVES.
SCORE_HOOKS, SCORE_CAVE_CODE = _build_score_patch(_SCORE_SITES, SCORE_TABLE, SCORE_CAVES)


def score_table_words(multiplier: int) -> tuple[int, ...]:
    """The table as 32-bit words (two 16-bit numbers each) for a multiplier of 1-4."""
    return _table_words(SCORE_BASE_POINTS, multiplier)


# ---- Miscellaneous Challenges score multiplier ----
# The same idea for Cortez Can't Jump!, TSUG and Plainly Off His Rocker, with its own table and
# code a little further on in the same low memory.
#   Plainly Off His Rocker: 100 per UFO and 25 per plane (the popup and the score, two places each).
#   TSUG: 25 per TimeSplitter (0x8022A260).
#   Cortez Can't Jump!: the routine at 0x80229B28 works out 5 to 100 points for a jump and ends
#   with "mr r3, r0; blr"; that result is multiplied.
MISC_MULTIPLIER_ITEM_NAME = "Progressive Miscellaneous Challenges Score Multiplier"
MISC_MULTIPLIER_COPIES = 3                   # x2, x3, x4
MISC_TABLE = 0x80002E80
MISC_BASE_POINTS = (100, 25, 25, 1)          # UFO, plane, TimeSplitter, Cortez Can't Jump! multiplier
MISC_CAVES = 0x80002E90
_MISC_SITES = (
    (0x80229788, 0x38800064, 0, ("li", 4)),
    (0x8022978C, 0x38050064, 0, ("add", 5)),
    (0x802297A4, 0x38800019, 1, ("li", 4)),
    (0x802297A8, 0x38050019, 1, ("add", 5)),
    (0x8022A260, 0x38030019, 2, ("add", 3)),
    (0x80229B8C, 0x7C030378, 3, ("multiply", 3)),
)
MISC_HOOKS, MISC_CAVE_CODE = _build_score_patch(_MISC_SITES, MISC_TABLE, MISC_CAVES)
assert MISC_CAVES + 4 * len(MISC_CAVE_CODE) <= 0x80002EFC      # must stop before the Death Link trigger


def misc_table_words(multiplier: int) -> tuple[int, ...]:
    return _table_words(MISC_BASE_POINTS, multiplier)


# ---- Milestones: a Bronze or better on every mission of a group, a league or all Challenges ----
LEAGUE_NAMES = {"AL": "Amateur League", "HL": "Honorary League", "EL": "Elite League"}
MILESTONE_TROPHY = 1    # Bronze
# Which option switches each milestone on.
MILESTONE_ARCADE_GROUPS, MILESTONE_CHALLENGE_GROUPS, MILESTONE_LEAGUES, MILESTONE_ALL_CHALLENGES = range(4)
# (location name, location ID, the missions it needs, kind)
MILESTONES: tuple[tuple[str, int, tuple[Mission, ...], int], ...] = (
    *(
        (f"{prefix} - {group} - Group Completed", BASE_ID + 300 + g,
         tuple(m for m in MISSIONS if m.group == group),
         MILESTONE_CHALLENGE_GROUPS if prefix == "Challenge" else MILESTONE_ARCADE_GROUPS)
        for g, (prefix, group, _missions) in enumerate(GROUPS)
    ),
    *(
        (f"{league} Completed", BASE_ID + 320 + k, tuple(m for m in MISSIONS if m.prefix == prefix),
         MILESTONE_LEAGUES)
        for k, (prefix, league) in enumerate(LEAGUE_NAMES.items())
    ),
    ("All Challenges Completed", BASE_ID + 323, tuple(m for m in MISSIONS if m.prefix == "Challenge"),
     MILESTONE_ALL_CHALLENGES),
)

# ---- Names and IDs shared by the world and the client ----
FILLER_ITEM_NAME = "Nothing"
VICTORY_ITEM_NAME = "Victory"
# Goal events (they have no ID: the client reports the goal itself).
STORY_GOAL_LOCATION_NAME = f"{STORY_LEVELS[FINAL_STORY_LEVEL]} Completed"
TROPHY_GOAL_LOCATION_NAME = "Trophy Hunt Completed"
GOAL_FUTURE_PERFECT, GOAL_ALL_TROPHIES = 0, 1          # GOAL_ALL_TROPHIES is the Trophy Hunt goal
# Trophy Hunt: which missions count.
HUNT_ARCADE, HUNT_CHALLENGES, HUNT_ALL = 0, 1, 2


def hunted_missions(setting: int) -> tuple["Mission", ...]:
    if setting == HUNT_ARCADE:
        return tuple(m for m in MISSIONS if m.prefix != "Challenge")
    if setting == HUNT_CHALLENGES:
        return tuple(m for m in MISSIONS if m.prefix == "Challenge")
    return MISSIONS


STORY_INDIVIDUAL, STORY_PROGRESSIVE = 0, 1


def location_name(mission: Mission, tier: int) -> str:
    """tier is 1 (Bronze) to 4 (Platinum)."""
    return f"{mission.item_name} ({TIERS[tier - 1]})"


def location_id(mission_index: int, tier: int) -> int:
    return BASE_ID + mission_index * len(TIERS) + (tier - 1)


LOCATION_NAME_TO_ID: dict[str, int] = {
    **{
        location_name(mission, tier): location_id(mission.index, tier)
        for mission in MISSIONS
        for tier in range(1, len(TIERS) + 1)
    },
    **{
        story_location_name(level, d): story_location_id(level, d)
        for level in range(len(STORY_LEVELS))
        for d in range(len(STORY_DIFFICULTIES))
    },
    **{
        objective_location_name(level, name): objective_location_id(level, slot)
        for level, objectives in STORY_OBJECTIVES.items()
        for slot, name, _hidden in objectives
    },
    **{name: location_id for name, location_id, _missions, _kind in MILESTONES},
}

ITEM_NAME_TO_ID: dict[str, int] = {
    **{m.item_name: BASE_ID + 1000 + m.index for m in MISSIONS},
    FILLER_ITEM_NAME: BASE_ID + 2000,
    **{character_item_name(c[0]): BASE_ID + 3000 + c[2] for c in CHARACTERS},
    **{cheat_item_name(c[0]): BASE_ID + 4000 + c[2] for c in CHEATS},
    **{story_item_name(k): BASE_ID + 1100 + k for k in range(len(STORY_LEVELS))},
    PROGRESSIVE_STORY_ITEM_NAME: BASE_ID + 1150,
    **{weapon_item_name(w[0]): BASE_ID + 5000 + w[1] for w in WEAPONS},
    SCORE_MULTIPLIER_ITEM_NAME: BASE_ID + 6000,
    MISC_MULTIPLIER_ITEM_NAME: BASE_ID + 6002,
    STARTING_ARMOUR_ITEM_NAME: BASE_ID + 6001,
    **{name: BASE_ID + 7000 + k for k, name in enumerate(WEAPON_BUFF_ITEM_NAMES)},
}
