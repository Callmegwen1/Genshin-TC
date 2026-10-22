# Current gaps and problems

Engine model 5.0, after all five phases of the improvement plan (2026-10-10). Ordered by how much each one
affects the answers you get. Each entry says what is wrong, how we know, and what would fix it.

## 1. Answers you might act on

**The theorycraft calculator is unreliable outside Lunar teams.**
- On 200 sampled one-member swaps, only 37% of predictions land within 10% of gcsim; the target was 90%.
  The median error is 15 to 17%, and a few predictions are off by several times the real damage.
- Its formulas model direct hits, Lunar damage and Swirl only. Vaporize, Melt, Hyperbloom, Aggravate and
  the other reactions are not recalculated when a swap changes buffs.
- Generated kits (108 characters) did not help.
- **Fix:** extend the calculator's damage model to every reaction, then find and fix the outliers.
- **Until then:** trust `gtc theory` only for Lunar teams. The account plan and pull values do not use it.

**Benchmark answers are mostly Claude's reading of community consensus, and some were changed after the first
run.**
- 35 of 46 cases passed first time. Two disputed answers were relaxed because gcsim data disagreed: Hu Tao's
  double Hydro team, and Xiao with Faruzan. Five pull questions were narrowed to support-only pools.
- **Fix:** review knowledge/benchmark.yaml and add your own cases.

**The benchmark cannot tune anything.**
- Every value tried for the ranking risk, the sidegrade factor and the unproven-teammate quality passes all
  46 cases. So do extreme values.
- The cases are orderings that hold across wide ranges, so the parameters are untested judgments.
- **Fix:** add cases that hinge on magnitudes, such as a close call between two pulls, or whether a sidegrade
  is still worth it.

**Small accounts can lose their best team to a second one.**
- With equal weight on the first two teams, an eight-character account may take Aino out of the best Flins
  team to build a weak second team.
- This is deliberate for Spiral Abyss, but it surprises when the question is "my best team".
- The content modes help: Stygian picks one team. But the default plan still trades.

**Labels can mislead even when values are right.**
- Raiden / Kazuha / Xingqiu / Yaoyao is labelled Hyperbloom but plays as a Raiden hypercarry team.
- Chevreuse is named lead of the hand-written Overloaded archetype because it puts her in the first slot.
- **Fix:** label teams by measured damage structure rather than by the archetype whose slots they fill.

## 2. Measurement limits

**Team validity.** 25 of 35 archetypes accept at least 98% of their own simulated teams; all accept at least
90%. The misses are mostly lineups the slot matcher places in archetypes they do not play. A stricter
membership test would lift the number without changing answers.

**Team structure for unsimulated lineups.**
- The top damage dealer is predicted right 86% of the time.
- The team type (hypercarry, dual carry...) is right 75% of the time; the target was 90%.
- The type thresholds sit inside simulation noise.

**Pair model.**
- 6.2% median error one member from a simulated lineup, and 11% two or more away (target under 8 points).
- The taser core (Fischl with Beidou) does not come out as a significant pair.

**AoE.**
- **Assumed layout.** Ratios assume three tightly grouped enemies, so most teams land near 3x and the
  differences are modest.
- **No outside check.** The community has only 3 lineups with comparable multi-target sims, so the ratios
  cannot be checked against outside data.
- **Unmeasured carries.** Tartaglia and Wriothesley have no measurement and use their element's median.

**Artifact quality.**
- Validated on only 8 characters.
- Energy Recharge is capped at the lowest requirement Keqing Mains lists, which is optimistic for harder teams.
- Main stats are judged by the review's guide checks, not by the roll count.

**Energy Recharge reality mode.**
- The burst rewriter changes 5 of 80 community configs by more than 2%, the worst by 10%. Their rotations
  wait longer than 5 seconds for a Burst.
- Tested on a sample of 80, not all 3,800 configs.
- Character ascension is unknown (HoYoLAB does not report it), so characters at a level breakpoint are
  assumed ascended. Weapons now use their real cap.

**Uncertainty.**
- Your own simulations' uncertainty (tier A) counts only iteration noise, not rotation differences, so it
  understates the real spread.
- Hand-written kits only reach tier E, not D, because they place characters by role, not by a damage
  formula.

**Simulation noise (plan item 5) is half done.**
- Values use medians.
- But submitter counts are not stored.
- The popularity-bias check (do popular lineups still look better?) was never run.
- The "never separate options within noise" rule is applied to pull comparisons and the benchmark only, not
  to every recommendation.

**Enablement.** Crediting appliers for the reactions they enable gives sensible values (Xingqiu 42% with
Hu Tao, as much as Furina). But it did not improve swap predictions, so it feeds explanations and teammate
ratings only.

## 3. Coverage

**New characters.**
- Nefer, Sandrone, Vesna, Zibai and Lohen have no simulations and no kit numbers: "cannot evaluate".
- Alyosha, Iansan, Illuga, Kachina, Linnea, Odette and Vodyanitsa are judged from role rules only (tier E).
- A hand-written kit in knowledge/kits_custom/ places them in teams.

**Content modes are simplified.**
- Stygian does not use Prydwen's per-boss ratings.
- Theater ignores its seasonal element rules and the plan's duplicate-role penalty.

**Generated kits.**
- **Kazuha.** His element bonus appears as the element his representative team swirled (Cryo), not
  "whatever he swirls".
- **Conditional buffs.** Buffs gcsim did not trigger in that one rotation are missing.

**Data freshness.** Everything rests on the downloaded gcsim database, Prydwen and Keqing Mains pages.
Re-running `python -m gtc sources` and `python -m gtc derive` refreshes them. The synergy database rebuild
takes about 35 minutes.

## 4. Never built

**Resin efficiency**, the second core feature from the first brainstorm, was never started. Its closest
existing piece is the review's ranked build priorities: talents, levels and artifacts by team-damage gain.

**Performance.** The account report takes 45 to 60 seconds, up from 18 before phase 1, mostly from validity
and two-member swap estimates.
