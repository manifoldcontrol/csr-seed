"""Gambit engine stub. Symbols carry registry ids for drift detection."""

MELD = "csr.Rules.meld"           # frozen face-up set
CAPTURE = "csr.Rules.capture"     # rulebook sense: trick -> score pile
TURN_ORDER = "csr.Engine.turn_order"


def resolve_trick(cards: list) -> str:
    """Winner takes the trick (csr.Rules.capture)."""
    return "player_1"
