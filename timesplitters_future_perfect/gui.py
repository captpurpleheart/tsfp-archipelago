"""The client window: Archipelago's own (or Universal Tracker's) plus an "Inventory" tab."""

EMPTY = {
    "resistances": "No Resistances have been found yet.",
    "buffs": "No Weapon Buffs have been found yet.",
    "multipliers": "No Score Multipliers have been found yet.",
    "other": "Nothing has been found yet.",
}


def _escape(text: str) -> str:
    """Item and player names shown as they are, not read as Kivy markup."""
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def inventory_text(shop=None, resistances=(), buffs=(), multipliers=(), other=()) -> str:
    """
    The Inventory tab, in Kivy markup (bold headings). Every section but the shop always shows:
      shop: None (no shop in this game) or (points or None while connecting, the 15 rows' texts);
      resistances: (group, copies counted, most copies that count, percent less damage);
      buffs: (weapon, stat, total percent, normal value, value now, copies counted, most copies);
      multipliers: (name, factor now, copies counted, most copies);
      other: (name, percent, copies counted, most copies), e.g. Starting Armour.
    """
    def section(heading: str, lines: list[str], empty: str) -> str:
        return f"[b]{heading}[/b]\n" + "\n".join(lines or [empty])

    sections = []
    if shop is not None:
        points, rows = shop
        heading = "[b]Archipelago Shop List[/b] - " + ("connecting..." if points is None else f"{points} Points")
        sections.append("\n".join([heading] + [_escape(row) for row in rows]))
    sections.append(section("Damage Resistances", [
        f"{group} Damage x{have} of {most} ({percent}% less Damage)"
        for group, have, most, percent in resistances], EMPTY["resistances"]))
    sections.append(section("Weapon Buffs", [
        f"{_escape(weapon)} +{percent}% {stat} ({normal} -> {now}) ({have}/{most})"
        for weapon, stat, percent, normal, now, have, most in buffs], EMPTY["buffs"]))
    sections.append(section("Score Multipliers", [
        f"{name} x{factor} ({have}/{most})" for name, factor, have, most in multipliers], EMPTY["multipliers"]))
    sections.append(section("Other", [
        f"{name} {percent}% ({have}/{most})" for name, percent, have, most in other], EMPTY["other"]))
    return "\n\n".join(sections)


def make_gui(base_class: type) -> type:
    from kivy.metrics import dp
    from kivymd.uix.label import MDLabel
    from kivymd.uix.scrollview import MDScrollView

    import Utils

    def window_title() -> str:
        return f"TimeSplitters: Future Perfect Client (AP Version {Utils.__version__})"

    class TsfpManager(base_class):
        def build(self):
            container = super().build()
            self.title = window_title()
            try:
                self.inventory_label = MDLabel(text=inventory_text(), halign="left", adaptive_height=True,
                                               padding=(dp(12), dp(12)), markup=True)
                scroll = MDScrollView()
                scroll.add_widget(self.inventory_label)
                self.add_client_tab("Inventory", scroll)
            except Exception:
                self.inventory_label = None      # an older Archipelago: carry on without the tab
            return container

        def update_texts(self, dt):
            # Archipelago (or Universal Tracker) writes its own name here; keep "| Connected to: ..."
            super().update_texts(dt)
            _, connected, details = self.title.partition(" | ")
            self.title = window_title() + (f" | {details}" if connected else "")

        def update_inventory(self, text: str) -> None:
            if getattr(self, "inventory_label", None) is not None:
                self.inventory_label.text = text

    return TsfpManager
