# Engine implementation notes (v1)

## 1. turn_order

Turn order is a rotating ring seeded by the dealer button; the engine
advances it after every resolved trick.

## 2. shuffle

Fisher-Yates over a seeded PRNG so replays are deterministic per match id.

## 3. capture (superseded)

The engine once used "capture" for removing any card from the table,
including discards. That collided with the rulebook's capture; the engine
sense is deprecated and the code now says take_to_pile for the broad sense.
