#!/usr/bin/env python3
"""A command-line implementation of the Palm Island solo base game.

Run with ``python3 palm_island_solo.py``. The main menu chooses a random or
entered seed, then asks whether to play manually or run an automatic demo.

This version has 16 development cards and one round tracker. Card values
follow the revised card reference; the base rules are documented at
https://www.rulespal.com/palm-island/rulebook.
"""

import itertools
import random
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field


RESOURCE_NAMES = ("wood", "fish", "stone") # resource types
TRACKER_ID = 17 # the number of tracker card
MAX_STORED = 4 # the maximum limit of stored cards


@dataclass(frozen=True)
class Resource:
#   Keep resources in a fixed order for reliable comparisons.

    wood: int = 0
    fish: int = 0
    stone: int = 0

    def covers(self, cost: Resource) -> bool:
        return (self.wood >= cost.wood and self.fish >= cost.fish
                and self.stone >= cost.stone)
        # used to check whether current resources are enough for the cost

    def __add__(self, other: Resource) -> Resource:
        return Resource(self.wood + other.wood,
                        self.fish + other.fish,
                        self.stone + other.stone)
        # define method about counting resources

    def __str__(self) -> str:
        parts = [f"{n}{label}" for n, label in zip(
            (self.wood, self.fish, self.stone), RESOURCE_NAMES) if n]
        return "+".join(parts) if parts else "none"
        # define method about describing resources


def sum_resources(resources: tuple[Resource, ...]) -> Resource:
    total = Resource()
    for resource in resources:
        total += resource
    return total


def resource_overlaps(gain: Resource, cost: Resource) -> bool:
    """A spent card must supply at least one type required by the cost."""

    return ((gain.wood > 0 and cost.wood > 0)
            or (gain.fish > 0 and cost.fish > 0)
            or (gain.stone > 0 and cost.stone > 0))


def parse_resource(text: str) -> Resource:
# Convert card data such as ``1wood+2fish`` into resource counts.
# Convert from str to
# Input : a string 'text' about resources, including types and amounts

    text = text.strip() # remove blank space
    if text in ("", "-", "free"): # none is produced, or no resource cost
        return Resource() # an empty object
    counts = dict.fromkeys(RESOURCE_NAMES, 0) # generate a dictionary about amounts of resources
    for token in text.split("+"): # split the whole resources string to
        token = token.strip()
        index = 0
        while index < len(token) and token[index] in "0123456789": # the first character must be a number ( amount )
            index += 1 # an example of token: 3fish -> 3: :fish
        amount, name = token[:index], token[index:] # amount = '3'(converted to int in line 67), name = 'fish'
        if not amount or name not in RESOURCE_NAMES: # unknown resources or incorrect string structure
            raise ValueError(f"Unrecognized resource: {text}")
        counts[name] += int(amount) # update resources
    return Resource(counts["wood"], counts["fish"], counts["stone"])


def parse_cost(text: str | None) -> tuple[Resource, ...] | None:
    # None means the action is absent / not available ; 'or' separates alternative costs.

    if text is None or text.strip() == "-":
        return None
    if text.strip() == "free":
        return (Resource(),)
    return tuple(parse_resource(part) for part in text.split(' or '))


@dataclass(frozen=True)
class Face:
    label: str
    store_cost: tuple[Resource, ...] | None
    gain: Resource
    rotate_cost: tuple[Resource, ...] | None
    flip_cost: tuple[Resource, ...] | None
    points: int = 0
    alternate_gains: tuple[Resource, ...] = ()
# Each card has 4 faces, corresponding to 4 levels.
# these three costs uses tuple since they may have an alternative cost. e.g. 1fish or 1wood or 1stone

def face(label: str, store: str = "-", gain: str = "-",
         rotate: str = "-", flip: str = "-", points: int = 0) -> Face:
    # A slash on Statue of Trust means a choice of one resource type.
    gains = tuple(parse_resource(part) for part in gain.split(" or "))
    return Face(label, parse_cost(store), gains[0],
                parse_cost(rotate), parse_cost(flip), points, gains[1:])


def gain_text(spec: Face) -> str:
    """Describe every resource choice printed on a face."""

    return " or ".join(str(gain) for gain in
                       (spec.gain, *spec.alternate_gains))


# F/B identify the front/back; 0/1 identify upright/inverted orientation.
# Storage is independent of orientation. Rotation toggles 0/1; flipping toggles F/B.
# Good design.
ROTATE_TO = {"F0": "F1", "F1": "F0", "B0": "B1", "B1": "B0"}
FLIP_TO = {"F0": "B0", "B0": "F0", "F1": "B1", "B1": "F1"}

@dataclass(frozen=True)
class CardKind:
    english: str # its name
    faces: Mapping[str, Face] # its effects, cost, and supported actions

# Is it some kind of hard-coding? I don't know.
# Maybe I should put these data in another file and let this program read that file to import these data?
CARD_KINDS: dict[str, CardKind] = {
    "Canoe House": CardKind("Canoe House", { # mainly produces fish, may produces wood after upgraded
        "F0": face("Level 0", "free", "1fish", "1fish", "1fish"),
        "F1": face("Level 1 (double fish)", "free", "2fish", flip="1wood+1fish"),
        "B0": face("Level 1 (fish + wood)", "free", "1wood+1fish", rotate="1wood+1fish"),
        "B1": face("Level 2", "free", "1wood+2fish"),
    }),
    "Logger": CardKind("Logger", { # mainly produces wood, gain VP when upgraded
        "F0": face("Level 0", "free", "1wood", rotate="1wood+1fish"),
        "F1": face("Level 1", "free", "1wood", flip="1wood+1stone", points=1),
        "B1": face("Level 2", "free", "2wood", rotate="2wood+2stone", points=2),
        "B0": face("Level 3", points=5), # the final level no longer produce wood but worth 5 VP!
    }),
    "Quarry": CardKind("Quarry", { # initially produces nothing, but stone after upgraded
        "F0": face("Level 0", rotate="2wood", flip="2fish"),
        "F1": face("Level 1 (wood path)", "free", "1stone", flip="2wood+1fish"),
        "B0": face("Level 1 (fish path)", "free", "1stone", rotate="1wood+2fish"),
        "B1": face("Level 2", "free", "2stone", points=2), # 2 paths to the only final level
    }),
    "Market": CardKind("Market", { # pay some resources to gain more resources
        "F0": face("Level 0", "1wood or 1fish", "1stone", "2wood", "2fish"),
        "F1": face("Level 1 (upgraded by wood)", "1wood", "1fish+1stone", flip="1wood+1stone"),
        "B0": face("Level 1 (upgraded by fish)", "1fish", "1wood+1stone", rotate="1fish+1stone"),
        "B1": face("Level 2", "1wood or 1fish or 1stone", "1wood+1fish+1stone"), # pay 1, get 3!
    }),
    "Trade House": CardKind("Trade House", { # 2 sames for 1+1, trading for lots of specific resource after upgraded
        "F0": face("Level 0 (2fish/wood for 1+1)", "2fish or 2wood", "1wood+1fish", "1fish", "1wood"),
        "F1": face("Level 1 (2same for 3wood)", "2fish or 2stone", "3wood", flip="1wood+1fish"),
        "B0": face("Level 1 (2same for 3fish)", "2wood or 2stone", "3fish", rotate="1wood+1fish"),
        # The advanced Trade House can still rotate or flip to another orientation.
        "B1": face("Level 2 (2same for 3stone)", "2wood or 2fish", "3stone", "1stone", "1stone"),
    }),
    "Tool Maker": CardKind("Tool Maker", { # produce many resource after upgraded
        "F0": face("Level 0", rotate="1wood+1fish+2stone", flip="1wood+1fish"),
        "F1": face("Level 3", points=4),
        # the final level (F1) produce no resource, and can be reached directly from the initial level(F0).
        "B0": face("Level 1", "free", "1wood+1fish", rotate="1wood+1fish+1stone"),
        "B1": face("Level 2", "free", "1wood+1fish+1stone", flip="2wood+2fish+2stone"),
    }),
    "Housing": CardKind("Housing", { # VP provider, affordable
        "F0": face("Level 0", rotate="1wood+1fish"),
        "F1": face("Level 1", flip="1wood+1fish+1stone", points=1),
        "B1": face("Level 2", rotate="2wood+2fish+2stone", points=3),
        "B0": face("Level 3", points=6),
    }),
    "Temple": CardKind("Temple", { # luxury VP provider, higher cost for more VP
        "F0": face("Level 0", rotate="1wood+1fish+2stone"),
        "F1": face("Level 1", flip="2wood+2fish+3stone", points=3),
        "B1": face("Level 2", rotate="3wood+3fish+4stone", points=6),
        "B0": face("Level 3", points=10),
    }),
    "Statue of Trust": CardKind("Statue of Trust", {
        "F0": face("Locked: score at least 30 VP"),
        "F1": face("Unlocked", flip="1wood+1fish"),
        "B1": face("Level 1", "free", "1wood or 1fish or 1stone",
                   rotate="1wood+1fish+1stone", points=1),
        "B0": face("Level 2", "free", "2wood or 2fish or 2stone",
                   points=2),
    }),
    "Heart of the Mountain": CardKind("Heart of the Mountain", {
        "F0": face("Locked: end with 9 stone stored and 25 VP"),
        "F1": face("Unavailable"),
        "B0": face("Unlocked", "free", "1stone"),
        "B1": face("Unavailable"),
    }),
    "Strength of Spirit": CardKind("Strength of Spirit", {
        "F0": face("Locked: no Temple upgrades and 30 VP"),
        # This printed flip requires two level-3 Housing cards, not resources.
        "F1": face("Unlocked", flip="free"),
        "B1": face("Level 1", rotate="3wood+3fish+3stone", points=1),
        "B0": face("Level 2", points=5),
    }),
    "Horn of Honor": CardKind("Horn of Honor", {
        "F0": face("Locked: Market and Trade House level 2; 32 VP"),
        "F1": face("Unlocked", flip="1wood+1fish"),
        "B1": face("Wood and fish", "3stone", "2wood+2fish",
                   rotate="free", points=1),
        "B0": face("Stone", "2wood+1fish", "4stone",
                   rotate="free", points=1),
    }),
    "Monument of Glory": CardKind("Monument of Glory", {
        "F0": face("Locked: two Temples level 3; 30 VP"),
        "F1": face("Unavailable"),
        "B0": face("Once per game", "free", "1wood+1fish+1stone"),
        "B1": face("Unavailable"),
    }),
    "Mark of Balance": CardKind("Mark of Balance", {
        "F0": face("Locked: all development cards level 2"),
        "F1": face("Unavailable"),
        "B0": face("Unlocked", "free", "1wood+1fish"),
        "B1": face("Unavailable"),
    }),
}


FEAT_NAMES = (
    "Statue of Trust", "Heart of the Mountain", "Strength of Spirit",
    "Horn of Honor", "Tooth of the Beast", "Axe of Greatness",
    "Vision Stone", "Monument of Glory", "Mark of Balance",
)
DECK_FEATS = (
    "Statue of Trust", "Heart of the Mountain", "Strength of Spirit",
    "Horn of Honor", "Monument of Glory", "Mark of Balance",
)
START_FEATS = ("Tooth of the Beast", "Axe of Greatness", "Vision Stone")
FEAT_CARD_IDS = {name: number for number, name in enumerate(DECK_FEATS, 18)}
FEAT_START_ORIENTATION = {
    "Statue of Trust": "F1", "Heart of the Mountain": "B0",
    "Strength of Spirit": "F1", "Horn of Honor": "F1",
    "Monument of Glory": "B0", "Mark of Balance": "B0",
}


# Numbers match the physical deck; copies of a kind keep unique numbers.
CARD_NUMBER_KIND = {
    **dict.fromkeys(range(1, 4), "Canoe House"), # 3 copies of Canoe House
    **dict.fromkeys(range(4, 7), "Logger"), # 3 copies
    **dict.fromkeys(range(7, 10), "Quarry"), # 3 copies
    10: "Market", 11: "Trade House", 12: "Tool Maker", # unique
    13: "Housing", 14: "Housing", 15: "Temple", 16: "Temple", # 2 copies of each
}


@dataclass
class Card:
    number: int # A unique card ID; 17 is reserved for the round tracker.
    kind: str # ^^^
    orientation: str = "F0" # F0, F1, B0, F1
    stored: bool = False # True = 90 degrees rotated = stored

    @property
    def spec(self) -> Face: # values like cost,VP... is on face object, not card object,
        return CARD_KINDS[self.kind].faces[self.orientation]
        # input kind as key to find the specific card, and input orientation to find the specific face
        # just like card.face.points or so on ( if spec is replaced by face)

    @property
    def display_name(self) -> str:
        return f"#{self.number} {CARD_KINDS[self.kind].english}" #e.g. #1 Canoe House

    @property
    def gain_choices(self) -> tuple[Resource, ...]:
        """The resource profiles this stored card can provide, one at a time."""

        return (self.spec.gain, *self.spec.alternate_gains)

    @property
    def gain_text(self) -> str:
        return gain_text(self.spec)


@dataclass(frozen=True)
class Option:
    # One payable action; position is the first or second deck slot.

    position: int # to the card this action is for
    action: str # pass, store, flip, rotate
    payment: tuple[int, ...] = () # alternative cost allowed
    release: int | None = None # 4 resources card limit, if not None, target card will be released for room


class RuleError(ValueError):
    pass
    #The requested action conflicts with the deck or stored resources.


@dataclass
class Game:
    deck: list[int] # each number 1 - 17 = 1 specific card
    cards: dict[int, Card] # a dictionary saving all cards' status
    round_number: int = 1 # starting round, the game ends at the end of round 8
    finished: bool = False # end game flag
    history: list[str] = field(default_factory=list) # game_history
    feat_used: set[int] = field(default_factory=set)
    applied_start_feats: set[str] = field(default_factory=set)

    @classmethod
    def new(cls, seed: int | None = None,
            feat_order: tuple[str, ...] = ()) -> Game: # object = a new game
        numbers = list(range(1, 17)) # from 1 to 16 = 16 cards
        random.Random(seed).shuffle(numbers) # seed -> random card order
        cards = {n: Card(n, kind) for n, kind in CARD_NUMBER_KIND.items()} # <-line 166,put all card into this dict
        game = cls(numbers + [TRACKER_ID], cards)
        for name in feat_order:
            game.add_feat_card(name)
        return game # return Game object
        # numbers = random card order, [TRACKER_ID] = 17 added to the end
        # They are combined into a deck for this game

    def _ensure_setup(self) -> None:
        if self.finished or self.round_number != 1 or self.history:
            raise RuleError("Starting Feats can only be applied before the first turn")

    def add_feat_card(self, name: str) -> int:
        """Place an activated cycling Feat at the deck's back in chosen order."""

        self._ensure_setup()
        if name not in FEAT_CARD_IDS:
            raise RuleError(f"Unknown cycling Feat: {name}")
        number = FEAT_CARD_IDS[name]
        if number in self.cards:
            raise RuleError(f"Feat already added: {name}")
        self.cards[number] = Card(number, name, FEAT_START_ORIENTATION[name])
        self.deck.append(number)
        return number

    def apply_starting_upgrade(self, kind: str, card_number: int,
                               orientation: str) -> None:
        """Apply Tooth or Axe to one chosen basic card at game setup."""

        self._ensure_setup()
        feat_name = {
            "Canoe House": "Tooth of the Beast",
            "Logger": "Axe of Greatness",
        }.get(kind)
        if feat_name is None:
            raise RuleError("Only Canoe House and Logger have starting Feat upgrades")
        if feat_name in self.applied_start_feats:
            raise RuleError(f"Starting Feat already applied: {feat_name}")
        choices = {"Canoe House": ("F1", "B0"), "Logger": ("F1",)}[kind]
        if orientation not in choices:
            raise RuleError(f"Invalid starting upgrade orientation: {orientation}")
        card = self.cards.get(card_number)
        if card is None or card.number > 16 or card.kind != kind or card.orientation != "F0":
            raise RuleError(f"Card #{card_number} cannot receive this starting upgrade")
        card.orientation = orientation
        self.applied_start_feats.add(feat_name)

    def apply_vision_stone(self, card_number: int) -> None:
        """Move one selected card, including a cycling Feat, to deck position 1."""

        self._ensure_setup()
        if "Vision Stone" in self.applied_start_feats:
            raise RuleError("Vision Stone was already applied")
        if card_number == TRACKER_ID or card_number not in self.cards:
            raise RuleError("Vision Stone requires a development or cycling Feat card")
        self.deck.remove(card_number)
        self.deck.insert(0, card_number)
        self.applied_start_feats.add("Vision Stone")

    @staticmethod
    def _level(card: Card) -> int:
        """Read the explicit printed level from a basic development card."""

        return int(card.spec.label.split()[1])

    def check_unlocked_feats(self) -> tuple[str, ...]:
        """Check all nine end-of-game achievements against the current deck."""

        if not self.finished:
            return ()
        score = self.total_score()
        def level(number: int) -> int:
            return self._level(self.cards[number])
        stored_stone = sum(max(choice.stone for choice in card.gain_choices)
                           for card in self.stored_cards())
        criteria = {
            "Statue of Trust": score >= 30,
            "Heart of the Mountain": score >= 25 and stored_stone >= 9,
            "Strength of Spirit": score >= 30 and all(level(n) == 0 for n in (15, 16)),
            "Horn of Honor": score >= 32 and level(10) >= 2 and level(11) >= 2,
            "Tooth of the Beast": score >= 30 and all(level(n) >= 2 for n in (1, 2, 3)),
            "Axe of Greatness": score >= 34 and all(level(n) >= 2 for n in (4, 5, 6)),
            "Vision Stone": score >= 40,
            "Monument of Glory": score >= 30 and all(level(n) >= 3 for n in (15, 16)),
            # The tracker and added Feats have no basic development level.
            "Mark of Balance": all(level(n) >= 2 for n in range(1, 17)),
        }
        return tuple(name for name in FEAT_NAMES if criteria[name])

    def special_action_issue(self, number: int, action: str) -> str | None:
        """Explain non-resource action restrictions printed on Feat cards."""

        card = self.cards.get(number)
        if card is None:
            return None
        if (card.kind == "Strength of Spirit" and card.orientation == "F1"
                and action == "flip"
                and not all(self._level(self.cards[n]) >= 3 for n in (13, 14))):
            return "Requires both Housing cards at level 3 or higher"
        if (card.kind == "Monument of Glory" and action == "store"
                and number in self.feat_used):
            return "Monument of Glory can be stored only once per game"
        return None

    def stored_cards(self) -> list[Card]: # return all stored card
        all_stored_cards: list[Card] = []
        for n in self.deck:
            if n != TRACKER_ID and self.cards[n].stored: # trying card[TRACKER_ID] will occur KeyError
                all_stored_cards.append(self.cards[n])
        return all_stored_cards


    def total_score(self) -> int: #return current total VP
        total_vp = 0
        for i in self.cards.values(): # using the elements(card) in dictionary cards
            total_vp += i.spec.points # -> card.spec.points
        return total_vp

    def _payment_sets(self, cost: tuple[Resource, ...]) -> list[tuple[int, ...]]:
        if any(c == Resource() for c in cost): # Free cost
            return [()] # return empty list
        stored = self.stored_cards() # read all stored cards
        matches: list[tuple[int, ...]] = [] # the container of all legal payments
        for size in range(1, len(stored) + 1): # size 1 -> amount of stored card
            for group in itertools.combinations(stored, size): # Full combination of size i
                if any(
                    sum_resources(choices).covers(alternative)
                    and all(resource_overlaps(choice, alternative)
                            for choice in choices)
                    for alternative in cost
                    for choices in itertools.product(
                        *(card.gain_choices for card in group)
                    )
                ):
                    matches.append(tuple(card.number for card in group))
        return matches # it returns all legal payments

    def legal_options(self) -> list[Option]:
        if self.finished: # when game ends
            return []
        options = [Option(0, "pass")] # always allow to discard the first card
        for position in range(min(2, len(self.deck))): # usually range(2) -> 0 and 1
            number = self.deck[position] # find the number of that card
            if number == TRACKER_ID or self.cards[number].stored:
                continue # tracker card and stored card don't provide legal action
            spec = self.cards[number].spec # find the face
            for action, cost in (("store", spec.store_cost),
                                 ("rotate", spec.rotate_cost),
                                 ("flip", spec.flip_cost)):
                if cost is None: # None means unavailable, not free action
                    continue
                if self.special_action_issue(number, action):
                    continue
                for payment in self._payment_sets(cost): # for the cost of an action, returns all legal payments for it
                    if action == "store" and len(self.stored_cards()) - len(payment) >= MAX_STORED:
                        # storage limit check
                        for old in self.stored_cards():
                            if old.number not in payment: # release this old stored card for room for new store card
                                options.append(Option(position, action, payment, old.number))
                    else:
                        options.append(Option(position, action, payment))
        return options # returns all possible options

    def _settle_front(self) -> list[str]:
        #

        events: list[str] = []
        for _ in range(len(self.deck) * 2 + 2): # loop maximum limit
            first = self.deck[0] # the topmost card
            if first == TRACKER_ID: # event: current round ends
                if self.round_number == 8: # final round ends -> game ends
                    self.finished = True
                    events.append(f"Round 8 complete. Final score: {self.total_score()} points")
                    return events
                events.append(f"Round {self.round_number} complete. Round {self.round_number + 1} begins")
                self.round_number += 1 # a new round
                self.deck.append(self.deck.pop(0)) #move the tracker card from the top to the bottom
                continue

            card = self.cards[first] # find the specific card
            if card.stored:
                card.stored = False # cancel storage status
                self.deck.append(self.deck.pop(0)) # move the stored card to the bottom of the deck
                events.append(f"{card.display_name} reached the front; its stored resource expires and it moves to the back")
                continue
            return events # a card with possible actions is found, no matter it is affordable
        raise RuntimeError("No playable card found in the deck")

    def play(self, chosen: Option) -> list[str]:
        # Recheck the action, spend resources, then update the card and deck.

        if chosen not in self.legal_options():
            raise RuleError("Action unavailable or selected payment/release is invalid")
        events: list[str] = []
        if chosen.action == "pass": # discard the topmost card
            number = self.deck.pop(0)
            self.deck.append(number)
            events.append(f"Discarded {self.cards[number].display_name} to the back of the deck")
        else: # one of these actions: store, flip, or rotate
            number = self.deck[chosen.position]
            card = self.cards[number]
            for used in chosen.payment: # spend resources
                resource_card = self.cards[used]
                resource_card.stored = False # resources spent
                events.append(f"Spent {resource_card.display_name} ({resource_card.gain_text})")
            if chosen.release is not None: # store action: releases old resources
                released = self.cards[chosen.release]
                released.stored = False
                events.append(f"Released {released.display_name} to free a storage slot")

            if chosen.action == "store": # rotate the card by 90 degree to store it
                card.stored = True
                if card.kind == "Monument of Glory":
                    self.feat_used.add(card.number)
                events.append(f"Stored {card.display_name}: {card.gain_text}")

            elif chosen.action == "rotate": # rotate the card by 180 degree
                card.orientation = ROTATE_TO[card.orientation]
                events.append(f"Rotated {card.display_name} -> {face_summary(card.spec)}")

            elif chosen.action == "flip": # flip the card to the other side
                card.orientation = FLIP_TO[card.orientation]
                events.append(f"Flipped {card.display_name} -> {face_summary(card.spec)}")

            self.deck.append(self.deck.pop(chosen.position)) #move that card to the bottom
        events.extend(self._settle_front()) # check whether the topmost card is the tracker / stored
        self.history.extend(events) # record all events
        return events


def cost_text(cost: tuple[Resource, ...] | None) -> str:
    if cost is None:
        return "unavailable"
    return " or ".join("free" if c == Resource() else str(c) for c in cost)
    # if cost = [()], return 'free'. Otherwise, return the cost text e.g. 2fish or 2wood


ACTION_NAMES = {"pass": "Discard first card", "store": "Store",
                "rotate": "Rotate", "flip": "Flip"}


def face_summary(spec: Face) -> str:
    # Describe the resulting face and its future storage output

    if spec.store_cost is None:
        return f"{spec.label}, {spec.points} VP."
        # this card has no store action
    else:
        gain = gain_text(spec)
    return f"{spec.label}, {spec.points} VP, produces: {gain}"


def payment_text(game: Game, option: Option) -> str:
    #Show every card consumed and any card released to free storage.

    if option.payment:
        spent = ", ".join(
            f"{game.cards[number].display_name} ({game.cards[number].gain_text})"
            for number in option.payment
        )
        label = f"spend {spent}"
    else:
        label = "pay nothing"
    if option.release is not None:
        label += f"; release {game.cards[option.release].display_name}"
    return label


def action_entries(game: Game) -> list[tuple[str, list[Option]]]:
    #Return fixed menu slots 0-6, even for absent or unaffordable actions.

    legal = game.legal_options()
    entries: list[tuple[str, list[Option]]] = [
        ("Discard first card to the bottom of the deck", [Option(0, "pass")])
    ]
    for position in (0, 1): # the top 2 cards
        number = game.deck[position] # find their numbers
        for action in ("store", "rotate", "flip"): # show all of their actions
            if position == 0:
                slot = "First"
            else:
                slot = "Second"
            if number == TRACKER_ID or game.cards[number].stored: # tracker card or stored card
                entries.append((f"{slot} card: {ACTION_NAMES[action]} (unavailable)", []))
                continue
            card = game.cards[number] # find their faces
            cost = getattr(card.spec, f"{action}_cost") # find specific action cost
            label = f"{slot} card {card.display_name}: {ACTION_NAMES[action]}" # e.g. First card #1 Canoe House: Flip
            if cost is None:
                entries.append((label + " (unavailable)", [])) # unavailable action followed by an empty option
                continue
            if action == "store":
                label += f" -> {card.gain_text}" # e.g. ...Canoe House: Store -> 2fish

            if action == "rotate":
                next_state = ROTATE_TO[card.orientation]
                label += f" -> {face_summary(CARD_KINDS[card.kind].faces[next_state])}"
            if action == "flip":
                next_state = FLIP_TO[card.orientation]
                label += f" -> {face_summary(CARD_KINDS[card.kind].faces[next_state])}"
                # e.g. Canon House: Flip -> ... (cost: ...)
            label += f" (cost: {cost_text(cost)})"
            variants = sorted(
                (o for o in legal if o.position == position and o.action == action),
                key=lambda o: (o.payment, -1 if o.release is None else o.release),
            ) # list all legal payment for specific action on specific card
            if not variants: # no legal payment
                issue = game.special_action_issue(number, action)
                label += f" ({issue})" if issue else " (insufficient resources)"
            elif len(variants) == 1: # just 1
                label += f" ({payment_text(game, variants[0])})"
            else: # more than 1
                label += f" ({len(variants)} payment options)"
            entries.append((label, variants))
    return entries


def card_preview_text(game: Game, position: int) -> str:
    #Preview one of the first three cards without changing game state.

    if position not in (1, 2, 3) or position > len(game.deck):
        raise ValueError("Only the first three cards can be previewed")
    number = game.deck[position - 1]
    if number == TRACKER_ID:
        return f"Card {position} is the round tracker: round {game.round_number} of 8."
    card = game.cards[number]
    lines = [f"Four orientations of card {position}, {card.display_name} (preview only):"]
    for orientation, orientation_name in (("F0", "Front upright"), ("F1", "Front inverted"),
                                          ("B0", "Back upright"), ("B1", "Back inverted")):
        spec = CARD_KINDS[card.kind].faces[orientation]
        marker = " <- current" if card.orientation == orientation else ""
        if spec.store_cost is None:
            storage = "no store action"
        else:
            storage = f"cost {cost_text(spec.store_cost)} -> {gain_text(spec)}"
        lines.append(f"  {orientation_name} [{spec.label}]{marker}: {spec.points} points; "
                     f"store {storage}; rotate cost {cost_text(spec.rotate_cost)}; "
                     f"flip cost {cost_text(spec.flip_cost)}")
    return "\n".join(lines)


def show_state(game: Game) -> None:
    print(f"\n=== Round {game.round_number}/8 ===")
    visible = game.deck[:3]
    for position, number in enumerate(visible, 1):
        if number == TRACKER_ID:
            print(f"  Card {position}: Round tracker")
            continue
        card = game.cards[number]
        note = " [stored]" if card.stored else ""
        print(f"  Card {position}: {card.display_name} | {card.spec.label} | "
              f"{card.spec.points} points{note}")
    resources = game.stored_cards()
    if resources:
        print("  Stored: " + ", ".join(f"#{c.number} {c.gain_text}" for c in resources))
    else:
        print("  Stored: none")
    print(f"  Current score: {game.total_score()}")


def print_result(game: Game) -> None:
    print(f"\nGame over: {game.total_score()} points")
    for kind in CARD_KINDS:
        cards = [c for c in game.cards.values() if c.kind == kind]
        if not cards:
            continue
        points = sum(c.spec.points for c in cards)
        print(f"  {CARD_KINDS[kind].english} x{len(cards)}: {points} points")


def run_interactive(game: Game) -> None:
    """Play one game with fixed action slots and optional payment menus."""

    print("Palm Island solo game. Enter 0-6 to act, p1/p2/p3 to preview, or q for the main menu.")
    while not game.finished:
        show_state(game)
        entries = action_entries(game)
        for index, (label, _) in enumerate(entries):
            print(f"  {index}. {label}")
        answer = input("Choose an action: ").strip().lower()
        if answer in ("q", "quit"):
            print("Game closed without saving. Returning to the main menu.")
            return
        if answer.startswith("p") and answer[1:].strip() in ("1", "2", "3"):
            print(card_preview_text(game, int(answer[1:].strip())))
            continue
        if not answer.isdecimal() or not (0 <= int(answer) < len(entries)):
            print("Enter an action number from 0 to 6, or p1/p2/p3 for a preview.")
            continue
        label, variants = entries[int(answer)]
        if not variants:
            print("This action is unavailable or cannot be paid for.")
            continue
        if len(variants) == 1:
            chosen = variants[0]
        else:
            print(f"Payment choices for {label}:")
            print("  0. Back to actions")
            for index, option in enumerate(variants, 1):
                print(f"  {index}. {payment_text(game, option)}")
            while True:
                payment_answer = input("Choose a payment: ").strip().lower()
                if payment_answer in ("q", "quit"):
                    print("Game closed without saving. Returning to the main menu.")
                    return
                if payment_answer.isdecimal() and 0 <= int(payment_answer) <= len(variants):
                    break
                print(f"Enter a payment number from 0 to {len(variants)}.")
            if payment_answer == "0":
                continue
            chosen = variants[int(payment_answer) - 1]
        try:
            events = game.play(chosen)
        except RuleError as exc:
            print(f"Action not performed: {exc}")
            continue
        for event in events:
            print("  - " + event)
    print_result(game)


def run_auto(game: Game) -> None:
    """Prefer affordable upgrades, then storage, then discarding."""

    turns = 0
    while not game.finished:
        options = game.legal_options()
        upgrades = [o for o in options if o.action in ("rotate", "flip")]
        stores = [o for o in options if o.action == "store"]
        if upgrades:
            chosen = min(upgrades, key=lambda o: (len(o.payment), o.position))
        elif stores:
            chosen = min(stores, key=lambda o: (len(o.payment), o.position))
        else:
            chosen = options[0]
        game.play(chosen)
        turns += 1
        if turns > 5000:
            raise RuntimeError("Demo exceeded 5,000 actions; check deck progression")
    print(f"Automatic demo complete: {turns} actions, {game.total_score()} points.")
    print_result(game)


def main() -> None:
    """Choose a seed and play mode from in-program menus."""

    try:
        while True:
            print("\n=== Palm Island: Main Menu ===")
            print("  1. New game with a random seed")
            print("  2. New game with an entered seed")
            print("  0. Exit")
            choice = input("Choose: ").strip()
            if choice == "0":
                print("Goodbye.")
                return
            if choice == "1":
                seed = secrets.randbits(64)
            elif choice == "2":
                while True:
                    entered = input("Enter an integer seed (q to cancel): ").strip()
                    if entered.lower() == "q":
                        seed = None
                        break
                    try:
                        seed = int(entered)
                        break
                    except ValueError:
                        print("Enter an integer seed.")
                if seed is None:
                    continue
            else:
                print("Choose 0, 1, or 2.")
                continue
            print(f"Game seed: {seed}")
            while True:
                demo = input("Run an automatic demo? (y/n, 0 to cancel): ").strip().lower()
                if demo in ("y", "n", "0"):
                    break
                print("Enter y, n, or 0.")
            if demo == "0":
                continue
            game = Game.new(seed)
            if demo == "y":
                run_auto(game)
            else:
                run_interactive(game)
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
