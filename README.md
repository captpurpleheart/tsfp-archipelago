# TimeSplitters: Future Perfect for Archipelago

An [Archipelago](https://archipelago.gg) world and Dolphin client for TimeSplitters: Future Perfect
(GameCube, North American version, game ID `G3FE69`), created by CaptPurpleHeart.

No game files are included; you need your own copy of the game. The PAL, PlayStation 2 and Xbox
versions are not supported.

## Download and setup

1. Download `timesplitters_future_perfect.apworld` from the
   [latest release](https://github.com/captpurpleheart/tsfp-archipelago/releases/latest).
2. Double-click it (or copy it into Archipelago's `custom_worlds` folder) and restart the
   Archipelago Launcher.
3. Follow the [setup guide](timesplitters_future_perfect/docs/en_Setup.md).

The [game page](timesplitters_future_perfect/docs/en_TimeSplitters%20Future%20Perfect.md) describes
every item, check and option.

## Support

For help, discussion and bug reports, join the TimeSplitters Archipelago Discord:
https://discord.gg/M9cbCqc8sF

## What the randomizer does

* **Items:** all 48 Arcade League missions and Challenges, the 13 story levels (or Progressive Story
  Levels), all 150 characters, the 13 cheats and 34 arcade weapons, optional bonus items (Progressive
  Starting Armour, Progressive Behead The Undead Score Multiplier, Progressive Miscellaneous
  Challenges Score Multiplier), Progressive Damage Resistances, Progressive Shop Restocks, Trophy
  items for shop points, and weapon buffs filling the leftover locations.
* **Locations:** Bronze/Silver/Gold/Platinum trophies on every mission, story level completions per
  difficulty, story objectives, optional group/league/all-Challenges milestones, and the optional
  Archipelago Shop.
* **Goals:** complete 1924 Future Perfect (optionally needing a number of story levels and trophies
  first), or a Trophy Hunt: a chosen grade of trophy on every Arcade League mission, every Challenge,
  or all 48.
* **Easier trophies (optional):** easier times for Astro Jocks, Rumble In The Jungle and Electro Chimp
  Discomatic, and lower Platinum scores for the Cut-Out Shoot-Out Challenges.
* **Death Link:** failing a mission sends a death; a death received kills you in the mission you are in.
  In Arcade League missions, Death Link Amnesty (1 to 5) sets how many deaths send one.
* **In-game announcements:** items you receive, send and find appear as on-screen text while you
  play, and received Death Links in large text. Use `/announce` in the client to choose which.
* **Archipelago Shop:** Extras & Shop > Archipelago Shop sells 15 to 75 items for points earned from
  kills, trophies and story levels.
* **Inventory tab:** the client lists the shop's items and your points, and the damage resistances,
  weapon buffs, score multipliers and starting armour you have.
* **Award screen:** after a mission, the "New Feature Unlocked" screen also lists the story levels,
  missions, challenges, bonus items and other players' items you found or received.
* **Streamer Mode:** replaces the licensed Disco and credits song with another track from the game.
* **Universal Tracker** is supported when installed (optional).

## Building from source

Run `py build_apworld.py` to make `timesplitters_future_perfect.apworld` from the
`timesplitters_future_perfect/` folder.

## License

MIT. See `LICENSE`.
