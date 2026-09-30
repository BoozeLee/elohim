# From measured fact to deterministic rule

A probability is not testable and not teachable. A counted structure with a
proved bound is both. This is the procedure that turned three facts from
`references/mathematics.md` into game rules, with a worked case below.

1. **Find the mechanism that already makes a number a number.** Not the display,
   not the fiction — the comparison.
2. **Ask whether the mechanism is deterministic.** A `0.7` success chance is
   not. A lattice node being solid is.
3. **Check the bound is tight before relying on it.** A loose bound is a knob
   that will be loosened. A tight one forces the difficulty to move elsewhere.
4. **Compute the precision budget**, and bound the range the rule is evaluated
   over. A rule that needs 109 digits does not belong in a double.
5. **Keep one source of truth for the mechanic** until the replacement has been
   compared against the old one under real play. Two sources for one mechanic is
   the failure mode that costs the most.
6. **Record the portability hazard** if any part of the rule is precision
   sensitive, in the save format rather than in a comment.

## Worked case

The full write-up of the case below, including the mechanics that were
deliberately left alone, is what a step-1-through-6 record looks like. The
setting already had a lattice void and a machine that decides whether you get
out. The shard supplies the actual mathematics for that description, which is
why three of its facts became mechanics rather than decoration.

Target: an existing game project rather than a greenfield one. The web build is
the shipped artefact; a second engine slice is an approved greybox, not a port,
and a reviewer whose job is to stop an unapproved port.

## Pisot bound: a real lattice instead of a coin flip

`navigate_void` in the lattice void was `navigateSuccessChance: 0.7`. A
probability is neither testable nor teachable. Replace it with the theorem.

    a node at lambda^n is solid exactly when
        |lambda^n - round(lambda^n)| <= 2 * |alpha|^n

with `lambda` the tribonacci constant `1.83928675521416118421` and
`|alpha| = sqrt(1/lambda) = 0.7373527057603276`, an identity with zero
discrepancy.

Two properties make this better than a dice roll, and both were measured rather
than assumed:

- **Deterministic.** A node at a given `n` is the same node for every player
  and every run. The lattice becomes a place with a layout, not a sequence of
  coin tosses.
- **Unloosenable.** Pisot's bound `2` is tight, not loose: the maximum of
  `|lambda^n - round(lambda^n)| / |alpha|^n` reaches `1.9999748` at `n = 192`
  for tribonacci and `1.9999996` at `n = 183` for plastic. Raising the constant
  to make a level more forgiving admits real lattice, so the difficulty knob
  has to move somewhere else.

The working precision budget is `n_max * (log10(lambda) - log10(|alpha|)) + 30`
digits, which is `109` digits at `n_max = 200`. The web build runs in doubles,
so the rule must be evaluated for a bounded `n` range rather than at the
lattice's far end.

## Knife edge: the thesis, and a portability hazard

The same base phi, the same code, flips between a finite expansion and an
infinite one purely by decimal working precision: 50 digits gives `11`, 60
gives an infinite tail, 80 gives `11` again, 100 gives infinite.

This is the game's argument rather than a fact about it. The lattice is real;
the machine's rounding decides how it resolves. It justifies seed-bound runs and
an echo that may not resolve to the same void on another machine.

It is also the one place where this mathematics can hurt the product. The echo
carries `{v, ending, mood, lastMemory, seed}` across runs, and a replay
fingerprint computed at a different precision than the one that recorded it will
not match. If the fingerprint leans on a precision-sensitive computation,
document the precision in the save format. Do not let it decide quietly.

## Unicorn curve: bond made visible

`|x|^n + |y|^n = 1` has a perimeter that rises monotonically from `2*pi` at
`n = 2` to just under `8` at `n = 256`. It never dips below the circle.

The Child's bond is currently a number in a HUD with six static mood inks in
`assets/portraits/child-ai.webp`. Drive the glyph's exponent from bond instead:
the Child is a circle at low bond and approaches a square as it trusts you,
then falls back through the ashen cut when the bond is burned to zero. The six
inks become a continuum that costs no new assets, and the shape change is the
bond, so a player reads their own relationship with the Child without reading a
number.

## What was not changed

- `requireAiBond: 70` and `counselRefuseAboveBond: 45` are untouched. Bond is a
  one-way ratchet after the cut, and the stall fix was a floor of `1` in
  `content/v1/balance.json` read by all six sites. Do not paper over a stall by
  moving a threshold.
- The web engine stays the source of truth for balance. `content/v1/balance.json`
  remains the single balance source until an approved Godot Resource mirrors it.
- `navigateSuccessChance` stays in the balance file until the lattice rule is
  implemented and a playtest has compared the two. Two sources for one mechanic
  is the failure mode this project already has a history with.
