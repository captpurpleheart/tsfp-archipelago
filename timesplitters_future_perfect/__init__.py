"""
Archipelago world for TimeSplitters: Future Perfect.
Locations: trophies on all 48 Arcade League missions and Challenges, story level completions
per difficulty, story objectives and group/league milestones. Items: missions, story levels, characters, cheats
and arcade weapons.
"""
from dataclasses import dataclass
from typing import Any

from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region, Tutorial
from Options import Choice, DeathLink, DefaultOnToggle, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import set_rule
from worlds.LauncherComponents import Component, components, icon_paths, launch_subprocess

from . import game_data



class TsfpItem(Item):
    game = game_data.GAME_NAME


class TsfpLocation(Location):
    game = game_data.GAME_NAME


class StartingItem(Choice):
    """
    What you start with (as well as one random character and one random weapon).
    Random Arcade Or Challenge Mission: one of the 48 Arcade League missions and Challenges.
    Random Arcade Mission: one of the 27 Arcade League missions.
    Random Challenge Mission: one of the 21 Challenges.
    Random Story Mission: one story level, never 1924 Future Perfect.
    Random Any Mission: one mission from any of the three pools (never 1924 Future Perfect).
    Time To Split: 2401 Time To Split.
    With Progressive Story Level, a story start is always 2401 Time To Split (one Progressive Story Level).
    """
    display_name = "Starting Item"
    option_random_arcade_or_challenge_mission = 0
    option_random_arcade_mission = 1
    option_random_challenge_mission = 2
    option_random_story_mission = 3
    option_random_any_mission = 4
    option_time_to_split = 5
    default = 0


class StoryMode(Choice):
    """
    Individual Items: every story level is its own item. Finding "2401 Time To Split" unlocks that level.
    Progressive Story Level: story levels unlock in order, one more for each Progressive Story Level you have.
    """
    display_name = "Story Mode Setting"
    option_individual_items = game_data.STORY_INDIVIDUAL
    option_progressive_story_level = game_data.STORY_PROGRESSIVE
    default = game_data.STORY_INDIVIDUAL


class Goal(Choice):
    """
    Future Perfect: complete 1924 Future Perfect (on any difficulty).
    All Trophies: earn a trophy of the chosen grade or better on every Arcade League mission and Challenge.
    """
    display_name = "Goal"
    option_future_perfect = game_data.GOAL_FUTURE_PERFECT
    option_all_trophies = game_data.GOAL_ALL_TROPHIES
    default = game_data.GOAL_FUTURE_PERFECT


class StoryLevelsRequired(Range):
    """
    Only used when the goal is Future Perfect. How many of the other 12 story levels you must have
    completed before 1924 Future Perfect opens (you also need its item, or all 13 Progressive
    Story Levels).
    """
    display_name = "Story Levels Required For Goal"
    range_start = 0
    range_end = game_data.FINAL_STORY_LEVEL
    default = game_data.FINAL_STORY_LEVEL


class TrophyGrade(Choice):
    """Only used when the goal is All Trophies. The lowest trophy you need on every mission."""
    display_name = "Trophy Grade Required For Goal"
    option_bronze = 1
    option_silver = 2
    option_gold = 3
    option_platinum = 4
    default = 1


class ExcludeHardStory(DefaultOnToggle):
    """Completing story levels on Hard only ever gives filler items, never anything useful or required."""
    display_name = "Exclude Hard Difficulty On Story Levels"


class ExcludeAllPlatinum(Toggle):
    """Platinum trophies only ever give filler items, never anything useful or required."""
    display_name = "Exclude All Platinum Trophies"


class ExcludePlatinumTrophies(OptionSet):
    """
    Missions whose Platinum trophy only ever gives a filler item. Use the mission's own name,
    for example ["Rare Or Well Done?", "Astro Jocks"].
    """
    display_name = "Exclude Specific Platinum Trophies"
    valid_keys = frozenset(name.casefold() for name in game_data.MISSION_NAMES)
    valid_keys_casefold = True


class EasierAstroJocks(Toggle):
    """Easier trophy times for Astro Jocks: Platinum 2:15 (normally 2:00), Gold 2:30 (2:15),
    Silver 3:00 (2:30)."""
    display_name = "Easier Astro Jocks"


class EasierRumbleInTheJungle(Toggle):
    """Easier Platinum time for Rumble In The Jungle: 3:15 (normally 2:50). Gold stays 3:30 and
    Silver 4:00."""
    display_name = "Easier Rumble In The Jungle"


class EasierCutOutShootOut(Toggle):
    """Slightly lower Platinum scores for the Cut-Out Shoot-Out Challenges: Hart Attack 1775
    (normally 1800), Come Hell Or High Water 1700 (1800), Balls Of Steel 1200 (1250)."""
    display_name = "Easier Cut-Out Shoot-Out Platinum Scores"


class QuickerElectroChimpDiscomatic(Toggle):
    """Shorter trophy times for Electro Chimp Discomatic: Platinum 4:00 (normally 6:00), Gold 3:00
    (4:30), Silver 2:00 (4:00), Bronze 1:00 (3:00)."""
    display_name = "Quicker Electro Chimp Discomatic"


class ScoreMultiplier(Choice):
    """
    Progressive Behead The Undead Score Multiplier: each one you have multiplies the points for
    every kill in Brain Drain, Rare Or Well Done? and Boxing Clever (x2, x3, then x4 with all three).
    Off: there are none; points are normal.
    Start With One: you start with one (x2) and the other two are shuffled.
    Shuffle All: all three are shuffled.
    """
    display_name = "Progressive Behead The Undead Score Multipliers"
    option_off = 0
    option_start_with_one = 1
    option_shuffle_all = 2
    default = 2


class EarlyScoreMultiplier(Toggle):
    """
    Makes one of the shuffled Progressive Behead The Undead Score Multipliers an early item, even
    if you already start with one. Does nothing when Behead The Undead Score Multiplier is Off.
    """
    display_name = "Early Behead The Undead Score Multiplier"


class MiscScoreMultiplier(Choice):
    """
    Progressive Miscellaneous Challenges Score Multiplier: each one you have multiplies the points
    you score in Cortez Can't Jump!, TSUG: TimeSplitters Underground and Plainly Off His Rocker
    (x2, x3, then x4 with all three).
    Off: there are none; points are normal.
    Start With One: you start with one (x2) and the other two are shuffled.
    Shuffle All: all three are shuffled.
    """
    display_name = "Progressive Miscellaneous Challenges Score Multipliers"
    option_off = 0
    option_start_with_one = 1
    option_shuffle_all = 2
    default = 2


class EarlyMiscScoreMultiplier(Toggle):
    """
    Makes one of the shuffled Progressive Miscellaneous Challenges Score Multipliers an early item,
    even if you already start with one. Does nothing when the multiplier is Off.
    """
    display_name = "Early Miscellaneous Challenges Score Multiplier"


class StartingArmour(Choice):
    """
    Progressive Starting Armour: four items. Each one you have raises the armour you get when you
    start a mission, restart from a checkpoint or respawn: 25%, 50%, 75%, then a full bar.
    It applies in Story, Arcade League, Behead The Undead and TimeSplitters 'Story' Classic.
    Off: there are none.
    Start With One: you start with one (25%) and the other three are shuffled.
    Shuffle All: all four are shuffled.
    """
    display_name = "Progressive Starting Armour"
    option_off = 0
    option_start_with_one = 1
    option_shuffle_all = 2
    default = 2


class StreamerMode(Toggle):
    """Replace the licensed song played in the Disco map and the credits with another track from the
    game ("Like A Monkey"), so that streams and recordings are not flagged for copyrighted music."""
    display_name = "Streamer Mode"


class IncludeWeaponBuffs(DefaultOnToggle):
    """
    Adds weapon buffs (bigger clips, more reserve ammo) to the item pool. They fill whatever
    locations are left after every other item, so a game holds a random selection of them.
    When off, those locations hold "Nothing" instead.
    """
    display_name = "Include Weapon Buffs"


class ArcadeGroupMilestones(DefaultOnToggle):
    """
    Adds a location for each Arcade League group, such as "AL - One Gun Fun - Group Completed" and
    "HL - Dead Weight - Group Completed". Each needs at least a Bronze trophy on every mission of
    its group.
    """
    display_name = "Arcade League Group Milestones"


class ChallengeGroupMilestones(DefaultOnToggle):
    """
    Adds a location for each Challenge group, such as "Challenge - Behead The Undead - Group
    Completed" and "Challenge - Cat Driving - Group Completed". Each needs at least a Bronze trophy
    on every mission of its group.
    """
    display_name = "Challenge Group Milestones"


class LeagueMilestones(DefaultOnToggle):
    """
    Adds "Amateur League Completed", "Honorary League Completed" and "Elite League Completed".
    Each needs at least a Bronze trophy on every mission of that league.
    """
    display_name = "Complete Arcade League Milestones"


class AllChallengesMilestone(DefaultOnToggle):
    """Adds "All Challenges Completed". It needs at least a Bronze trophy on every Challenge."""
    display_name = "Complete All Challenges Milestone"


@dataclass
class TsfpOptions(PerGameCommonOptions):
    starting_item: StartingItem
    story_mode: StoryMode
    death_link: DeathLink
    streamer_mode: StreamerMode
    goal: Goal
    story_levels_required: StoryLevelsRequired
    trophy_grade: TrophyGrade
    exclude_hard_story: ExcludeHardStory
    exclude_all_platinum: ExcludeAllPlatinum
    exclude_platinum_trophies: ExcludePlatinumTrophies
    easier_astro_jocks: EasierAstroJocks
    easier_rumble_in_the_jungle: EasierRumbleInTheJungle
    easier_cut_out_shoot_out: EasierCutOutShootOut
    quicker_electro_chimp_discomatic: QuickerElectroChimpDiscomatic
    starting_armour: StartingArmour
    score_multiplier: ScoreMultiplier
    early_score_multiplier: EarlyScoreMultiplier
    misc_score_multiplier: MiscScoreMultiplier
    early_misc_score_multiplier: EarlyMiscScoreMultiplier
    include_weapon_buffs: IncludeWeaponBuffs
    arcade_group_milestones: ArcadeGroupMilestones
    challenge_group_milestones: ChallengeGroupMilestones
    league_milestones: LeagueMilestones
    all_challenges_milestone: AllChallengesMilestone


class TsfpWebWorld(WebWorld):
    tutorials = [
        Tutorial(
            tutorial_name="Setup Guide",
            description="A guide to setting up TimeSplitters: Future Perfect for Archipelago.",
            language="English",
            file_name="en_Setup.md",
            link="setup/en",
            authors=["CaptPurpleHeart"],
        )
    ]
    option_groups = [
        OptionGroup("Game Options", [StartingItem, StoryMode, DeathLink, StreamerMode]),
        OptionGroup("Goal Options", [Goal, StoryLevelsRequired, TrophyGrade]),
        OptionGroup("Difficulty Settings", [ExcludeHardStory, ExcludeAllPlatinum, ExcludePlatinumTrophies,
                                            EasierAstroJocks, EasierRumbleInTheJungle, EasierCutOutShootOut,
                                            QuickerElectroChimpDiscomatic]),
        OptionGroup("Bonus Items", [StartingArmour, ScoreMultiplier, EarlyScoreMultiplier,
                                    MiscScoreMultiplier, EarlyMiscScoreMultiplier, IncludeWeaponBuffs]),
        OptionGroup("Milestone Locations", [ArcadeGroupMilestones, ChallengeGroupMilestones, LeagueMilestones,
                                            AllChallengesMilestone]),
    ]


class TsfpWorld(World):
    """
    TimeSplitters: Future Perfect is a time-travelling first person shooter.
    Arcade League missions, Challenges and story levels are unlocked by items; trophies,
    story level completions and story objectives are the checks.
    """
    game = game_data.GAME_NAME
    web = TsfpWebWorld()

    options_dataclass = TsfpOptions
    options: TsfpOptions

    item_name_to_id = game_data.ITEM_NAME_TO_ID
    location_name_to_id = game_data.LOCATION_NAME_TO_ID
    item_name_groups = {
        "Story Levels": set(game_data.STORY_ITEM_NAMES),
        "Arcade Missions": set(game_data.ARCADE_ITEM_NAMES),
        "Challenges": set(game_data.CHALLENGE_ITEM_NAMES),
        "Characters": set(game_data.CHARACTER_ITEM_NAMES),
        "Cheats": set(game_data.CHEAT_ITEM_NAMES),
        "Weapons": set(game_data.WEAPON_ITEM_NAMES),
        "Weapon Buffs": set(game_data.WEAPON_BUFF_ITEM_NAMES),
    }

    # Universal Tracker: it can rebuild this world from slot data alone (see interpret_slot_data).
    ut_can_gen_without_yaml = True

    starting_opener: str = ""
    starting_character: str = ""
    starting_weapon: str = ""

    @property
    def progressive(self) -> bool:
        return self.options.story_mode == game_data.STORY_PROGRESSIVE

    @property
    def story_goal(self) -> bool:
        return self.options.goal == game_data.GOAL_FUTURE_PERFECT

    def generate_early(self) -> None:
        # Universal Tracker rebuilds the world from the slot data of the game you connected to.
        passthrough = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if passthrough:
            self.options.story_mode.value = passthrough["story_mode"]
            self.options.goal.value = passthrough["goal"]
            self.options.story_levels_required.value = passthrough["story_levels_required"]
            self.options.trophy_grade.value = passthrough["trophy_grade"]
            self.options.arcade_group_milestones.value = passthrough["arcade_group_milestones"]
            self.options.challenge_group_milestones.value = passthrough["challenge_group_milestones"]
            self.options.league_milestones.value = passthrough["league_milestones"]
            self.options.all_challenges_milestone.value = passthrough["all_challenges_milestone"]
            self.options.score_multiplier.value = passthrough["score_multiplier"]
            self.options.misc_score_multiplier.value = passthrough.get("misc_score_multiplier", 0)
            self.options.starting_armour.value = passthrough["starting_armour"]
            self.options.include_weapon_buffs.value = passthrough["include_weapon_buffs"]
            self.starting_opener = passthrough["starting_opener"]
            self.starting_character = passthrough["starting_character"]
            self.starting_weapon = passthrough["starting_weapon"]
            for name in (self.starting_opener, self.starting_character, self.starting_weapon):
                self.multiworld.push_precollected(self.create_item(name))
            return
        story = list(game_data.STORY_ITEM_NAMES[:game_data.FINAL_STORY_LEVEL])   # never Future Perfect
        choice = self.options.starting_item
        if choice == StartingItem.option_random_arcade_mission:
            pool = list(game_data.ARCADE_ITEM_NAMES)
        elif choice == StartingItem.option_random_challenge_mission:
            pool = list(game_data.CHALLENGE_ITEM_NAMES)
        elif choice == StartingItem.option_random_story_mission:
            pool = story
        elif choice == StartingItem.option_random_any_mission:
            pool = list(game_data.MISSION_ITEM_NAMES) + story
        elif choice == StartingItem.option_time_to_split:
            pool = [game_data.STORY_ITEM_NAMES[0]]
        else:
            pool = list(game_data.MISSION_ITEM_NAMES)
        self.starting_opener = self.random.choice(pool)
        if self.progressive and self.starting_opener in game_data.STORY_ITEM_NAMES:
            # Progressive levels open in order, so a story start is always the first level.
            self.starting_opener = game_data.PROGRESSIVE_STORY_ITEM_NAME
        self.multiworld.push_precollected(self.create_item(self.starting_opener))
        self.starting_character = self.random.choice(game_data.CHARACTER_ITEM_NAMES)
        self.multiworld.push_precollected(self.create_item(self.starting_character))
        # One weapon to start with: the custom weapon set menu needs at least one to offer.
        self.starting_weapon = self.random.choice(game_data.WEAPON_ITEM_NAMES)
        self.multiworld.push_precollected(self.create_item(self.starting_weapon))
        if self.options.score_multiplier == ScoreMultiplier.option_start_with_one:
            self.multiworld.push_precollected(self.create_item(game_data.SCORE_MULTIPLIER_ITEM_NAME))
        if self.options.starting_armour == StartingArmour.option_start_with_one:
            self.multiworld.push_precollected(self.create_item(game_data.STARTING_ARMOUR_ITEM_NAME))
        if self.options.score_multiplier != ScoreMultiplier.option_off and self.options.early_score_multiplier:
            self.multiworld.early_items[self.player][game_data.SCORE_MULTIPLIER_ITEM_NAME] = 1
        if self.options.misc_score_multiplier == MiscScoreMultiplier.option_start_with_one:
            self.multiworld.push_precollected(self.create_item(game_data.MISC_MULTIPLIER_ITEM_NAME))
        if (self.options.misc_score_multiplier != MiscScoreMultiplier.option_off
                and self.options.early_misc_score_multiplier):
            self.multiworld.early_items[self.player][game_data.MISC_MULTIPLIER_ITEM_NAME] = 1

    # ---- logic ----

    def has_story_level(self, state, level: int) -> bool:
        if self.progressive:
            if not state.has(game_data.PROGRESSIVE_STORY_ITEM_NAME, self.player, level + 1):
                return False
        elif not state.has(game_data.STORY_ITEM_NAMES[level], self.player):
            return False
        if level == game_data.FINAL_STORY_LEVEL and self.story_goal and not self.progressive:
            # Future Perfect also waits for N other levels to be beaten. (With progressive items,
            # owning Future Perfect already means owning all 12 others.)
            others = game_data.STORY_ITEM_NAMES[:game_data.FINAL_STORY_LEVEL]
            return state.has_from_list_unique(others, self.player, self.options.story_levels_required.value)
        return True

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        excluded_platinum = {name.casefold() for name in self.options.exclude_platinum_trophies.value}

        for mission in game_data.MISSIONS:
            region = Region(mission.item_name, self.player, self.multiworld)
            region.add_locations(
                {
                    game_data.location_name(mission, tier): game_data.location_id(mission.index, tier)
                    for tier in range(1, len(game_data.TIERS) + 1)
                },
                TsfpLocation,
            )
            self.multiworld.regions.append(region)
            if self.options.exclude_all_platinum or mission.name.casefold() in excluded_platinum:
                platinum = game_data.location_name(mission, len(game_data.TIERS))
                self.get_location(platinum).progress_type = LocationProgressType.EXCLUDED

            # Every mission needs only its own item: the client keeps both leagues open.
            entrance = menu.connect(region)
            set_rule(entrance, lambda state, name=mission.item_name: state.has(name, self.player))

        # Milestones: every mission of a group, a league or all Challenges, with a Bronze or better.
        milestones_on = {
            game_data.MILESTONE_ARCADE_GROUPS: self.options.arcade_group_milestones,
            game_data.MILESTONE_CHALLENGE_GROUPS: self.options.challenge_group_milestones,
            game_data.MILESTONE_LEAGUES: self.options.league_milestones,
            game_data.MILESTONE_ALL_CHALLENGES: self.options.all_challenges_milestone,
        }
        for name, location_id, missions, kind in game_data.MILESTONES:
            if not milestones_on[kind]:
                continue
            menu.add_locations({name: location_id}, TsfpLocation)
            needed = tuple(m.item_name for m in missions)
            set_rule(self.get_location(name), lambda state, needed=needed: state.has_all(needed, self.player))

        hard = len(game_data.STORY_DIFFICULTIES) - 1
        for level in range(len(game_data.STORY_LEVELS)):
            region = Region(f"Story: {game_data.STORY_LEVELS[level]}", self.player, self.multiworld)
            locations: dict[str, int | None] = {
                game_data.objective_location_name(level, name): game_data.objective_location_id(level, slot)
                for slot, name, _hidden in game_data.STORY_OBJECTIVES.get(level, ())
            }
            if level == game_data.FINAL_STORY_LEVEL and self.story_goal:
                # Future Perfect is the goal: one "Completed" event instead of the three checks.
                locations[game_data.STORY_GOAL_LOCATION_NAME] = None
            else:
                for d in range(len(game_data.STORY_DIFFICULTIES)):
                    locations[game_data.story_location_name(level, d)] = game_data.story_location_id(level, d)
            region.add_locations(locations, TsfpLocation)
            self.multiworld.regions.append(region)
            if self.options.exclude_hard_story and game_data.story_location_name(level, hard) in locations:
                self.get_location(game_data.story_location_name(level, hard)).progress_type = \
                    LocationProgressType.EXCLUDED
            entrance = menu.connect(region)
            set_rule(entrance, lambda state, k=level: self.has_story_level(state, k))

        # Goal: an event location holding a locked "Victory" item.
        if self.story_goal:
            victory = self.get_location(game_data.STORY_GOAL_LOCATION_NAME)
        else:
            menu.add_locations({game_data.TROPHY_GOAL_LOCATION_NAME: None}, TsfpLocation)
            victory = self.get_location(game_data.TROPHY_GOAL_LOCATION_NAME)
            set_rule(victory, lambda state: state.has_all(game_data.MISSION_ITEM_NAMES, self.player))
        victory.place_locked_item(self.create_item(game_data.VICTORY_ITEM_NAME))

    def create_items(self) -> None:
        names = list(game_data.MISSION_ITEM_NAMES)
        if self.progressive:
            names += [game_data.PROGRESSIVE_STORY_ITEM_NAME] * len(game_data.STORY_LEVELS)
        else:
            names += list(game_data.STORY_ITEM_NAMES)
        names.remove(self.starting_opener)
        names += list(game_data.CHEAT_ITEM_NAMES)
        names += [n for n in game_data.WEAPON_ITEM_NAMES if n != self.starting_weapon]
        if self.options.score_multiplier == ScoreMultiplier.option_shuffle_all:
            names += [game_data.SCORE_MULTIPLIER_ITEM_NAME] * game_data.SCORE_MULTIPLIER_COPIES
        elif self.options.score_multiplier == ScoreMultiplier.option_start_with_one:
            names += [game_data.SCORE_MULTIPLIER_ITEM_NAME] * (game_data.SCORE_MULTIPLIER_COPIES - 1)
        if self.options.misc_score_multiplier == MiscScoreMultiplier.option_shuffle_all:
            names += [game_data.MISC_MULTIPLIER_ITEM_NAME] * game_data.MISC_MULTIPLIER_COPIES
        elif self.options.misc_score_multiplier == MiscScoreMultiplier.option_start_with_one:
            names += [game_data.MISC_MULTIPLIER_ITEM_NAME] * (game_data.MISC_MULTIPLIER_COPIES - 1)
        names += [n for n in game_data.CHARACTER_ITEM_NAMES if n != self.starting_character]
        if self.options.starting_armour == StartingArmour.option_shuffle_all:
            names += [game_data.STARTING_ARMOUR_ITEM_NAME] * game_data.STARTING_ARMOUR_COPIES
        elif self.options.starting_armour == StartingArmour.option_start_with_one:
            names += [game_data.STARTING_ARMOUR_ITEM_NAME] * (game_data.STARTING_ARMOUR_COPIES - 1)
        location_count = sum(1 for loc in self.multiworld.get_locations(self.player) if loc.address is not None)
        # Whatever room is left (after starting armour and score multipliers, added above) goes to
        # weapon buffs when they are switched on: first every copy of the ones marked "always
        # in the pool", then a random pick from all the other copies. "Nothing" only if buffs run out.
        always, others = [], []
        if self.options.include_weapon_buffs:
            for name, buff in zip(game_data.WEAPON_BUFF_ITEM_NAMES, game_data.WEAPON_BUFFS):
                (always if buff[6] else others).extend([name] * buff[5])
        self.random.shuffle(others)
        names += (always + others)[:max(0, location_count - len(names))]
        names += [game_data.FILLER_ITEM_NAME] * (location_count - len(names))
        self.multiworld.itempool += [self.create_item(name) for name in names]

    def create_item(self, name: str) -> TsfpItem:
        if name == game_data.VICTORY_ITEM_NAME:
            return TsfpItem(name, ItemClassification.progression, None, self.player)
        if name in game_data.STORY_ITEM_NAMES or name == game_data.PROGRESSIVE_STORY_ITEM_NAME:
            classification = ItemClassification.progression
        elif name in game_data.MISSION_ITEM_NAMES:
            classification = ItemClassification.progression_skip_balancing
        elif (name in game_data.CHEAT_ITEM_NAMES or name in game_data.WEAPON_BUFF_ITEM_NAMES
              or name in (game_data.SCORE_MULTIPLIER_ITEM_NAME, game_data.MISC_MULTIPLIER_ITEM_NAME,
                          game_data.STARTING_ARMOUR_ITEM_NAME)):
            classification = ItemClassification.useful
        else:
            classification = ItemClassification.filler   # characters, weapons and "Nothing"
        return TsfpItem(name, classification, game_data.ITEM_NAME_TO_ID[name], self.player)

    def get_filler_item_name(self) -> str:
        return game_data.FILLER_ITEM_NAME

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has(
            game_data.VICTORY_ITEM_NAME, self.player
        )

    def fill_slot_data(self) -> dict[str, Any]:
        return {
            "world_version": game_data.WORLD_VERSION,
            "starting_opener": self.starting_opener,
            "starting_character": self.starting_character,
            "starting_weapon": self.starting_weapon,
            "score_multiplier": int(self.options.score_multiplier.value),
            "misc_score_multiplier": int(self.options.misc_score_multiplier.value),
            "starting_armour": int(self.options.starting_armour.value),
            "death_link": int(bool(self.options.death_link)),
            "streamer_mode": int(bool(self.options.streamer_mode)),
            **{option: int(bool(getattr(self.options, option))) for option in game_data.EASIER_TROPHIES},
            "include_weapon_buffs": int(bool(self.options.include_weapon_buffs)),
            "arcade_group_milestones": int(bool(self.options.arcade_group_milestones)),
            "challenge_group_milestones": int(bool(self.options.challenge_group_milestones)),
            "league_milestones": int(bool(self.options.league_milestones)),
            "all_challenges_milestone": int(bool(self.options.all_challenges_milestone)),
            "story_mode": int(self.options.story_mode.value),
            "goal": int(self.options.goal.value),
            "story_levels_required": int(self.options.story_levels_required.value),
            "trophy_grade": int(self.options.trophy_grade.value),
        }

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        """Universal Tracker: hand the slot data back to generate_early (as re_gen_passthrough)."""
        return slot_data


def launch_client(*args):
    from .tsfp_client import main
    launch_subprocess(main, name="TSFP Client", args=args)


icon_paths["TSFP"] = f"ap:{__name__}/images/icon.png"

components.append(
    Component(
        "TimeSplitters Future Perfect Client",
        func=launch_client,
        game_name=game_data.GAME_NAME,
        icon="TSFP",
        supports_uri=True,
    )
)
