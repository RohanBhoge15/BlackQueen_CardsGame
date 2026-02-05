"""
Card Game Logic - Trump Card Game with Bidding and Partners
"""
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

class Suit(Enum):
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"

SUIT_SYMBOLS = {
    Suit.HEARTS: "♥",
    Suit.DIAMONDS: "♦",
    Suit.CLUBS: "♣",
    Suit.SPADES: "♠"
}

SUIT_COLORS = {
    Suit.HEARTS: "red",
    Suit.DIAMONDS: "red",
    Suit.CLUBS: "black",
    Suit.SPADES: "black"
}

# Card ranks in order (2 is lowest, Ace is highest)
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {rank: i for i, rank in enumerate(RANKS)}

# Point values for scoring
POINT_VALUES = {
    '5': 5,
    '10': 10,
    'A': 15,
}
# Special: Queen of Spades = 30 points

@dataclass
class Card:
    suit: Suit
    rank: str

    def to_dict(self) -> dict:
        return {
            "suit": self.suit.value,
            "rank": self.rank,
            "symbol": SUIT_SYMBOLS[self.suit],
            "color": SUIT_COLORS[self.suit],
            "display": f"{self.rank}{SUIT_SYMBOLS[self.suit]}"
        }

    def get_points(self) -> int:
        # Queen of Spades = 30 points
        if self.suit == Suit.SPADES and self.rank == 'Q':
            return 30
        return POINT_VALUES.get(self.rank, 0)

    def __eq__(self, other):
        if isinstance(other, Card):
            return self.suit == other.suit and self.rank == other.rank
        return False

    def __hash__(self):
        return hash((self.suit, self.rank))

@dataclass
class Player:
    id: str
    name: str
    hand: List[Card] = field(default_factory=list)
    is_bidder: bool = False
    is_partner: bool = False
    partner_revealed: bool = False
    current_bid: int = 0
    has_passed: bool = False

    def to_dict(self, hide_cards: bool = True) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "card_count": len(self.hand),
            "cards": [] if hide_cards else [c.to_dict() for c in self.hand],
            "is_bidder": self.is_bidder,
            "is_partner": self.is_partner,
            "partner_revealed": self.partner_revealed,
            "current_bid": self.current_bid,
            "has_passed": self.has_passed
        }

class GamePhase(Enum):
    WAITING = "waiting"
    VIEWING_CARDS = "viewing_cards"  # 90 second card viewing phase
    BIDDING = "bidding"
    PARTNER_SELECTION = "partner_selection"
    PLAYING = "playing"
    ROUND_END = "round_end"
    GAME_OVER = "game_over"

@dataclass
class GameRoom:
    room_code: str
    host_id: str
    num_decks: int = 1
    max_players: int = 4
    num_partners: int = 2  # 0, 1, or 2 partners for the bidder
    players: Dict[str, Player] = field(default_factory=dict)
    player_order: List[str] = field(default_factory=list)
    phase: GamePhase = GamePhase.WAITING

    # Bidding
    current_bid: int = 50
    current_bidder_index: int = 0
    highest_bidder_id: Optional[str] = None
    bid_amount: int = 0
    players_passed: int = 0

    # Trump and Partners
    trump_suit: Optional[Suit] = None
    partner_cards: List[Tuple[str, str]] = field(default_factory=list)  # [(rank, suit), ...]
    partner_cards_revealed: List[Tuple[str, str]] = field(default_factory=list)  # Partner cards already used
    partner_ids: List[str] = field(default_factory=list)

    # Current trick/round
    current_trick: List[Tuple[str, Card]] = field(default_factory=list)  # [(player_id, card), ...]
    last_trick: List[Tuple[str, Card]] = field(default_factory=list)     # Store completed trick for display
    led_suit: Optional[Suit] = None
    current_player_index: int = 0
    trick_number: int = 0

    # Scoring
    bidder_team_points: int = 0
    against_team_points: int = 0
    tricks_won: Dict[str, int] = field(default_factory=dict)
    # Track points per player for retroactive transfer when partner revealed
    player_points_earned: Dict[str, int] = field(default_factory=dict)

    # Cards removed for equal distribution
    removed_cards: List[Card] = field(default_factory=list)
    cards_per_player: int = 0

    # Cheating detection log
    cheating_log: List[dict] = field(default_factory=list)

    # RageBait surrender votes
    surrender_votes: set = field(default_factory=set)
    surrendered: bool = False

    def get_required_surrender_votes(self) -> int:
        """Get number of votes needed to surrender based on player count"""
        num_players = len(self.players)
        if num_players <= 2:
            return num_players  # All must agree
        elif num_players <= 4:
            return 2  # 2 votes for 3-4 players
        elif num_players <= 6:
            return 3  # 3 votes for 5-6 players
        elif num_players <= 8:
            return 5  # 5 votes for 7-8 players
        else:
            return (num_players // 2) + 1  # Majority for 9+ players

    def vote_surrender(self, player_id: str) -> Tuple[bool, str, bool]:
        """
        Vote to surrender (RageBait).
        Returns: (success, message, game_ended)
        """
        if player_id not in self.players:
            return False, "Player not in game", False

        if self.phase not in [GamePhase.PLAYING, GamePhase.BIDDING, GamePhase.PARTNER_SELECTION]:
            return False, "Cannot surrender in current phase", False

        if player_id in self.surrender_votes:
            return False, "You already voted to surrender", False

        self.surrender_votes.add(player_id)
        required = self.get_required_surrender_votes()
        current_votes = len(self.surrender_votes)

        if current_votes >= required:
            # Surrender successful - end game
            self.surrendered = True
            self.phase = GamePhase.GAME_OVER
            return True, f"RageBait successful! ({current_votes}/{required} votes)", True

        return True, f"Vote recorded ({current_votes}/{required} needed)", False

    def add_player(self, player_id: str, name: str) -> bool:
        if len(self.players) >= self.max_players:
            return False
        if player_id in self.players:
            return False
        self.players[player_id] = Player(id=player_id, name=name)
        self.player_order.append(player_id)
        return True

    def remove_player(self, player_id: str) -> bool:
        """Remove a player from the game. Handles mid-game removal properly."""
        if player_id not in self.players:
            return False

        # Get index before removal for adjustments
        player_index = self.player_order.index(player_id) if player_id in self.player_order else -1

        # Remove the player
        del self.players[player_id]
        if player_id in self.player_order:
            self.player_order.remove(player_id)

        # If game is in progress, adjust indices
        if self.phase != GamePhase.WAITING and player_index >= 0:
            # Adjust current_player_index if needed
            if player_index < self.current_player_index:
                self.current_player_index = max(0, self.current_player_index - 1)
            elif player_index == self.current_player_index:
                # Current player was removed, move to next
                if len(self.player_order) > 0:
                    self.current_player_index = self.current_player_index % len(self.player_order)

            # Adjust current_bidder_index if in bidding phase
            if self.phase == GamePhase.BIDDING:
                if player_index < self.current_bidder_index:
                    self.current_bidder_index = max(0, self.current_bidder_index - 1)
                elif player_index == self.current_bidder_index:
                    if len(self.player_order) > 0:
                        self.current_bidder_index = self.current_bidder_index % len(self.player_order)

            # Remove from partner_ids if applicable
            if player_id in self.partner_ids:
                self.partner_ids.remove(player_id)

            # If this was the highest bidder and we're past bidding, game might need reset
            # But for now we'll just let it continue

        return True

    def create_deck(self) -> List[Card]:
        """Create deck(s) of cards"""
        deck = []
        for _ in range(self.num_decks):
            for suit in Suit:
                for rank in RANKS:
                    deck.append(Card(suit=suit, rank=rank))
        return deck

    def create_balanced_deck(self, num_players: int) -> Tuple[List[Card], List[Card]]:
        """
        Create deck(s) and remove lowest-ranked cards for equal distribution.
        Removes cards starting from 2s, then 3s, etc. - spread across suits fairly.
        Never removes point cards (5, 10, A) or Queen of Spades.

        Returns: (deck, removed_cards)
        """
        deck = self.create_deck()
        total_cards = len(deck)
        remainder = total_cards % num_players

        if remainder == 0:
            # Already divides evenly
            return deck, []

        # Cards to remove (lowest ranks first, but never point cards)
        # Point cards: 5, 10, A, and Q of Spades
        protected_ranks = {'5', '10', 'A'}

        # Sort deck by rank (lowest first) for removal selection
        # We'll remove from lowest ranks, spreading across suits
        cards_to_remove = []
        cards_removed = 0

        # Go through ranks from lowest (2) to highest, skip protected
        for rank in RANKS:
            if cards_removed >= remainder:
                break

            # Skip point cards
            if rank in protected_ranks:
                continue

            # For this rank, find cards across all suits
            for suit in Suit:
                if cards_removed >= remainder:
                    break

                # Skip Queen of Spades (30 points)
                if rank == 'Q' and suit == Suit.SPADES:
                    continue

                # Find and mark cards of this rank/suit for removal
                # With multiple decks, we might have multiple copies
                for card in deck:
                    if card.rank == rank and card.suit == suit and card not in cards_to_remove:
                        cards_to_remove.append(card)
                        cards_removed += 1
                        if cards_removed >= remainder:
                            break

        # Remove the selected cards from deck
        for card in cards_to_remove:
            deck.remove(card)

        return deck, cards_to_remove

    def deal_cards(self):
        """Shuffle and deal cards equally to all players"""
        num_players = len(self.players)

        # Get balanced deck (removes low cards if needed for equal distribution)
        deck, removed = self.create_balanced_deck(num_players)
        self.removed_cards = removed
        random.shuffle(deck)

        self.cards_per_player = len(deck) // num_players

        for i, player_id in enumerate(self.player_order):
            start = i * self.cards_per_player
            end = start + self.cards_per_player
            self.players[player_id].hand = deck[start:end]
            # Sort hand by suit and rank
            self.players[player_id].hand.sort(
                key=lambda c: (list(Suit).index(c.suit), RANK_VALUES[c.rank])
            )

    def start_viewing_phase(self):
        """Start the 90-second card viewing phase"""
        self.phase = GamePhase.VIEWING_CARDS

    def start_bidding(self):
        """Initialize bidding phase"""
        self.phase = GamePhase.BIDDING
        self.current_bid = 50
        self.current_bidder_index = 0
        self.highest_bidder_id = None
        self.bid_amount = 0
        self.players_passed = 0

        for player in self.players.values():
            player.has_passed = False
            player.current_bid = 0

    def get_max_bid(self) -> int:
        """Get maximum possible bid based on number of decks (150 points per deck)"""
        return self.num_decks * 150

    def place_bid(self, player_id: str, bid_amount: int) -> Tuple[bool, str]:
        """Place a bid or pass"""
        current_player_id = self.player_order[self.current_bidder_index]

        if player_id != current_player_id:
            return False, "Not your turn to bid"

        if self.players[player_id].has_passed:
            return False, "You have already passed"

        max_bid = self.get_max_bid()

        if bid_amount == 0:  # Pass
            self.players[player_id].has_passed = True
            self.players_passed += 1
        elif bid_amount <= self.current_bid:
            return False, f"Bid must be higher than {self.current_bid}"
        elif bid_amount > max_bid:
            return False, f"Bid cannot exceed {max_bid} (max points possible)"
        else:
            self.current_bid = bid_amount
            self.highest_bidder_id = player_id
            self.bid_amount = bid_amount
            self.players[player_id].current_bid = bid_amount

        # Move to next player
        self._move_to_next_bidder()

        # Check if bidding is over
        if self._is_bidding_over():
            self._end_bidding()

        return True, "Bid placed"

    def _move_to_next_bidder(self):
        """Move to next player who hasn't passed"""
        num_players = len(self.player_order)
        for _ in range(num_players):
            self.current_bidder_index = (self.current_bidder_index + 1) % num_players
            next_player_id = self.player_order[self.current_bidder_index]
            if not self.players[next_player_id].has_passed:
                break

    def _is_bidding_over(self) -> bool:
        """Check if bidding phase is complete"""
        active_bidders = sum(1 for p in self.players.values() if not p.has_passed)

        # Bidding ends when only 1 bidder remains (and someone has bid)
        # OR when everyone has passed (no one bid)
        if active_bidders <= 1 and self.highest_bidder_id is not None:
            return True
        if active_bidders == 0:
            # Everyone passed - force first player to be bidder at minimum bid (100)
            return True
        return False

    def _end_bidding(self):
        """End bidding and move to partner selection"""
        if self.highest_bidder_id:
            self.players[self.highest_bidder_id].is_bidder = True
            self.phase = GamePhase.PARTNER_SELECTION
        else:
            # Everyone passed - force first player to bid at 50
            first_player_id = self.player_order[0]
            self.highest_bidder_id = first_player_id
            self.bid_amount = 50
            self.current_bid = 50
            self.players[first_player_id].is_bidder = True
            self.phase = GamePhase.PARTNER_SELECTION

    def select_trump_and_partners(self, bidder_id: str, trump_suit: str,
                                   partner_cards: List[dict]) -> Tuple[bool, str]:
        """Bidder selects trump suit and partner cards"""
        if bidder_id != self.highest_bidder_id:
            return False, "Only the highest bidder can select trump and partners"

        if self.phase != GamePhase.PARTNER_SELECTION:
            return False, "Not in partner selection phase"

        # Set trump suit
        try:
            self.trump_suit = Suit(trump_suit)
        except ValueError:
            return False, "Invalid trump suit"

        # Validate partner cards count based on num_partners setting
        if len(partner_cards) != self.num_partners:
            if self.num_partners == 0:
                return False, "No partners allowed in this game mode"
            elif self.num_partners == 1:
                return False, "Must select exactly 1 partner card"
            else:
                return False, "Must select exactly 2 partner cards"

        self.partner_cards = []
        for card in partner_cards:
            self.partner_cards.append((card['rank'], card['suit']))

        # Start playing phase
        self.phase = GamePhase.PLAYING
        self.current_player_index = self.player_order.index(self.highest_bidder_id)
        self.trick_number = 1

        return True, "Trump and partners selected"

    def play_card(self, player_id: str, card_suit: str, card_rank: str) -> Tuple[bool, str, dict]:
        """Play a card in the current trick"""
        result_data = {}

        if self.phase != GamePhase.PLAYING:
            return False, "Not in playing phase", result_data

        current_player_id = self.player_order[self.current_player_index]
        if player_id != current_player_id:
            return False, "Not your turn", result_data

        player = self.players[player_id]

        # Find the card in player's hand
        try:
            suit = Suit(card_suit)
        except ValueError:
            return False, "Invalid suit", result_data

        card = Card(suit=suit, rank=card_rank)

        if card not in player.hand:
            return False, "Card not in your hand", result_data

        # Cheating detection: Check if player has led suit but played different suit
        # Only check if not the first card (led_suit is set)
        if self.led_suit is not None and card.suit != self.led_suit:
            # Check if player has the led suit in their hand
            has_led_suit = any(c.suit == self.led_suit for c in player.hand)
            if has_led_suit:
                # Player cheated! Log the violation
                self.cheating_log.append({
                    'player_id': player_id,
                    'player_name': player.name,
                    'trick_number': self.trick_number,
                    'led_suit': self.led_suit.value,
                    'led_suit_symbol': SUIT_SYMBOLS[self.led_suit],
                    'played_card': card.to_dict(),
                    'reason': f"Had {SUIT_SYMBOLS[self.led_suit]} {self.led_suit.value} but played {card.rank}{SUIT_SYMBOLS[card.suit]}"
                })

        # Play the card (trust-based - we log but don't block)
        player.hand.remove(card)
        self.current_trick.append((player_id, card))

        # Set led suit if first card
        if self.led_suit is None:
            self.led_suit = card.suit

        # Check if this is a partner card (only first player to play each specific card becomes partner)
        partner_revealed = False
        card_key = (card.rank, card.suit.value)
        if card_key in self.partner_cards and card_key not in self.partner_cards_revealed:
            # This partner card hasn't been used yet - reveal this player as partner
            self.partner_cards_revealed.append(card_key)
            if player_id not in self.partner_ids:
                self.partner_ids.append(player_id)
                player.is_partner = True
                player.partner_revealed = True
                partner_revealed = True

                # Retroactive point transfer: Move points this player has already earned
                # from against team to bidder team
                points_to_transfer = self.player_points_earned.get(player_id, 0)
                if points_to_transfer > 0:
                    self.against_team_points -= points_to_transfer
                    self.bidder_team_points += points_to_transfer

        result_data['partner_revealed'] = partner_revealed
        result_data['revealed_player'] = player.name if partner_revealed else None

        # Move to next player
        self.current_player_index = (self.current_player_index + 1) % len(self.player_order)

        # Check if trick is complete
        if len(self.current_trick) == len(self.player_order):
            winner_id, points = self._resolve_trick()
            result_data['trick_complete'] = True
            result_data['trick_winner'] = self.players[winner_id].name
            result_data['trick_winner_id'] = winner_id
            result_data['points_won'] = points
            result_data['bidder_team_points'] = self.bidder_team_points
            result_data['against_team_points'] = self.against_team_points

            # Check if game is over
            if all(len(p.hand) == 0 for p in self.players.values()):
                self._end_game()
                result_data['game_over'] = True
                result_data['bidder_won'] = self.bidder_team_points >= self.bid_amount
                # Store last trick before clearing
                self.last_trick = list(self.current_trick)
                self.current_trick = []
            else:
                # Store last trick before clearing
                self.last_trick = list(self.current_trick)
                # Start new trick
                self.current_trick = []
                self.led_suit = None
                self.current_player_index = self.player_order.index(winner_id)
                self.trick_number += 1

        return True, "Card played", result_data

    def _resolve_trick(self) -> Tuple[str, int]:
        """Determine winner of current trick and award points"""
        winner_id = None
        winning_card = None
        points = 0

        for player_id, card in self.current_trick:
            points += card.get_points()

            if winning_card is None:
                winner_id = player_id
                winning_card = card
            else:
                # Trump beats non-trump
                if card.suit == self.trump_suit and winning_card.suit != self.trump_suit:
                    winner_id = player_id
                    winning_card = card
                # Same suit, higher rank wins
                elif card.suit == winning_card.suit:
                    if RANK_VALUES[card.rank] > RANK_VALUES[winning_card.rank]:
                        winner_id = player_id
                        winning_card = card

        # Award points
        winner = self.players[winner_id]
        if winner.is_bidder or winner.is_partner or winner_id == self.highest_bidder_id:
            self.bidder_team_points += points
        else:
            self.against_team_points += points

        # Track points earned by specific player for retroactive transfer
        if winner_id not in self.player_points_earned:
            self.player_points_earned[winner_id] = 0
        self.player_points_earned[winner_id] += points

        # Track tricks won
        if winner_id not in self.tricks_won:
            self.tricks_won[winner_id] = 0
        self.tricks_won[winner_id] += 1

        return winner_id, points

    def _end_game(self):
        """End the game and determine winner"""
        self.phase = GamePhase.GAME_OVER

    def reset_game(self):
        """Reset the game state for a new round while keeping players in the room"""
        # Reset to waiting phase
        self.phase = GamePhase.WAITING

        # Reset bidding state
        self.current_bid = 50
        self.current_bidder_index = 0
        self.highest_bidder_id = None
        self.bid_amount = 0
        self.players_passed = 0

        # Reset trump and partners
        self.trump_suit = None
        self.partner_cards = []
        self.partner_cards_revealed = []
        self.partner_ids = []

        # Reset trick/round state
        self.current_trick = []
        self.last_trick = []
        self.led_suit = None
        self.current_player_index = 0
        self.trick_number = 0

        # Reset scoring
        self.bidder_team_points = 0
        self.against_team_points = 0
        self.tricks_won = {}
        self.player_points_earned = {}

        # Reset cards
        self.removed_cards = []
        self.cards_per_player = 0

        # Reset cheating log
        self.cheating_log = []

        # Reset surrender votes
        self.surrender_votes = set()
        self.surrendered = False

        # Reset player states (but keep them in room)
        for player in self.players.values():
            player.hand = []
            player.is_bidder = False
            player.is_partner = False
            player.partner_revealed = False
            player.current_bid = 0
            player.has_passed = False

    def get_state(self, for_player_id: str = None) -> dict:
        """Get current game state"""
        state = {
            "room_code": self.room_code,
            "phase": self.phase.value,
            "num_decks": self.num_decks,
            "max_players": self.max_players,
            "num_partners": self.num_partners,
            "player_count": len(self.players),
            "host_id": self.host_id,
            "players": {},
            "player_order": [self.players[pid].name for pid in self.player_order],
            "cards_per_player": self.cards_per_player,
            "removed_cards": [c.to_dict() for c in self.removed_cards] if self.removed_cards else [],
            "surrender_votes": len(self.surrender_votes),
            "surrender_required": self.get_required_surrender_votes(),
            "has_voted_surrender": for_player_id in self.surrender_votes if for_player_id else False,
            "surrendered": self.surrendered,
        }

        # Add player info
        for pid, player in self.players.items():
            hide_cards = pid != for_player_id
            state["players"][pid] = player.to_dict(hide_cards=hide_cards)

        # Add bidding info
        if self.phase in [GamePhase.BIDDING, GamePhase.PARTNER_SELECTION,
                          GamePhase.PLAYING, GamePhase.GAME_OVER]:
            state["current_bid"] = self.current_bid
            state["max_bid"] = self.get_max_bid()
            state["highest_bidder"] = self.players[self.highest_bidder_id].name if self.highest_bidder_id else None
            state["highest_bidder_id"] = self.highest_bidder_id
            state["bid_amount"] = self.bid_amount

            if self.phase == GamePhase.BIDDING:
                current_bidder_id = self.player_order[self.current_bidder_index]
                state["current_bidder"] = self.players[current_bidder_id].name
                state["current_bidder_id"] = current_bidder_id

        # Add trump and partner info
        if self.phase in [GamePhase.PLAYING, GamePhase.GAME_OVER]:
            state["trump_suit"] = self.trump_suit.value if self.trump_suit else None
            state["trump_symbol"] = SUIT_SYMBOLS[self.trump_suit] if self.trump_suit else None
            state["partner_cards"] = [{"rank": r, "suit": s} for r, s in self.partner_cards]
            state["partners_revealed"] = [
                {"id": pid, "name": self.players[pid].name}
                for pid in self.partner_ids if self.players[pid].partner_revealed
            ]

        # Add current trick info
        if self.phase == GamePhase.PLAYING:
            current_player_id = self.player_order[self.current_player_index]
            state["current_player"] = self.players[current_player_id].name
            state["current_player_id"] = current_player_id
            state["trick_number"] = self.trick_number
            state["led_suit"] = self.led_suit.value if self.led_suit else None
            state["current_trick"] = [
                {"player": self.players[pid].name, "card": card.to_dict()}
                for pid, card in self.current_trick
            ]
            state["last_trick"] = [
                {"player": self.players[pid].name, "card": card.to_dict()}
                for pid, card in self.last_trick
            ]

        # Add scoring
        if self.phase in [GamePhase.PLAYING, GamePhase.GAME_OVER]:
            state["bidder_team_points"] = self.bidder_team_points
            state["against_team_points"] = self.against_team_points
            state["target_points"] = self.bid_amount

        # Add game result
        if self.phase == GamePhase.GAME_OVER:
            bidder_won = self.bidder_team_points >= self.bid_amount
            state["bidder_won"] = bidder_won
            state["final_bidder_points"] = self.bidder_team_points
            state["final_against_points"] = self.against_team_points

            # Reveal all partners
            state["all_partners"] = [
                {"id": pid, "name": self.players[pid].name}
                for pid in self.partner_ids
            ]
            # Include bidder
            if self.highest_bidder_id:
                state["bidder"] = {
                    "id": self.highest_bidder_id,
                    "name": self.players[self.highest_bidder_id].name
                }

            # Include cheating log
            state["cheating_log"] = self.cheating_log
            state["cheaters_found"] = len(self.cheating_log) > 0

        return state

    def get_valid_cards(self, player_id: str) -> List[dict]:
        """Get list of valid cards a player can play.
        Trust-based system: ALL cards are playable.
        Players are expected to follow rules themselves.
        """
        if self.phase != GamePhase.PLAYING:
            return []

        player = self.players.get(player_id)
        if not player:
            return []

        # All cards are playable (trust-based system)
        return [c.to_dict() for c in player.hand]


class GameManager:
    """Manages all game rooms"""

    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}

    def generate_room_code(self) -> str:
        """Generate a unique 6-character room code"""
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.rooms:
                return code

    def create_room(self, host_id: str, host_name: str, num_decks: int = 1,
                    max_players: int = 4, num_partners: int = 2) -> GameRoom:
        """Create a new game room"""
        room_code = self.generate_room_code()
        room = GameRoom(
            room_code=room_code,
            host_id=host_id,
            num_decks=max(1, min(3, num_decks)),  # Clamp to 1-3
            max_players=max(2, min(10, max_players)),  # Clamp to 2-10
            num_partners=max(0, min(2, num_partners))  # Clamp to 0-2
        )
        room.add_player(host_id, host_name)
        self.rooms[room_code] = room
        return room

    def join_room(self, room_code: str, player_id: str, player_name: str) -> Tuple[bool, str, Optional[GameRoom]]:
        """Join an existing room"""
        if room_code not in self.rooms:
            return False, "Room not found", None

        room = self.rooms[room_code]

        if room.phase != GamePhase.WAITING:
            return False, "Game already in progress", None

        if not room.add_player(player_id, player_name):
            return False, "Room is full", None

        return True, "Joined successfully", room

    def get_room(self, room_code: str) -> Optional[GameRoom]:
        """Get a room by code"""
        return self.rooms.get(room_code)

    def start_game(self, room_code: str, player_id: str) -> Tuple[bool, str]:
        """Start the game (host only)"""
        room = self.rooms.get(room_code)
        if not room:
            return False, "Room not found"

        if player_id != room.host_id:
            return False, "Only host can start the game"

        if len(room.players) < 2:
            return False, "Need at least 2 players"

        # Deal cards
        room.deal_cards()

        # Start viewing phase (90 seconds to view cards before bidding)
        room.start_viewing_phase()

        return True, "Game started"

    def delete_room(self, room_code: str):
        """Delete a room"""
        if room_code in self.rooms:
            del self.rooms[room_code]
