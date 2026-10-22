# Golden output changes

Every update of tests/golden, newest last.

## 2026-10-11 05:55, model 5.1

Baseline at model 5.1, after the theory guard (phase 0); captured before the phase 2 performance work.

38 changed values in 38 outputs: + account, + roster_alhaitham_nahida, + roster_arlecchino_bennett, + roster_ayaka_freeze_core, + roster_ayaka_kazuha_over_sucrose, + roster_carry_gap_supports_only, + roster_flins_aino_over_xingqiu, + roster_flins_lunar_core, + roster_hutao_double_hydro, + roster_hyperbloom_core, + roster_mavuika_citlali, + roster_mavuika_sidegrade_for_arlecchino, + roster_navia_xilonen, + roster_neuvillette_furina_kazuha, + roster_neuvillette_sidegrade_with_neuvillette_like, + roster_no_clorinde_lunar, + roster_no_freeze_with_pyro, + roster_no_mizuki_hyperbloom_lead, + roster_no_neuvillette_mono_pyro, + roster_no_raiden_damage_anemo_carry, + roster_no_skirk_without_hydro, + roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, + roster_plan_flins_keeps_lunar_core, + roster_plan_raiden_and_nahida, + roster_pull_citlali_for_mavuika, + roster_pull_columbina_for_flins, + roster_pull_enabler_for_skirk, + roster_pull_furina_for_neuvillette, + roster_pull_hydro_for_hutao, + roster_pull_shenhe_for_ayaka.

```
+ account: no stored golden output
+ roster_flins_lunar_core: no stored golden output
+ roster_flins_aino_over_xingqiu: no stored golden output
+ roster_no_clorinde_lunar: no stored golden output
+ roster_alhaitham_nahida: no stored golden output
+ roster_mavuika_sidegrade_for_arlecchino: no stored golden output
+ roster_arlecchino_bennett: no stored golden output
+ roster_pull_columbina_for_flins: no stored golden output
+ roster_razor_chevreuse: no stored golden output
+ roster_navia_xilonen: no stored golden output
+ roster_mavuika_citlali: no stored golden output
+ roster_no_neuvillette_mono_pyro: no stored golden output
+ roster_pull_shenhe_for_ayaka: no stored golden output
+ roster_skirk_hydro_cryo: no stored golden output
+ roster_wanderer_faruzan: no stored golden output
+ roster_xiao_faruzan: no stored golden output
+ roster_neuvillette_sidegrade_with_neuvillette_like: no stored golden output
+ roster_neuvillette_furina_kazuha: no stored golden output
+ roster_carry_gap_supports_only: no stored golden output
+ roster_pull_hydro_for_hutao: no stored golden output
+ roster_hutao_double_hydro: no stored golden output
+ roster_pull_furina_for_neuvillette: no stored golden output
+ roster_hyperbloom_core: no stored golden output
+ roster_ayaka_kazuha_over_sucrose: no stored golden output
+ roster_ayaka_freeze_core: no stored golden output
+ roster_pull_citlali_for_mavuika: no stored golden output
+ roster_pull_trigger_for_hyperbloom: no stored golden output
+ roster_raiden_national: no stored golden output
+ roster_pull_enabler_for_skirk: no stored golden output
+ roster_yoimiya_hydro: no stored golden output
+ roster_no_freeze_with_pyro: no stored golden output
+ roster_plan_raiden_and_nahida: no stored golden output
+ roster_skirk_not_with_geo: no stored golden output
+ roster_no_skirk_without_hydro: no stored golden output
+ roster_no_raiden_damage_anemo_carry: no stored golden output
+ roster_plan_flins_keeps_lunar_core: no stored golden output
+ roster_no_mizuki_hyperbloom_lead: no stored golden output
+ roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka: no stored golden output
```

## 2026-10-11 06:05, model 5.1

Deterministic tie-breaks: rankings of teams, plans, carries and pulls now break exact ties by lineup or name instead of by insertion order, which depended on Python's per-process hash seed (two runs of the same code disagreed on Lyney against Varka at 47.3). The 9 changes are all between options of equal value: a tied best team, a tied plan (which changes one pull's kind from 'no change' to 'upgrade' at zero expected gain), and tied carries.

9 changed values in 3 outputs: account, roster_mavuika_citlali, roster_no_clorinde_lunar.

```
[account] ~ pulls.28.best_team.1: "Fischl" -> "Kaedehara Kazuha"
[account] ~ pulls.28.kind: "no change" -> "upgrade"
[account] ~ pulls.28.sd: 0.0 -> 4.7
[account] ~ pulls.28.tier: "B" -> "C"
[roster_no_clorinde_lunar] ~ carries_for_supports.3.1.2: "Kaedehara Kazuha" -> "Ineffa"
[roster_no_clorinde_lunar] ~ carries_for_supports.3.1.3: "Nicole" -> "Kaedehara Kazuha"
[roster_mavuika_citlali] ~ pulls.1.best_team.1: "Columbina" -> "Citlali"
[roster_mavuika_citlali] ~ pulls.1.best_team.2: "Mavuika" -> "Columbina"
[roster_mavuika_citlali] ~ pulls.1.best_team.3: "Xilonen" -> "Mavuika"
```

## 2026-10-11 13:26, model 5.2

Phase 3, submitter-aware lineup values: each lineup is now the median of per-submitter medians (gcsim_db.lineup_values) instead of the median of all submissions, then derive was re-run (capabilities, roles, validity, pair model, uncertainty). 94 of 3,800 lineup values changed (20 by more than 5%), all lineups where one submitter had re-submitted. Across 38 accounts: 1 plan changed (two pair-model estimates at 50.3 against 50.2 swapped after the refit), 2 top pulls changed, 9 pull kinds changed, pull gains moved by a median of 0.1 (48 of 364 by more than 1 point; the largest, Yelan for a Skirk account 28.0 to 15.1 and Xilonen for a Neuvillette account 46.8 to 39.8, follow the 14% drops of Skirk / Escoffier / Furina / Yelan and Neuvillette / Furina / Kazuha / Xilonen). The user's own plan and top pull are unchanged.

5983 changed values in 38 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_no_skirk_without_hydro, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka.

```
[account] ~ candidates.0.ranking: 73.9 -> 72.4
[account] ~ candidates.0.sd: 5.5 -> 7.7
[account] ~ candidates.1.expected: 69.4 -> 69.7
[account] ~ candidates.1.ranking: 62.9 -> 63.1
[account] ~ candidates.1.sd: 9.7 -> 9.8
[account] ~ candidates.2.sd: 9.6 -> 9.7
[account] ~ candidates.3.ranking: 61.7 -> 60.5
[account] ~ candidates.3.sd: 4.6 -> 6.4
[account] ~ candidates.4.expected: 62.2 -> 64.3
[account] ~ candidates.4.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.4.lineup.1: "Fischl" -> "Flins"
[account] ~ candidates.4.lineup.2: "Flins" -> "Ineffa"
[account] ~ candidates.4.lineup.3: "Sucrose" -> "Xingqiu"
[account] ~ candidates.4.ranking: 59.3 -> 58.2
[account] ~ candidates.4.sd: 4.4 -> 9.0
[account] ~ candidates.4.tier: "B" -> "C"
[account] ~ candidates.5.expected: 64.3 -> 62.2
[account] ~ candidates.5.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.5.lineup.1: "Flins" -> "Fischl"
[account] ~ candidates.5.lineup.2: "Ineffa" -> "Flins"
[account] ~ candidates.5.lineup.3: "Xingqiu" -> "Sucrose"
[account] ~ candidates.5.ranking: 58.3 -> 58.1
[account] ~ candidates.5.sd: 9.0 -> 6.2
[account] ~ candidates.5.tier: "C" -> "B"
[account] ~ candidates.6.expected: 64.0 -> 64.1
[account] ~ candidates.6.sd: 8.9 -> 9.0
[account] ~ candidates.7.expected: 61.9 -> 62.0
[account] ~ candidates.7.lineup.3: "Lan Yan" -> "Lynette"
[account] ~ candidates.7.sd: 8.6 -> 8.7
[account] ~ candidates.8.expected: 62.0 -> 61.9
[account] ~ candidates.8.lineup.3: "Lynette" -> "Lan Yan"
[account] ~ candidates.8.ranking: 56.1 -> 56.0
[account] ~ candidates.8.sd: 8.6 -> 8.7
[account] ~ candidates.9.expected: 60.0 -> 59.9
[account] ~ candidates.9.ranking: 54.3 -> 54.2
[account] ~ candidates.10.expected: 59.6 -> 59.5
[account] ~ candidates.10.ranking: 54.0 -> 53.8
[account] ~ candidates.10.sd: 8.3 -> 8.4
[account] ~ candidates.11.expected: 58.3 -> 58.4
[account] ~ candidates.11.ranking: 52.8 -> 52.9
[account] ~ candidates.11.sd: 8.1 -> 8.2
[account] ~ candidates.12.ranking: 52.3 -> 52.2
[account] ~ candidates.12.sd: 8.0 -> 8.1
[account] ~ candidates.13.sd: 5.1 -> 5.2
[account] ~ candidates.14.sd: 4.9 -> 5.0
[account] ~ candidates.15.expected: 51.9 -> 52.1
[account] ~ candidates.15.sd: 7.2 -> 7.3
[account] ~ candidates.16.expected: 48.8 -> 49.1
[account] ~ candidates.16.sd: 3.0 -> 3.4
[account] ~ candidates.17.expected: 47.7 -> 50.5
[account] ~ candidates.17.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.17.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Lunar-Charged (Flins hypercarry)"
[account] ~ candidates.17.lead: "Xiangling" -> "Flins"
[account] ~ candidates.17.lineup.0: "Bennett" -> "Aino"
[account] ~ candidates.17.lineup.1: "Raiden Shogun" -> "Flins"
[account] ~ candidates.17.lineup.2: "Xiangling" -> "Ineffa"
[account] ~ candidates.17.lineup.3: "Xingqiu" -> "Sayu"
[account] ~ candidates.17.ranking: 46.0 -> 45.7
[account] ~ candidates.17.sd: 2.6 -> 7.1
[account] ~ candidates.17.template: "national" -> "lunar_charged"
[account] ~ candidates.17.tier: "B" -> "C"
[account] ~ candidates.18.expected: 50.4 -> 50.3
[account] ~ candidates.18.label: "Lunar-Charged (Flins hypercarry)" -> "Overloaded (Electro carry) (from gcsim data)"
[account] ~ candidates.18.lead: "Flins" -> "Razor"
[account] ~ candidates.18.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.18.lineup.1: "Flins" -> "Fischl"
[account] ~ candidates.18.lineup.2: "Ineffa" -> "Razor"
[account] ~ candidates.18.lineup.3: "Sayu" -> "Zhongli"
[account] ~ candidates.18.ranking: 45.7 -> 45.5
[account] ~ candidates.18.sd: 7.0 -> 7.1
[account] ~ candidates.18.template: "lunar_charged" -> "auto_overloaded_electro_carry"
[account] ~ candidates.19.expected: 50.4 -> 47.7
[account] ~ candidates.19.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.19.label: "Overloaded (Electro carry) (from gcsim data)" -> "National (Xiangling, Xingqiu, Bennett, driver)"
[account] ~ candidates.19.lead: "Razor" -> "Xiangling"
[account] ~ candidates.19.lineup.0: "Chevreuse" -> "Bennett"
[account] ~ candidates.19.lineup.1: "Fischl" -> "Raiden Shogun"
[account] ~ candidates.19.lineup.2: "Razor" -> "Xiangling"
[account] ~ candidates.19.lineup.3: "Zhongli" -> "Xingqiu"
[account] ~ candidates.19.ranking: 45.7 -> 45.4
[account] ~ candidates.19.sd: 7.0 -> 3.4
[account] ~ candidates.19.template: "auto_overloaded_electro_carry" -> "national"
[account] ~ candidates.19.tier: "C" -> "B"
[account] ~ candidates.20.ranking: 45.2 -> 45.1
[account] ~ candidates.20.sd: 8.6 -> 8.7
[account] ~ candidates.21.sd: 6.9 -> 7.0
[account] ~ candidates.22.expected: 49.3 -> 49.4
[account] ~ candidates.22.sd: 6.9 -> 7.0
[account] ~ candidates.23.expected: 49.2 -> 49.3
[account] ~ candidates.24.expected: 48.9 -> 48.8
[account] ~ candidates.24.ranking: 44.3 -> 44.2
[account] ~ candidates.24.sd: 6.8 -> 6.9
[account] ~ candidates.25.expected: 48.4 -> 48.6
[account] ~ candidates.25.label: "Electro hypercarry" -> "Hyperbloom (Electro carry) (from gcsim data)"
[account] ~ candidates.25.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.25.lineup.1: "Ineffa" -> "Raiden Shogun"
[account] ~ candidates.25.lineup.2: "Kaedehara Kazuha" -> "Xingqiu"
[account] ~ candidates.25.lineup.3: "Raiden Shogun" -> "Yaoyao"
[account] ~ candidates.25.ranking: 43.9 -> 44.0
[account] ~ candidates.25.sd: 6.7 -> 6.8
[account] ~ candidates.25.template: "electro_hypercarry" -> "auto_hyperbloom_electro_carry"
[account] ~ candidates.26.expected: 48.4 -> 48.6
[account] ~ candidates.26.lineup.0: "Fischl" -> "Raiden Shogun"
[account] ~ candidates.26.lineup.1: "Raiden Shogun" -> "Sucrose"
[account] ~ candidates.26.ranking: 43.9 -> 44.0
[account] ~ candidates.27.expected: 48.3 -> 48.5
[account] ~ candidates.27.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Electro hypercarry"
[account] ~ candidates.27.lineup.0: "Raiden Shogun" -> "Bennett"
[account] ~ candidates.27.lineup.1: "Sucrose" -> "Ineffa"
[account] ~ candidates.27.lineup.2: "Xingqiu" -> "Kaedehara Kazuha"
[account] ~ candidates.27.lineup.3: "Yaoyao" -> "Raiden Shogun"
[account] ~ candidates.27.ranking: 43.8 -> 43.9
[account] ~ candidates.27.sd: 6.7 -> 6.8
[account] ~ candidates.27.template: "auto_hyperbloom_electro_carry" -> "electro_hypercarry"
[account] ~ candidates.28.expected: 45.8 -> 47.6
[account] ~ candidates.28.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.28.label: "Aggravate (Quicken)" -> "Melt (Pyro carry) (from gcsim data)"
[account] ~ candidates.28.lead: "Fischl" -> "Yoimiya"
[account] ~ candidates.28.lineup.0: "Fischl" -> "Bennett"
[account] ~ candidates.28.lineup.1: "Kaedehara Kazuha" -> "Citlali"
[account] ~ candidates.28.lineup.2: "Yae Miko" -> "Fischl"
[account] ~ candidates.28.lineup.3: "Yaoyao" -> "Yoimiya"
[account] ~ candidates.28.sd: 3.2 -> 5.8
[account] ~ candidates.28.template: "aggravate" -> "auto_melt_pyro_carry"
[account] ~ candidates.28.tier: "B" -> "C"
[account] ~ candidates.29.expected: 48.1 -> 48.0
[account] ~ candidates.29.ranking: 43.6 -> 43.5
[account] ~ candidates.29.sd: 6.7 -> 6.8
[account] ~ candidates.30.expected: 47.3 -> 47.9
[account] ~ candidates.30.label: "Melt (Pyro carry) (from gcsim data)" -> "Hyperbloom (Electro carry) (from gcsim data)"
[account] ~ candidates.30.lead: "Yoimiya" -> "Raiden Shogun"
[account] ~ candidates.30.lineup.0: "Bennett" -> "Kaedehara Kazuha"
[account] ~ candidates.30.lineup.1: "Citlali" -> "Raiden Shogun"
[account] ~ candidates.30.lineup.2: "Fischl" -> "Xingqiu"
[account] ~ candidates.30.lineup.3: "Yoimiya" -> "Yaoyao"
[account] ~ candidates.30.sd: 5.8 -> 6.7
[account] ~ candidates.30.template: "auto_melt_pyro_carry" -> "auto_hyperbloom_electro_carry"
[account] ~ candidates.31.expected: 47.8 -> 47.9
[account] ~ candidates.31.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.31.lead: "Raiden Shogun" -> "Flins"
[account] ~ candidates.31.lineup.0: "Kaedehara Kazuha" -> "Aino"
[account] ~ candidates.31.lineup.1: "Raiden Shogun" -> "Flins"
[account] ~ candidates.31.lineup.2: "Xingqiu" -> "Sucrose"
[account] ~ candidates.31.lineup.3: "Yaoyao" -> "Xingqiu"
[account] ~ candidates.31.template: "auto_hyperbloom_electro_carry" -> "lunar_charged_offfield"
[account] ~ candidates.32.expected: 47.7 -> 44.9
[account] ~ candidates.32.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.32.label: "Lunar-Charged off-field (taser style)" -> "Aggravate (Quicken)"
[account] ~ candidates.32.lead: "Flins" -> "Fischl"
[account] ~ candidates.32.lineup.0: "Aino" -> "Fischl"
[account] ~ candidates.32.lineup.1: "Flins" -> "Kaedehara Kazuha"
[account] ~ candidates.32.lineup.2: "Sucrose" -> "Yae Miko"
[account] ~ candidates.32.lineup.3: "Xingqiu" -> "Yaoyao"
[account] ~ candidates.32.ranking: 43.2 -> 42.8
[account] ~ candidates.32.sd: 6.7 -> 3.2
[account] ~ candidates.32.template: "lunar_charged_offfield" -> "aggravate"
[account] ~ candidates.32.tier: "C" -> "B"
[account] ~ candidates.33.expected: 47.0 -> 47.1
[account] ~ candidates.33.sd: 6.5 -> 6.6
[account] ~ candidates.34.ranking: 42.6 -> 42.5
[account] ~ candidates.34.sd: 6.5 -> 6.6
[account] ~ candidates.36.expected: 45.8 -> 46.4
[account] ~ candidates.36.label: "Superconduct (Electro carry) (from gcsim data)" -> "Melt (Pyro carry) (from gcsim data)"
[account] ~ candidates.36.lead: "Razor" -> "Yoimiya"
[account] ~ candidates.36.lineup.2: "Razor" -> "Sucrose"
[account] ~ candidates.36.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.36.ranking: 41.5 -> 41.6
[account] ~ candidates.36.sd: 6.4 -> 7.2
[account] ~ candidates.36.template: "auto_superconduct_electro_carry" -> "auto_melt_pyro_carry"
[account] ~ candidates.36.tier: "C" -> "D"
[account] ~ candidates.37.expected: 46.3 -> 45.8
[account] ~ candidates.37.label: "Melt (Pyro carry) (from gcsim data)" -> "Superconduct (Electro carry) (from gcsim data)"
[account] ~ candidates.37.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.37.lineup.2: "Sucrose" -> "Razor"
[account] ~ candidates.37.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.37.sd: 7.2 -> 6.4
[account] ~ candidates.37.template: "auto_melt_pyro_carry" -> "auto_superconduct_electro_carry"
[account] ~ candidates.37.tier: "D" -> "C"
[account] ~ candidates.38.expected: 43.5 -> 46.4
[account] ~ candidates.38.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.38.label: "Freeze" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.38.lead: "Kamisato Ayaka" -> "Ineffa"
[account] ~ candidates.38.lineup.0: "Kaedehara Kazuha" -> "Aino"
[account] ~ candidates.38.lineup.1: "Kamisato Ayaka" -> "Fischl"
[account] ~ candidates.38.lineup.2: "Mona" -> "Ineffa"
[account] ~ candidates.38.lineup.3: "Shenhe" -> "Kaedehara Kazuha"
[account] ~ candidates.38.ranking: 41.5 -> 41.0
[account] ~ candidates.38.sd: 3.0 -> 7.9
[account] ~ candidates.38.template: "freeze" -> "lunar_charged_offfield"
[account] ~ candidates.38.tier: "B" -> "D"
[account] ~ candidates.39.expected: 46.4 -> 45.0
[account] ~ candidates.39.label: "Lunar-Charged off-field (taser style)" -> "Mono Electro (from gcsim data)"
[account] ~ candidates.39.lead: "Ineffa" -> "Yae Miko"
[account] ~ candidates.39.lineup.0: "Aino" -> "Fischl"
[account] ~ candidates.39.lineup.1: "Fischl" -> "Ineffa"
[account] ~ candidates.39.lineup.2: "Ineffa" -> "Kaedehara Kazuha"
[account] ~ candidates.39.lineup.3: "Kaedehara Kazuha" -> "Yae Miko"
[account] ~ candidates.39.ranking: 41.1 -> 40.7
[account] ~ candidates.39.sd: 7.8 -> 6.3
[account] ~ candidates.39.template: "lunar_charged_offfield" -> "auto_mono_electro"
...
```

## 2026-10-16 02:18, model 5.3

Phase 5 (model 5.3): TeamEvaluation pipeline; power from the lineup, not the generating template. (1) A simulated lineup is valued by its own community simulations whatever template produced it (previously 81 of 141 simulated lineups in these accounts were valued another way, e.g. measured teams the template rated 0). (2) Unsimulated lineups: pair model over the normaliser, refit without its archetype term (CV 6.42% -> 6.48% near, removes template dependence), lead from the structure; sd from the pair model's held-out error alone, no longer compounded with the archetype best lineup's noise. (3) Execution difficulty from the structure's damage owner. (4) Pair model not used for two carries never simulated together (Mualani + Neuvillette). (5) Templates generating the same four now tie; the label comes from the template whose own estimate fits best. (6) Golden records each team's route. Known regressions, explained: Hu Tao / Xingqiu / Yelan / Zhongli now uses its own data, 41k median (two of three submitters run Hu Tao on Deathmatch), which flips vape vs mono and lowers Yelan for Hu Tao.

12325 changed values in 38 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_no_skirk_without_hydro, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka.

```
[account] ~ candidates.0.expected: 77.6 -> 78.0
[account] ~ candidates.0.ranking: 72.4 -> 72.8
[account] + candidates.0.route: "exact_community"
[account] ~ candidates.1.expected: 69.7 -> 70.1
[account] ~ candidates.1.ranking: 63.1 -> 65.4
[account] + candidates.1.route: "pair_model"
[account] ~ candidates.1.sd: 9.8 -> 7.1
[account] ~ candidates.2.expected: 69.2 -> 68.4
[account] ~ candidates.2.ranking: 62.7 -> 63.7
[account] + candidates.2.route: "pair_model"
[account] ~ candidates.2.sd: 9.7 -> 6.9
[account] ~ candidates.3.expected: 64.8 -> 65.1
[account] ~ candidates.3.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.3.label: "Overloaded (Electro carry) (from gcsim data)" -> "Lunar-Charged (Flins hypercarry)"
[account] ~ candidates.3.lead: "Razor" -> "Flins"
[account] ~ candidates.3.lineup.0: "Bennett" -> "Aino"
[account] ~ candidates.3.lineup.1: "Chevreuse" -> "Flins"
[account] ~ candidates.3.lineup.2: "Fischl" -> "Ineffa"
[account] ~ candidates.3.lineup.3: "Razor" -> "Xingqiu"
[account] ~ candidates.3.ranking: 60.5 -> 60.7
[account] + candidates.3.route: "pair_model"
[account] ~ candidates.3.sd: 6.4 -> 6.6
[account] ~ candidates.3.template: "auto_overloaded_electro_carry" -> "lunar_charged"
[account] ~ candidates.3.tier: "B" -> "C"
[account] ~ candidates.4.expected: 64.3 -> 64.8
[account] ~ candidates.4.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.4.label: "Lunar-Charged (Flins hypercarry)" -> "Overloaded (Electro carry) (from gcsim data)"
[account] ~ candidates.4.lead: "Flins" -> "Razor"
[account] ~ candidates.4.lineup.0: "Aino" -> "Bennett"
[account] ~ candidates.4.lineup.1: "Flins" -> "Chevreuse"
[account] ~ candidates.4.lineup.2: "Ineffa" -> "Fischl"
[account] ~ candidates.4.lineup.3: "Xingqiu" -> "Razor"
[account] ~ candidates.4.ranking: 58.2 -> 60.5
[account] + candidates.4.route: "exact_community"
[account] ~ candidates.4.sd: 9.0 -> 6.4
[account] ~ candidates.4.template: "lunar_charged" -> "auto_overloaded_electro_carry"
[account] ~ candidates.4.tier: "C" -> "B"
[account] ~ candidates.5.expected: 62.2 -> 64.1
[account] ~ candidates.5.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.5.lineup.1: "Fischl" -> "Flins"
[account] ~ candidates.5.lineup.2: "Flins" -> "Ineffa"
[account] ~ candidates.5.lineup.3: "Sucrose" -> "Kaedehara Kazuha"
[account] ~ candidates.5.ranking: 58.1 -> 59.7
[account] + candidates.5.route: "pair_model"
[account] ~ candidates.5.sd: 6.2 -> 6.4
[account] ~ candidates.5.tier: "B" -> "C"
[account] ~ candidates.6.expected: 64.1 -> 62.5
[account] ~ candidates.6.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.6.lineup.1: "Flins" -> "Fischl"
[account] ~ candidates.6.lineup.2: "Ineffa" -> "Flins"
[account] ~ candidates.6.lineup.3: "Kaedehara Kazuha" -> "Sucrose"
[account] ~ candidates.6.ranking: 58.0 -> 58.3
[account] + candidates.6.route: "exact_community"
[account] ~ candidates.6.sd: 9.0 -> 6.2
[account] ~ candidates.6.tier: "C" -> "B"
[account] ~ candidates.7.expected: 62.0 -> 61.5
[account] ~ candidates.7.lineup.3: "Lynette" -> "Lan Yan"
[account] ~ candidates.7.ranking: 56.1 -> 57.3
[account] + candidates.7.route: "pair_model"
[account] ~ candidates.7.sd: 8.7 -> 6.2
[account] ~ candidates.8.expected: 61.9 -> 61.5
[account] ~ candidates.8.lineup.3: "Lan Yan" -> "Lynette"
[account] ~ candidates.8.ranking: 56.0 -> 57.3
[account] + candidates.8.route: "pair_model"
[account] ~ candidates.8.sd: 8.7 -> 6.2
[account] ~ candidates.9.expected: 59.9 -> 60.5
[account] ~ candidates.9.label: "Lunar-Charged (Flins hypercarry)" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.9.lead: "Flins" -> "Ineffa"
[account] ~ candidates.9.lineup.1: "Flins" -> "Ineffa"
[account] ~ candidates.9.lineup.2: "Ineffa" -> "Sucrose"
[account] ~ candidates.9.lineup.3: "Zhongli" -> "Yae Miko"
[account] ~ candidates.9.ranking: 54.2 -> 56.4
[account] + candidates.9.route: "pair_model"
[account] ~ candidates.9.sd: 8.4 -> 6.1
[account] ~ candidates.9.template: "lunar_charged" -> "lunar_charged_offfield"
[account] ~ candidates.10.expected: 59.5 -> 61.8
[account] ~ candidates.10.fit_source: "pairmodel" -> "model"
[account] ~ candidates.10.label: "Lunar-Charged (Flins hypercarry)" -> "Hyperbloom"
[account] ~ candidates.10.lead: "Ineffa" -> "Yaoyao"
[account] ~ candidates.10.lineup.0: "Aino" -> "Ineffa"
[account] ~ candidates.10.lineup.1: "Fischl" -> "Sucrose"
[account] ~ candidates.10.lineup.2: "Ineffa" -> "Xingqiu"
[account] ~ candidates.10.lineup.3: "Sucrose" -> "Yaoyao"
[account] ~ candidates.10.ranking: 53.8 -> 56.4
[account] + candidates.10.route: "pair_model"
[account] ~ candidates.10.sd: 8.4 -> 7.9
[account] ~ candidates.10.template: "lunar_charged" -> "hyperbloom"
[account] ~ candidates.10.tier: "C" -> "D"
[account] ~ candidates.11.expected: 58.4 -> 59.8
[account] ~ candidates.11.ranking: 52.9 -> 55.7
[account] + candidates.11.route: "pair_model"
[account] ~ candidates.11.sd: 8.2 -> 6.0
[account] ~ candidates.12.expected: 57.7 -> 59.4
[account] ~ candidates.12.label: "Lunar-Charged off-field (taser style)" -> "Lunar-Charged (Flins hypercarry)"
[account] ~ candidates.12.lead: "Ineffa" -> "Flins"
[account] ~ candidates.12.lineup.1: "Ineffa" -> "Flins"
[account] ~ candidates.12.lineup.2: "Sucrose" -> "Ineffa"
[account] ~ candidates.12.lineup.3: "Yae Miko" -> "Zhongli"
[account] ~ candidates.12.ranking: 52.2 -> 55.4
[account] + candidates.12.route: "pair_model"
[account] ~ candidates.12.sd: 8.1 -> 6.0
[account] ~ candidates.12.template: "lunar_charged_offfield" -> "lunar_charged"
[account] ~ candidates.13.expected: 51.9 -> 58.5
[account] ~ candidates.13.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.13.label: "Overloaded (Electro carry) (from gcsim data)" -> "Lunar-Charged (Flins hypercarry)"
[account] ~ candidates.13.lead: "Razor" -> "Ineffa"
[account] ~ candidates.13.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.13.lineup.2: "Razor" -> "Ineffa"
[account] ~ candidates.13.lineup.3: "Xiangling" -> "Sucrose"
[account] ~ candidates.13.ranking: 48.5 -> 54.5
[account] + candidates.13.route: "pair_model"
[account] ~ candidates.13.sd: 5.2 -> 5.9
[account] ~ candidates.13.template: "auto_overloaded_electro_carry" -> "lunar_charged"
[account] ~ candidates.13.tier: "B" -> "C"
[account] ~ candidates.14.expected: 50.5 -> 56.3
[account] ~ candidates.14.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.14.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Chevreuse Overloaded"
[account] ~ candidates.14.lead: "Razor" -> "Chevreuse"
[account] ~ candidates.14.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.14.lineup.2: "Razor" -> "Ineffa"
[account] ~ candidates.14.lineup.3: "Xingqiu" -> "Xiangling"
[account] ~ candidates.14.ranking: 47.2 -> 52.5
[account] + candidates.14.route: "pair_model"
[account] ~ candidates.14.sd: 5.0 -> 5.7
[account] ~ candidates.14.template: "auto_electro_charged_electro_carry" -> "overloaded"
[account] ~ candidates.14.tier: "B" -> "C"
[account] ~ candidates.15.expected: 52.1 -> 56.1
[account] ~ candidates.15.ranking: 47.1 -> 52.3
[account] + candidates.15.route: "pair_model"
[account] ~ candidates.15.sd: 7.3 -> 5.6
[account] ~ candidates.16.expected: 49.1 -> 53.7
[account] ~ candidates.16.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.16.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Mono Electro (from gcsim data)"
[account] ~ candidates.16.lead: "Yoimiya" -> "Yae Miko"
[account] ~ candidates.16.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.16.lineup.1: "Chevreuse" -> "Ineffa"
[account] ~ candidates.16.lineup.2: "Fischl" -> "Kaedehara Kazuha"
[account] ~ candidates.16.lineup.3: "Yoimiya" -> "Yae Miko"
[account] ~ candidates.16.ranking: 46.8 -> 50.1
[account] + candidates.16.route: "pair_model"
[account] ~ candidates.16.sd: 3.4 -> 5.4
[account] ~ candidates.16.template: "auto_overloaded_pyro_carry" -> "auto_mono_electro"
[account] ~ candidates.16.tier: "B" -> "C"
[account] ~ candidates.17.expected: 50.5 -> 52.9
[account] ~ candidates.17.label: "Lunar-Charged (Flins hypercarry)" -> "Chevreuse Overloaded"
[account] ~ candidates.17.lead: "Flins" -> "Chevreuse"
[account] ~ candidates.17.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.17.lineup.1: "Flins" -> "Ineffa"
[account] ~ candidates.17.lineup.2: "Ineffa" -> "Raiden Shogun"
[account] ~ candidates.17.lineup.3: "Sayu" -> "Xiangling"
[account] ~ candidates.17.ranking: 45.7 -> 49.4
[account] + candidates.17.route: "pair_model"
[account] ~ candidates.17.sd: 7.1 -> 5.3
[account] ~ candidates.17.template: "lunar_charged" -> "overloaded"
[account] ~ candidates.18.expected: 50.3 -> 52.7
[account] ~ candidates.18.label: "Overloaded (Electro carry) (from gcsim data)" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.18.lead: "Razor" -> "Flins"
[account] ~ candidates.18.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.18.lineup.1: "Fischl" -> "Flins"
[account] ~ candidates.18.lineup.2: "Razor" -> "Sucrose"
[account] ~ candidates.18.lineup.3: "Zhongli" -> "Xingqiu"
[account] ~ candidates.18.ranking: 45.5 -> 49.1
[account] + candidates.18.route: "pair_model"
[account] ~ candidates.18.sd: 7.1 -> 5.3
[account] ~ candidates.18.template: "auto_overloaded_electro_carry" -> "lunar_charged_offfield"
[account] ~ candidates.19.expected: 47.7 -> 53.6
[account] ~ candidates.19.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.19.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Electro-Charged (Electro carry) (from gcsim data)"
[account] ~ candidates.19.lead: "Xiangling" -> "Razor"
[account] ~ candidates.19.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.19.lineup.1: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.19.lineup.2: "Xiangling" -> "Razor"
[account] ~ candidates.19.ranking: 45.4 -> 49.0
[account] + candidates.19.route: "pair_model"
[account] ~ candidates.19.sd: 3.4 -> 6.9
[account] ~ candidates.19.template: "national" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.19.tier: "B" -> "D"
[account] ~ candidates.20.expected: 51.0 -> 51.1
[account] ~ candidates.20.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Chevreuse Overloaded"
[account] ~ candidates.20.lead: "Razor" -> "Chevreuse"
[account] ~ candidates.20.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.20.lineup.2: "Razor" -> "Xiangling"
[account] ~ candidates.20.lineup.3: "Xingqiu" -> "Yae Miko"
[account] ~ candidates.20.ranking: 45.1 -> 48.7
[account] + candidates.20.route: "exact_community"
[account] ~ candidates.20.sd: 8.7 -> 3.6
[account] ~ candidates.20.template: "auto_electro_charged_electro_carry" -> "overloaded"
[account] ~ candidates.20.tier: "D" -> "B"
[account] ~ candidates.21.expected: 49.6 -> 51.9
[account] ~ candidates.21.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.21.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Overloaded (Electro carry) (from gcsim data)"
[account] ~ candidates.21.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.21.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.21.lineup.3: "Xingqiu" -> "Xiangling"
[account] ~ candidates.21.ranking: 44.9 -> 48.5
[account] + candidates.21.route: "exact_community"
[account] ~ candidates.21.sd: 7.0 -> 5.2
[account] ~ candidates.21.template: "auto_electro_charged_electro_carry" -> "auto_overloaded_electro_carry"
[account] ~ candidates.21.tier: "C" -> "B"
[account] ~ candidates.22.expected: 49.4 -> 51.8
...
```

## 2026-10-16 02:58, model 5.3.1

Model 5.3.1 correctness cleanup. No expected power changed (0 of 1,089 matched teams). Intended: exact community values now carry between-build disagreement in their sd (estimate.exact_rel_sd; 545 of 3,800 lineups mix builds); 22 candidate teams in these accounts get a wider sd (e.g. Hu Tao / Xingqiu / Yelan / Zhongli 2.1 -> 8.5: Deathmatch ~41k vs Ballad ~69k; Xiao / Faruzan / Furina / Xianyun 3.1 -> 10.1), and 44 pull sds change. Through the decision score (expected - 0.674 sd) this moves one top pull (plan_raiden_and_nahida: Furina -> Columbina, a close call) and 4 pull kinds. No plan changed. Display-only changes (expected values in text, coverage guard, swap advice, (A) labels) are not in the golden outputs.

1270 changed values in 18 outputs: account, roster_alhaitham_nahida, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_hyperbloom_core, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_mizuki_hyperbloom_lead, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom, roster_raiden_national, roster_skirk_not_with_geo, roster_xiao_faruzan.

```
[account] ~ candidates.34.expected: 47.7 -> 48.5
[account] ~ candidates.34.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.34.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Hyperbloom (Electro carry) (from gcsim data)"
[account] ~ candidates.34.lead: "Xiangling" -> "Raiden Shogun"
[account] ~ candidates.34.lineup.0: "Bennett" -> "Raiden Shogun"
[account] ~ candidates.34.lineup.1: "Raiden Shogun" -> "Sucrose"
[account] ~ candidates.34.lineup.2: "Xiangling" -> "Xingqiu"
[account] ~ candidates.34.lineup.3: "Xingqiu" -> "Yaoyao"
[account] ~ candidates.34.ranking: 45.4 -> 45.2
[account] ~ candidates.34.route: "exact_community" -> "pair_model"
[account] ~ candidates.34.sd: 3.4 -> 4.9
[account] ~ candidates.34.template: "national" -> "auto_hyperbloom_electro_carry"
[account] ~ candidates.34.tier: "B" -> "C"
[account] ~ candidates.35.expected: 48.5 -> 47.9
[account] ~ candidates.35.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.35.lead: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.35.lineup.0: "Raiden Shogun" -> "Aino"
[account] ~ candidates.35.lineup.1: "Sucrose" -> "Ineffa"
[account] ~ candidates.35.lineup.2: "Xingqiu" -> "Kaedehara Kazuha"
[account] ~ candidates.35.lineup.3: "Yaoyao" -> "Xingqiu"
[account] ~ candidates.35.ranking: 45.2 -> 44.7
[account] ~ candidates.35.sd: 4.9 -> 4.8
[account] ~ candidates.35.template: "auto_hyperbloom_electro_carry" -> "lunar_charged_offfield"
[account] ~ candidates.36.expected: 47.9 -> 48.0
[account] ~ candidates.36.label: "Lunar-Charged off-field (taser style)" -> "Electro hypercarry"
[account] ~ candidates.36.lead: "Ineffa" -> "Raiden Shogun"
[account] ~ candidates.36.lineup.0: "Aino" -> "Bennett"
[account] ~ candidates.36.lineup.2: "Kaedehara Kazuha" -> "Raiden Shogun"
[account] ~ candidates.36.lineup.3: "Xingqiu" -> "Sucrose"
[account] ~ candidates.36.template: "lunar_charged_offfield" -> "electro_hypercarry"
[account] ~ candidates.37.expected: 48.0 -> 47.7
[account] ~ candidates.37.label: "Electro hypercarry" -> "Electro-Charged (Electro carry) (from gcsim data)"
[account] ~ candidates.37.lead: "Raiden Shogun" -> "Razor"
[account] ~ candidates.37.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.37.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.37.lineup.2: "Raiden Shogun" -> "Razor"
[account] ~ candidates.37.lineup.3: "Sucrose" -> "Xingqiu"
[account] ~ candidates.37.ranking: 44.7 -> 44.5
[account] ~ candidates.37.template: "electro_hypercarry" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.38.expected: 47.7 -> 47.4
[account] ~ candidates.38.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Hyperbloom (Electro carry) (from gcsim data)"
[account] ~ candidates.38.lead: "Razor" -> "Raiden Shogun"
[account] ~ candidates.38.lineup.0: "Chevreuse" -> "Fischl"
[account] ~ candidates.38.lineup.1: "Fischl" -> "Raiden Shogun"
[account] ~ candidates.38.lineup.2: "Razor" -> "Xingqiu"
[account] ~ candidates.38.lineup.3: "Xingqiu" -> "Yaoyao"
[account] ~ candidates.38.ranking: 44.5 -> 44.1
[account] ~ candidates.38.template: "auto_electro_charged_electro_carry" -> "auto_hyperbloom_electro_carry"
[account] ~ candidates.39.expected: 47.4 -> 47.3
[account] ~ candidates.39.lineup.0: "Fischl" -> "Kaedehara Kazuha"
[account] ~ candidates.40.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Electro hypercarry"
[account] ~ candidates.40.lineup.0: "Kaedehara Kazuha" -> "Bennett"
[account] ~ candidates.40.lineup.1: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.40.lineup.2: "Xingqiu" -> "Kaedehara Kazuha"
[account] ~ candidates.40.lineup.3: "Yaoyao" -> "Raiden Shogun"
[account] ~ candidates.40.ranking: 44.1 -> 44.0
[account] ~ candidates.40.template: "auto_hyperbloom_electro_carry" -> "electro_hypercarry"
[account] ~ candidates.41.expected: 47.3 -> 47.2
[account] ~ candidates.41.label: "Electro hypercarry" -> "Superconduct (Electro carry) (from gcsim data)"
[account] ~ candidates.41.lead: "Raiden Shogun" -> "Razor"
[account] ~ candidates.41.lineup.0: "Bennett" -> "Citlali"
[account] ~ candidates.41.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.41.lineup.2: "Kaedehara Kazuha" -> "Razor"
[account] ~ candidates.41.lineup.3: "Raiden Shogun" -> "Zhongli"
[account] ~ candidates.41.template: "electro_hypercarry" -> "auto_superconduct_electro_carry"
[account] ~ candidates.42.expected: 47.2 -> 46.0
[account] ~ candidates.42.label: "Superconduct (Electro carry) (from gcsim data)" -> "Chevreuse Overloaded"
[account] ~ candidates.42.lead: "Razor" -> "Chevreuse"
[account] ~ candidates.42.lineup.0: "Citlali" -> "Bennett"
[account] ~ candidates.42.lineup.1: "Fischl" -> "Chevreuse"
[account] ~ candidates.42.lineup.2: "Razor" -> "Raiden Shogun"
[account] ~ candidates.42.lineup.3: "Zhongli" -> "Xiangling"
[account] ~ candidates.42.ranking: 44.0 -> 43.9
[account] ~ candidates.42.route: "pair_model" -> "exact_community"
[account] ~ candidates.42.sd: 4.8 -> 3.2
[account] ~ candidates.42.template: "auto_superconduct_electro_carry" -> "overloaded"
[account] ~ candidates.42.tier: "C" -> "B"
[account] ~ candidates.43.expected: 46.0 -> 46.9
[account] ~ candidates.43.label: "Chevreuse Overloaded" -> "Melt (Pyro carry) (from gcsim data)"
[account] ~ candidates.43.lead: "Chevreuse" -> "Yoimiya"
[account] ~ candidates.43.lineup.1: "Chevreuse" -> "Citlali"
[account] ~ candidates.43.lineup.2: "Raiden Shogun" -> "Fischl"
[account] ~ candidates.43.lineup.3: "Xiangling" -> "Yoimiya"
[account] ~ candidates.43.ranking: 43.9 -> 43.8
[account] ~ candidates.43.route: "exact_community" -> "pair_model"
[account] ~ candidates.43.sd: 3.2 -> 4.7
[account] ~ candidates.43.template: "overloaded" -> "auto_melt_pyro_carry"
[account] ~ candidates.43.tier: "B" -> "C"
[account] ~ candidates.44.expected: 46.9 -> 47.7
[account] ~ candidates.44.label: "Melt (Pyro carry) (from gcsim data)" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.44.lead: "Yoimiya" -> "Flins"
[account] ~ candidates.44.lineup.0: "Bennett" -> "Aino"
[account] ~ candidates.44.lineup.1: "Citlali" -> "Flins"
[account] ~ candidates.44.lineup.2: "Fischl" -> "Lan Yan"
[account] ~ candidates.44.lineup.3: "Yoimiya" -> "Xingqiu"
[account] ~ candidates.44.ranking: 43.8 -> 43.6
[account] ~ candidates.44.sd: 4.7 -> 6.1
[account] ~ candidates.44.template: "auto_melt_pyro_carry" -> "lunar_charged_offfield"
[account] ~ candidates.44.tier: "C" -> "D"
[account] ~ candidates.45.fit_source: "pairmodel" -> "model"
[account] ~ candidates.45.label: "Lunar-Charged off-field (taser style)" -> "Hyperbloom"
[account] ~ candidates.45.lead: "Flins" -> "Yaoyao"
[account] ~ candidates.45.lineup.0: "Aino" -> "Sucrose"
[account] ~ candidates.45.lineup.1: "Flins" -> "Xingqiu"
[account] ~ candidates.45.lineup.2: "Lan Yan" -> "Yae Miko"
[account] ~ candidates.45.lineup.3: "Xingqiu" -> "Yaoyao"
[account] ~ candidates.45.template: "lunar_charged_offfield" -> "hyperbloom"
[account] ~ candidates.46.expected: 47.7 -> 46.4
[account] ~ candidates.46.fit_source: "model" -> "pairmodel"
[account] ~ candidates.46.label: "Hyperbloom" -> "Overloaded (Electro carry) (from gcsim data)"
[account] ~ candidates.46.lead: "Yaoyao" -> "Razor"
[account] ~ candidates.46.lineup.0: "Sucrose" -> "Chevreuse"
[account] ~ candidates.46.lineup.1: "Xingqiu" -> "Fischl"
[account] ~ candidates.46.lineup.2: "Yae Miko" -> "Kaedehara Kazuha"
[account] ~ candidates.46.lineup.3: "Yaoyao" -> "Razor"
[account] ~ candidates.46.ranking: 43.6 -> 43.3
[account] ~ candidates.46.sd: 6.1 -> 4.7
[account] ~ candidates.46.template: "hyperbloom" -> "auto_overloaded_electro_carry"
[account] ~ candidates.46.tier: "D" -> "C"
[account] ~ candidates.47.expected: 46.4 -> 45.5
[account] ~ candidates.47.label: "Overloaded (Electro carry) (from gcsim data)" -> "Chevreuse Overloaded"
[account] ~ candidates.47.lead: "Razor" -> "Chevreuse"
[account] ~ candidates.47.lineup.1: "Fischl" -> "Raiden Shogun"
[account] ~ candidates.47.lineup.2: "Kaedehara Kazuha" -> "Xiangling"
[account] ~ candidates.47.lineup.3: "Razor" -> "Yae Miko"
[account] ~ candidates.47.route: "pair_model" -> "exact_community"
[account] ~ candidates.47.sd: 4.7 -> 3.2
[account] ~ candidates.47.template: "auto_overloaded_electro_carry" -> "overloaded"
[account] ~ candidates.47.tier: "C" -> "B"
[account] ~ candidates.48.expected: 45.5 -> 47.7
[account] ~ candidates.48.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.48.label: "Chevreuse Overloaded" -> "National (Xiangling, Xingqiu, Bennett, driver)"
[account] ~ candidates.48.lead: "Chevreuse" -> "Xiangling"
[account] ~ candidates.48.lineup.0: "Chevreuse" -> "Bennett"
[account] ~ candidates.48.lineup.3: "Yae Miko" -> "Xingqiu"
[account] ~ candidates.48.ranking: 43.3 -> 43.1
[account] ~ candidates.48.sd: 3.2 -> 6.9
[account] ~ candidates.48.template: "overloaded" -> "national"
[account] ~ candidates.58.ranking: 40.6 -> 40.1
[account] ~ candidates.58.sd: 4.3 -> 5.0
[account] ~ candidates.98.expected: 38.3 -> 39.2
[account] ~ candidates.98.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.98.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Freeze"
[account] ~ candidates.98.lead: "Xiangling" -> "Kamisato Ayaka"
[account] ~ candidates.98.lineup.0: "Bennett" -> "Candace"
[account] ~ candidates.98.lineup.1: "Sucrose" -> "Kamisato Ayaka"
[account] ~ candidates.98.lineup.2: "Xiangling" -> "Mona"
[account] ~ candidates.98.lineup.3: "Xingqiu" -> "Shenhe"
[account] ~ candidates.98.route: "exact_community" -> "pair_model"
[account] ~ candidates.98.sd: 2.7 -> 3.9
[account] ~ candidates.98.template: "national" -> "freeze"
[account] ~ candidates.98.tier: "B" -> "C"
[account] ~ candidates.99.label: "Freeze" -> "Aggravate (Quicken)"
[account] ~ candidates.99.lead: "Kamisato Ayaka" -> "Razor"
[account] ~ candidates.99.lineup.0: "Candace" -> "Fischl"
[account] ~ candidates.99.lineup.1: "Kamisato Ayaka" -> "Kaedehara Kazuha"
[account] ~ candidates.99.lineup.2: "Mona" -> "Razor"
[account] ~ candidates.99.lineup.3: "Shenhe" -> "Yaoyao"
[account] ~ candidates.99.template: "freeze" -> "aggravate"
[account] ~ candidates.100.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.100.label: "Aggravate (Quicken)" -> "Mono Cryo (from gcsim data)"
[account] ~ candidates.100.lead: "Razor" -> "Kamisato Ayaka"
[account] ~ candidates.100.lineup.0: "Fischl" -> "Kaedehara Kazuha"
[account] ~ candidates.100.lineup.1: "Kaedehara Kazuha" -> "Kamisato Ayaka"
[account] ~ candidates.100.lineup.2: "Razor" -> "Layla"
[account] ~ candidates.100.lineup.3: "Yaoyao" -> "Shenhe"
[account] ~ candidates.100.route: "pair_model" -> "exact_community"
[account] ~ candidates.100.template: "aggravate" -> "auto_mono_cryo"
[account] ~ candidates.100.tier: "C" -> "B"
[account] ~ candidates.101.expected: 39.2 -> 38.8
[account] ~ candidates.101.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.101.label: "Mono Cryo (from gcsim data)" -> "Overloaded (Pyro carry) (from gcsim data)"
[account] ~ candidates.101.lead: "Kamisato Ayaka" -> "Yoimiya"
[account] ~ candidates.101.lineup.0: "Kaedehara Kazuha" -> "Bennett"
[account] ~ candidates.101.lineup.1: "Kamisato Ayaka" -> "Fischl"
[account] ~ candidates.101.lineup.2: "Layla" -> "Yoimiya"
[account] ~ candidates.101.lineup.3: "Shenhe" -> "Zhongli"
[account] ~ candidates.101.ranking: 36.5 -> 36.2
[account] ~ candidates.101.route: "exact_community" -> "pair_model"
[account] ~ candidates.101.template: "auto_mono_cryo" -> "auto_overloaded_pyro_carry"
[account] ~ candidates.101.tier: "B" -> "C"
[account] ~ candidates.102.label: "Chevreuse Overloaded" -> "Aggravate (Quicken)"
[account] ~ candidates.102.lead: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.102.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.102.lineup.1: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.102.lineup.2: "Raiden Shogun" -> "Xiangling"
[account] ~ candidates.102.lineup.3: "Yoimiya" -> "Yaoyao"
[account] ~ candidates.102.ranking: 36.3 -> 36.2
[account] ~ candidates.102.route: "exact_community" -> "pair_model"
[account] ~ candidates.102.template: "overloaded" -> "aggravate"
[account] ~ candidates.102.tier: "B" -> "C"
[account] ~ candidates.103.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Freeze"
[account] ~ candidates.103.lead: "Yoimiya" -> "Kamisato Ayaka"
[account] ~ candidates.103.lineup.0: "Bennett" -> "Kamisato Ayaka"
[account] ~ candidates.103.lineup.1: "Fischl" -> "Kujou Sara"
[account] ~ candidates.103.lineup.2: "Yoimiya" -> "Mona"
[account] ~ candidates.103.lineup.3: "Zhongli" -> "Shenhe"
[account] ~ candidates.103.template: "auto_overloaded_pyro_carry" -> "freeze"
[account] ~ candidates.104.expected: 38.9 -> 38.7
[account] ~ candidates.104.fit_source: "pairmodel" -> "model"
...
```

## 2026-10-16 21:07, model 5.4

Phase 6 (model 5.4): the one synergy rebuild. Lineup values unchanged (0 refreshed), so exact-route power is unchanged. Re-sampling (gcsim draws a new seed per sample: total damage median change 1.6%, member damage shares median 0.4 points) flipped the measured structure type of 166 of 3,788 lineups (4.4%) near hard thresholds, which changes damage leads, the pair model's lead effects and predicted structures. reaction_share now counts Lunar-Bloom and Lunar-Crystallize (16 lineups moved >5 points). Derive refit: pair model 6.4% CV, validity recall >= 93%. Effect here: 116 of 1,051 matched teams moved >0.5 (median 0.1, largest Columbina / Flins / Sucrose / Xingqiu -7.8 from a structure flip), 1 plan (pull_furina_for_neuvillette, a 40.8 vs 40.7 tie), 2 top pulls (top-two swaps), 23 pull kinds, 17 labels. The reaction-table refactor itself changed nothing (golden checked before the rebuild).

3285 changed values in 38 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_no_skirk_without_hydro, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka.

```
[account] ~ candidates: [{"expected": 78.0, "fit_source": "gcsim", "label": "Lunar-Charged (Flins hypercarry)", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"expected": 78.0, "fit_source": "gcsim", "label": "Lunar-Charged (Flins hypercarry)", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank
[account] ~ carries_for_supports.1.2: 66.1 -> 66.3
[account] ~ carries_for_supports.3.0: "Gaming" -> "Skirk"
[account] ~ carries_for_supports.3.1.0: "Bennett" -> "Citlali"
[account] ~ carries_for_supports.3.1.1: "Gaming" -> "Mona"
[account] ~ carries_for_supports.3.1.2: "Rosaria" -> "Skirk"
[account] ~ carries_for_supports.3.2: 61.5 -> 62.5
[account] ~ carries_for_supports.4.0: "Skirk" -> "Gaming"
[account] ~ carries_for_supports.4.1.0: "Citlali" -> "Bennett"
[account] ~ carries_for_supports.4.1.1: "Mona" -> "Gaming"
[account] ~ carries_for_supports.4.1.2: "Skirk" -> "Rosaria"
[account] ~ carries_for_supports.4.2: 61.2 -> 61.5
[account] ~ modes.abyss.score: 126.0 -> 126.1
[account] ~ modes.general.score: 160.9 -> 160.7
[account] ~ modes.general.teams.3.0: "Citlali" -> "Kamisato Ayaka"
[account] ~ modes.general.teams.3.1: "Kamisato Ayaka" -> "Mona"
[account] ~ modes.general.teams.3.2: "Mona" -> "Rosaria"
[account] ~ modes.theater.score: 244.7 -> 243.4
[account] ~ modes.theater.teams.3.0: "Citlali" -> "Kamisato Ayaka"
[account] ~ modes.theater.teams.3.1: "Kamisato Ayaka" -> "Mona"
[account] ~ modes.theater.teams.3.2: "Mona" -> "Rosaria"
[account] ~ plan.2.expected: 47.3 -> 46.9
[account] ~ plan.2.ranking: 44.1 -> 43.8
[account] ~ plan.2.sd: 4.8 -> 4.6
[account] ~ plan.3.expected: 42.1 -> 41.7
[account] ~ plan.3.ranking: 39.2 -> 38.9
[account] ~ plan.3.sd: 4.2 -> 4.1
[account] ~ plan_value: 165.2 -> 164.9
[account] ~ pulls.2.best_team.0: "Citlali" -> "Bennett"
[account] ~ pulls.2.best_team.1: "Lauma" -> "Citlali"
[account] ~ pulls.2.best_team.2: "Raiden Shogun" -> "Mavuika"
[account] ~ pulls.2.best_team.3: "Xingqiu" -> "Zhongli"
[account] ~ pulls.2.expected: 9.5 -> 11.1
[account] ~ pulls.2.gain: 8.7 -> 10.4
[account] ~ pulls.2.kind: "fills a gap" -> "new archetype"
[account] ~ pulls.2.name: "Lauma" -> "Mavuika"
[account] ~ pulls.2.sd: 7.2 -> 9.9
[account] ~ pulls.3.best_team.0: "Bennett" -> "Citlali"
[account] ~ pulls.3.best_team.1: "Citlali" -> "Lauma"
[account] ~ pulls.3.best_team.2: "Mavuika" -> "Raiden Shogun"
[account] ~ pulls.3.best_team.3: "Zhongli" -> "Xingqiu"
[account] ~ pulls.3.expected: 8.2 -> 9.5
[account] ~ pulls.3.gain: 8.1 -> 8.8
[account] ~ pulls.3.kind: "new archetype" -> "fills a gap"
[account] ~ pulls.3.name: "Mavuika" -> "Lauma"
[account] ~ pulls.3.sd: 9.8 -> 7.0
[account] ~ pulls.4.expected: 8.0 -> 8.9
[account] ~ pulls.4.gain: 7.4 -> 8.3
[account] ~ pulls.5.expected: 6.5 -> 6.6
[account] ~ pulls.5.gain: 5.8 -> 6.1
[account] ~ pulls.5.sd: 10.3 -> 10.2
[account] ~ pulls.6.best_team.0: "Escoffier" -> "Neuvillette"
[account] ~ pulls.6.best_team.1: "Kamisato Ayaka" -> "Raiden Shogun"
[account] ~ pulls.6.best_team.2: "Mona" -> "Xingqiu"
[account] ~ pulls.6.best_team.3: "Shenhe" -> "Yaoyao"
[account] ~ pulls.6.expected: 4.5 -> 4.2
[account] ~ pulls.6.gain: 4.2 -> 3.9
[account] ~ pulls.6.name: "Escoffier" -> "Neuvillette"
[account] ~ pulls.6.sd: 2.9 -> 3.8
[account] ~ pulls.7.best_team.0: "Chevreuse" -> "Escoffier"
[account] ~ pulls.7.best_team.1: "Nicole" -> "Kamisato Ayaka"
[account] ~ pulls.7.best_team.2: "Xiangling" -> "Mona"
[account] ~ pulls.7.best_team.3: "Yae Miko" -> "Shenhe"
[account] ~ pulls.7.expected: 4.2 -> 4.1
[account] ~ pulls.7.gain: 3.9 -> 3.8
[account] ~ pulls.7.name: "Nicole" -> "Escoffier"
[account] ~ pulls.7.sd: 10.1 -> 2.8
[account] ~ pulls.8.best_team.0: "Arlecchino" -> "Prune"
[account] ~ pulls.8.best_team.1: "Bennett" -> "Raiden Shogun"
[account] ~ pulls.8.best_team.2: "Chevreuse" -> "Xingqiu"
[account] ~ pulls.8.best_team.3: "Fischl" -> "Yaoyao"
[account] ~ pulls.8.expected: 2.5 -> 4.0
[account] ~ pulls.8.gain: 3.6 -> 3.8
[account] ~ pulls.8.kind: "new archetype" -> "upgrade"
[account] ~ pulls.8.name: "Arlecchino" -> "Prune"
[account] ~ pulls.8.sd: 8.0 -> 3.8
[account] ~ pulls.8.tier: "B" -> "C"
[account] ~ pulls.9.best_team.0: "Prune" -> "Arlecchino"
[account] ~ pulls.9.best_team.1: "Raiden Shogun" -> "Bennett"
[account] ~ pulls.9.best_team.2: "Xingqiu" -> "Chevreuse"
[account] ~ pulls.9.best_team.3: "Yaoyao" -> "Fischl"
[account] ~ pulls.9.expected: 3.9 -> 2.5
[account] ~ pulls.9.kind: "upgrade" -> "new archetype"
[account] ~ pulls.9.name: "Prune" -> "Arlecchino"
[account] ~ pulls.9.sd: 3.9 -> 8.0
[account] ~ pulls.9.tier: "C" -> "B"
[account] ~ pulls.10.best_team.0: "Neuvillette" -> "Furina"
[account] ~ pulls.10.expected: 3.8 -> 3.7
[account] ~ pulls.10.name: "Neuvillette" -> "Furina"
[account] ~ pulls.10.sd: 3.9 -> 3.8
[account] ~ pulls.11.best_team.0: "Furina" -> "Chevreuse"
[account] ~ pulls.11.best_team.1: "Raiden Shogun" -> "Nicole"
[account] ~ pulls.11.best_team.2: "Xingqiu" -> "Xiangling"
[account] ~ pulls.11.best_team.3: "Yaoyao" -> "Yae Miko"
[account] ~ pulls.11.expected: 3.0 -> 3.6
[account] ~ pulls.11.gain: 2.8 -> 3.5
[account] ~ pulls.11.kind: "upgrade" -> "fills a gap"
[account] ~ pulls.11.name: "Furina" -> "Nicole"
[account] ~ pulls.11.sd: 3.9 -> 9.9
[account] ~ pulls.12.expected: 3.1 -> 3.3
[account] ~ pulls.12.gain: 2.8 -> 3.1
[account] ~ pulls.12.sd: 3.9 -> 3.8
[account] ~ pulls.13.best_team.0: "Raiden Shogun" -> "Chevreuse"
[account] ~ pulls.13.best_team.1: "Varka" -> "Citlali"
[account] ~ pulls.13.best_team.2: "Xingqiu" -> "Razor"
[account] ~ pulls.13.best_team.3: "Zhongli" -> "Xianyun"
[account] ~ pulls.13.expected: 2.5 -> 5.2
[account] ~ pulls.13.gain: 2.3 -> 3.0
[account] ~ pulls.13.kind: "new archetype" -> "upgrade"
[account] ~ pulls.13.name: "Varka" -> "Xianyun"
[account] ~ pulls.13.sd: 3.8 -> 11.8
[account] ~ pulls.13.tier: "C" -> "D"
[account] ~ pulls.14.best_team.0: "Clorinde" -> "Raiden Shogun"
[account] ~ pulls.14.best_team.1: "Raiden Shogun" -> "Varka"
[account] ~ pulls.14.best_team.3: "Yaoyao" -> "Zhongli"
[account] ~ pulls.14.expected: 1.7 -> 2.8
[account] ~ pulls.14.gain: 1.6 -> 2.6
[account] ~ pulls.14.kind: "upgrade" -> "new archetype"
[account] ~ pulls.14.name: "Clorinde" -> "Varka"
[account] ~ pulls.14.sd: 3.8 -> 3.7
[account] ~ pulls.15.best_team.0: "Kamisato Ayaka" -> "Bennett"
[account] ~ pulls.15.best_team.1: "Mona" -> "Citlali"
[account] ~ pulls.15.best_team.2: "Shenhe" -> "Gaming"
[account] ~ pulls.15.best_team.3: "Xilonen" -> "Rosaria"
[account] ~ pulls.15.expected: 1.7 -> 2.6
[account] ~ pulls.15.gain: 1.6 -> 2.5
[account] ~ pulls.15.kind: "upgrade" -> "new archetype"
[account] ~ pulls.15.name: "Xilonen" -> "Gaming"
[account] ~ pulls.15.sd: 2.6 -> 9.3
[account] ~ pulls.16.best_team.0: "Kirara" -> "Raiden Shogun"
[account] ~ pulls.16.best_team.1: "Raiden Shogun" -> "Xilonen"
[account] ~ pulls.16.expected: 1.5 -> 1.8
[account] ~ pulls.16.gain: 1.3 -> 1.7
[account] ~ pulls.16.name: "Kirara" -> "Xilonen"
[account] ~ pulls.16.sd: 3.8 -> 3.7
[account] ~ pulls.17.best_team.0: "Chevreuse" -> "Kirara"
[account] ~ pulls.17.best_team.1: "Citlali" -> "Raiden Shogun"
[account] ~ pulls.17.best_team.2: "Razor" -> "Xingqiu"
[account] ~ pulls.17.best_team.3: "Xianyun" -> "Yaoyao"
[account] ~ pulls.17.expected: 3.3 -> 1.7
[account] ~ pulls.17.gain: 1.3 -> 1.6
[account] ~ pulls.17.name: "Xianyun" -> "Kirara"
[account] ~ pulls.17.sd: 11.6 -> 3.6
[account] ~ pulls.17.tier: "D" -> "C"
[account] ~ pulls.18.best_team.0: "Citlali" -> "Raiden Shogun"
[account] ~ pulls.18.best_team.1: "Raiden Shogun" -> "Sangonomiya Kokomi"
[account] ~ pulls.18.best_team.3: "Yelan" -> "Yaoyao"
[account] ~ pulls.18.expected: 1.3 -> 1.1
[account] ~ pulls.18.kind: "new archetype" -> "upgrade"
[account] ~ pulls.18.name: "Yelan" -> "Sangonomiya Kokomi"
[account] ~ pulls.18.sd: 3.8 -> 3.6
[account] ~ pulls.19.best_team.0: "Bennett" -> "Clorinde"
[account] ~ pulls.19.best_team.1: "Citlali" -> "Kaedehara Kazuha"
[account] ~ pulls.19.best_team.2: "Gaming" -> "Yae Miko"
[account] ~ pulls.19.best_team.3: "Rosaria" -> "Yaoyao"
[account] ~ pulls.19.expected: 0.5 -> 1.0
[account] ~ pulls.19.gain: 0.9 -> 1.0
[account] ~ pulls.19.kind: "new archetype" -> "sidegrade"
[account] ~ pulls.19.name: "Gaming" -> "Clorinde"
[account] ~ pulls.19.sd: 9.2 -> 2.0
[account] ~ pulls.20.best_team.0: "Raiden Shogun" -> "Kamisato Ayaka"
[account] ~ pulls.20.best_team.1: "Sangonomiya Kokomi" -> "Mona"
[account] ~ pulls.20.best_team.2: "Xingqiu" -> "Shenhe"
[account] ~ pulls.20.best_team.3: "Yaoyao" -> "Venti"
[account] ~ pulls.20.gain: 0.9 -> 1.0
[account] ~ pulls.20.name: "Sangonomiya Kokomi" -> "Venti"
[account] ~ pulls.20.sd: 3.7 -> 1.5
[account] ~ pulls.20.tier: "C" -> "B"
[account] ~ pulls.21.best_team.0: "Kamisato Ayaka" -> "Nahida"
[account] ~ pulls.21.best_team.1: "Mona" -> "Raiden Shogun"
[account] ~ pulls.21.best_team.2: "Shenhe" -> "Xingqiu"
[account] ~ pulls.21.best_team.3: "Venti" -> "Zhongli"
[account] ~ pulls.21.expected: 0.9 -> 1.1
[account] ~ pulls.21.gain: 0.9 -> 0.8
[account] ~ pulls.21.name: "Venti" -> "Nahida"
[account] ~ pulls.21.sd: 1.6 -> 3.9
[account] ~ pulls.21.tier: "B" -> "C"
[account] ~ pulls.22.sd: 3.7 -> 3.6
[account] ~ pulls.23.best_team.0: "Nahida" -> "Kujou Sara"
[account] ~ pulls.23.best_team.1: "Raiden Shogun" -> "Wriothesley"
[account] ~ pulls.23.best_team.2: "Xingqiu" -> "Xiangling"
[account] ~ pulls.23.best_team.3: "Zhongli" -> "Yae Miko"
[account] ~ pulls.23.expected: 0.9 -> 0.3
[account] ~ pulls.23.gain: 0.6 -> 0.3
[account] ~ pulls.23.kind: "upgrade" -> "fills a gap"
[account] ~ pulls.23.name: "Nahida" -> "Wriothesley"
[account] ~ pulls.23.sd: 3.9 -> 1.5
[account] ~ pulls.24.best_team.0: "Citlali" -> "Kamisato Ayaka"
[account] ~ pulls.24.best_team.1: "Lynette" -> "Mona"
[account] ~ pulls.24.best_team.2: "Mona" -> "Shenhe"
[account] ~ pulls.24.best_team.3: "Mualani" -> "Yelan"
[account] ~ pulls.24.expected: 0.5 -> 0.3
[account] ~ pulls.24.kind: "new archetype" -> "upgrade"
[account] ~ pulls.24.name: "Mualani" -> "Yelan"
[account] ~ pulls.24.sd: 1.8 -> 1.5
[account] ~ pulls.24.tier: "D" -> "C"
[account] ~ pulls.25.best_team.0: "Kujou Sara" -> "Citlali"
[account] ~ pulls.25.best_team.1: "Wriothesley" -> "Lynette"
[account] ~ pulls.25.best_team.2: "Xiangling" -> "Mona"
[account] ~ pulls.25.best_team.3: "Yae Miko" -> "Mualani"
...
```

## 2026-10-16 23:56, model 5.5

Phase 6.5 (model 5.5): Provisional Kits Lite. Hand-written kits for Lohen, Nefer, Sandrone, Vesna and Zibai (knowledge/kits_provisional/), valued on the new provisional_kit route (tier E, coverage unknown, sd from a 471-lineup back-test: 19%). They now appear in pull lists and in carries-for-supports lists where a team within two members of a Prydwen-listed team exists (7 carry lists changed: Sandrone and Lohen entered; account pulls gained 5 entries, Sandrone 4th at +13.1 E provisional). Ifa was simulated in 6 lineups but never placed in a template; now placed by hand in characters.yaml and valued from his own data. No existing team value, plan or pull changed.

110 changed values in 7 outputs: account, roster_alhaitham_nahida, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_skirk_hydro_cryo, roster_skirk_not_with_geo.

```
[account] ~ carries_for_supports.4.0: "Gaming" -> "Sandrone"
[account] ~ carries_for_supports.4.1.0: "Bennett" -> "Fischl"
[account] ~ carries_for_supports.4.1.1: "Gaming" -> "Sandrone"
[account] ~ carries_for_supports.4.1.2: "Rosaria" -> "Yae Miko"
[account] ~ carries_for_supports.4.1.3: "Sucrose" -> "Zhongli"
[account] ~ carries_for_supports.4.2: 61.5 -> 62.2
[account] ~ pulls: [{"best_team": ["Columbina", "Flins", "Ineffa", "Sucrose"], "expected": 22.0, "gain": 20.5, "kind": "fills a gap", "name": "Columbina", "sd": 12.6, "tier": "B"} -> [{"best_team": ["Columbina", "Flins", "Ineffa", "Sucrose"], "expected": 22.0, "gain": 20.5, "kind": "fills a gap", "name": "Columbina", "sd": 12.6, "tier": "B"}
[roster_alhaitham_nahida] ~ carries_for_supports.0.0: "Varka" -> "Sandrone"
[roster_alhaitham_nahida] ~ carries_for_supports.0.1.0: "Kuki Shinobu" -> "Fischl"
[roster_alhaitham_nahida] ~ carries_for_supports.0.1.1: "Nahida" -> "Kuki Shinobu"
[roster_alhaitham_nahida] ~ carries_for_supports.0.1.2: "Varka" -> "Sandrone"
[roster_alhaitham_nahida] ~ carries_for_supports.0.1.3: "Xingqiu" -> "Yae Miko"
[roster_alhaitham_nahida] ~ carries_for_supports.0.2: 58.5 -> 62.2
[roster_alhaitham_nahida] ~ carries_for_supports.1.0: "Neuvillette" -> "Varka"
[roster_alhaitham_nahida] ~ carries_for_supports.1.1.2: "Neuvillette" -> "Varka"
[roster_alhaitham_nahida] ~ carries_for_supports.1.2: 53.4 -> 58.5
[roster_alhaitham_nahida] ~ carries_for_supports.2.0: "Clorinde" -> "Neuvillette"
[roster_alhaitham_nahida] ~ carries_for_supports.2.1.0: "Clorinde" -> "Kuki Shinobu"
[roster_alhaitham_nahida] ~ carries_for_supports.2.1.1: "Fischl" -> "Nahida"
[roster_alhaitham_nahida] ~ carries_for_supports.2.1.2: "Nahida" -> "Neuvillette"
[roster_alhaitham_nahida] ~ carries_for_supports.2.1.3: "Yae Miko" -> "Xingqiu"
[roster_alhaitham_nahida] ~ carries_for_supports.2.2: 50.1 -> 53.4
[roster_alhaitham_nahida] ~ carries_for_supports.3.0: "Razor" -> "Clorinde"
[roster_alhaitham_nahida] ~ carries_for_supports.3.1.0: "Fischl" -> "Clorinde"
[roster_alhaitham_nahida] ~ carries_for_supports.3.1.1: "Nahida" -> "Fischl"
[roster_alhaitham_nahida] ~ carries_for_supports.3.1.2: "Razor" -> "Nahida"
[roster_alhaitham_nahida] ~ carries_for_supports.3.2: 49.3 -> 50.1
[roster_alhaitham_nahida] ~ carries_for_supports.4.0: "Varesa" -> "Razor"
[roster_alhaitham_nahida] ~ carries_for_supports.4.1.2: "Varesa" -> "Razor"
[roster_alhaitham_nahida] ~ carries_for_supports.4.1.3: "Xingqiu" -> "Yae Miko"
[roster_alhaitham_nahida] ~ carries_for_supports.4.2: 48.9 -> 49.3
[roster_skirk_hydro_cryo] ~ carries_for_supports.1.0: "Neuvillette" -> "Sandrone"
[roster_skirk_hydro_cryo] ~ carries_for_supports.1.1.1: "Furina" -> "Kaedehara Kazuha"
[roster_skirk_hydro_cryo] ~ carries_for_supports.1.1.2: "Neuvillette" -> "Sandrone"
[roster_skirk_hydro_cryo] ~ carries_for_supports.1.2: 59.1 -> 62.2
[roster_skirk_hydro_cryo] ~ carries_for_supports.2.0: "Mavuika" -> "Neuvillette"
[roster_skirk_hydro_cryo] ~ carries_for_supports.2.1.0: "Bennett" -> "Escoffier"
[roster_skirk_hydro_cryo] ~ carries_for_supports.2.1.1: "Escoffier" -> "Furina"
[roster_skirk_hydro_cryo] ~ carries_for_supports.2.1.2: "Mavuika" -> "Neuvillette"
[roster_skirk_hydro_cryo] ~ carries_for_supports.2.2: 57.5 -> 59.1
[roster_skirk_hydro_cryo] ~ carries_for_supports.3.0: "Varka" -> "Lohen"
[roster_skirk_hydro_cryo] ~ carries_for_supports.3.1.0: "Furina" -> "Escoffier"
[roster_skirk_hydro_cryo] ~ carries_for_supports.3.1.1: "Kaedehara Kazuha" -> "Furina"
[roster_skirk_hydro_cryo] ~ carries_for_supports.3.1.2: "Shenhe" -> "Kaedehara Kazuha"
[roster_skirk_hydro_cryo] ~ carries_for_supports.3.1.3: "Varka" -> "Lohen"
[roster_skirk_hydro_cryo] ~ carries_for_supports.3.2: 57.1 -> 58.5
[roster_skirk_hydro_cryo] ~ carries_for_supports.4.0: "Ganyu" -> "Mavuika"
[roster_skirk_hydro_cryo] ~ carries_for_supports.4.1.0: "Escoffier" -> "Bennett"
[roster_skirk_hydro_cryo] ~ carries_for_supports.4.1.1: "Furina" -> "Escoffier"
[roster_skirk_hydro_cryo] ~ carries_for_supports.4.1.2: "Ganyu" -> "Mavuika"
[roster_skirk_hydro_cryo] ~ carries_for_supports.4.2: 53.9 -> 57.5
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.2.0: "Arlecchino" -> "Lohen"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.2.1.0: "Arlecchino" -> "Lohen"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.2.1.1: "Bennett" -> "Mona"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.2.1.2: "Kaedehara Kazuha" -> "Shenhe"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.2.1.3: "Zhongli" -> "Sucrose"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.2.2: 48.2 -> 49.3
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.3.0: "Mualani" -> "Arlecchino"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.3.1.0: "Bennett" -> "Arlecchino"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.3.1.1: "Mualani" -> "Bennett"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.3.1.2: "Sucrose" -> "Kaedehara Kazuha"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.3.1.3: "Xiangling" -> "Zhongli"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.3.2: 47.2 -> 48.2
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.4.0: "Lyney" -> "Mualani"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.4.1.1: "Kaedehara Kazuha" -> "Mualani"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.4.1.2: "Lyney" -> "Sucrose"
[roster_ayaka_kazuha_over_sucrose] ~ carries_for_supports.4.2: 46.3 -> 47.2
[roster_ayaka_freeze_core] ~ carries_for_supports.3.0: "Arlecchino" -> "Lohen"
[roster_ayaka_freeze_core] ~ carries_for_supports.3.1.0: "Arlecchino" -> "Lohen"
[roster_ayaka_freeze_core] ~ carries_for_supports.3.1.1: "Bennett" -> "Mona"
[roster_ayaka_freeze_core] ~ carries_for_supports.3.1.2: "Sucrose" -> "Shenhe"
[roster_ayaka_freeze_core] ~ carries_for_supports.3.1.3: "Xingqiu" -> "Sucrose"
[roster_ayaka_freeze_core] ~ carries_for_supports.3.2: 47.4 -> 49.3
[roster_ayaka_freeze_core] ~ carries_for_supports.4.0: "Lyney" -> "Arlecchino"
[roster_ayaka_freeze_core] ~ carries_for_supports.4.1.0: "Bennett" -> "Arlecchino"
[roster_ayaka_freeze_core] ~ carries_for_supports.4.1.1: "Lyney" -> "Bennett"
[roster_ayaka_freeze_core] ~ carries_for_supports.4.2: 46.5 -> 47.4
[roster_skirk_not_with_geo] ~ carries_for_supports.0.0: "Varka" -> "Sandrone"
[roster_skirk_not_with_geo] ~ carries_for_supports.0.1.0: "Escoffier" -> "Chiori"
[roster_skirk_not_with_geo] ~ carries_for_supports.0.1.1: "Furina" -> "Escoffier"
[roster_skirk_not_with_geo] ~ carries_for_supports.0.1.2: "Varka" -> "Lan Yan"
[roster_skirk_not_with_geo] ~ carries_for_supports.0.1.3: "Zhongli" -> "Sandrone"
[roster_skirk_not_with_geo] ~ carries_for_supports.0.2: 60.1 -> 62.2
[roster_skirk_not_with_geo] ~ carries_for_supports.1.0: "Mavuika" -> "Varka"
[roster_skirk_not_with_geo] ~ carries_for_supports.1.1.0: "Chiori" -> "Escoffier"
[roster_skirk_not_with_geo] ~ carries_for_supports.1.1.1: "Escoffier" -> "Furina"
[roster_skirk_not_with_geo] ~ carries_for_supports.1.1.2: "Mavuika" -> "Varka"
[roster_skirk_not_with_geo] ~ carries_for_supports.1.2: 55.1 -> 60.1
[roster_skirk_not_with_geo] ~ carries_for_supports.2.0: "Neuvillette" -> "Lohen"
[roster_skirk_not_with_geo] ~ carries_for_supports.2.1.2: "Neuvillette" -> "Lohen"
[roster_skirk_not_with_geo] ~ carries_for_supports.2.2: 53.6 -> 58.5
[roster_skirk_not_with_geo] ~ carries_for_supports.3.0: "Navia" -> "Mavuika"
[roster_skirk_not_with_geo] ~ carries_for_supports.3.1.0: "Escoffier" -> "Chiori"
[roster_skirk_not_with_geo] ~ carries_for_supports.3.1.1: "Furina" -> "Escoffier"
[roster_skirk_not_with_geo] ~ carries_for_supports.3.1.2: "Navia" -> "Mavuika"
[roster_skirk_not_with_geo] ~ carries_for_supports.3.2: 47.1 -> 55.1
[roster_skirk_not_with_geo] ~ carries_for_supports.4.0: "Gaming" -> "Neuvillette"
[roster_skirk_not_with_geo] ~ carries_for_supports.4.1.0: "Chiori" -> "Escoffier"
[roster_skirk_not_with_geo] ~ carries_for_supports.4.1.1: "Escoffier" -> "Furina"
[roster_skirk_not_with_geo] ~ carries_for_supports.4.1.2: "Gaming" -> "Neuvillette"
[roster_skirk_not_with_geo] ~ carries_for_supports.4.2: 45.4 -> 53.6
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.3.0: "Arlecchino" -> "Lohen"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.3.1.0: "Arlecchino" -> "Lohen"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.3.1.1: "Kaedehara Kazuha" -> "Mona"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.3.1.2: "Xingqiu" -> "Shenhe"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.3.2: 43.2 -> 44.3
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.4.0: "Mualani" -> "Arlecchino"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.4.1.0: "Kaedehara Kazuha" -> "Arlecchino"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.4.1.1: "Mualani" -> "Kaedehara Kazuha"
[roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka] ~ carries_for_supports.4.2: 41.6 -> 43.2
```

## 2026-10-17 00:18, model 5.6

Phase 7 (model 5.6): Structure v2. Structures are now distributions (gtc/structure.py): measured lineups keep their measured label with probabilities from one sample's noise; predicted lineups propagate the held-out share error (calibrated: calibration error 2.4%). The most probable type replaces the point-estimate label (held-out accuracy 77.5% vs 74.6%), which moves damage leads and the pair model's lead effect near thresholds: 29 of 977 matched teams moved >0.5 (median 0). Validity's damage-owner check for unsimulated teams is now probabilistic (rejects when a non-fitting owner is more likely than not): e.g. Bennett / Kazuha / Nahida / Xingqiu is no longer accepted as Kazuha's Anemo-carry team (Xingqiu 78% likely top dealer), so the hyperbloom-trigger roster's plan falls 30.9 -> 24.7. Templates producing the same lineup now prefer the one led by the most probable damage dealer (54 labels). 4 plans (3 near ties), 3 top pulls, 27 pull kinds changed. Probability-weighted lead effects were tested and not adopted (calibration 80.4% vs 81.6%). The user's plan and top pull are unchanged.

1344 changed values in 38 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_no_skirk_without_hydro, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka.

```
[account] ~ candidates: [{"expected": 78.0, "fit_source": "gcsim", "label": "Lunar-Charged (Flins hypercarry)", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"expected": 78.0, "fit_source": "gcsim", "label": "Lunar-Charged (Flins hypercarry)", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank
[account] ~ pulls.24.best_team.0: "Kujou Sara" -> "Kamisato Ayaka"
[account] ~ pulls.24.best_team.1: "Wriothesley" -> "Mona"
[account] ~ pulls.24.best_team.2: "Xiangling" -> "Shenhe"
[account] ~ pulls.24.best_team.3: "Yae Miko" -> "Yelan"
[account] ~ pulls.24.kind: "fills a gap" -> "upgrade"
[account] ~ pulls.24.name: "Wriothesley" -> "Yelan"
[account] ~ pulls.25.best_team.0: "Kamisato Ayaka" -> "Citlali"
[account] ~ pulls.25.best_team.1: "Mona" -> "Lynette"
[account] ~ pulls.25.best_team.2: "Shenhe" -> "Mona"
[account] ~ pulls.25.best_team.3: "Yelan" -> "Mualani"
[account] ~ pulls.25.expected: 0.3 -> 0.5
[account] ~ pulls.25.gain: 0.3 -> 0.2
[account] ~ pulls.25.kind: "upgrade" -> "new archetype"
[account] ~ pulls.25.name: "Yelan" -> "Mualani"
[account] ~ pulls.25.sd: 1.5 -> 1.7
[account] ~ pulls.25.tier: "C" -> "D"
[account] ~ pulls.26.best_team.0: "Citlali" -> "Aino"
[account] ~ pulls.26.best_team.1: "Lynette" -> "Albedo"
[account] ~ pulls.26.best_team.2: "Mona" -> "Flins"
[account] ~ pulls.26.best_team.3: "Mualani" -> "Ineffa"
[account] ~ pulls.26.expected: 0.5 -> 0.0
[account] ~ pulls.26.gain: 0.2 -> 0.0
[account] ~ pulls.26.kind: "new archetype" -> "no change"
[account] ~ pulls.26.name: "Mualani" -> "Albedo"
[account] ~ pulls.26.sd: 1.7 -> 0.0
[account] ~ pulls.26.tier: "D" -> "B"
[account] ~ pulls.27.best_team.0: "Aino" -> "Alhaitham"
[account] ~ pulls.27.best_team.1: "Albedo" -> "Bennett"
[account] ~ pulls.27.best_team.2: "Flins" -> "Citlali"
[account] ~ pulls.27.best_team.3: "Ineffa" -> "Yae Miko"
[account] ~ pulls.27.name: "Albedo" -> "Alhaitham"
[account] ~ pulls.28.best_team.0: "Alhaitham" -> "Arataki Itto"
[account] ~ pulls.28.best_team.1: "Bennett" -> "Chiori"
[account] ~ pulls.28.best_team.2: "Citlali" -> "Ineffa"
[account] ~ pulls.28.best_team.3: "Yae Miko" -> "Zhongli"
[account] ~ pulls.28.name: "Alhaitham" -> "Arataki Itto"
[account] ~ pulls.29.best_team.0: "Arataki Itto" -> "Baizhu"
[account] ~ pulls.29.best_team.1: "Chiori" -> "Fischl"
[account] ~ pulls.29.best_team.2: "Ineffa" -> "Raiden Shogun"
[account] ~ pulls.29.best_team.3: "Zhongli" -> "Xingqiu"
[account] ~ pulls.29.name: "Arataki Itto" -> "Baizhu"
[account] ~ pulls.30.best_team.0: "Baizhu" -> "Charlotte"
[account] ~ pulls.30.best_team.1: "Fischl" -> "Chevreuse"
[account] ~ pulls.30.best_team.2: "Raiden Shogun" -> "Fischl"
[account] ~ pulls.30.best_team.3: "Xingqiu" -> "Razor"
[account] ~ pulls.30.name: "Baizhu" -> "Charlotte"
[account] ~ pulls.31.best_team.0: "Charlotte" -> "Bennett"
[account] ~ pulls.31.best_team.1: "Chevreuse" -> "Chasca"
[account] ~ pulls.31.best_team.2: "Fischl" -> "Citlali"
[account] ~ pulls.31.best_team.3: "Razor" -> "Ineffa"
[account] ~ pulls.31.name: "Charlotte" -> "Chasca"
[account] ~ pulls.32.best_team.0: "Bennett" -> "Chevreuse"
[account] ~ pulls.32.best_team.1: "Chasca" -> "Citlali"
[account] ~ pulls.32.best_team.2: "Citlali" -> "Cyno"
[account] ~ pulls.32.best_team.3: "Ineffa" -> "Fischl"
[account] ~ pulls.32.name: "Chasca" -> "Cyno"
[account] ~ pulls.33.best_team.1: "Citlali" -> "Dehya"
[account] ~ pulls.33.best_team.2: "Cyno" -> "Fischl"
[account] ~ pulls.33.best_team.3: "Fischl" -> "Razor"
[account] ~ pulls.33.name: "Cyno" -> "Dehya"
[account] ~ pulls.34.best_team.0: "Chevreuse" -> "Aino"
[account] ~ pulls.34.best_team.1: "Dehya" -> "Dori"
[account] ~ pulls.34.best_team.2: "Fischl" -> "Flins"
[account] ~ pulls.34.best_team.3: "Razor" -> "Ineffa"
[account] ~ pulls.34.name: "Dehya" -> "Dori"
[account] ~ pulls.35.best_team.0: "Aino" -> "Emilie"
[account] ~ pulls.35.best_team.1: "Dori" -> "Ineffa"
[account] ~ pulls.35.best_team.2: "Flins" -> "Sucrose"
[account] ~ pulls.35.best_team.3: "Ineffa" -> "Xingqiu"
[account] ~ pulls.35.name: "Dori" -> "Emilie"
[account] ~ pulls.36.best_team.0: "Emilie" -> "Bennett"
[account] ~ pulls.36.best_team.1: "Ineffa" -> "Citlali"
[account] ~ pulls.36.best_team.2: "Sucrose" -> "Eula"
[account] ~ pulls.36.best_team.3: "Xingqiu" -> "Xiangling"
[account] ~ pulls.36.name: "Emilie" -> "Eula"
[account] ~ pulls.37.best_team.1: "Eula" -> "Freminet"
[account] ~ pulls.37.name: "Eula" -> "Freminet"
[account] ~ pulls.38.best_team.0: "Bennett" -> "Chevreuse"
[account] ~ pulls.38.best_team.1: "Freminet" -> "Fischl"
[account] ~ pulls.38.best_team.2: "Ineffa" -> "Gorou"
[account] ~ pulls.38.best_team.3: "Xiangling" -> "Razor"
[account] ~ pulls.38.name: "Freminet" -> "Gorou"
[account] ~ pulls.39.best_team.2: "Gorou" -> "Hu Tao"
[account] ~ pulls.39.best_team.3: "Razor" -> "Ineffa"
[account] ~ pulls.39.name: "Gorou" -> "Hu Tao"
[account] ~ pulls.40.best_team.0: "Chevreuse" -> "Aino"
[account] ~ pulls.40.best_team.1: "Fischl" -> "Ifa"
[account] ~ pulls.40.best_team.2: "Hu Tao" -> "Ineffa"
[account] ~ pulls.40.best_team.3: "Ineffa" -> "Yae Miko"
[account] ~ pulls.40.name: "Hu Tao" -> "Ifa"
[account] ~ pulls.41.best_team.0: "Ifa" -> "Bennett"
[account] ~ pulls.41.best_team.1: "Ineffa" -> "Citlali"
[account] ~ pulls.41.best_team.2: "Sucrose" -> "Diluc"
[account] ~ pulls.41.best_team.3: "Xingqiu" -> "Illuga"
[account] ~ pulls.41.name: "Ifa" -> "Illuga"
[account] ~ pulls.42.best_team.0: "Bennett" -> "Aino"
[account] ~ pulls.42.best_team.1: "Citlali" -> "Flins"
[account] ~ pulls.42.best_team.2: "Diluc" -> "Ineffa"
[account] ~ pulls.42.best_team.3: "Illuga" -> "Jean"
[account] ~ pulls.42.name: "Illuga" -> "Jean"
[account] ~ pulls.43.best_team.0: "Aino" -> "Bennett"
[account] ~ pulls.43.best_team.1: "Flins" -> "Fischl"
[account] ~ pulls.43.best_team.3: "Jean" -> "Kaveh"
[account] ~ pulls.43.name: "Jean" -> "Kaveh"
[account] ~ pulls.44.best_team.1: "Kaveh" -> "Citlali"
[account] ~ pulls.44.best_team.2: "Layla" -> "Fischl"
[account] ~ pulls.44.best_team.3: "Raiden Shogun" -> "Kinich"
[account] ~ pulls.44.name: "Kaveh" -> "Kinich"
[account] ~ pulls.45.best_team.0: "Bennett" -> "Chevreuse"
[account] ~ pulls.45.best_team.1: "Citlali" -> "Fischl"
[account] ~ pulls.45.best_team.2: "Fischl" -> "Ineffa"
[account] ~ pulls.45.best_team.3: "Kinich" -> "Klee"
[account] ~ pulls.45.name: "Kinich" -> "Klee"
[account] ~ pulls.46.best_team.0: "Chevreuse" -> "Aino"
[account] ~ pulls.46.best_team.1: "Fischl" -> "Flins"
[account] ~ pulls.46.best_team.3: "Klee" -> "Kuki Shinobu"
[account] ~ pulls.46.name: "Klee" -> "Kuki Shinobu"
[account] ~ pulls.47.best_team.3: "Kuki Shinobu" -> "Linnea"
[account] ~ pulls.47.name: "Kuki Shinobu" -> "Linnea"
[account] ~ pulls.48.best_team.0: "Aino" -> "Lohen"
[account] ~ pulls.48.best_team.1: "Flins" -> "Mona"
[account] ~ pulls.48.best_team.2: "Ineffa" -> "Rosaria"
[account] ~ pulls.48.best_team.3: "Linnea" -> "Sucrose"
[account] ~ pulls.48.name: "Linnea" -> "Lohen"
[account] ~ pulls.49.best_team.0: "Lohen" -> "Chiori"
[account] ~ pulls.49.best_team.1: "Mona" -> "Ineffa"
[account] ~ pulls.49.best_team.2: "Rosaria" -> "Navia"
[account] ~ pulls.49.best_team.3: "Sucrose" -> "Zhongli"
[account] ~ pulls.49.name: "Lohen" -> "Navia"
[account] ~ pulls.50.best_team.0: "Chiori" -> "Odette"
[account] ~ pulls.50.best_team.1: "Ineffa" -> "Razor"
[account] ~ pulls.50.best_team.2: "Navia" -> "Yae Miko"
[account] ~ pulls.50.best_team.3: "Zhongli" -> "Yaoyao"
[account] ~ pulls.50.name: "Navia" -> "Odette"
[account] ~ pulls.51.best_team.0: "Odette" -> "Aino"
[account] ~ pulls.51.best_team.1: "Razor" -> "Flins"
[account] ~ pulls.51.best_team.2: "Yae Miko" -> "Ineffa"
[account] ~ pulls.51.best_team.3: "Yaoyao" -> "Ororon"
[account] ~ pulls.51.name: "Odette" -> "Ororon"
[account] ~ pulls.52.best_team.3: "Ororon" -> "Sigewinne"
[account] ~ pulls.52.name: "Ororon" -> "Sigewinne"
[account] ~ pulls.53.best_team.0: "Aino" -> "Fischl"
[account] ~ pulls.53.best_team.1: "Flins" -> "Mona"
[account] ~ pulls.53.best_team.2: "Ineffa" -> "Tighnari"
[account] ~ pulls.53.best_team.3: "Sigewinne" -> "Yaoyao"
[account] ~ pulls.53.name: "Sigewinne" -> "Tighnari"
[account] ~ pulls.54.best_team.0: "Fischl" -> "Bennett"
[account] ~ pulls.54.best_team.1: "Mona" -> "Chevreuse"
[account] ~ pulls.54.best_team.2: "Tighnari" -> "Kujou Sara"
[account] ~ pulls.54.best_team.3: "Yaoyao" -> "Varesa"
[account] ~ pulls.54.name: "Tighnari" -> "Varesa"
[account] ~ pulls.55.best_team.0: "Bennett" -> "Aino"
[account] ~ pulls.55.best_team.1: "Chevreuse" -> "Flins"
[account] ~ pulls.55.best_team.2: "Kujou Sara" -> "Ineffa"
[account] ~ pulls.55.best_team.3: "Varesa" -> "Vodyanitsa"
[account] ~ pulls.55.name: "Varesa" -> "Vodyanitsa"
[account] ~ pulls.56.best_team.0: "Aino" -> "Bennett"
[account] ~ pulls.56.best_team.1: "Flins" -> "Ineffa"
[account] ~ pulls.56.best_team.2: "Ineffa" -> "Wanderer"
[account] ~ pulls.56.best_team.3: "Vodyanitsa" -> "Xiangling"
[account] ~ pulls.56.name: "Vodyanitsa" -> "Wanderer"
[account] ~ pulls.57.best_team.2: "Wanderer" -> "Wriothesley"
[account] ~ pulls.57.name: "Wanderer" -> "Wriothesley"
[roster_flins_lunar_core] ~ candidates.11.expected: 64.2 -> 65.3
[roster_flins_lunar_core] ~ candidates.11.lead: "Ineffa" -> "Flins"
[roster_flins_lunar_core] ~ candidates.11.lineup.0: "Aino" -> "Columbina"
[roster_flins_lunar_core] ~ candidates.11.lineup.1: "Columbina" -> "Flins"
[roster_flins_lunar_core] ~ candidates.11.lineup.2: "Ineffa" -> "Sucrose"
[roster_flins_lunar_core] ~ candidates.11.ranking: 59.9 -> 60.9
[roster_flins_lunar_core] ~ candidates.11.sd: 6.3 -> 6.4
[roster_flins_lunar_core] ~ candidates.12.expected: 60.5 -> 64.2
[roster_flins_lunar_core] ~ candidates.12.lead: "Flins" -> "Ineffa"
[roster_flins_lunar_core] ~ candidates.12.lineup.0: "Columbina" -> "Aino"
[roster_flins_lunar_core] ~ candidates.12.lineup.1: "Flins" -> "Columbina"
[roster_flins_lunar_core] ~ candidates.12.lineup.2: "Sucrose" -> "Ineffa"
[roster_flins_lunar_core] ~ candidates.12.ranking: 56.5 -> 59.9
[roster_flins_lunar_core] ~ candidates.12.sd: 5.9 -> 6.3
[roster_flins_lunar_core] ~ candidates.15.expected: 55.5 -> 57.1
[roster_flins_lunar_core] ~ candidates.15.lineup.0: "Aino" -> "Bennett"
[roster_flins_lunar_core] ~ candidates.15.ranking: 50.7 -> 52.2
[roster_flins_lunar_core] ~ candidates.15.sd: 7.1 -> 7.4
[roster_flins_lunar_core] ~ candidates.16.expected: 53.0 -> 55.5
[roster_flins_lunar_core] ~ candidates.16.lineup.0: "Bennett" -> "Aino"
[roster_flins_lunar_core] ~ candidates.16.ranking: 48.4 -> 50.7
[roster_flins_lunar_core] ~ candidates.16.sd: 6.8 -> 7.1
[roster_flins_lunar_core] ~ carries_for_supports.0.1.0: "Columbina" -> "Bennett"
[roster_flins_lunar_core] ~ carries_for_supports.0.1.1: "Ineffa" -> "Columbina"
[roster_flins_lunar_core] ~ carries_for_supports.0.1.2: "Varka" -> "Ineffa"
[roster_flins_lunar_core] ~ carries_for_supports.0.1.3: "Xingqiu" -> "Varka"
[roster_flins_lunar_core] ~ carries_for_supports.0.2: 84.6 -> 86.1
[roster_flins_lunar_core] ~ carries_for_supports.4.0: "Sethos" -> "Lyney"
[roster_flins_lunar_core] ~ carries_for_supports.4.1.0: "Columbina" -> "Bennett"
[roster_flins_lunar_core] ~ carries_for_supports.4.1.1: "Ineffa" -> "Columbina"
[roster_flins_lunar_core] ~ carries_for_supports.4.1.2: "Sethos" -> "Ineffa"
[roster_flins_lunar_core] ~ carries_for_supports.4.1.3: "Sucrose" -> "Lyney"
[roster_flins_lunar_core] ~ pulls: [{"best_team": ["Aino", "Bennett", "Varka", "Xingqiu"], "expected": 56.4, "gain": 51.5, "kind": "new archetype", "name": "Varka", "sd": 7.3, "tier": "D"}, {"bes -> [{"best_team": ["Aino", "Bennett", "Varka", "Xingqiu"], "expected": 56.4, "gain": 51.5, "kind": "new archetype", "name": "Varka", "sd": 7.3, "tier": "D"}, {"bes
[roster_flins_aino_over_xingqiu] ~ candidates: [{"expected": 78.0, "fit_source": "gcsim", "label": "Lunar-Charged (Flins hypercarry)", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"expected": 78.0, "fit_source": "gcsim", "label": "Lunar-Charged (Flins hypercarry)", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank
[roster_flins_aino_over_xingqiu] ~ modes.abyss.score: 98.9 -> 96.1
[roster_flins_aino_over_xingqiu] ~ modes.general.score: 97.7 -> 95.0
...
```

## 2026-10-17 00:33, model 5.6

Phase 7 follow-up: structure draws 400 -> 200 from one fixed shared bank (deterministic, common random numbers) for speed; held-out structure metrics unchanged within 0.5 points (calibration error 2.9%). Against the previous update: no power, plan or top pull changed; 6 pull kinds and 10 labels moved where structure probabilities sit near a decision boundary.

2186 changed values in 26 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_raiden_national, roster_skirk_not_with_geo, roster_xiao_faruzan.

```
[account] ~ candidates.3.label: "Lunar-Charged (Flins hypercarry)" -> "Lunar-Charged off-field (taser style)"
[account] ~ candidates.3.template: "lunar_charged" -> "lunar_charged_offfield"
[account] ~ candidates.26.label: "Lunar-Charged off-field (taser style)" -> "Lunar-Charged (Flins hypercarry)"
[account] ~ candidates.26.template: "lunar_charged_offfield" -> "lunar_charged"
[account] ~ candidates.140.expected: 35.5 -> 35.1
[account] ~ candidates.140.label: "Melt (Cryo carry)" -> "National (Xiangling, Xingqiu, Bennett, driver)"
[account] ~ candidates.140.lead: "Ganyu" -> "Xiangling"
[account] ~ candidates.140.lineup.1: "Ganyu" -> "Lan Yan"
[account] ~ candidates.140.lineup.2: "Kujou Sara" -> "Xiangling"
[account] ~ candidates.140.lineup.3: "Xiangling" -> "Xingqiu"
[account] ~ candidates.140.ranking: 33.1 -> 32.8
[account] ~ candidates.140.sd: 3.5 -> 3.4
[account] ~ candidates.140.template: "melt" -> "national"
[account] ~ candidates.141.expected: 35.1 -> 35.2
[account] ~ candidates.141.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Superconduct (Electro carry) (from gcsim data)"
[account] ~ candidates.141.lead: "Xiangling" -> "Razor"
[account] ~ candidates.141.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.141.lineup.1: "Lan Yan" -> "Layla"
[account] ~ candidates.141.lineup.2: "Xiangling" -> "Razor"
[account] ~ candidates.141.lineup.3: "Xingqiu" -> "Zhongli"
[account] ~ candidates.141.sd: 3.4 -> 3.5
[account] ~ candidates.141.template: "national" -> "auto_superconduct_electro_carry"
[account] ~ candidates.142.expected: 35.2 -> 35.0
[account] ~ candidates.142.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.142.label: "Superconduct (Electro carry) (from gcsim data)" -> "Pyro vaporize carry"
[account] ~ candidates.142.lead: "Razor" -> "Yoimiya"
[account] ~ candidates.142.lineup.0: "Fischl" -> "Bennett"
[account] ~ candidates.142.lineup.2: "Razor" -> "Xingqiu"
[account] ~ candidates.142.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.142.ranking: 32.8 -> 32.7
[account] ~ candidates.142.route: "pair_model" -> "exact_community"
[account] ~ candidates.142.template: "auto_superconduct_electro_carry" -> "vaporize_pyro"
[account] ~ candidates.142.tier: "C" -> "B"
[account] ~ candidates.143.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.143.label: "Pyro vaporize carry" -> "Superconduct (Electro carry) (from gcsim data)"
[account] ~ candidates.143.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.143.lineup.0: "Bennett" -> "Diona"
[account] ~ candidates.143.lineup.1: "Layla" -> "Fischl"
[account] ~ candidates.143.lineup.2: "Xingqiu" -> "Razor"
[account] ~ candidates.143.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.143.route: "exact_community" -> "pair_model"
[account] ~ candidates.143.sd: 3.5 -> 3.4
[account] ~ candidates.143.template: "vaporize_pyro" -> "auto_superconduct_electro_carry"
[account] ~ candidates.143.tier: "B" -> "C"
[account] ~ candidates.144.label: "Superconduct (Electro carry) (from gcsim data)" -> "Electro-Charged (Hydro carry) (from gcsim data)"
[account] ~ candidates.144.lead: "Razor" -> "Kamisato Ayato"
[account] ~ candidates.144.lineup.0: "Diona" -> "Ineffa"
[account] ~ candidates.144.lineup.1: "Fischl" -> "Kaedehara Kazuha"
[account] ~ candidates.144.lineup.2: "Razor" -> "Kamisato Ayato"
[account] ~ candidates.144.template: "auto_superconduct_electro_carry" -> "auto_electro_charged_hydro_carry"
[account] ~ candidates.145.expected: 35.0 -> 34.9
[account] ~ candidates.145.label: "Electro-Charged (Hydro carry) (from gcsim data)" -> "Pyro vaporize carry"
[account] ~ candidates.145.lead: "Kamisato Ayato" -> "Yoimiya"
[account] ~ candidates.145.lineup.0: "Ineffa" -> "Bennett"
[account] ~ candidates.145.lineup.1: "Kaedehara Kazuha" -> "Diona"
[account] ~ candidates.145.lineup.2: "Kamisato Ayato" -> "Xingqiu"
[account] ~ candidates.145.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.145.ranking: 32.7 -> 32.6
[account] ~ candidates.145.template: "auto_electro_charged_hydro_carry" -> "vaporize_pyro"
[account] ~ candidates.146.expected: 34.9 -> 34.8
[account] ~ candidates.146.label: "Pyro vaporize carry" -> "Chevreuse Overloaded"
[account] ~ candidates.146.lead: "Yoimiya" -> "Chevreuse"
[account] ~ candidates.146.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.146.lineup.1: "Diona" -> "Raiden Shogun"
[account] ~ candidates.146.lineup.2: "Xingqiu" -> "Xiangling"
[account] ~ candidates.146.ranking: 32.6 -> 32.5
[account] ~ candidates.146.template: "vaporize_pyro" -> "overloaded"
[account] ~ candidates.147.expected: 34.8 -> 34.7
[account] ~ candidates.147.label: "Chevreuse Overloaded" -> "Aggravate (Quicken)"
[account] ~ candidates.147.lead: "Chevreuse" -> "Fischl"
[account] ~ candidates.147.lineup.0: "Chevreuse" -> "Fischl"
[account] ~ candidates.147.lineup.1: "Raiden Shogun" -> "Keqing"
[account] ~ candidates.147.lineup.2: "Xiangling" -> "Yaoyao"
[account] ~ candidates.147.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.147.ranking: 32.5 -> 32.4
[account] ~ candidates.147.template: "overloaded" -> "aggravate"
[account] ~ candidates.148.label: "Aggravate (Quicken)" -> "Freeze"
[account] ~ candidates.148.lead: "Fischl" -> "Kamisato Ayaka"
[account] ~ candidates.148.lineup.0: "Fischl" -> "Kamisato Ayaka"
[account] ~ candidates.148.lineup.1: "Keqing" -> "Mona"
[account] ~ candidates.148.lineup.2: "Yaoyao" -> "Shenhe"
[account] ~ candidates.148.lineup.3: "Zhongli" -> "Yun Jin"
[account] ~ candidates.148.template: "aggravate" -> "freeze"
[account] ~ candidates.149.expected: 34.7 -> 35.3
[account] ~ candidates.149.fit_source: "pairmodel" -> "model"
[account] ~ candidates.149.label: "Freeze" -> "Hyperbloom"
[account] ~ candidates.149.lead: "Kamisato Ayaka" -> "Yaoyao"
[account] ~ candidates.149.lineup.0: "Kamisato Ayaka" -> "Xingqiu"
[account] ~ candidates.149.lineup.1: "Mona" -> "Yae Miko"
[account] ~ candidates.149.lineup.2: "Shenhe" -> "Yaoyao"
[account] ~ candidates.149.lineup.3: "Yun Jin" -> "Zhongli"
[account] ~ candidates.149.ranking: 32.4 -> 32.3
[account] ~ candidates.149.sd: 3.4 -> 4.5
[account] ~ candidates.149.template: "freeze" -> "hyperbloom"
[account] ~ candidates.149.tier: "C" -> "D"
[account] ~ candidates.150.expected: 35.3 -> 34.5
[account] ~ candidates.150.fit_source: "model" -> "pairmodel"
[account] ~ candidates.150.label: "Hyperbloom" -> "Electro hypercarry"
[account] ~ candidates.150.lead: "Yaoyao" -> "Raiden Shogun"
[account] ~ candidates.150.lineup.0: "Xingqiu" -> "Bennett"
[account] ~ candidates.150.lineup.1: "Yae Miko" -> "Kaedehara Kazuha"
[account] ~ candidates.150.lineup.2: "Yaoyao" -> "Raiden Shogun"
[account] ~ candidates.150.lineup.3: "Zhongli" -> "Xiangling"
[account] ~ candidates.150.ranking: 32.3 -> 32.2
[account] ~ candidates.150.route: "pair_model" -> "exact_community"
[account] ~ candidates.150.sd: 4.5 -> 3.4
[account] ~ candidates.150.template: "hyperbloom" -> "electro_hypercarry"
[account] ~ candidates.150.tier: "D" -> "B"
[account] ~ candidates.151.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.151.label: "Electro hypercarry" -> "National (Xiangling, Xingqiu, Bennett, driver)"
[account] ~ candidates.151.lead: "Raiden Shogun" -> "Xiangling"
[account] ~ candidates.151.lineup.1: "Kaedehara Kazuha" -> "Lynette"
[account] ~ candidates.151.lineup.2: "Raiden Shogun" -> "Xiangling"
[account] ~ candidates.151.lineup.3: "Xiangling" -> "Xingqiu"
[account] ~ candidates.151.template: "electro_hypercarry" -> "national"
[account] ~ candidates.152.expected: 34.5 -> 35.3
[account] ~ candidates.152.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.152.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Melt (Pyro carry) (from gcsim data)"
[account] ~ candidates.152.lead: "Xiangling" -> "Yoimiya"
[account] ~ candidates.152.lineup.0: "Bennett" -> "Citlali"
[account] ~ candidates.152.lineup.1: "Lynette" -> "Kaedehara Kazuha"
[account] ~ candidates.152.lineup.2: "Xiangling" -> "Yoimiya"
[account] ~ candidates.152.lineup.3: "Xingqiu" -> "Zhongli"
[account] ~ candidates.152.route: "exact_community" -> "pair_model"
[account] ~ candidates.152.sd: 3.4 -> 4.5
[account] ~ candidates.152.template: "national" -> "auto_melt_pyro_carry"
[account] ~ candidates.152.tier: "B" -> "D"
[account] ~ candidates.153.expected: 35.3 -> 34.5
[account] ~ candidates.153.label: "Melt (Pyro carry) (from gcsim data)" -> "Aggravate (Quicken)"
[account] ~ candidates.153.lead: "Yoimiya" -> "Yae Miko"
[account] ~ candidates.153.lineup.0: "Citlali" -> "Fischl"
[account] ~ candidates.153.lineup.1: "Kaedehara Kazuha" -> "Yae Miko"
[account] ~ candidates.153.lineup.2: "Yoimiya" -> "Yaoyao"
[account] ~ candidates.153.sd: 4.5 -> 3.4
[account] ~ candidates.153.template: "auto_melt_pyro_carry" -> "aggravate"
[account] ~ candidates.153.tier: "D" -> "C"
[account] ~ candidates.154.expected: 34.5 -> 34.4
[account] ~ candidates.154.label: "Aggravate (Quicken)" -> "Burning (Pyro carry) (from gcsim data)"
[account] ~ candidates.154.lead: "Yae Miko" -> "Yoimiya"
[account] ~ candidates.154.lineup.0: "Fischl" -> "Bennett"
[account] ~ candidates.154.lineup.1: "Yae Miko" -> "Chiori"
[account] ~ candidates.154.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.154.ranking: 32.2 -> 32.1
[account] ~ candidates.154.template: "aggravate" -> "auto_burning_pyro_carry"
[account] ~ candidates.155.expected: 34.4 -> 34.5
[account] ~ candidates.155.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.155.label: "Burning (Pyro carry) (from gcsim data)" -> "National (Xiangling, Xingqiu, Bennett, driver)"
[account] ~ candidates.155.lead: "Yoimiya" -> "Xiangling"
[account] ~ candidates.155.lineup.1: "Chiori" -> "Kaedehara Kazuha"
[account] ~ candidates.155.lineup.2: "Yaoyao" -> "Xiangling"
[account] ~ candidates.155.lineup.3: "Yoimiya" -> "Xingqiu"
[account] ~ candidates.155.route: "pair_model" -> "exact_community"
[account] ~ candidates.155.template: "auto_burning_pyro_carry" -> "national"
[account] ~ candidates.155.tier: "C" -> "B"
[account] ~ candidates.156.expected: 34.5 -> 34.4
[account] ~ candidates.156.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.156.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Pyro vaporize carry"
[account] ~ candidates.156.lead: "Xiangling" -> "Yoimiya"
[account] ~ candidates.156.lineup.1: "Kaedehara Kazuha" -> "Xingqiu"
[account] ~ candidates.156.lineup.2: "Xiangling" -> "Yoimiya"
[account] ~ candidates.156.lineup.3: "Xingqiu" -> "Yun Jin"
[account] ~ candidates.156.route: "exact_community" -> "pair_model"
[account] ~ candidates.156.template: "national" -> "vaporize_pyro"
[account] ~ candidates.156.tier: "B" -> "C"
[account] ~ candidates.157.expected: 34.4 -> 34.3
[account] ~ candidates.157.lineup.3: "Yun Jin" -> "Zhongli"
[account] ~ candidates.158.label: "Pyro vaporize carry" -> "Melt (Cryo carry)"
[account] ~ candidates.158.lead: "Yoimiya" -> "Ganyu"
[account] ~ candidates.158.lineup.1: "Xingqiu" -> "Ganyu"
[account] ~ candidates.158.lineup.2: "Yoimiya" -> "Kaedehara Kazuha"
[account] ~ candidates.158.lineup.3: "Zhongli" -> "Xiangling"
[account] ~ candidates.158.ranking: 32.1 -> 32.0
[account] ~ candidates.158.template: "vaporize_pyro" -> "melt"
[account] ~ candidates.159.expected: 34.3 -> 34.2
[account] ~ candidates.159.label: "Melt (Cryo carry)" -> "Electro hypercarry"
[account] ~ candidates.159.lead: "Ganyu" -> "Raiden Shogun"
[account] ~ candidates.159.lineup.1: "Ganyu" -> "Raiden Shogun"
[account] ~ candidates.159.lineup.2: "Kaedehara Kazuha" -> "Sucrose"
[account] ~ candidates.159.template: "melt" -> "electro_hypercarry"
[account] ~ candidates.160.label: "Electro hypercarry" -> "Mono Cryo (from gcsim data)"
[account] ~ candidates.160.lead: "Raiden Shogun" -> "Kamisato Ayaka"
[account] ~ candidates.160.lineup.0: "Bennett" -> "Diona"
[account] ~ candidates.160.lineup.1: "Raiden Shogun" -> "Kaedehara Kazuha"
[account] ~ candidates.160.lineup.2: "Sucrose" -> "Kamisato Ayaka"
[account] ~ candidates.160.lineup.3: "Xiangling" -> "Shenhe"
[account] ~ candidates.160.template: "electro_hypercarry" -> "auto_mono_cryo"
[account] ~ candidates.161.expected: 34.2 -> 35.8
[account] ~ candidates.161.fit_source: "pairmodel" -> "synergy"
[account] ~ candidates.161.label: "Mono Cryo (from gcsim data)" -> "Freeze"
[account] ~ candidates.161.lineup.0: "Diona" -> "Iansan"
[account] ~ candidates.161.lineup.1: "Kaedehara Kazuha" -> "Kamisato Ayaka"
[account] ~ candidates.161.lineup.2: "Kamisato Ayaka" -> "Mona"
[account] ~ candidates.161.route: "pair_model" -> "role_rules"
[account] ~ candidates.161.sd: 3.4 -> 5.7
[account] ~ candidates.161.template: "auto_mono_cryo" -> "freeze"
[account] ~ candidates.161.tier: "C" -> "D"
[account] ~ candidates.162.expected: 35.8 -> 34.3
[account] ~ candidates.162.fit_source: "synergy" -> "pairmodel"
[account] ~ candidates.162.label: "Freeze" -> "Mono Cryo (from gcsim data)"
[account] ~ candidates.162.lineup.0: "Iansan" -> "Kamisato Ayaka"
...
```

## 2026-10-17 01:41, model 5.7

Phase 8 (model 5.7): Identity v2. Team labels now come from identity (primary actor, structure, central and incidental mechanics with their owners), not from the generating template, so every label changed (1,021). The team's lead in account logic is identity's primary actor where one exists (48 of 351 assessments switched on the Arlecchino roster), which moved 6 pull kinds. No power, plan or top pull changed.

1181 changed values in 35 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom, roster_raiden_national, roster_razor_chevreuse.

```
[account] ~ candidates.0.label: "Lunar-Charged (Flins hypercarry)" -> "Flins dual carry · Lunar-Charged"
[account] ~ candidates.1.label: "Lunar-Charged (Flins hypercarry)" -> "Flins and Ineffa dual carry · incidental Swirl"
[account] ~ candidates.2.label: "Lunar-Charged (Flins hypercarry)" -> "Flins dual carry · Lunar-Charged"
[account] ~ candidates.3.label: "Lunar-Charged off-field (taser style)" -> "Flins and Ineffa dual carry · incidental Lunar-Charged"
[account] ~ candidates.4.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · Overloaded"
[account] ~ candidates.5.label: "Lunar-Charged (Flins hypercarry)" -> "Flins and Ineffa dual carry · Lunar-Charged · incidental Swirl"
[account] ~ candidates.6.label: "Lunar-Charged (Flins hypercarry)" -> "Flins on-field · Lunar-Charged"
[account] ~ candidates.7.label: "Lunar-Charged (Flins hypercarry)" -> "Flins and Ineffa dual carry · Lunar-Charged"
[account] ~ candidates.8.label: "Lunar-Charged (Flins hypercarry)" -> "Ineffa and Yae Miko dual carry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.9.label: "Hyperbloom" -> "Ineffa dual carry · incidental Swirl, Hyperbloom"
[account] ~ candidates.9.lead: "Yaoyao" -> "Ineffa"
[account] ~ candidates.10.label: "Lunar-Charged (Flins hypercarry)" -> "Flins and Ineffa dual carry · Lunar-Charged"
[account] ~ candidates.11.label: "Lunar-Charged (Flins hypercarry)" -> "Ineffa dual carry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.12.label: "Chevreuse Overloaded" -> "Ineffa and Fischl dual carry · incidental Overloaded"
[account] ~ candidates.12.lead: "Chevreuse" -> "Ineffa"
[account] ~ candidates.13.label: "Lunar-Charged off-field (taser style)" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.14.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor dual carry · Overloaded"
[account] ~ candidates.15.label: "Mono Electro (from gcsim data)" -> "Yae Miko and Fischl dual carry · incidental Swirl"
[account] ~ candidates.16.label: "Chevreuse Overloaded" -> "Raiden Shogun and Ineffa dual carry · Overloaded"
[account] ~ candidates.16.lead: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.17.label: "Hyperbloom" -> "Ineffa and Fischl dual carry · Quicken"
[account] ~ candidates.17.lead: "Yaoyao" -> "Ineffa"
[account] ~ candidates.18.label: "Lunar-Charged off-field (taser style)" -> "Flins on-field · incidental Lunar-Charged"
[account] ~ candidates.19.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.20.label: "Chevreuse Overloaded" -> "Yae Miko dual carry · Overloaded from Xiangling"
[account] ~ candidates.20.lead: "Chevreuse" -> "Yae Miko"
[account] ~ candidates.21.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor dual carry · Overloaded from Xiangling"
[account] ~ candidates.22.label: "Lunar-Charged (Flins hypercarry)" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.23.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · Overloaded"
[account] ~ candidates.24.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.25.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor on-field · Vaporize · incidental Electro-Charged, Overloaded"
[account] ~ candidates.26.label: "Lunar-Charged (Flins hypercarry)" -> "Ineffa and Fischl dual carry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.27.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.28.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Overloaded"
[account] ~ candidates.29.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Overloaded, Vaporize"
[account] ~ candidates.30.label: "Hyperbloom" -> "Fischl dual carry · Quicken · incidental Swirl, Electro-Charged"
[account] ~ candidates.30.lead: "Yaoyao" -> "Fischl"
[account] ~ candidates.31.label: "Lunar-Charged (Flins hypercarry)" -> "Flins on-field · incidental Lunar-Charged"
[account] ~ candidates.32.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field"
[account] ~ candidates.33.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun hypercarry · incidental Hyperbloom, Swirl"
[account] ~ candidates.34.label: "Electro hypercarry" -> "Raiden Shogun and Ineffa dual carry · Overloaded"
[account] ~ candidates.35.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor on-field · Overloaded · incidental Electro-Charged"
[account] ~ candidates.36.label: "Lunar-Charged off-field (taser style)" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.37.label: "Superconduct (Electro carry) (from gcsim data)" -> "Razor on-field"
[account] ~ candidates.38.label: "Hyperbloom" -> "Yae Miko dual carry · incidental Swirl"
[account] ~ candidates.38.lead: "Yaoyao" -> "Yae Miko"
[account] ~ candidates.39.label: "Chevreuse Overloaded" -> "Raiden Shogun dual carry · Overloaded"
[account] ~ candidates.39.lead: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.40.label: "Electro hypercarry" -> "Raiden Shogun and Ineffa dual carry · incidental Overloaded, Swirl"
[account] ~ candidates.41.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun dual carry · Aggravate + Quicken · incidental Electro-Charged"
[account] ~ candidates.42.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun hypercarry · incidental Hyperbloom, Swirl"
[account] ~ candidates.43.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · Overloaded · incidental Swirl"
[account] ~ candidates.44.label: "Chevreuse Overloaded" -> "Yae Miko dual carry · Overloaded from Xiangling"
[account] ~ candidates.44.lead: "Chevreuse" -> "Yae Miko"
[account] ~ candidates.45.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize · incidental Overloaded, Electro-Charged"
[account] ~ candidates.46.label: "Lunar-Charged off-field (taser style)" -> "Flins on-field · incidental Lunar-Charged, Swirl"
[account] ~ candidates.47.label: "Aggravate (Quicken)" -> "Yae Miko and Fischl dual carry · Aggravate + Quicken · incidental Swirl"
[account] ~ candidates.48.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Overloaded"
[account] ~ candidates.49.label: "Melt (Cryo carry)" -> "Ganyu dual carry · Melt · incidental Overloaded"
[account] ~ candidates.50.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · Overloaded"
[account] ~ candidates.51.label: "Hyperbloom" -> "Ineffa hypercarry"
[account] ~ candidates.51.lead: "Yaoyao" -> "Ineffa"
[account] ~ candidates.52.label: "Mono Cryo (from gcsim data)" -> "Kamisato Ayaka hypercarry · incidental Swirl"
[account] ~ candidates.53.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.54.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze · incidental Swirl"
[account] ~ candidates.55.label: "Chevreuse Overloaded" -> "Chevreuse dual carry · Overloaded from Fischl"
[account] ~ candidates.56.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.57.label: "Chevreuse Overloaded" -> "Raiden Shogun dual carry · Overloaded from Xiangling"
[account] ~ candidates.57.lead: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.58.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.59.label: "Superconduct (Electro carry) (from gcsim data)" -> "Razor dual carry · incidental Superconduct"
[account] ~ candidates.60.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Melt + Vaporize"
[account] ~ candidates.61.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.62.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya and Fischl dual carry · Overloaded · incidental Swirl"
[account] ~ candidates.63.label: "Mono Electro (from gcsim data)" -> "No single carry spread damage · incidental Swirl"
[account] ~ candidates.64.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.65.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.66.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.67.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.68.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.69.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize"
[account] ~ candidates.70.label: "Mono Geo" -> "No single carry dual carry"
[account] ~ candidates.71.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun dual carry · Quicken + Hyperbloom + Aggravate · incidental Electro-Charged"
[account] ~ candidates.72.label: "Aggravate (Quicken)" -> "Yae Miko and Fischl dual carry · Aggravate + Quicken + Overloaded"
[account] ~ candidates.73.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field · Overloaded · incidental Superconduct"
[account] ~ candidates.74.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · incidental Overloaded"
[account] ~ candidates.75.label: "International (Hydro carry with Pyro)" -> "Tartaglia dual carry · Vaporize · incidental Swirl"
[account] ~ candidates.76.label: "Hyperbloom" -> "Fischl hypercarry · Quicken · incidental Aggravate, Swirl"
[account] ~ candidates.76.lead: "Yaoyao" -> "Fischl"
[account] ~ candidates.77.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun hypercarry · Hyperbloom · incidental Electro-Charged, Quicken"
[account] ~ candidates.78.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize"
[account] ~ candidates.79.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.80.label: "Electro hypercarry" -> "Raiden Shogun dual carry · incidental Overloaded"
[account] ~ candidates.81.label: "Aggravate (Quicken)" -> "Raiden Shogun and Fischl dual carry · Aggravate + Quicken · incidental Swirl"
[account] ~ candidates.82.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Electro-Charged"
[account] ~ candidates.83.label: "Mono Cryo (from gcsim data)" -> "Kamisato Ayaka hypercarry · incidental Swirl"
[account] ~ candidates.84.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor on-field"
[account] ~ candidates.85.label: "Overloaded (Electro carry) (from gcsim data)" -> "Razor dual carry · incidental Overloaded"
[account] ~ candidates.86.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · incidental Overloaded, Swirl"
[account] ~ candidates.87.label: "Melt (Cryo carry)" -> "Kamisato Ayaka and Xiangling dual carry · Melt · incidental Swirl"
[account] ~ candidates.88.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.89.label: "Aggravate (Quicken)" -> "Razor on-field · Quicken · incidental Aggravate"
[account] ~ candidates.90.label: "Aggravate (Quicken)" -> "Fischl dual carry · Aggravate + Quicken"
[account] ~ candidates.91.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun hypercarry · incidental Hyperbloom"
[account] ~ candidates.92.label: "Melt (Cryo carry)" -> "Ganyu on-field · Melt"
[account] ~ candidates.93.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.94.label: "Chevreuse Overloaded" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.94.lead: "Chevreuse" -> "Yoimiya"
[account] ~ candidates.95.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Overloaded, Vaporize"
[account] ~ candidates.96.label: "Aggravate (Quicken)" -> "Razor and Fischl dual carry · Quicken · incidental Aggravate, Swirl"
[account] ~ candidates.97.label: "Mono Cryo (from gcsim data)" -> "Kamisato Ayaka hypercarry · incidental Swirl"
[account] ~ candidates.98.label: "Electro hypercarry" -> "Raiden Shogun and Fischl dual carry · incidental Overloaded, Swirl"
[account] ~ candidates.99.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.100.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.101.label: "Aggravate (Quicken)" -> "Razor dual carry · Quicken · incidental Overloaded, Aggravate"
[account] ~ candidates.102.label: "Electro-Charged (Electro carry) (from gcsim data)" -> "Razor dual carry · Vaporize · incidental Electro-Charged"
[account] ~ candidates.103.label: "Aggravate (Quicken)" -> "No single carry dual carry · Aggravate + Overloaded + Quicken"
[account] ~ candidates.104.label: "Hyperbloom" -> "No single carry dual carry · Aggravate + Quicken · incidental Electro-Charged"
[account] ~ candidates.105.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.106.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · incidental Overloaded"
[account] ~ candidates.107.label: "Mono Electro (from gcsim data)" -> "Yae Miko and Fischl dual carry · incidental Swirl"
[account] ~ candidates.108.label: "Mono Cryo (from gcsim data)" -> "Kamisato Ayaka hypercarry"
[account] ~ candidates.109.label: "Chevreuse Overloaded" -> "Yoimiya on-field · Overloaded from Raiden Shogun"
[account] ~ candidates.109.lead: "Chevreuse" -> "Yoimiya"
[account] ~ candidates.110.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun dual carry · Hyperbloom · incidental Electro-Charged, Swirl"
[account] ~ candidates.111.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun hypercarry · Hyperbloom · incidental Electro-Charged, Quicken"
[account] ~ candidates.112.label: "Electro hypercarry" -> "Raiden Shogun hypercarry · incidental Overloaded"
[account] ~ candidates.113.label: "Melt (Cryo carry)" -> "Ganyu hypercarry · Melt"
[account] ~ candidates.114.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.115.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · incidental Overloaded"
[account] ~ candidates.116.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize"
[account] ~ candidates.117.label: "Aggravate (Quicken)" -> "Fischl and Keqing dual carry · Aggravate + Quicken + Overloaded"
[account] ~ candidates.117.lead: "Keqing" -> "Fischl"
[account] ~ candidates.118.label: "Hyperbloom" -> "Fischl and Xingqiu dual carry · Quicken · incidental Electro-Charged"
[account] ~ candidates.118.lead: "Yaoyao" -> "Fischl"
[account] ~ candidates.119.label: "Mono Pyro (from gcsim data)" -> "Diluc dual carry"
[account] ~ candidates.120.label: "Superconduct (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Superconduct, Overloaded"
[account] ~ candidates.121.label: "Geo carry (from gcsim data)" -> "Chiori hypercarry"
[account] ~ candidates.122.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.123.label: "Melt (Cryo carry)" -> "Kamisato Ayaka and Xiangling dual carry · Melt"
[account] ~ candidates.124.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling hypercarry · Vaporize"
[account] ~ candidates.125.label: "Superconduct (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Superconduct"
[account] ~ candidates.126.label: "Geo carry (from gcsim data)" -> "Chiori dual carry · incidental Overloaded"
[account] ~ candidates.127.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Vaporize"
[account] ~ candidates.128.label: "Overloaded (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry · incidental Overloaded"
[account] ~ candidates.129.label: "Geo carry (from gcsim data)" -> "Ningguang on-field"
[account] ~ candidates.130.label: "Anemo carry (from gcsim data)" -> "No single carry dual carry · Vaporize · incidental Overloaded, Electro-Charged"
[account] ~ candidates.131.label: "Electro hypercarry" -> "Yae Miko and Raiden Shogun dual carry · incidental Overloaded"
[account] ~ candidates.131.lead: "Raiden Shogun" -> "Yae Miko"
[account] ~ candidates.132.label: "Anemo carry (from gcsim data)" -> "Shikanoin Heizou and Xiangling dual carry · Overloaded · incidental Swirl"
[account] ~ candidates.133.label: "Melt (Cryo carry)" -> "Ganyu on-field · Melt"
[account] ~ candidates.134.label: "Geo carry (from gcsim data)" -> "Chiori dual carry · incidental Superconduct"
[account] ~ candidates.135.label: "Hyperbloom" -> "Fischl and Xingqiu dual carry · Quicken · incidental Electro-Charged"
[account] ~ candidates.135.lead: "Yaoyao" -> "Fischl"
[account] ~ candidates.136.label: "Mono Pyro (from gcsim data)" -> "Diluc on-field"
[account] ~ candidates.137.label: "Anemo carry (from gcsim data)" -> "Shikanoin Heizou and Fischl dual carry · Vaporize · incidental Swirl, Overloaded"
[account] ~ candidates.138.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling and Raiden Shogun dual carry · Vaporize · incidental Overloaded"
[account] ~ candidates.139.label: "Geo carry (from gcsim data)" -> "Ningguang on-field"
[account] ~ candidates.140.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize"
[account] ~ candidates.141.label: "Superconduct (Electro carry) (from gcsim data)" -> "Razor on-field · incidental Superconduct"
[account] ~ candidates.142.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Melt + Vaporize · incidental Freeze"
[account] ~ candidates.143.label: "Superconduct (Electro carry) (from gcsim data)" -> "Razor on-field"
[account] ~ candidates.144.label: "Electro-Charged (Hydro carry) (from gcsim data)" -> "Kamisato Ayato and Ineffa dual carry · incidental Swirl, Lunar-Charged"
[account] ~ candidates.145.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Melt + Vaporize + Freeze"
[account] ~ candidates.146.label: "Chevreuse Overloaded" -> "Yoimiya and Raiden Shogun dual carry · Overloaded"
[account] ~ candidates.146.lead: "Chevreuse" -> "Yoimiya"
[account] ~ candidates.147.label: "Aggravate (Quicken)" -> "Fischl and Keqing dual carry · Aggravate + Quicken"
[account] ~ candidates.148.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.149.label: "Hyperbloom" -> "Yae Miko dual carry"
[account] ~ candidates.149.lead: "Yaoyao" -> "Yae Miko"
[account] ~ candidates.150.label: "Electro hypercarry" -> "Xiangling and Raiden Shogun dual carry · Overloaded · incidental Swirl"
[account] ~ candidates.150.lead: "Raiden Shogun" -> "Xiangling"
[account] ~ candidates.151.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize · incidental Swirl"
[account] ~ candidates.152.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt · incidental Swirl"
[account] ~ candidates.153.label: "Aggravate (Quicken)" -> "Yae Miko and Yae Miko dual carry · Aggravate + Quicken"
[account] ~ candidates.154.label: "Burning (Pyro carry) (from gcsim data)" -> "Yoimiya dual carry"
[account] ~ candidates.155.label: "National (Xiangling, Xingqiu, Bennett, driver)" -> "Xiangling dual carry · Vaporize"
[account] ~ candidates.156.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Vaporize"
[account] ~ candidates.157.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Vaporize"
[account] ~ candidates.158.label: "Melt (Cryo carry)" -> "Ganyu dual carry · Melt · incidental Swirl"
[account] ~ candidates.159.label: "Electro hypercarry" -> "Raiden Shogun and Xiangling dual carry · incidental Overloaded"
[account] ~ candidates.160.label: "Mono Cryo (from gcsim data)" -> "Kamisato Ayaka hypercarry · incidental Swirl"
[account] ~ candidates.161.label: "Freeze" -> "Team · Freeze"
[account] ~ candidates.162.label: "Mono Cryo (from gcsim data)" -> "Kamisato Ayaka hypercarry"
[account] ~ candidates.163.label: "Mono Electro (from gcsim data)" -> "Yae Miko and Fischl dual carry"
[account] ~ candidates.164.label: "Anemo carry (from gcsim data)" -> "Kaedehara Kazuha hypercarry · Melt"
[account] ~ candidates.165.label: "Freeze" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.166.label: "Melt (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · Melt · incidental Swirl"
[account] ~ candidates.167.label: "Melt (Cryo carry)" -> "Ganyu dual carry · Melt"
[account] ~ candidates.168.label: "Pyro vaporize carry" -> "Yoimiya hypercarry · Vaporize"
[account] ~ candidates.169.label: "Burning (Pyro carry) (from gcsim data)" -> "Yoimiya hypercarry · incidental Swirl"
[account] ~ candidates.170.label: "Geo carry (from gcsim data)" -> "Ningguang on-field"
[account] ~ candidates.171.label: "Hyperbloom (Electro carry) (from gcsim data)" -> "Raiden Shogun hypercarry · Hyperbloom + Freeze · incidental Electro-Charged, Quicken"
[account] ~ candidates.172.label: "Anemo carry (from gcsim data)" -> "Kaedehara Kazuha dual carry · Overloaded"
[account] ~ candidates.173.label: "Mono Geo" -> "Noelle and Chiori dual carry"
[account] ~ candidates.174.label: "Geo carry (from gcsim data)" -> "Chiori and Yae Miko dual carry"
[account] ~ candidates.175.label: "Electro hypercarry" -> "Raiden Shogun and Yae Miko dual carry · incidental Overloaded"
[account] ~ candidates.176.label: "Anemo carry (from gcsim data)" -> "Shikanoin Heizou and Xiangling dual carry · Vaporize · incidental Swirl"
[account] ~ candidates.176.template: "auto_anemo_carry" -> "national"
[account] ~ candidates.177.label: "Mono Geo" -> "Noelle and Ineffa dual carry"
...
```

## 2026-10-17 12:28, model 5.8

Phase 9 (model 5.8): Validity v2 + typicality. Teams are rejected only for mechanical reasons (template slots, required roles, the mechanic's elements; Chevreuse's all Pyro/Electro restriction is part of her template). The learned resemblance rules (elements never seen in an archetype, on-field count, application minimums, a carry's usual teammate elements) and the damage-owner check no longer reject: they became typicality findings that widen extrapolated sd by 84% each (measured on simulated lineups: held-out pair-model error 18.0% with a finding against 9.8% without, n = 17 vs 3,741), and identity. Candidates in these accounts grew from 1,021 to 1,369; no existing team's power moved. 11 plans changed, mostly where previously rejected functional teams are now available (Flins keeps Aino on the small account, 90.5 -> 96.6; rosters that had no plan now have one, e.g. Kazuha / Raiden / Shenhe / Citlali); 10 top pulls and 44 pull kinds changed. The user's plan and top pull are unchanged.

1667 changed values in 38 outputs: - roster_no_skirk_without_hydro, account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka.

```
[account] ~ candidates: [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank
[account] ~ carries_for_supports.2.1.1: "Bennett" -> "Chevreuse"
[account] ~ carries_for_supports.2.1.2: "Chevreuse" -> "Fischl"
[account] ~ carries_for_supports.2.1.3: "Fischl" -> "Razor"
[account] ~ carries_for_supports.2.2: 64.1 -> 65.9
[account] ~ carries_for_supports.3.0: "Skirk" -> "Sandrone"
[account] ~ carries_for_supports.3.1.0: "Citlali" -> "Bennett"
[account] ~ carries_for_supports.3.1.1: "Mona" -> "Sandrone"
[account] ~ carries_for_supports.3.1.2: "Skirk" -> "Shenhe"
[account] ~ carries_for_supports.3.1.3: "Sucrose" -> "Yae Miko"
[account] ~ carries_for_supports.3.2: 62.5 -> 62.2
[account] ~ carries_for_supports.4.0: "Sandrone" -> "Gaming"
[account] ~ carries_for_supports.4.1.0: "Fischl" -> "Bennett"
[account] ~ carries_for_supports.4.1.1: "Sandrone" -> "Gaming"
[account] ~ carries_for_supports.4.1.2: "Yae Miko" -> "Rosaria"
[account] ~ carries_for_supports.4.1.3: "Zhongli" -> "Sucrose"
[account] ~ carries_for_supports.4.2: 62.2 -> 61.5
[account] ~ pulls.1.best_team.1: "Chevreuse" -> "Citlali"
[account] ~ pulls.1.best_team.2: "Durin" -> "Kaedehara Kazuha"
[account] ~ pulls.1.best_team.3: "Fischl" -> "Mavuika"
[account] ~ pulls.1.expected: 9.9 -> 13.4
[account] ~ pulls.1.gain: 10.7 -> 12.5
[account] ~ pulls.1.name: "Durin" -> "Mavuika"
[account] ~ pulls.1.sd: 8.3 -> 10.5
[account] ~ pulls.1.tier: "B" -> "C"
[account] ~ pulls.2.best_team.1: "Citlali" -> "Chevreuse"
[account] ~ pulls.2.best_team.2: "Mavuika" -> "Durin"
[account] ~ pulls.2.best_team.3: "Zhongli" -> "Fischl"
[account] ~ pulls.2.expected: 11.1 -> 9.9
[account] ~ pulls.2.gain: 10.4 -> 10.7
[account] ~ pulls.2.name: "Mavuika" -> "Durin"
[account] ~ pulls.2.sd: 9.9 -> 8.3
[account] ~ pulls.2.tier: "C" -> "B"
[account] ~ pulls.6.best_team.0: "Bennett" -> "Nicole"
[account] ~ pulls.6.best_team.1: "Chevreuse" -> "Raiden Shogun"
[account] ~ pulls.6.best_team.2: "Citlali" -> "Xingqiu"
[account] ~ pulls.6.best_team.3: "Lyney" -> "Yaoyao"
[account] ~ pulls.6.expected: 6.6 -> 7.5
[account] ~ pulls.6.gain: 6.1 -> 7.0
[account] ~ pulls.6.kind: "new archetype" -> "fills a gap"
[account] ~ pulls.6.name: "Lyney" -> "Nicole"
[account] ~ pulls.6.sd: 10.2 -> 4.0
[account] ~ pulls.7.best_team.0: "Neuvillette" -> "Bennett"
[account] ~ pulls.7.best_team.1: "Raiden Shogun" -> "Chevreuse"
[account] ~ pulls.7.best_team.2: "Xingqiu" -> "Citlali"
[account] ~ pulls.7.best_team.3: "Yaoyao" -> "Lyney"
[account] ~ pulls.7.expected: 4.2 -> 6.6
[account] ~ pulls.7.gain: 3.9 -> 6.1
[account] ~ pulls.7.kind: "fills a gap" -> "new archetype"
[account] ~ pulls.7.name: "Neuvillette" -> "Lyney"
[account] ~ pulls.7.sd: 3.8 -> 10.2
[account] ~ pulls.8.best_team.0: "Escoffier" -> "Arlecchino"
[account] ~ pulls.8.best_team.1: "Kamisato Ayaka" -> "Chevreuse"
[account] ~ pulls.8.best_team.2: "Mona" -> "Fischl"
[account] ~ pulls.8.best_team.3: "Shenhe" -> "Razor"
[account] ~ pulls.8.expected: 4.1 -> 6.8
[account] ~ pulls.8.gain: 3.8 -> 5.6
[account] ~ pulls.8.kind: "fills a gap" -> "new archetype"
[account] ~ pulls.8.name: "Escoffier" -> "Arlecchino"
[account] ~ pulls.8.sd: 2.8 -> 10.5
[account] ~ pulls.9.best_team.0: "Prune" -> "Neuvillette"
[account] ~ pulls.9.expected: 4.0 -> 4.2
[account] ~ pulls.9.gain: 3.8 -> 3.9
[account] ~ pulls.9.kind: "upgrade" -> "fills a gap"
[account] ~ pulls.9.name: "Prune" -> "Neuvillette"
[account] ~ pulls.10.best_team.0: "Arlecchino" -> "Escoffier"
[account] ~ pulls.10.best_team.1: "Bennett" -> "Kamisato Ayaka"
[account] ~ pulls.10.best_team.2: "Chevreuse" -> "Mona"
[account] ~ pulls.10.best_team.3: "Fischl" -> "Shenhe"
[account] ~ pulls.10.expected: 2.5 -> 4.1
[account] ~ pulls.10.gain: 3.6 -> 3.8
[account] ~ pulls.10.kind: "new archetype" -> "fills a gap"
[account] ~ pulls.10.name: "Arlecchino" -> "Escoffier"
[account] ~ pulls.10.sd: 8.0 -> 2.8
[account] ~ pulls.10.tier: "B" -> "C"
[account] ~ pulls.11.best_team.0: "Furina" -> "Prune"
[account] ~ pulls.11.expected: 3.7 -> 4.0
[account] ~ pulls.11.gain: 3.5 -> 3.8
[account] ~ pulls.11.name: "Furina" -> "Prune"
[account] ~ pulls.12.best_team.0: "Chevreuse" -> "Furina"
[account] ~ pulls.12.best_team.1: "Nicole" -> "Raiden Shogun"
[account] ~ pulls.12.best_team.2: "Xiangling" -> "Xingqiu"
[account] ~ pulls.12.best_team.3: "Yae Miko" -> "Yaoyao"
[account] ~ pulls.12.expected: 3.6 -> 3.7
[account] ~ pulls.12.kind: "fills a gap" -> "upgrade"
[account] ~ pulls.12.name: "Nicole" -> "Furina"
[account] ~ pulls.12.sd: 9.9 -> 3.8
[account] ~ pulls.15.best_team.0: "Raiden Shogun" -> "Bennett"
[account] ~ pulls.15.best_team.1: "Varka" -> "Citlali"
[account] ~ pulls.15.best_team.2: "Xingqiu" -> "Gaming"
[account] ~ pulls.15.best_team.3: "Zhongli" -> "Rosaria"
[account] ~ pulls.15.expected: 2.8 -> 2.6
[account] ~ pulls.15.gain: 2.6 -> 2.5
[account] ~ pulls.15.name: "Varka" -> "Gaming"
[account] ~ pulls.15.sd: 3.7 -> 9.3
[account] ~ pulls.16.best_team.0: "Bennett" -> "Raiden Shogun"
[account] ~ pulls.16.best_team.1: "Citlali" -> "Xilonen"
[account] ~ pulls.16.best_team.2: "Gaming" -> "Xingqiu"
[account] ~ pulls.16.best_team.3: "Rosaria" -> "Yaoyao"
[account] ~ pulls.16.expected: 2.6 -> 1.8
[account] ~ pulls.16.gain: 2.5 -> 1.7
[account] ~ pulls.16.kind: "new archetype" -> "upgrade"
[account] ~ pulls.16.name: "Gaming" -> "Xilonen"
[account] ~ pulls.16.sd: 9.3 -> 3.7
[account] ~ pulls.17.best_team.0: "Raiden Shogun" -> "Kirara"
[account] ~ pulls.17.best_team.1: "Xilonen" -> "Raiden Shogun"
[account] ~ pulls.17.expected: 1.8 -> 1.7
[account] ~ pulls.17.gain: 1.7 -> 1.6
[account] ~ pulls.17.kind: "upgrade" -> "fills a gap"
[account] ~ pulls.17.name: "Xilonen" -> "Kirara"
[account] ~ pulls.17.sd: 3.7 -> 3.6
[account] ~ pulls.18.best_team.0: "Kirara" -> "Raiden Shogun"
[account] ~ pulls.18.best_team.1: "Raiden Shogun" -> "Varka"
[account] ~ pulls.18.best_team.3: "Yaoyao" -> "Zhongli"
[account] ~ pulls.18.expected: 1.7 -> 2.8
[account] ~ pulls.18.gain: 1.6 -> 1.2
[account] ~ pulls.18.kind: "fills a gap" -> "new archetype"
[account] ~ pulls.18.name: "Kirara" -> "Varka"
[account] ~ pulls.18.sd: 3.6 -> 5.4
[account] ~ pulls.24.best_team.0: "Kamisato Ayaka" -> "Citlali"
[account] ~ pulls.24.best_team.1: "Mona" -> "Lynette"
[account] ~ pulls.24.best_team.2: "Shenhe" -> "Mualani"
[account] ~ pulls.24.best_team.3: "Yelan" -> "Zhongli"
[account] ~ pulls.24.expected: 0.3 -> 0.6
[account] ~ pulls.24.gain: 0.3 -> 0.6
[account] ~ pulls.24.kind: "upgrade" -> "new archetype"
[account] ~ pulls.24.name: "Yelan" -> "Mualani"
[account] ~ pulls.25.best_team.0: "Citlali" -> "Kamisato Ayaka"
[account] ~ pulls.25.best_team.1: "Lynette" -> "Mona"
[account] ~ pulls.25.best_team.2: "Mona" -> "Shenhe"
[account] ~ pulls.25.best_team.3: "Mualani" -> "Yelan"
[account] ~ pulls.25.expected: 0.5 -> 0.3
[account] ~ pulls.25.gain: 0.2 -> 0.3
[account] ~ pulls.25.kind: "new archetype" -> "upgrade"
[account] ~ pulls.25.name: "Mualani" -> "Yelan"
[account] ~ pulls.25.sd: 1.7 -> 1.5
[account] ~ pulls.25.tier: "D" -> "C"
[account] ~ pulls.29.best_team.1: "Fischl" -> "Flins"
[account] ~ pulls.29.best_team.2: "Raiden Shogun" -> "Ineffa"
[account] ~ pulls.30.best_team.0: "Charlotte" -> "Aino"
[account] ~ pulls.30.best_team.1: "Chevreuse" -> "Charlotte"
[account] ~ pulls.30.best_team.2: "Fischl" -> "Flins"
[account] ~ pulls.30.best_team.3: "Razor" -> "Ineffa"
[account] ~ pulls.35.best_team.0: "Emilie" -> "Aino"
[account] ~ pulls.35.best_team.1: "Ineffa" -> "Emilie"
[account] ~ pulls.35.best_team.2: "Sucrose" -> "Flins"
[account] ~ pulls.35.best_team.3: "Xingqiu" -> "Ineffa"
[account] ~ pulls.36.best_team.1: "Citlali" -> "Eula"
[account] ~ pulls.36.best_team.2: "Eula" -> "Ineffa"
[account] ~ pulls.37.best_team.1: "Freminet" -> "Chiori"
[account] ~ pulls.37.best_team.2: "Ineffa" -> "Freminet"
[account] ~ pulls.37.best_team.3: "Xiangling" -> "Rosaria"
[account] ~ pulls.40.best_team.1: "Ifa" -> "Flins"
[account] ~ pulls.40.best_team.2: "Ineffa" -> "Ifa"
[account] ~ pulls.40.best_team.3: "Yae Miko" -> "Ineffa"
[account] ~ pulls.43.best_team.0: "Bennett" -> "Citlali"
[account] ~ pulls.43.best_team.2: "Ineffa" -> "Kaveh"
[account] ~ pulls.43.best_team.3: "Kaveh" -> "Raiden Shogun"
[account] ~ pulls.45.best_team.0: "Chevreuse" -> "Bennett"
[account] ~ pulls.45.best_team.1: "Fischl" -> "Chevreuse"
[account] ~ pulls.45.best_team.2: "Ineffa" -> "Klee"
[account] ~ pulls.45.best_team.3: "Klee" -> "Razor"
[account] ~ pulls.50.best_team.0: "Odette" -> "Aino"
[account] ~ pulls.50.best_team.1: "Razor" -> "Flins"
[account] ~ pulls.50.best_team.2: "Yae Miko" -> "Ineffa"
[account] ~ pulls.50.best_team.3: "Yaoyao" -> "Odette"
[account] ~ pulls.53.best_team.1: "Mona" -> "Tighnari"
[account] ~ pulls.53.best_team.2: "Tighnari" -> "Yae Miko"
[account] ~ pulls.53.best_team.3: "Yaoyao" -> "Zhongli"
[account] ~ pulls.57.best_team.0: "Bennett" -> "Aino"
[account] ~ pulls.57.best_team.1: "Ineffa" -> "Flins"
[account] ~ pulls.57.best_team.2: "Wriothesley" -> "Ineffa"
[account] ~ pulls.57.best_team.3: "Xiangling" -> "Wriothesley"
[roster_flins_lunar_core] ~ candidates: [{"expected": 100.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged · incidental Swirl", "lead": "Flins", "lineup": ["Columbina", "Flins", "I -> [{"expected": 100.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged · incidental Swirl", "lead": "Flins", "lineup": ["Columbina", "Flins", "I
[roster_flins_lunar_core] ~ carries_for_supports.0.0: "Varka" -> "Gaming"
[roster_flins_lunar_core] ~ carries_for_supports.0.1.0: "Bennett" -> "Columbina"
[roster_flins_lunar_core] ~ carries_for_supports.0.1.1: "Columbina" -> "Gaming"
[roster_flins_lunar_core] ~ carries_for_supports.0.1.3: "Varka" -> "Sucrose"
[roster_flins_lunar_core] ~ carries_for_supports.0.2: 86.1 -> 82.1
[roster_flins_lunar_core] ~ carries_for_supports.1.0: "Gaming" -> "Mavuika"
[roster_flins_lunar_core] ~ carries_for_supports.1.1.0: "Columbina" -> "Bennett"
[roster_flins_lunar_core] ~ carries_for_supports.1.1.1: "Gaming" -> "Columbina"
[roster_flins_lunar_core] ~ carries_for_supports.1.1.3: "Sucrose" -> "Mavuika"
[roster_flins_lunar_core] ~ carries_for_supports.1.2: 82.1 -> 81.9
[roster_flins_lunar_core] ~ carries_for_supports.2.0: "Mavuika" -> "Varka"
[roster_flins_lunar_core] ~ carries_for_supports.2.1.3: "Mavuika" -> "Varka"
[roster_flins_lunar_core] ~ carries_for_supports.2.2: 81.9 -> 81.0
[roster_flins_lunar_core] ~ pulls: [{"best_team": ["Aino", "Bennett", "Varka", "Xingqiu"], "expected": 56.4, "gain": 51.5, "kind": "new archetype", "name": "Varka", "sd": 7.3, "tier": "D"}, {"bes -> [{"best_team": ["Aino", "Bennett", "Varka", "Xingqiu"], "expected": 56.4, "gain": 47.4, "kind": "new archetype", "name": "Varka", "sd": 13.3, "tier": "D"}, {"be
[roster_flins_aino_over_xingqiu] ~ candidates: [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.0.1.3: "Xingqiu" -> "Sucrose"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.0.2: 63.4 -> 69.4
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.1.0: "Lyney" -> "Gaming"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.1.1.0: "Aino" -> "Bennett"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.1.1.1: "Bennett" -> "Gaming"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.1.1.3: "Lyney" -> "Sucrose"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.1.2: 60.6 -> 62.2
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.2.0: "Varka" -> "Lyney"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.2.1.0: "Aino" -> "Bennett"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.2.1.2: "Varka" -> "Lyney"
[roster_flins_aino_over_xingqiu] ~ carries_for_supports.2.1.3: "Zhongli" -> "Sucrose"
...
```

## 2026-10-17 12:55, model 5.9

Phase 10 (model 5.9): power and uncertainty separated. The decision policy (gtc/decision.py) holds the risk weight (decision.risk, unchanged 0.674) and compare() with a calibrated tie zone (claims of 'better' only from P >= 0.80, where held-out claims are right 85% of the time). Pair-model sd now follows each lineup's functional distance to its nearest simulation (gtc/distance.py; held-out coverage 72% / 94% against 70% / 93% flat; members changed and the least simulated member's data drive it), so Varka, with one simulated lineup, gets a wide sd and drops from the top of 5 pull lists. The swap estimator and its parameters are deleted; the 7 teams it valued fall to the calibrated role model (largest move -5.8), none in a plan. 2 plans, 7 top pulls, 9 pull kinds changed; the user's plan and top pull are unchanged.

9203 changed values in 37 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom.

```
[account] ~ candidates.1.ranking: 65.4 -> 64.4
[account] ~ candidates.1.sd: 6.9 -> 8.4
[account] ~ candidates.2.ranking: 64.1 -> 62.8
[account] ~ candidates.2.sd: 6.7 -> 8.7
[account] ~ candidates.3.expected: 65.4 -> 64.8
[account] ~ candidates.3.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.3.label: "Flins and Ineffa dual carry · incidental Lunar-Charged" -> "Razor on-field · Overloaded"
[account] ~ candidates.3.lead: "Flins" -> "Razor"
[account] ~ candidates.3.lineup.0: "Aino" -> "Bennett"
[account] ~ candidates.3.lineup.1: "Flins" -> "Chevreuse"
[account] ~ candidates.3.lineup.2: "Ineffa" -> "Fischl"
[account] ~ candidates.3.lineup.3: "Xingqiu" -> "Razor"
[account] ~ candidates.3.ranking: 61.0 -> 60.5
[account] ~ candidates.3.route: "pair_model" -> "exact_community"
[account] ~ candidates.3.template: "lunar_charged_offfield" -> "auto_overloaded_electro_carry"
[account] ~ candidates.3.tier: "C" -> "B"
[account] ~ candidates.4.expected: 64.8 -> 65.4
[account] ~ candidates.4.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.4.label: "Razor on-field · Overloaded" -> "Flins and Ineffa dual carry · incidental Lunar-Charged"
[account] ~ candidates.4.lead: "Razor" -> "Flins"
[account] ~ candidates.4.lineup.0: "Bennett" -> "Aino"
[account] ~ candidates.4.lineup.1: "Chevreuse" -> "Flins"
[account] ~ candidates.4.lineup.2: "Fischl" -> "Ineffa"
[account] ~ candidates.4.lineup.3: "Razor" -> "Xingqiu"
[account] ~ candidates.4.ranking: 60.5 -> 59.8
[account] ~ candidates.4.route: "exact_community" -> "pair_model"
[account] ~ candidates.4.sd: 6.4 -> 8.3
[account] ~ candidates.4.template: "auto_overloaded_electro_carry" -> "lunar_charged_offfield"
[account] ~ candidates.4.tier: "B" -> "C"
[account] ~ candidates.5.ranking: 59.8 -> 59.0
[account] ~ candidates.5.sd: 6.3 -> 7.5
[account] ~ candidates.7.ranking: 57.8 -> 56.9
[account] ~ candidates.7.sd: 6.1 -> 7.4
[account] ~ candidates.8.ranking: 56.5 -> 56.0
[account] ~ candidates.8.sd: 5.9 -> 6.8
[account] ~ candidates.9.expected: 61.8 -> 59.2
[account] ~ candidates.9.fit_source: "model" -> "pairmodel"
[account] ~ candidates.9.label: "Ineffa dual carry · incidental Swirl, Hyperbloom" -> "Ineffa dual carry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.9.lineup.0: "Ineffa" -> "Aino"
[account] ~ candidates.9.lineup.1: "Sucrose" -> "Fischl"
[account] ~ candidates.9.lineup.2: "Xingqiu" -> "Ineffa"
[account] ~ candidates.9.lineup.3: "Yaoyao" -> "Sucrose"
[account] ~ candidates.9.ranking: 56.4 -> 54.7
[account] ~ candidates.9.sd: 8.0 -> 6.8
[account] ~ candidates.9.template: "hyperbloom" -> "lunar_charged"
[account] ~ candidates.9.tier: "D" -> "C"
[account] ~ candidates.10.expected: 59.2 -> 61.8
[account] ~ candidates.10.fit_source: "pairmodel" -> "model"
[account] ~ candidates.10.label: "Ineffa dual carry · incidental Lunar-Charged, Swirl" -> "Ineffa dual carry · incidental Swirl, Hyperbloom"
[account] ~ candidates.10.lineup.0: "Aino" -> "Ineffa"
[account] ~ candidates.10.lineup.1: "Fischl" -> "Sucrose"
[account] ~ candidates.10.lineup.2: "Ineffa" -> "Xingqiu"
[account] ~ candidates.10.lineup.3: "Sucrose" -> "Yaoyao"
[account] ~ candidates.10.ranking: 55.3 -> 52.1
[account] ~ candidates.10.sd: 5.8 -> 14.4
[account] ~ candidates.10.template: "lunar_charged" -> "hyperbloom"
[account] ~ candidates.10.tier: "C" -> "D"
[account] ~ candidates.11.expected: 59.8 -> 56.2
[account] ~ candidates.11.label: "Flins and Ineffa dual carry · Lunar-Charged" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.11.lead: "Flins" -> "Ineffa"
[account] ~ candidates.11.lineup.1: "Flins" -> "Ineffa"
[account] ~ candidates.11.lineup.2: "Ineffa" -> "Sucrose"
[account] ~ candidates.11.lineup.3: "Zhongli" -> "Xingqiu"
[account] ~ candidates.11.ranking: 52.6 -> 51.5
[account] ~ candidates.11.sd: 10.8 -> 7.0
[account] ~ candidates.11.template: "lunar_charged" -> "lunar_charged_offfield"
[account] ~ candidates.12.expected: 56.2 -> 55.4
[account] ~ candidates.12.label: "Ineffa hypercarry · incidental Lunar-Charged, Swirl" -> "Razor dual carry · Overloaded"
[account] ~ candidates.12.lead: "Ineffa" -> "Razor"
[account] ~ candidates.12.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.12.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.12.lineup.2: "Sucrose" -> "Razor"
[account] ~ candidates.12.lineup.3: "Xingqiu" -> "Yae Miko"
[account] ~ candidates.12.ranking: 52.5 -> 51.3
[account] ~ candidates.12.sd: 5.5 -> 6.0
[account] ~ candidates.12.template: "lunar_charged_offfield" -> "auto_overloaded_electro_carry"
[account] ~ candidates.13.expected: 55.4 -> 59.8
[account] ~ candidates.13.label: "Razor dual carry · Overloaded" -> "Flins and Ineffa dual carry · Lunar-Charged"
[account] ~ candidates.13.lead: "Razor" -> "Flins"
[account] ~ candidates.13.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.13.lineup.1: "Fischl" -> "Flins"
[account] ~ candidates.13.lineup.2: "Razor" -> "Ineffa"
[account] ~ candidates.13.lineup.3: "Yae Miko" -> "Zhongli"
[account] ~ candidates.13.ranking: 51.7 -> 51.2
[account] ~ candidates.13.sd: 5.4 -> 12.8
[account] ~ candidates.13.template: "auto_overloaded_electro_carry" -> "lunar_charged"
[account] ~ candidates.14.ranking: 50.2 -> 49.7
[account] ~ candidates.14.sd: 10.3 -> 11.0
[account] ~ candidates.15.ranking: 49.3 -> 49.5
[account] ~ candidates.15.sd: 5.2 -> 4.8
[account] ~ candidates.16.expected: 52.4 -> 51.1
[account] ~ candidates.16.fit_source: "model" -> "pairmodel"
[account] ~ candidates.16.label: "Ineffa and Fischl dual carry · Quicken" -> "Yae Miko dual carry · Overloaded from Xiangling"
[account] ~ candidates.16.lead: "Ineffa" -> "Yae Miko"
[account] ~ candidates.16.lineup.0: "Fischl" -> "Chevreuse"
[account] ~ candidates.16.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.16.lineup.2: "Xingqiu" -> "Xiangling"
[account] ~ candidates.16.lineup.3: "Yaoyao" -> "Yae Miko"
[account] ~ candidates.16.ranking: 48.9 -> 48.7
[account] ~ candidates.16.route: "pair_model" -> "exact_community"
[account] ~ candidates.16.sd: 5.1 -> 3.6
[account] ~ candidates.16.template: "hyperbloom" -> "overloaded"
[account] ~ candidates.16.tier: "C" -> "B"
[account] ~ candidates.17.expected: 53.5 -> 52.1
[account] ~ candidates.17.label: "Razor dual carry · incidental Electro-Charged" -> "No single carry dual carry · incidental Electro-Charged"
[account] ~ candidates.17.lineup.0: "Chevreuse" -> "Ineffa"
[account] ~ candidates.17.lineup.1: "Ineffa" -> "Raiden Shogun"
[account] ~ candidates.17.ranking: 48.8 -> 48.6
[account] ~ candidates.17.sd: 6.9 -> 5.2
[account] ~ candidates.17.tier: "D" -> "C"
[account] ~ candidates.18.expected: 51.1 -> 51.9
[account] ~ candidates.18.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.18.label: "Yae Miko dual carry · Overloaded from Xiangling" -> "Razor dual carry · Overloaded from Xiangling"
[account] ~ candidates.18.lead: "Yae Miko" -> "Razor"
[account] ~ candidates.18.lineup.2: "Xiangling" -> "Razor"
[account] ~ candidates.18.lineup.3: "Yae Miko" -> "Xiangling"
[account] ~ candidates.18.ranking: 48.7 -> 48.5
[account] ~ candidates.18.sd: 3.6 -> 5.2
[account] ~ candidates.18.template: "overloaded" -> "auto_overloaded_electro_carry"
[account] ~ candidates.19.expected: 52.1 -> 51.6
[account] ~ candidates.19.label: "No single carry dual carry · incidental Electro-Charged" -> "Razor dual carry · incidental Vaporize, Overloaded"
[account] ~ candidates.19.lineup.0: "Ineffa" -> "Bennett"
[account] ~ candidates.19.lineup.1: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.19.ranking: 48.7 -> 48.4
[account] ~ candidates.19.sd: 5.1 -> 4.8
[account] ~ candidates.20.expected: 51.9 -> 52.4
[account] ~ candidates.20.fit_source: "gcsim" -> "model"
[account] ~ candidates.20.label: "Razor dual carry · Overloaded from Xiangling" -> "Ineffa and Fischl dual carry · Quicken"
[account] ~ candidates.20.lead: "Razor" -> "Ineffa"
[account] ~ candidates.20.lineup.0: "Chevreuse" -> "Fischl"
[account] ~ candidates.20.lineup.1: "Fischl" -> "Ineffa"
[account] ~ candidates.20.lineup.2: "Razor" -> "Xingqiu"
[account] ~ candidates.20.lineup.3: "Xiangling" -> "Yaoyao"
[account] ~ candidates.20.ranking: 48.5 -> 48.1
[account] ~ candidates.20.route: "exact_community" -> "pair_model"
[account] ~ candidates.20.sd: 5.2 -> 6.3
[account] ~ candidates.20.template: "auto_overloaded_electro_carry" -> "hyperbloom"
[account] ~ candidates.20.tier: "B" -> "C"
[account] ~ candidates.21.expected: 51.6 -> 51.4
[account] ~ candidates.21.label: "Razor dual carry · incidental Vaporize, Overloaded" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.21.lead: "Razor" -> "Yoimiya"
[account] ~ candidates.21.lineup.1: "Ineffa" -> "Chevreuse"
[account] ~ candidates.21.lineup.2: "Razor" -> "Citlali"
[account] ~ candidates.21.lineup.3: "Xingqiu" -> "Yoimiya"
[account] ~ candidates.21.ranking: 48.2 -> 47.9
[account] ~ candidates.21.sd: 5.1 -> 5.2
[account] ~ candidates.21.template: "auto_electro_charged_electro_carry" -> "auto_melt_pyro_carry"
[account] ~ candidates.22.expected: 51.4 -> 51.2
[account] ~ candidates.22.label: "Yoimiya hypercarry · Melt" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.22.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.22.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.22.lineup.1: "Chevreuse" -> "Ineffa"
[account] ~ candidates.22.lineup.2: "Citlali" -> "Razor"
[account] ~ candidates.22.lineup.3: "Yoimiya" -> "Xingqiu"
[account] ~ candidates.22.ranking: 48.0 -> 47.8
[account] ~ candidates.22.sd: 5.0 -> 5.1
[account] ~ candidates.22.template: "auto_melt_pyro_carry" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.23.ranking: 47.9 -> 47.1
[account] ~ candidates.23.sd: 5.0 -> 6.2
[account] ~ candidates.24.expected: 51.2 -> 50.1
[account] ~ candidates.24.label: "Razor on-field · Overloaded" -> "Razor on-field · incidental Overloaded"
[account] ~ candidates.24.lineup.0: "Chevreuse" -> "Bennett"
[account] ~ candidates.24.lineup.1: "Fischl" -> "Chevreuse"
[account] ~ candidates.24.ranking: 47.8 -> 47.1
[account] ~ candidates.24.sd: 5.0 -> 4.4
[account] ~ candidates.25.label: "Razor dual carry · incidental Electro-Charged" -> "Razor on-field · Overloaded"
[account] ~ candidates.25.lineup.0: "Fischl" -> "Chevreuse"
[account] ~ candidates.25.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.25.lineup.3: "Xingqiu" -> "Zhongli"
[account] ~ candidates.25.ranking: 47.8 -> 47.0
[account] ~ candidates.25.sd: 5.0 -> 6.2
[account] ~ candidates.25.template: "auto_electro_charged_electro_carry" -> "auto_overloaded_electro_carry"
[account] ~ candidates.26.expected: 54.3 -> 49.1
[account] ~ candidates.26.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.26.label: "Flins dual carry · Lunar-Charged" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.26.lead: "Flins" -> "Yoimiya"
[account] ~ candidates.26.lineup.0: "Aino" -> "Bennett"
[account] ~ candidates.26.lineup.1: "Diona" -> "Chevreuse"
[account] ~ candidates.26.lineup.2: "Flins" -> "Fischl"
[account] ~ candidates.26.lineup.3: "Ineffa" -> "Yoimiya"
[account] ~ candidates.26.ranking: 47.7 -> 46.8
[account] ~ candidates.26.route: "pair_model" -> "exact_community"
[account] ~ candidates.26.sd: 9.8 -> 3.4
[account] ~ candidates.26.template: "lunar_charged" -> "auto_overloaded_pyro_carry"
[account] ~ candidates.26.tier: "C" -> "B"
[account] ~ candidates.27.expected: 50.5 -> 54.3
[account] ~ candidates.27.label: "Ineffa and Fischl dual carry · incidental Lunar-Charged, Swirl" -> "Flins dual carry · Lunar-Charged"
[account] ~ candidates.27.lead: "Ineffa" -> "Flins"
[account] ~ candidates.27.lineup.1: "Fischl" -> "Diona"
[account] ~ candidates.27.lineup.2: "Ineffa" -> "Flins"
[account] ~ candidates.27.lineup.3: "Kaedehara Kazuha" -> "Ineffa"
[account] ~ candidates.27.ranking: 47.1 -> 46.4
[account] ~ candidates.27.sd: 5.0 -> 11.7
[account] ~ candidates.27.template: "lunar_charged_offfield" -> "lunar_charged"
[account] ~ candidates.28.expected: 49.1 -> 50.5
[account] ~ candidates.28.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.28.label: "Yoimiya dual carry · Overloaded" -> "Ineffa and Fischl dual carry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.28.lead: "Yoimiya" -> "Ineffa"
[account] ~ candidates.28.lineup.0: "Bennett" -> "Aino"
[account] ~ candidates.28.lineup.1: "Chevreuse" -> "Fischl"
...
```

## 2026-10-17 16:26, model 6.1

Phase 12 (model 6.1), planner v2 and pull value v2. Plans: a team below account.min_useful_value (30) is not counted and plan teams earn value over replacement (account.replacement_value 20), so leftover support lineups no longer split or pad plans (6 plans: ayaka_kazuha_over_sucrose, flins_aino_over_xingqiu, no_neuvillette_mono_pyro, plan_raiden_and_nahida, pull_columbina_for_flins, pull_trigger_for_hyperbloom). Pulls: the literal plan change with no duplicate-element discount; a second carry now outranks a support upgrade on one-team accounts (3 top pulls: Mavuika over Columbina for flins_aino_over_xingqiu and yoimiya_hydro, Varka for no_neuvillette_mono_pyro). Kinds describe observed deltas (123 kinds; luxury = only lower plan teams improve). Golden output adds the pull decomposition and each mode's note and locked core. Team power unchanged (0 lineups moved).

1641 changed values in 37 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom.

```
[account] + modes.abyss.core: ["Flins", "Ineffa", "Sucrose"]
[account] + modes.abyss.note: ""
[account] ~ modes.abyss.score: 126.1 -> 64.8
[account] + modes.general.core: ["Flins", "Ineffa", "Sucrose"]
[account] + modes.general.note: ""
[account] + modes.stygian.core: ["Flins", "Ineffa"]
[account] + modes.stygian.note: ""
[account] + modes.theater.core: []
[account] + modes.theater.note: "5 competent teams over 20 characters, 7 of 7 elements"
[account] ~ plan_value: 164.7 -> 109.7
[account] + pulls.0.decomposition: {"best_team_gain": 20.5, "displaced": ["Aino"], "improved": ["Flins", "Ineffa", "Sucrose"], "new_mechanics": [], "new_viable_teams": 131, "redundancy_score": 0.46, "second_team_gain": 0.0, "support_co
[account] + pulls.1.decomposition: {"best_team_gain": 0.0, "displaced": ["Raiden Shogun", "Xingqiu", "Yaoyao"], "improved": ["Bennett", "Citlali", "Kaedehara Kazuha"], "new_mechanics": ["melt"], "new_viable_teams": 216, "redundancy_sco
[account] + pulls.2.decomposition: {"best_team_gain": 0.0, "displaced": ["Razor"], "improved": ["Bennett", "Chevreuse", "Fischl"], "new_mechanics": [], "new_viable_teams": 184, "redundancy_score": 0.48, "second_team_gain": 10.7, "suppo
[account] ~ pulls.2.kind: "new archetype" -> "sidegrade"
[account] + pulls.3.decomposition: {"best_team_gain": 0.0, "displaced": ["Citlali", "Kamisato Ayaka", "Mona", "Shenhe"], "improved": [], "new_mechanics": [], "new_viable_teams": 5, "redundancy_score": 0.05, "second_team_gain": 0.0, "su
[account] ~ pulls.3.kind: "new archetype" -> "luxury"
[account] + pulls.4.decomposition: {"best_team_gain": 0.0, "displaced": ["Yaoyao"], "improved": ["Citlali", "Kamisato Ayaka", "Mona", "Raiden Shogun", "Shenhe", "Xingqiu"], "new_mechanics": [], "new_viable_teams": 171, "redundancy_scor
[account] ~ pulls.4.kind: "fills a gap" -> "luxury"
[account] + pulls.5.decomposition: {"best_team_gain": 0.0, "displaced": ["Kamisato Ayaka"], "improved": ["Citlali", "Mona", "Shenhe"], "new_mechanics": [], "new_viable_teams": 33, "redundancy_score": 0.48, "second_team_gain": 0.0, "sup
[account] ~ pulls.5.kind: "new archetype" -> "sidegrade"
[account] + pulls.6.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 218, "redundancy_scor
[account] ~ pulls.6.kind: "fills a gap" -> "luxury"
[account] + pulls.7.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona", "Yaoyao"], "improved": ["Chevreuse", "Citlali", "Fischl", "Kamisato Ayaka", "Razor", "Shenhe"], "new_mechanics": [], "new_viable_teams": 194, "redundancy_
[account] ~ pulls.7.kind: "new archetype" -> "sidegrade"
[account] + pulls.8.decomposition: {"best_team_gain": 0.0, "displaced": ["Kamisato Ayaka", "Mona", "Shenhe"], "improved": ["Bennett", "Chevreuse", "Citlali"], "new_mechanics": [], "new_viable_teams": 67, "redundancy_score": 0.45, "seco
[account] ~ pulls.8.kind: "new archetype" -> "sidegrade"
[account] + pulls.9.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 157, "redundancy_scor
[account] ~ pulls.9.kind: "fills a gap" -> "luxury"
[account] + pulls.10.decomposition: {"best_team_gain": 0.0, "displaced": ["Citlali"], "improved": ["Kamisato Ayaka", "Mona", "Shenhe"], "new_mechanics": [], "new_viable_teams": 160, "redundancy_score": 0.48, "second_team_gain": 0.0, "su
[account] ~ pulls.10.kind: "fills a gap" -> "luxury"
[account] + pulls.11.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 205, "redundancy_scor
[account] ~ pulls.11.kind: "upgrade" -> "luxury"
[account] + pulls.12.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 198, "redundancy_scor
[account] ~ pulls.12.kind: "upgrade" -> "luxury"
[account] + pulls.13.decomposition: {"best_team_gain": 0.0, "displaced": ["Kamisato Ayaka", "Mona", "Shenhe"], "improved": ["Citlali"], "new_mechanics": ["melt"], "new_viable_teams": 134, "redundancy_score": 0.24, "second_team_gain": -3
[account] ~ pulls.13.kind: "new archetype" -> "luxury"
[account] ~ pulls.14.best_team.0: "Raiden Shogun" -> "Clorinde"
[account] ~ pulls.14.best_team.1: "Xilonen" -> "Kaedehara Kazuha"
[account] ~ pulls.14.best_team.2: "Xingqiu" -> "Yae Miko"
[account] + pulls.14.decomposition: {"best_team_gain": 0.0, "displaced": ["Raiden Shogun", "Xingqiu"], "improved": ["Kaedehara Kazuha", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 160, "redundancy_score": 0.41, "second_team_gain
[account] ~ pulls.14.expected: 1.8 -> 1.7
[account] ~ pulls.14.gain: 1.7 -> 1.9
[account] ~ pulls.14.kind: "upgrade" -> "luxury"
[account] ~ pulls.14.name: "Xilonen" -> "Clorinde"
[account] ~ pulls.14.sd: 4.3 -> 3.7
[account] ~ pulls.15.best_team.0: "Jahoda" -> "Raiden Shogun"
[account] ~ pulls.15.best_team.1: "Raiden Shogun" -> "Xilonen"
[account] + pulls.15.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 187, "redundancy_scor
[account] ~ pulls.15.expected: 3.3 -> 1.8
[account] ~ pulls.15.gain: 1.6 -> 1.7
[account] ~ pulls.15.kind: "upgrade" -> "luxury"
[account] ~ pulls.15.name: "Jahoda" -> "Xilonen"
[account] ~ pulls.15.sd: 6.2 -> 4.3
[account] ~ pulls.16.best_team.0: "Kirara" -> "Jahoda"
[account] + pulls.16.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 171, "redundancy_scor
[account] ~ pulls.16.expected: 1.7 -> 3.3
[account] ~ pulls.16.kind: "fills a gap" -> "luxury"
[account] ~ pulls.16.name: "Kirara" -> "Jahoda"
[account] ~ pulls.16.sd: 4.2 -> 6.2
[account] ~ pulls.17.best_team.0: "Clorinde" -> "Kirara"
[account] ~ pulls.17.best_team.1: "Kaedehara Kazuha" -> "Raiden Shogun"
[account] ~ pulls.17.best_team.2: "Yae Miko" -> "Xingqiu"
[account] + pulls.17.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 145, "redundancy_scor
[account] ~ pulls.17.expected: 1.0 -> 1.7
[account] ~ pulls.17.gain: 1.1 -> 1.6
[account] ~ pulls.17.kind: "sidegrade" -> "luxury"
[account] ~ pulls.17.name: "Clorinde" -> "Kirara"
[account] ~ pulls.17.sd: 2.2 -> 4.2
[account] + pulls.18.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona", "Yaoyao"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu"], "new_mechanics": ["hyperbloom", "quicken"], "new_viable_teams"
[account] ~ pulls.18.kind: "upgrade" -> "luxury"
[account] + pulls.19.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"], "new_mechanics": [], "new_viable_teams": 128, "redundancy_scor
[account] ~ pulls.19.kind: "upgrade" -> "luxury"
[account] + pulls.20.decomposition: {"best_team_gain": 0.0, "displaced": ["Citlali"], "improved": ["Kamisato Ayaka", "Mona", "Shenhe"], "new_mechanics": [], "new_viable_teams": 88, "redundancy_score": 0.4, "second_team_gain": 0.0, "supp
[account] ~ pulls.20.kind: "upgrade" -> "luxury"
[account] + pulls.21.decomposition: {"best_team_gain": 0.0, "displaced": ["Raiden Shogun", "Xingqiu", "Yaoyao"], "improved": ["Citlali", "Kaedehara Kazuha"], "new_mechanics": [], "new_viable_teams": 215, "redundancy_score": 0.2, "second
[account] ~ pulls.21.kind: "fills a gap" -> "luxury"
[account] + pulls.22.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Shenhe"], "new_mechanics": [], "new_viable_teams": 125, "redundancy_score": 0.24, "second_team_gain": 0.0, "su
[account] ~ pulls.22.kind: "upgrade" -> "luxury"
[account] + pulls.23.decomposition: {"best_team_gain": 0.0, "displaced": ["Kamisato Ayaka", "Mona", "Shenhe"], "improved": ["Citlali"], "new_mechanics": [], "new_viable_teams": 23, "redundancy_score": 0.2, "second_team_gain": 0.0, "supp
[account] ~ pulls.23.kind: "new archetype" -> "luxury"
[account] + pulls.24.decomposition: {"best_team_gain": 0.0, "displaced": ["Citlali"], "improved": ["Kamisato Ayaka", "Mona", "Shenhe"], "new_mechanics": [], "new_viable_teams": 164, "redundancy_score": 0.48, "second_team_gain": 0.0, "su
[account] ~ pulls.24.kind: "upgrade" -> "no change"
[account] + pulls.25.decomposition: {"best_team_gain": 0.0, "displaced": ["Yaoyao"], "improved": [], "new_mechanics": ["quicken"], "new_viable_teams": 113, "redundancy_score": 0.27, "second_team_gain": 0.0, "support_contention": []}
[account] ~ pulls.25.gain: 0.2 -> 0.1
[account] ~ pulls.25.kind: "upgrade" -> "no change"
[account] + pulls.26.decomposition: {"best_team_gain": 0.0, "displaced": ["Mona"], "improved": ["Citlali", "Kamisato Ayaka", "Shenhe"], "new_mechanics": ["hyperbloom", "quicken"], "new_viable_teams": 71, "redundancy_score": 0.26, "secon
[account] ~ pulls.26.kind: "upgrade" -> "no change"
[account] + pulls.27.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 38, "redundancy_score": 0.24, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.28.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 27, "redundancy_score": 0.12, "second_team_gain": 0.0, "support_contention": ["Citlali"]}
[account] + pulls.29.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 12, "redundancy_score": 0.25, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.30.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 66, "redundancy_score": 0.45, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.31.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 11, "redundancy_score": 0.18, "second_team_gain": 0.0, "support_contention": ["Bennett", "Citlali"]}
[account] + pulls.32.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 14, "redundancy_score": 0.6, "second_team_gain": 0.0, "support_contention": ["Citlali"]}
[account] + pulls.33.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 52, "redundancy_score": 0.43, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.34.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 103, "redundancy_score": 0.41, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.35.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 103, "redundancy_score": 0.45, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.36.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 9, "redundancy_score": 0.22, "second_team_gain": 0.0, "support_contention": ["Bennett"]}
[account] + pulls.37.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 9, "redundancy_score": 0.15, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.38.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 46, "redundancy_score": 0.48, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.39.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 55, "redundancy_score": 0.57, "second_team_gain": 0.0, "support_contention": ["Ineffa"]}
[account] + pulls.40.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 106, "redundancy_score": 0.42, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.41.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 32, "redundancy_score": 0.37, "second_team_gain": 0.0, "support_contention": ["Bennett"]}
[account] + pulls.42.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 77, "redundancy_score": 0.44, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.43.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 7, "redundancy_score": 0.18, "second_team_gain": 0.0, "support_contention": ["Citlali", "Raiden Shogun
[account] + pulls.44.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 41, "redundancy_score": 0.17, "second_team_gain": 0.0, "support_contention": ["Citlali"]}
[account] + pulls.45.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 72, "redundancy_score": 0.22, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.46.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 61, "redundancy_score": 0.27, "second_team_gain": 0.0, "support_contention": ["Fischl"]}
[account] + pulls.47.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 23, "redundancy_score": 0.25, "second_team_gain": 0.0, "support_contention": ["Mona"]}
[account] + pulls.48.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 22, "redundancy_score": 0.25, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.49.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 19, "redundancy_score": 0.3, "second_team_gain": 0.0, "support_contention": ["Fischl"]}
[account] + pulls.50.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 104, "redundancy_score": 0.47, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.51.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 120, "redundancy_score": 0.55, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.52.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 12, "redundancy_score": 0.05, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.53.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 52, "redundancy_score": 0.6, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.54.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 8, "redundancy_score": 0.1, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.55.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 43, "redundancy_score": 0.3, "second_team_gain": 0.0, "support_contention": ["Fischl"]}
[account] + pulls.56.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 7, "redundancy_score": 0.12, "second_team_gain": 0.0, "support_contention": ["Bennett"]}
[account] + pulls.57.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 58, "redundancy_score": 0.5, "second_team_gain": 0.0, "support_contention": []}
[account] + pulls.58.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 2, "redundancy_score": 0.05, "second_team_gain": 0.0, "support_contention": []}
[roster_flins_lunar_core] + modes.abyss.core: ["Columbina", "Flins", "Ineffa"]
[roster_flins_lunar_core] + modes.abyss.note: "No second team worth building yet."
[roster_flins_lunar_core] + modes.general.core: ["Columbina", "Flins", "Ineffa"]
[roster_flins_lunar_core] + modes.general.note: ""
[roster_flins_lunar_core] + modes.stygian.core: ["Columbina", "Flins", "Ineffa"]
[roster_flins_lunar_core] + modes.stygian.note: ""
[roster_flins_lunar_core] + modes.theater.core: []
[roster_flins_lunar_core] + modes.theater.note: "1 competent teams over 4 characters, 3 of 7 elements"
[roster_flins_lunar_core] ~ plan_value: 93.3 -> 73.3
[roster_flins_lunar_core] + pulls.0.decomposition: {"best_team_gain": -13.5, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 15, "redundancy_score": 0.17, "second_team_gain": 54.3, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.0.expected: 44.5 -> 24.5
[roster_flins_lunar_core] ~ pulls.0.gain: 40.8 -> 20.8
[roster_flins_lunar_core] + pulls.1.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 12, "redundancy_score": 0.0, "second_team_gain": 35.4, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.1.expected: 56.4 -> 36.4
[roster_flins_lunar_core] ~ pulls.1.gain: 35.4 -> 15.4
[roster_flins_lunar_core] + pulls.2.decomposition: {"best_team_gain": -20.5, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 23, "redundancy_score": 0.13, "second_team_gain": 55.3, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.2.expected: 37.2 -> 17.2
[roster_flins_lunar_core] ~ pulls.2.gain: 34.8 -> 14.8
[roster_flins_lunar_core] ~ pulls.2.kind: "fills a gap" -> "upgrade"
[roster_flins_lunar_core] + pulls.3.decomposition: {"best_team_gain": -20.5, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 26, "redundancy_score": 0.18, "second_team_gain": 49.1, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.3.expected: 30.7 -> 10.7
[roster_flins_lunar_core] ~ pulls.3.gain: 28.6 -> 8.6
[roster_flins_lunar_core] ~ pulls.3.kind: "fills a gap" -> "upgrade"
[roster_flins_lunar_core] + pulls.4.decomposition: {"best_team_gain": -13.5, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 21, "redundancy_score": 0.06, "second_team_gain": 41.2, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.4.expected: 30.6 -> 10.6
[roster_flins_lunar_core] ~ pulls.4.gain: 27.7 -> 7.7
[roster_flins_lunar_core] + pulls.5.decomposition: {"best_team_gain": -13.5, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 26, "redundancy_score": 0.18, "second_team_gain": 40.1, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.5.expected: 29.9 -> 9.9
[roster_flins_lunar_core] ~ pulls.5.gain: 26.6 -> 6.6
[roster_flins_lunar_core] + pulls.6.decomposition: {"best_team_gain": -13.5, "displaced": [], "improved": [], "new_mechanics": ["freeze", "melt", "vaporize"], "new_viable_teams": 21, "redundancy_score": 0.13, "second_team_gain": 39.9, "support_content
[roster_flins_lunar_core] ~ pulls.6.expected: 28.9 -> 8.9
[roster_flins_lunar_core] ~ pulls.6.gain: 26.4 -> 6.4
[roster_flins_lunar_core] + pulls.7.decomposition: {"best_team_gain": -13.5, "displaced": [], "improved": [], "new_mechanics": ["melt", "vaporize"], "new_viable_teams": 21, "redundancy_score": 0.09, "second_team_gain": 39.1, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.7.expected: 28.3 -> 8.3
[roster_flins_lunar_core] ~ pulls.7.gain: 25.6 -> 5.6
[roster_flins_lunar_core] ~ pulls.7.kind: "fills a gap" -> "upgrade"
[roster_flins_lunar_core] + pulls.8.decomposition: {"best_team_gain": -31.1, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 18, "redundancy_score": 0.16, "second_team_gain": 53.9, "support_contention": []}
[roster_flins_lunar_core] ~ pulls.8.expected: 25.1 -> 5.1
[roster_flins_lunar_core] ~ pulls.8.gain: 22.8 -> 2.8
[roster_flins_aino_over_xingqiu] + modes.abyss.core: []
[roster_flins_aino_over_xingqiu] + modes.abyss.note: ""
[roster_flins_aino_over_xingqiu] ~ modes.abyss.score: 100.5 -> 43.9
[roster_flins_aino_over_xingqiu] ~ modes.abyss.teams.0.2: "Ineffa" -> "Sucrose"
[roster_flins_aino_over_xingqiu] ~ modes.abyss.teams.0.3: "Sucrose" -> "Xingqiu"
[roster_flins_aino_over_xingqiu] ~ modes.abyss.teams.1.1: "Kaedehara Kazuha" -> "Ineffa"
[roster_flins_aino_over_xingqiu] ~ modes.abyss.teams.1.2: "Xingqiu" -> "Kaedehara Kazuha"
[roster_flins_aino_over_xingqiu] + modes.general.core: ["Aino", "Flins", "Ineffa"]
[roster_flins_aino_over_xingqiu] + modes.general.note: ""
[roster_flins_aino_over_xingqiu] ~ modes.general.score: 99.6 -> 83.9
[roster_flins_aino_over_xingqiu] ~ modes.general.teams.0.3: "Sucrose" -> "Zhongli"
[roster_flins_aino_over_xingqiu] ~ modes.general.teams.1.2: "Xingqiu" -> "Sucrose"
[roster_flins_aino_over_xingqiu] ~ modes.general.teams.1.3: "Zhongli" -> "Xingqiu"
[roster_flins_aino_over_xingqiu] + modes.stygian.core: ["Flins", "Ineffa"]
[roster_flins_aino_over_xingqiu] + modes.stygian.note: ""
[roster_flins_aino_over_xingqiu] + modes.theater.core: []
[roster_flins_aino_over_xingqiu] + modes.theater.note: "1 competent teams over 4 characters, 3 of 7 elements"
[roster_flins_aino_over_xingqiu] ~ plan: [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank
[roster_flins_aino_over_xingqiu] ~ plan_value: 96.4 -> 52.8
[roster_flins_aino_over_xingqiu] ~ pulls.0.best_team.0: "Columbina" -> "Bennett"
[roster_flins_aino_over_xingqiu] ~ pulls.0.best_team.1: "Flins" -> "Mavuika"
[roster_flins_aino_over_xingqiu] ~ pulls.0.best_team.2: "Ineffa" -> "Xingqiu"
[roster_flins_aino_over_xingqiu] ~ pulls.0.best_team.3: "Sucrose" -> "Zhongli"
[roster_flins_aino_over_xingqiu] + pulls.0.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 24, "redundancy_score": 0.12, "second_team_gain": 48.3, "support_contention": []}
[roster_flins_aino_over_xingqiu] ~ pulls.0.expected: 27.5 -> 31.1
[roster_flins_aino_over_xingqiu] ~ pulls.0.gain: 25.0 -> 28.3
[roster_flins_aino_over_xingqiu] ~ pulls.0.kind: "fills a gap" -> "new archetype"
[roster_flins_aino_over_xingqiu] ~ pulls.0.name: "Columbina" -> "Mavuika"
[roster_flins_aino_over_xingqiu] ~ pulls.0.sd: 13.6 -> 4.3
[roster_flins_aino_over_xingqiu] ~ pulls.1.best_team.1: "Mavuika" -> "Columbina"
[roster_flins_aino_over_xingqiu] + pulls.1.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 35, "redundancy_score": 0.11, "second_team_gain": 42.8, "support_contention": []}
[roster_flins_aino_over_xingqiu] ~ pulls.1.expected: 25.6 -> 26.3
[roster_flins_aino_over_xingqiu] ~ pulls.1.gain: 24.7 -> 22.8
[roster_flins_aino_over_xingqiu] ~ pulls.1.name: "Mavuika" -> "Columbina"
[roster_flins_aino_over_xingqiu] + pulls.2.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": [], "new_viable_teams": 10, "redundancy_score": 0.0, "second_team_gain": 38.7, "support_contention": []}
[roster_flins_aino_over_xingqiu] ~ pulls.2.expected: 24.3 -> 29.8
[roster_flins_aino_over_xingqiu] ~ pulls.2.gain: 15.1 -> 18.7
[roster_flins_aino_over_xingqiu] ~ pulls.2.sd: 16.7 -> 16.5
[roster_flins_aino_over_xingqiu] + pulls.3.decomposition: {"best_team_gain": 0.0, "displaced": [], "improved": [], "new_mechanics": ["vaporize"], "new_viable_teams": 28, "redundancy_score": 0.01, "second_team_gain": 37.2, "support_contention": []}
[roster_flins_aino_over_xingqiu] ~ pulls.3.expected: 13.9 -> 19.4
[roster_flins_aino_over_xingqiu] ~ pulls.3.gain: 13.6 -> 17.2
[roster_flins_aino_over_xingqiu] ~ pulls.3.sd: 4.4 -> 3.4
...
```

## 2026-10-17 16:52, model 6.2

Phase 13 (model 6.2), provisional kits (full). Every team gains evidence_state (simulation, interpolation, kit-model, rules-only). Seven provisional support kits (Alyosha, Iansan, Illuga, Kachina, Linnea, Odette, Vodyanitsa) are now valued: 35 candidates with provisional members changed, in the account scenario they displace 28 low-ranked measured candidates from the capped list; plans unchanged. Pull changes: Sandrone 9.5 -> 11.4 and Lohen 0 -> 0.9 (provisional); Clorinde, Lyney, Mavuika, Varesa, Xianyun move by at most 0.3 because the account's plans can now use its owned provisional supports. Three Diluc/Neuvillette lineups move 0.1 in decision score: the functional-distance scale includes the seven new kit capability profiles. No measured team power changed.

1484 changed values in 36 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom, roster_raiden_national.

```
[account] ~ candidates: [{"expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Flins", "Ineffa", "Sucrose"], "rank -> [{"evidence_state": "simulation", "expected": 78.0, "fit_source": "gcsim", "label": "Flins dual carry · Lunar-Charged", "lead": "Flins", "lineup": ["Aino", "Fli
[account] ~ carries_for_supports.3.1.0: "Bennett" -> "Alyosha"
[account] ~ carries_for_supports.3.1.1: "Sandrone" -> "Kaedehara Kazuha"
[account] ~ carries_for_supports.3.1.2: "Shenhe" -> "Sandrone"
[account] + plan.0.evidence_state: "simulation"
[account] + plan.1.evidence_state: "simulation"
[account] + plan.2.evidence_state: "interpolation"
[account] + plan.3.evidence_state: "interpolation"
[account] ~ pulls.0.decomposition.new_viable_teams: 131 -> 133
[account] ~ pulls.1.decomposition.displaced: ["Raiden Shogun", "Xingqiu", "Yaoyao"] -> ["Kamisato Ayaka", "Mona", "Shenhe", "Yaoyao"]
[account] ~ pulls.1.decomposition.new_viable_teams: 216 -> 220
[account] ~ pulls.1.expected: 13.4 -> 14.9
[account] ~ pulls.1.gain: 12.6 -> 12.9
[account] ~ pulls.1.sd: 10.7 -> 11.0
[account] ~ pulls.1.tier: "C" -> "E"
[account] ~ pulls.2.best_team.0: "Bennett" -> "Alyosha"
[account] ~ pulls.2.best_team.1: "Chevreuse" -> "Sandrone"
[account] ~ pulls.2.best_team.2: "Durin" -> "Yae Miko"
[account] ~ pulls.2.best_team.3: "Fischl" -> "Zhongli"
[account] ~ pulls.2.decomposition.displaced: ["Razor"] -> ["Citlali", "Kamisato Ayaka", "Mona", "Shenhe"]
[account] ~ pulls.2.decomposition.improved: ["Bennett", "Chevreuse", "Fischl"] -> []
[account] ~ pulls.2.decomposition.new_viable_teams: 184 -> 5
[account] ~ pulls.2.decomposition.redundancy_score: 0.48 -> 0.05
[account] ~ pulls.2.decomposition.second_team_gain: 10.7 -> 1.7
[account] ~ pulls.2.expected: 9.9 -> 18.2
[account] ~ pulls.2.gain: 10.7 -> 11.4
[account] ~ pulls.2.kind: "sidegrade" -> "new archetype"
[account] ~ pulls.2.name: "Durin" -> "Sandrone"
[account] ~ pulls.2.sd: 8.3 -> 15.7
[account] ~ pulls.2.tier: "B" -> "E"
[account] ~ pulls.3.best_team.0: "Rosaria" -> "Bennett"
[account] ~ pulls.3.best_team.1: "Sandrone" -> "Chevreuse"
[account] ~ pulls.3.best_team.2: "Yae Miko" -> "Durin"
[account] ~ pulls.3.best_team.3: "Zhongli" -> "Fischl"
[account] ~ pulls.3.decomposition.displaced: ["Citlali", "Kamisato Ayaka", "Mona", "Shenhe"] -> ["Razor"]
[account] ~ pulls.3.decomposition.improved: [] -> ["Bennett", "Chevreuse", "Fischl"]
[account] ~ pulls.3.decomposition.new_viable_teams: 5 -> 180
[account] ~ pulls.3.decomposition.redundancy_score: 0.05 -> 0.48
[account] ~ pulls.3.decomposition.second_team_gain: 0.0 -> 10.7
[account] ~ pulls.3.expected: 13.1 -> 9.9
[account] ~ pulls.3.gain: 9.5 -> 10.7
[account] ~ pulls.3.kind: "luxury" -> "sidegrade"
[account] ~ pulls.3.name: "Sandrone" -> "Durin"
[account] ~ pulls.3.sd: 7.6 -> 8.3
[account] ~ pulls.3.tier: "E" -> "B"
[account] ~ pulls.4.decomposition.new_viable_teams: 171 -> 176
[account] ~ pulls.5.decomposition.new_viable_teams: 33 -> 28
[account] ~ pulls.6.decomposition.new_viable_teams: 218 -> 225
[account] ~ pulls.7.decomposition.new_viable_teams: 194 -> 193
[account] ~ pulls.8.best_team.2: "Lyney" -> "Citlali"
[account] ~ pulls.8.best_team.3: "Yae Miko" -> "Lyney"
[account] ~ pulls.8.decomposition.displaced: ["Kamisato Ayaka", "Mona", "Shenhe"] -> ["Razor"]
[account] ~ pulls.8.decomposition.improved: ["Bennett", "Chevreuse", "Citlali"] -> ["Bennett", "Chevreuse", "Citlali", "Kamisato Ayaka", "Mona", "Raiden Shogun", "Shenhe", "Xingqiu", "Yaoyao"]
[account] ~ pulls.8.decomposition.new_mechanics: [] -> ["melt"]
[account] ~ pulls.8.decomposition.redundancy_score: 0.45 -> 0.32
[account] ~ pulls.8.decomposition.second_team_gain: 4.3 -> 5.2
[account] ~ pulls.8.decomposition.support_contention: [] -> ["Citlali"]
[account] ~ pulls.8.expected: 4.7 -> 6.6
[account] ~ pulls.8.gain: 5.9 -> 5.8
[account] ~ pulls.8.kind: "sidegrade" -> "new archetype"
[account] ~ pulls.8.sd: 8.4 -> 10.8
[account] ~ pulls.9.decomposition.new_viable_teams: 157 -> 164
[account] ~ pulls.10.decomposition.new_viable_teams: 160 -> 161
[account] ~ pulls.11.decomposition.new_viable_teams: 205 -> 210
[account] ~ pulls.12.decomposition.new_viable_teams: 198 -> 205
[account] ~ pulls.13.best_team.0: "Bennett" -> "Clorinde"
[account] ~ pulls.13.best_team.1: "Citlali" -> "Kaedehara Kazuha"
[account] ~ pulls.13.best_team.2: "Gaming" -> "Yae Miko"
[account] ~ pulls.13.best_team.3: "Rosaria" -> "Yaoyao"
[account] ~ pulls.13.decomposition.displaced: ["Kamisato Ayaka", "Mona", "Shenhe"] -> ["Citlali", "Kamisato Ayaka", "Mona", "Shenhe"]
[account] ~ pulls.13.decomposition.improved: ["Citlali"] -> ["Kaedehara Kazuha", "Yaoyao"]
[account] ~ pulls.13.decomposition.new_mechanics: ["melt"] -> []
[account] ~ pulls.13.decomposition.new_viable_teams: 134 -> 161
[account] ~ pulls.13.decomposition.redundancy_score: 0.24 -> 0.41
[account] ~ pulls.13.decomposition.second_team_gain: -3.1 -> 0.0
[account] ~ pulls.13.decomposition.support_contention: ["Citlali"] -> []
[account] ~ pulls.13.expected: 2.6 -> 3.2
[account] ~ pulls.13.gain: 2.0 -> 2.1
[account] ~ pulls.13.name: "Gaming" -> "Clorinde"
[account] ~ pulls.13.sd: 9.8 -> 4.8
[account] ~ pulls.13.tier: "C" -> "E"
[account] ~ pulls.14.best_team.0: "Clorinde" -> "Bennett"
[account] ~ pulls.14.best_team.1: "Kaedehara Kazuha" -> "Citlali"
[account] ~ pulls.14.best_team.2: "Yae Miko" -> "Gaming"
[account] ~ pulls.14.best_team.3: "Yaoyao" -> "Rosaria"
[account] ~ pulls.14.decomposition.displaced: ["Raiden Shogun", "Xingqiu"] -> ["Kamisato Ayaka", "Mona", "Shenhe"]
[account] ~ pulls.14.decomposition.improved: ["Kaedehara Kazuha", "Yaoyao"] -> ["Citlali"]
[account] ~ pulls.14.decomposition.new_mechanics: [] -> ["melt"]
[account] ~ pulls.14.decomposition.new_viable_teams: 160 -> 132
[account] ~ pulls.14.decomposition.redundancy_score: 0.41 -> 0.24
[account] ~ pulls.14.decomposition.second_team_gain: 0.0 -> -3.1
[account] ~ pulls.14.decomposition.support_contention: [] -> ["Citlali"]
[account] ~ pulls.14.expected: 1.7 -> 2.6
[account] ~ pulls.14.gain: 1.9 -> 2.0
[account] ~ pulls.14.name: "Clorinde" -> "Gaming"
[account] ~ pulls.14.sd: 3.7 -> 9.8
[account] ~ pulls.15.decomposition.new_viable_teams: 187 -> 192
[account] ~ pulls.16.decomposition.new_viable_teams: 171 -> 180
[account] ~ pulls.18.decomposition.new_viable_teams: 66 -> 65
[account] ~ pulls.19.decomposition.new_viable_teams: 128 -> 129
[account] ~ pulls.20.best_team.0: "Kamisato Ayaka" -> "Citlali"
[account] ~ pulls.20.best_team.1: "Mona" -> "Diluc"
[account] ~ pulls.20.best_team.2: "Shenhe" -> "Kaedehara Kazuha"
[account] ~ pulls.20.best_team.3: "Venti" -> "Xianyun"
[account] ~ pulls.20.decomposition.displaced: ["Citlali"] -> ["Kamisato Ayaka", "Mona", "Shenhe", "Yaoyao"]
[account] ~ pulls.20.decomposition.improved: ["Kamisato Ayaka", "Mona", "Shenhe"] -> ["Citlali", "Kaedehara Kazuha"]
[account] ~ pulls.20.decomposition.new_viable_teams: 88 -> 220
[account] ~ pulls.20.decomposition.redundancy_score: 0.4 -> 0.2
[account] ~ pulls.20.decomposition.support_contention: [] -> ["Citlali"]
[account] ~ pulls.20.expected: 1.0 -> 2.2
[account] ~ pulls.20.gain: 0.9 -> 1.1
[account] ~ pulls.20.name: "Venti" -> "Xianyun"
[account] ~ pulls.20.sd: 1.5 -> 4.8
[account] ~ pulls.20.tier: "B" -> "E"
[account] ~ pulls.21.best_team.0: "Citlali" -> "Iansan"
[account] ~ pulls.21.best_team.1: "Diluc" -> "Lohen"
[account] ~ pulls.21.best_team.2: "Kaedehara Kazuha" -> "Mona"
[account] ~ pulls.21.best_team.3: "Xianyun" -> "Shenhe"
[account] ~ pulls.21.decomposition.displaced: ["Raiden Shogun", "Xingqiu", "Yaoyao"] -> ["Citlali", "Kamisato Ayaka"]
[account] ~ pulls.21.decomposition.improved.0: "Citlali" -> "Mona"
[account] ~ pulls.21.decomposition.improved.1: "Kaedehara Kazuha" -> "Shenhe"
[account] ~ pulls.21.decomposition.new_viable_teams: 215 -> 19
[account] ~ pulls.21.decomposition.redundancy_score: 0.2 -> 0.23
[account] ~ pulls.21.decomposition.support_contention: ["Citlali"] -> []
[account] ~ pulls.21.expected: 0.7 -> 2.0
[account] ~ pulls.21.gain: 0.8 -> 0.9
[account] ~ pulls.21.name: "Xianyun" -> "Lohen"
[account] ~ pulls.21.sd: 4.0 -> 2.9
[account] ~ pulls.21.tier: "C" -> "E"
[account] ~ pulls.22.best_team.0: "Faruzan" -> "Kamisato Ayaka"
[account] ~ pulls.22.best_team.1: "Raiden Shogun" -> "Mona"
[account] ~ pulls.22.best_team.2: "Xingqiu" -> "Shenhe"
[account] ~ pulls.22.best_team.3: "Yaoyao" -> "Venti"
[account] ~ pulls.22.decomposition.displaced.0: "Mona" -> "Citlali"
[account] ~ pulls.22.decomposition.improved.0: "Citlali" -> "Kamisato Ayaka"
[account] ~ pulls.22.decomposition.improved.1: "Kamisato Ayaka" -> "Mona"
[account] ~ pulls.22.decomposition.new_viable_teams: 125 -> 84
[account] ~ pulls.22.decomposition.redundancy_score: 0.24 -> 0.4
[account] ~ pulls.22.expected: 0.7 -> 1.0
[account] ~ pulls.22.gain: 0.7 -> 0.9
[account] ~ pulls.22.name: "Faruzan" -> "Venti"
[account] ~ pulls.22.sd: 4.1 -> 1.5
[account] ~ pulls.22.tier: "C" -> "B"
[account] ~ pulls.23.best_team.0: "Citlali" -> "Faruzan"
[account] ~ pulls.23.best_team.1: "Lynette" -> "Raiden Shogun"
[account] ~ pulls.23.best_team.2: "Mualani" -> "Xingqiu"
[account] ~ pulls.23.best_team.3: "Zhongli" -> "Yaoyao"
[account] ~ pulls.23.decomposition.displaced: ["Kamisato Ayaka", "Mona", "Shenhe"] -> ["Mona"]
[account] ~ pulls.23.decomposition.improved: ["Citlali"] -> ["Citlali", "Kamisato Ayaka", "Shenhe"]
[account] ~ pulls.23.decomposition.new_viable_teams: 23 -> 127
[account] ~ pulls.23.decomposition.redundancy_score: 0.2 -> 0.24
[account] ~ pulls.23.expected: 0.6 -> 0.7
[account] ~ pulls.23.gain: 0.5 -> 0.7
[account] ~ pulls.23.name: "Mualani" -> "Faruzan"
[account] ~ pulls.23.sd: 1.5 -> 4.1
[account] ~ pulls.24.best_team.0: "Kamisato Ayaka" -> "Citlali"
[account] ~ pulls.24.best_team.1: "Mona" -> "Lynette"
[account] ~ pulls.24.best_team.2: "Shenhe" -> "Mualani"
[account] ~ pulls.24.best_team.3: "Yelan" -> "Zhongli"
[account] ~ pulls.24.decomposition.displaced: ["Citlali"] -> ["Kamisato Ayaka", "Mona", "Shenhe"]
[account] ~ pulls.24.decomposition.improved: ["Kamisato Ayaka", "Mona", "Shenhe"] -> ["Citlali"]
[account] ~ pulls.24.decomposition.new_viable_teams: 164 -> 28
[account] ~ pulls.24.decomposition.redundancy_score: 0.48 -> 0.2
[account] ~ pulls.24.expected: 0.3 -> 0.6
[account] ~ pulls.24.gain: 0.3 -> 0.5
[account] ~ pulls.24.kind: "no change" -> "luxury"
[account] ~ pulls.24.name: "Yelan" -> "Mualani"
[account] ~ pulls.25.best_team.0: "Baizhu" -> "Kamisato Ayaka"
[account] ~ pulls.25.best_team.1: "Kaedehara Kazuha" -> "Mona"
[account] ~ pulls.25.best_team.2: "Raiden Shogun" -> "Shenhe"
[account] ~ pulls.25.best_team.3: "Xingqiu" -> "Yelan"
[account] ~ pulls.25.decomposition.displaced.0: "Yaoyao" -> "Citlali"
[account] ~ pulls.25.decomposition.improved: [] -> ["Kamisato Ayaka", "Mona", "Shenhe"]
[account] ~ pulls.25.decomposition.new_mechanics: ["quicken"] -> []
[account] ~ pulls.25.decomposition.new_viable_teams: 113 -> 169
[account] ~ pulls.25.decomposition.redundancy_score: 0.27 -> 0.48
[account] ~ pulls.25.expected: -0.1 -> 0.3
[account] ~ pulls.25.gain: 0.1 -> 0.3
[account] ~ pulls.25.name: "Baizhu" -> "Yelan"
[account] ~ pulls.25.sd: 3.6 -> 1.5
[account] ~ pulls.26.best_team.0: "Kuki Shinobu" -> "Citlali"
[account] ~ pulls.26.best_team.1: "Raiden Shogun" -> "Kaedehara Kazuha"
[account] ~ pulls.26.best_team.2: "Xingqiu" -> "Kujou Sara"
[account] ~ pulls.26.best_team.3: "Yaoyao" -> "Varesa"
[account] ~ pulls.26.decomposition.displaced: ["Mona"] -> ["Kamisato Ayaka", "Mona", "Shenhe", "Yaoyao"]
[account] ~ pulls.26.decomposition.improved: ["Citlali", "Kamisato Ayaka", "Shenhe"] -> ["Citlali"]
[account] ~ pulls.26.decomposition.new_mechanics: ["hyperbloom", "quicken"] -> []
[account] ~ pulls.26.decomposition.new_viable_teams: 71 -> 52
[account] ~ pulls.26.decomposition.redundancy_score: 0.26 -> 0.42
[account] ~ pulls.26.decomposition.support_contention: [] -> ["Citlali"]
[account] ~ pulls.26.expected: -0.1 -> 2.4
[account] ~ pulls.26.gain: 0.1 -> 0.2
[account] ~ pulls.26.name: "Kuki Shinobu" -> "Varesa"
[account] ~ pulls.26.sd: 3.9 -> 5.9
[account] ~ pulls.26.tier: "C" -> "E"
[account] ~ pulls.27.best_team.0: "Aino" -> "Baizhu"
[account] ~ pulls.27.best_team.1: "Albedo" -> "Kaedehara Kazuha"
[account] ~ pulls.27.best_team.2: "Alyosha" -> "Raiden Shogun"
[account] ~ pulls.27.best_team.3: "Ineffa" -> "Xingqiu"
[account] ~ pulls.27.decomposition.displaced: [] -> ["Yaoyao"]
...
```

## 2026-10-17 17:53, model 6.3

Model 6.3 power reliability. (1) Pair model gains a cross-validated damage-capacity term, coef 0.344 x log(sum of members' average damage shares): low-capacity, support-heavy pair-model lineups drop (up to -5), high-capacity ones rise (up to +2.7); no exact-community value changes (0 of 152). (2) Functional-distance sd refitted by maximum likelihood (held-out log likelihood 1.699 -> 1.704; low-data lineups 63%/85% -> 68%/90% within 1/2 sd): pair-model sds +4% median. (3) New typicality finding low_capacity (below the 2nd percentile of simulated lineups) widens those sds (measured x1.81). (4) Planner: the separate useful-team gate (30) is removed, plan and mode utilities count max(0, value - 20) with no cliff: 6 plans change, mostly second teams between 20 and 30 now counting (ayaka_kazuha_over_sucrose keeps Mona; plan_raiden_and_nahida returns to Raiden national + hyperbloom). Pull kinds (48) and two top pulls follow the changed plans (arlecchino_bennett: Citlali first; mavuika_sidegrade_for_arlecchino: Neuvillette first). (5) Validity split: any legal team can be evaluated; templates only generate candidates.

12173 changed values in 37 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom.

```
[account] ~ candidates.1.expected: 70.1 -> 70.9
[account] ~ candidates.1.ranking: 64.4 -> 64.3
[account] ~ candidates.1.sd: 8.4 -> 9.8
[account] ~ candidates.2.expected: 68.6 -> 69.3
[account] ~ candidates.2.ranking: 62.8 -> 62.0
[account] ~ candidates.2.sd: 8.7 -> 10.7
[account] ~ candidates.4.expected: 65.4 -> 66.5
[account] ~ candidates.4.ranking: 59.8 -> 59.6
[account] ~ candidates.4.sd: 8.3 -> 10.1
[account] ~ candidates.5.expected: 64.1 -> 65.3
[account] ~ candidates.5.ranking: 59.0 -> 59.4
[account] ~ candidates.5.sd: 7.5 -> 8.7
[account] ~ candidates.7.expected: 61.9 -> 63.0
[account] ~ candidates.7.ranking: 56.9 -> 57.2
[account] ~ candidates.7.sd: 7.4 -> 8.5
[account] ~ candidates.8.expected: 60.5 -> 59.9
[account] ~ candidates.8.ranking: 56.0 -> 55.0
[account] ~ candidates.8.sd: 6.8 -> 7.2
[account] ~ candidates.9.expected: 59.2 -> 58.4
[account] ~ candidates.9.ranking: 54.7 -> 53.2
[account] ~ candidates.9.sd: 6.8 -> 7.6
[account] ~ candidates.11.expected: 61.8 -> 60.9
[account] ~ candidates.11.ranking: 52.1 -> 52.3
[account] ~ candidates.11.sd: 14.4 -> 12.8
[account] ~ candidates.12.expected: 56.2 -> 55.3
[account] ~ candidates.12.label: "Ineffa hypercarry · incidental Lunar-Charged, Swirl" -> "Razor dual carry · Overloaded"
[account] ~ candidates.12.lead: "Ineffa" -> "Razor"
[account] ~ candidates.12.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.12.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.12.lineup.2: "Sucrose" -> "Razor"
[account] ~ candidates.12.lineup.3: "Xingqiu" -> "Yae Miko"
[account] ~ candidates.12.ranking: 51.5 -> 51.1
[account] ~ candidates.12.sd: 7.0 -> 6.2
[account] ~ candidates.12.template: "lunar_charged_offfield" -> "auto_overloaded_electro_carry"
[account] ~ candidates.13.expected: 55.4 -> 60.8
[account] ~ candidates.13.label: "Razor dual carry · Overloaded" -> "Flins and Ineffa dual carry · Lunar-Charged"
[account] ~ candidates.13.lead: "Razor" -> "Flins"
[account] ~ candidates.13.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.13.lineup.1: "Fischl" -> "Flins"
[account] ~ candidates.13.lineup.2: "Razor" -> "Ineffa"
[account] ~ candidates.13.lineup.3: "Yae Miko" -> "Zhongli"
[account] ~ candidates.13.ranking: 51.3 -> 50.8
[account] ~ candidates.13.sd: 6.0 -> 14.8
[account] ~ candidates.13.template: "auto_overloaded_electro_carry" -> "lunar_charged"
[account] ~ candidates.14.expected: 59.8 -> 53.3
[account] ~ candidates.14.label: "Flins and Ineffa dual carry · Lunar-Charged" -> "Raiden Shogun and Ineffa dual carry · Overloaded"
[account] ~ candidates.14.lead: "Flins" -> "Raiden Shogun"
[account] ~ candidates.14.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.14.lineup.1: "Flins" -> "Ineffa"
[account] ~ candidates.14.lineup.2: "Ineffa" -> "Raiden Shogun"
[account] ~ candidates.14.lineup.3: "Zhongli" -> "Xiangling"
[account] ~ candidates.14.ranking: 51.2 -> 49.8
[account] ~ candidates.14.sd: 12.8 -> 5.2
[account] ~ candidates.14.template: "lunar_charged" -> "overloaded"
[account] ~ candidates.15.evidence_state: "kit-model" -> "interpolation"
[account] ~ candidates.15.expected: 59.2 -> 54.6
[account] ~ candidates.15.fit_source: "model" -> "pairmodel"
[account] ~ candidates.15.lineup.1: "Alyosha" -> "Ineffa"
[account] ~ candidates.15.lineup.2: "Ineffa" -> "Sucrose"
[account] ~ candidates.15.lineup.3: "Sucrose" -> "Xingqiu"
[account] ~ candidates.15.ranking: 49.7 -> 49.4
[account] ~ candidates.15.route: "provisional_kit" -> "pair_model"
[account] ~ candidates.15.sd: 14.2 -> 7.7
[account] ~ candidates.15.tier: "E" -> "C"
[account] ~ candidates.16.expected: 57.1 -> 56.9
[account] ~ candidates.16.ranking: 49.7 -> 49.4
[account] ~ candidates.16.sd: 11.0 -> 11.1
[account] ~ candidates.17.evidence_state: "interpolation" -> "kit-model"
[account] ~ candidates.17.expected: 52.8 -> 58.4
[account] ~ candidates.17.fit_source: "pairmodel" -> "model"
[account] ~ candidates.17.label: "Raiden Shogun and Ineffa dual carry · Overloaded" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.17.lead: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.17.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.17.lineup.1: "Ineffa" -> "Alyosha"
[account] ~ candidates.17.lineup.2: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.17.lineup.3: "Xiangling" -> "Sucrose"
[account] ~ candidates.17.ranking: 49.5 -> 49.0
[account] ~ candidates.17.route: "pair_model" -> "provisional_kit"
[account] ~ candidates.17.sd: 4.8 -> 13.9
[account] ~ candidates.17.template: "overloaded" -> "lunar_charged_offfield"
[account] ~ candidates.17.tier: "C" -> "E"
[account] ~ candidates.19.expected: 52.1 -> 51.8
[account] ~ candidates.19.label: "No single carry dual carry · incidental Electro-Charged" -> "Razor dual carry · incidental Vaporize, Overloaded"
[account] ~ candidates.19.lineup.0: "Ineffa" -> "Bennett"
[account] ~ candidates.19.lineup.1: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.19.ranking: 48.6 -> 48.5
[account] ~ candidates.19.sd: 5.2 -> 5.0
[account] ~ candidates.21.expected: 51.6 -> 51.3
[account] ~ candidates.21.label: "Razor dual carry · incidental Vaporize, Overloaded" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.21.lead: "Razor" -> "Yoimiya"
[account] ~ candidates.21.lineup.1: "Ineffa" -> "Chevreuse"
[account] ~ candidates.21.lineup.2: "Razor" -> "Citlali"
[account] ~ candidates.21.lineup.3: "Xingqiu" -> "Yoimiya"
[account] ~ candidates.21.ranking: 48.4 -> 47.9
[account] ~ candidates.21.sd: 4.8 -> 5.0
[account] ~ candidates.21.template: "auto_electro_charged_electro_carry" -> "auto_melt_pyro_carry"
[account] ~ candidates.22.ranking: 48.1 -> 47.9
[account] ~ candidates.22.sd: 6.3 -> 6.6
[account] ~ candidates.23.label: "Yoimiya hypercarry · Melt" -> "No single carry dual carry · incidental Electro-Charged"
[account] ~ candidates.23.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.23.lineup.0: "Bennett" -> "Ineffa"
[account] ~ candidates.23.lineup.1: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.23.lineup.2: "Citlali" -> "Razor"
[account] ~ candidates.23.lineup.3: "Yoimiya" -> "Xingqiu"
[account] ~ candidates.23.ranking: 47.9 -> 47.8
[account] ~ candidates.23.sd: 5.2 -> 5.4
[account] ~ candidates.23.template: "auto_melt_pyro_carry" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.24.expected: 51.2 -> 50.8
[account] ~ candidates.24.ranking: 47.8 -> 47.2
[account] ~ candidates.24.sd: 5.1 -> 5.4
[account] ~ candidates.25.expected: 51.3 -> 53.6
[account] ~ candidates.25.label: "Ineffa hypercarry · incidental Lunar-Charged, Swirl" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.25.lead: "Ineffa" -> "Razor"
[account] ~ candidates.25.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.25.lineup.1: "Beidou" -> "Ineffa"
[account] ~ candidates.25.lineup.2: "Ineffa" -> "Razor"
[account] ~ candidates.25.lineup.3: "Sucrose" -> "Xingqiu"
[account] ~ candidates.25.ranking: 47.1 -> 47.0
[account] ~ candidates.25.sd: 6.2 -> 9.7
[account] ~ candidates.25.template: "lunar_charged" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.25.tier: "C" -> "D"
[account] ~ candidates.26.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.26.expected: 50.1 -> 49.1
[account] ~ candidates.26.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.26.label: "Razor on-field · incidental Overloaded" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.26.lead: "Razor" -> "Yoimiya"
[account] ~ candidates.26.lineup.2: "Razor" -> "Fischl"
[account] ~ candidates.26.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.26.ranking: 47.1 -> 46.8
[account] ~ candidates.26.route: "pair_model" -> "exact_community"
[account] ~ candidates.26.sd: 4.4 -> 3.4
[account] ~ candidates.26.template: "auto_overloaded_electro_carry" -> "auto_overloaded_pyro_carry"
[account] ~ candidates.26.tier: "C" -> "B"
[account] ~ candidates.27.expected: 51.2 -> 55.9
[account] ~ candidates.27.label: "Razor on-field · Overloaded" -> "Flins dual carry · Lunar-Charged"
[account] ~ candidates.27.lead: "Razor" -> "Flins"
[account] ~ candidates.27.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.27.lineup.1: "Fischl" -> "Diona"
[account] ~ candidates.27.lineup.2: "Razor" -> "Flins"
[account] ~ candidates.27.lineup.3: "Zhongli" -> "Ineffa"
[account] ~ candidates.27.ranking: 47.0 -> 46.6
[account] ~ candidates.27.sd: 6.2 -> 13.7
[account] ~ candidates.27.template: "auto_overloaded_electro_carry" -> "lunar_charged"
[account] ~ candidates.28.evidence_state: "simulation" -> "interpolation"
[account] ~ candidates.28.expected: 49.1 -> 50.8
[account] ~ candidates.28.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.28.label: "Yoimiya dual carry · Overloaded" -> "Razor on-field · Overloaded"
[account] ~ candidates.28.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.28.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.28.lineup.1: "Chevreuse" -> "Fischl"
[account] ~ candidates.28.lineup.2: "Fischl" -> "Razor"
[account] ~ candidates.28.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.28.ranking: 46.8 -> 46.6
[account] ~ candidates.28.route: "exact_community" -> "pair_model"
[account] ~ candidates.28.sd: 3.4 -> 6.2
[account] ~ candidates.28.template: "auto_overloaded_pyro_carry" -> "auto_overloaded_electro_carry"
[account] ~ candidates.28.tier: "B" -> "C"
[account] ~ candidates.29.expected: 54.3 -> 49.5
[account] ~ candidates.29.label: "Flins dual carry · Lunar-Charged" -> "Razor on-field · incidental Overloaded"
[account] ~ candidates.29.lead: "Flins" -> "Razor"
[account] ~ candidates.29.lineup.0: "Aino" -> "Bennett"
[account] ~ candidates.29.lineup.1: "Diona" -> "Chevreuse"
[account] ~ candidates.29.lineup.2: "Flins" -> "Razor"
[account] ~ candidates.29.lineup.3: "Ineffa" -> "Zhongli"
[account] ~ candidates.29.ranking: 46.4 -> 46.5
[account] ~ candidates.29.sd: 11.7 -> 4.5
[account] ~ candidates.29.template: "lunar_charged" -> "auto_overloaded_electro_carry"
[account] ~ candidates.30.expected: 50.5 -> 49.7
[account] ~ candidates.30.label: "Ineffa and Fischl dual carry · incidental Lunar-Charged, Swirl" -> "Razor dual carry · Overloaded"
[account] ~ candidates.30.lead: "Ineffa" -> "Razor"
[account] ~ candidates.30.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.30.lineup.2: "Ineffa" -> "Raiden Shogun"
[account] ~ candidates.30.lineup.3: "Kaedehara Kazuha" -> "Razor"
[account] ~ candidates.30.ranking: 46.3 -> 46.0
[account] ~ candidates.30.sd: 6.3 -> 5.4
[account] ~ candidates.30.template: "lunar_charged_offfield" -> "auto_overloaded_electro_carry"
[account] ~ candidates.31.expected: 49.9 -> 50.1
[account] ~ candidates.31.label: "Razor dual carry · Overloaded" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.31.lead: "Razor" -> "Ineffa"
[account] ~ candidates.31.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.31.lineup.1: "Fischl" -> "Beidou"
[account] ~ candidates.31.lineup.2: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.31.lineup.3: "Razor" -> "Sucrose"
[account] ~ candidates.31.ranking: 46.3 -> 45.7
[account] ~ candidates.31.sd: 5.3 -> 6.6
[account] ~ candidates.31.template: "auto_overloaded_electro_carry" -> "lunar_charged"
[account] ~ candidates.32.expected: 49.0 -> 48.2
[account] ~ candidates.32.ranking: 45.9 -> 45.0
[account] ~ candidates.32.sd: 4.6 -> 4.8
[account] ~ candidates.33.expected: 53.5 -> 49.7
[account] ~ candidates.33.label: "Razor dual carry · incidental Electro-Charged" -> "Ineffa and Fischl dual carry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.33.lead: "Razor" -> "Ineffa"
[account] ~ candidates.33.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.33.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.33.lineup.2: "Razor" -> "Ineffa"
[account] ~ candidates.33.lineup.3: "Xingqiu" -> "Kaedehara Kazuha"
[account] ~ candidates.33.ranking: 45.7 -> 44.9
[account] ~ candidates.33.sd: 11.5 -> 7.1
[account] ~ candidates.33.template: "auto_electro_charged_electro_carry" -> "lunar_charged_offfield"
[account] ~ candidates.33.tier: "D" -> "C"
...
```

## 2026-10-17 18:24, model 6.4

Model 6.4 reliability validation. Golden candidates gain evidence_quality (community evidence: good / unconfirmed / mixed / poor). No team power, plan, pull or kind changed: the out-of-sample validation found no expected-value fix supported by data (a no-number guard for low-capacity lineups was tested and rejected as a harness artifact).

1417 changed values in 36 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom, roster_raiden_national.

```
[account] + candidates.0.evidence_quality: "unconfirmed"
[account] + candidates.1.evidence_quality: ""
[account] + candidates.2.evidence_quality: ""
[account] + candidates.3.evidence_quality: "unconfirmed"
[account] + candidates.4.evidence_quality: ""
[account] + candidates.5.evidence_quality: ""
[account] + candidates.6.evidence_quality: "unconfirmed"
[account] + candidates.7.evidence_quality: ""
[account] + candidates.8.evidence_quality: ""
[account] + candidates.9.evidence_quality: ""
[account] + candidates.10.evidence_quality: ""
[account] + candidates.11.evidence_quality: ""
[account] + candidates.12.evidence_quality: ""
[account] + candidates.13.evidence_quality: ""
[account] + candidates.14.evidence_quality: ""
[account] + candidates.15.evidence_quality: ""
[account] + candidates.16.evidence_quality: ""
[account] + candidates.17.evidence_quality: ""
[account] + candidates.18.evidence_quality: "good"
[account] + candidates.19.evidence_quality: ""
[account] + candidates.20.evidence_quality: "unconfirmed"
[account] + candidates.21.evidence_quality: ""
[account] + candidates.22.evidence_quality: ""
[account] + candidates.23.evidence_quality: ""
[account] + candidates.24.evidence_quality: ""
[account] + candidates.25.evidence_quality: ""
[account] + candidates.26.evidence_quality: "good"
[account] + candidates.27.evidence_quality: ""
[account] + candidates.28.evidence_quality: ""
[account] + candidates.29.evidence_quality: ""
[account] + candidates.30.evidence_quality: ""
[account] + candidates.31.evidence_quality: ""
[account] + candidates.32.evidence_quality: ""
[account] + candidates.33.evidence_quality: ""
[account] + candidates.34.evidence_quality: ""
[account] + candidates.35.evidence_quality: ""
[account] + candidates.36.evidence_quality: ""
[account] + candidates.37.evidence_quality: "good"
[account] + candidates.38.evidence_quality: ""
[account] + candidates.39.evidence_quality: ""
[account] + candidates.40.evidence_quality: ""
[account] + candidates.41.evidence_quality: "good"
[account] + candidates.42.evidence_quality: ""
[account] + candidates.43.evidence_quality: "mixed"
[account] + candidates.44.evidence_quality: ""
[account] + candidates.45.evidence_quality: "good"
[account] + candidates.46.evidence_quality: ""
[account] + candidates.47.evidence_quality: ""
[account] + candidates.48.evidence_quality: ""
[account] + candidates.49.evidence_quality: ""
[account] + candidates.50.evidence_quality: ""
[account] + candidates.51.evidence_quality: ""
[account] + candidates.52.evidence_quality: ""
[account] + candidates.53.evidence_quality: ""
[account] + candidates.54.evidence_quality: "unconfirmed"
[account] + candidates.55.evidence_quality: "good"
[account] + candidates.56.evidence_quality: ""
[account] + candidates.57.evidence_quality: "unconfirmed"
[account] + candidates.58.evidence_quality: ""
[account] + candidates.59.evidence_quality: ""
[account] + candidates.60.evidence_quality: ""
[account] + candidates.61.evidence_quality: ""
[account] + candidates.62.evidence_quality: ""
[account] + candidates.63.evidence_quality: ""
[account] + candidates.64.evidence_quality: ""
[account] + candidates.65.evidence_quality: ""
[account] + candidates.66.evidence_quality: ""
[account] + candidates.67.evidence_quality: ""
[account] + candidates.68.evidence_quality: ""
[account] + candidates.69.evidence_quality: ""
[account] + candidates.70.evidence_quality: ""
[account] + candidates.71.evidence_quality: ""
[account] + candidates.72.evidence_quality: ""
[account] + candidates.73.evidence_quality: ""
[account] + candidates.74.evidence_quality: "mixed"
[account] + candidates.75.evidence_quality: "unconfirmed"
[account] + candidates.76.evidence_quality: "unconfirmed"
[account] + candidates.77.evidence_quality: ""
[account] + candidates.78.evidence_quality: ""
[account] + candidates.79.evidence_quality: ""
[account] + candidates.80.evidence_quality: ""
[account] + candidates.81.evidence_quality: ""
[account] + candidates.82.evidence_quality: ""
[account] + candidates.83.evidence_quality: ""
[account] + candidates.84.evidence_quality: ""
[account] + candidates.85.evidence_quality: "unconfirmed"
[account] + candidates.86.evidence_quality: ""
[account] + candidates.87.evidence_quality: ""
[account] + candidates.88.evidence_quality: "unconfirmed"
[account] + candidates.89.evidence_quality: ""
[account] + candidates.90.evidence_quality: ""
[account] + candidates.91.evidence_quality: ""
[account] + candidates.92.evidence_quality: ""
[account] + candidates.93.evidence_quality: ""
[account] + candidates.94.evidence_quality: ""
[account] + candidates.95.evidence_quality: ""
[account] + candidates.96.evidence_quality: ""
[account] + candidates.97.evidence_quality: ""
[account] + candidates.98.evidence_quality: ""
[account] + candidates.99.evidence_quality: ""
[account] + candidates.100.evidence_quality: ""
[account] + candidates.101.evidence_quality: ""
[account] + candidates.102.evidence_quality: ""
[account] + candidates.103.evidence_quality: ""
[account] + candidates.104.evidence_quality: ""
[account] + candidates.105.evidence_quality: ""
[account] + candidates.106.evidence_quality: ""
[account] + candidates.107.evidence_quality: ""
[account] + candidates.108.evidence_quality: ""
[account] + candidates.109.evidence_quality: "good"
[account] + candidates.110.evidence_quality: "unconfirmed"
[account] + candidates.111.evidence_quality: ""
[account] + candidates.112.evidence_quality: ""
[account] + candidates.113.evidence_quality: ""
[account] + candidates.114.evidence_quality: ""
[account] + candidates.115.evidence_quality: ""
[account] + candidates.116.evidence_quality: ""
[account] + candidates.117.evidence_quality: "unconfirmed"
[account] + candidates.118.evidence_quality: ""
[account] + candidates.119.evidence_quality: "unconfirmed"
[account] + candidates.120.evidence_quality: ""
[account] + candidates.121.evidence_quality: "unconfirmed"
[account] + candidates.122.evidence_quality: ""
[account] + candidates.123.evidence_quality: ""
[account] + candidates.124.evidence_quality: "unconfirmed"
[account] + candidates.125.evidence_quality: ""
[account] + candidates.126.evidence_quality: "unconfirmed"
[account] + candidates.127.evidence_quality: "unconfirmed"
[account] + candidates.128.evidence_quality: ""
[account] + candidates.129.evidence_quality: ""
[account] + candidates.130.evidence_quality: ""
[account] + candidates.131.evidence_quality: ""
[account] + candidates.132.evidence_quality: ""
[account] + candidates.133.evidence_quality: ""
[account] + candidates.134.evidence_quality: ""
[account] + candidates.135.evidence_quality: ""
[account] + candidates.136.evidence_quality: ""
[account] + candidates.137.evidence_quality: ""
[account] + candidates.138.evidence_quality: ""
[account] + candidates.139.evidence_quality: ""
[account] + candidates.140.evidence_quality: "unconfirmed"
[account] + candidates.141.evidence_quality: ""
[account] + candidates.142.evidence_quality: ""
[account] + candidates.143.evidence_quality: ""
[account] + candidates.144.evidence_quality: "unconfirmed"
[account] + candidates.145.evidence_quality: ""
[account] + candidates.146.evidence_quality: ""
[account] + candidates.147.evidence_quality: ""
[account] + candidates.148.evidence_quality: ""
[account] + candidates.149.evidence_quality: ""
[account] + candidates.150.evidence_quality: ""
[account] + candidates.151.evidence_quality: ""
[account] + candidates.152.evidence_quality: ""
[account] + candidates.153.evidence_quality: ""
[account] + candidates.154.evidence_quality: ""
[account] + candidates.155.evidence_quality: ""
[account] + candidates.156.evidence_quality: ""
[account] + candidates.157.evidence_quality: "unconfirmed"
[account] + candidates.158.evidence_quality: "unconfirmed"
[account] + candidates.159.evidence_quality: ""
[account] + candidates.160.evidence_quality: "good"
[account] + candidates.161.evidence_quality: "unconfirmed"
[account] + candidates.162.evidence_quality: ""
[account] + candidates.163.evidence_quality: ""
[account] + candidates.164.evidence_quality: ""
[account] + candidates.165.evidence_quality: ""
[account] + candidates.166.evidence_quality: ""
[account] + candidates.167.evidence_quality: ""
[account] + candidates.168.evidence_quality: ""
[account] + candidates.169.evidence_quality: ""
[account] + candidates.170.evidence_quality: "unconfirmed"
[account] + candidates.171.evidence_quality: ""
[account] + candidates.172.evidence_quality: ""
[account] + candidates.173.evidence_quality: ""
[account] + candidates.174.evidence_quality: ""
[account] + candidates.175.evidence_quality: ""
[account] + candidates.176.evidence_quality: ""
[account] + candidates.177.evidence_quality: ""
[account] + candidates.178.evidence_quality: ""
[account] + candidates.179.evidence_quality: ""
[account] + candidates.180.evidence_quality: ""
[account] + candidates.181.evidence_quality: ""
[account] + candidates.182.evidence_quality: ""
[account] + candidates.183.evidence_quality: ""
[account] + candidates.184.evidence_quality: ""
[account] + candidates.185.evidence_quality: ""
[account] + candidates.186.evidence_quality: ""
[account] + candidates.187.evidence_quality: ""
[account] + candidates.188.evidence_quality: ""
[account] + candidates.189.evidence_quality: "unconfirmed"
[account] + candidates.190.evidence_quality: ""
[account] + candidates.191.evidence_quality: ""
[account] + candidates.192.evidence_quality: ""
[account] + candidates.193.evidence_quality: "unconfirmed"
[account] + candidates.194.evidence_quality: ""
[account] + candidates.195.evidence_quality: ""
[account] + candidates.196.evidence_quality: ""
[account] + candidates.197.evidence_quality: ""
[account] + candidates.198.evidence_quality: ""
[account] + candidates.199.evidence_quality: ""
...
```

## 2026-10-17 20:46, model 6.5

Model 6.5: kit conditions in the pair model (knowledge/kit_conditions.yaml; one fitted effect per support when its party condition is unmet: Escoffier -0.167 with fewer than four Hydro/Cryo members, Chevreuse -0.141 outside an all Pyro/Electro party; cross-validated median error 6.41% to 6.25%, unmet-lineup bias +3.0% to +0.6%). 93 candidates with an unmet condition move (median -2.5), 40 others by at most 1.6. Top pulls: Furina passes Escoffier on rosters with no other Hydro member (pull_enabler_for_skirk, pull_shenhe_for_ayaka), where Escoffier's shred cannot reach full strength; arlecchino_bennett: Mavuika first. The account scenario's fourth team takes Lan Yan over Citlali (a tie the report already discloses).

9432 changed values in 37 outputs: account, roster_alhaitham_nahida, roster_arlecchino_bennett, roster_ayaka_freeze_core, roster_ayaka_kazuha_over_sucrose, roster_carry_gap_supports_only, roster_flins_aino_over_xingqiu, roster_flins_lunar_core, roster_hutao_double_hydro, roster_hyperbloom_core, roster_mavuika_citlali, roster_mavuika_sidegrade_for_arlecchino, roster_navia_xilonen, roster_neuvillette_furina_kazuha, roster_neuvillette_sidegrade_with_neuvillette_like, roster_no_clorinde_lunar, roster_no_freeze_with_pyro, roster_no_mizuki_hyperbloom_lead, roster_no_neuvillette_mono_pyro, roster_no_raiden_damage_anemo_carry, roster_plan_ayaka_with_hutao_plan_hutao_and_ayaka, roster_plan_flins_keeps_lunar_core, roster_plan_raiden_and_nahida, roster_pull_citlali_for_mavuika, roster_pull_columbina_for_flins, roster_pull_enabler_for_skirk, roster_pull_furina_for_neuvillette, roster_pull_hydro_for_hutao, roster_pull_shenhe_for_ayaka, roster_pull_trigger_for_hyperbloom.

```
[account] ~ candidates.1.expected: 70.9 -> 70.8
[account] ~ candidates.1.ranking: 64.3 -> 64.1
[account] ~ candidates.1.sd: 9.8 -> 9.9
[account] ~ candidates.2.expected: 69.3 -> 68.5
[account] ~ candidates.2.ranking: 62.0 -> 61.3
[account] ~ candidates.4.sd: 10.1 -> 10.2
[account] ~ candidates.5.expected: 65.3 -> 65.4
[account] ~ candidates.5.sd: 8.7 -> 8.8
[account] ~ candidates.7.expected: 63.0 -> 63.3
[account] ~ candidates.7.ranking: 57.2 -> 57.4
[account] ~ candidates.7.sd: 8.5 -> 8.6
[account] ~ candidates.8.expected: 59.9 -> 59.8
[account] ~ candidates.8.ranking: 55.0 -> 54.9
[account] ~ candidates.9.expected: 58.4 -> 58.0
[account] ~ candidates.9.ranking: 53.2 -> 52.9
[account] ~ candidates.10.ranking: 52.5 -> 52.2
[account] ~ candidates.10.sd: 14.9 -> 15.3
[account] ~ candidates.11.expected: 60.9 -> 60.8
[account] ~ candidates.11.ranking: 52.3 -> 52.1
[account] ~ candidates.12.expected: 55.3 -> 54.9
[account] ~ candidates.12.label: "Razor dual carry · Overloaded" -> "Raiden Shogun and Ineffa dual carry · Overloaded"
[account] ~ candidates.12.lead: "Razor" -> "Raiden Shogun"
[account] ~ candidates.12.lineup.1: "Fischl" -> "Ineffa"
[account] ~ candidates.12.lineup.2: "Razor" -> "Raiden Shogun"
[account] ~ candidates.12.lineup.3: "Yae Miko" -> "Xiangling"
[account] ~ candidates.12.ranking: 51.1 -> 51.4
[account] ~ candidates.12.sd: 6.2 -> 5.2
[account] ~ candidates.12.template: "auto_overloaded_electro_carry" -> "overloaded"
[account] ~ candidates.13.ranking: 50.8 -> 51.0
[account] ~ candidates.13.sd: 14.8 -> 14.5
[account] ~ candidates.14.expected: 53.3 -> 55.1
[account] ~ candidates.14.label: "Raiden Shogun and Ineffa dual carry · Overloaded" -> "Razor dual carry · Overloaded"
[account] ~ candidates.14.lead: "Raiden Shogun" -> "Razor"
[account] ~ candidates.14.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.14.lineup.2: "Raiden Shogun" -> "Razor"
[account] ~ candidates.14.lineup.3: "Xiangling" -> "Yae Miko"
[account] ~ candidates.14.ranking: 49.8 -> 51.0
[account] ~ candidates.14.sd: 5.2 -> 6.0
[account] ~ candidates.14.template: "overloaded" -> "auto_overloaded_electro_carry"
[account] ~ candidates.15.expected: 54.6 -> 57.6
[account] ~ candidates.15.label: "Ineffa hypercarry · incidental Lunar-Charged, Swirl" -> "Ineffa and Fischl dual carry · incidental Overloaded"
[account] ~ candidates.15.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.15.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.15.lineup.2: "Sucrose" -> "Ineffa"
[account] ~ candidates.15.lineup.3: "Xingqiu" -> "Xiangling"
[account] ~ candidates.15.ranking: 49.4 -> 50.4
[account] ~ candidates.15.sd: 7.7 -> 10.8
[account] ~ candidates.15.template: "lunar_charged_offfield" -> "overloaded"
[account] ~ candidates.16.expected: 56.9 -> 54.8
[account] ~ candidates.16.label: "Ineffa and Fischl dual carry · incidental Overloaded" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.16.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.16.lineup.1: "Fischl" -> "Ineffa"
[account] ~ candidates.16.lineup.2: "Ineffa" -> "Sucrose"
[account] ~ candidates.16.lineup.3: "Xiangling" -> "Xingqiu"
[account] ~ candidates.16.ranking: 49.4 -> 49.6
[account] ~ candidates.16.sd: 11.1 -> 7.8
[account] ~ candidates.16.template: "overloaded" -> "lunar_charged_offfield"
[account] ~ candidates.17.evidence_quality: "" -> "good"
[account] ~ candidates.17.evidence_state: "kit-model" -> "simulation"
[account] ~ candidates.17.expected: 58.4 -> 51.1
[account] ~ candidates.17.fit_source: "model" -> "pairmodel"
[account] ~ candidates.17.label: "Ineffa hypercarry · incidental Lunar-Charged, Swirl" -> "Yae Miko dual carry · Overloaded from Xiangling"
[account] ~ candidates.17.lead: "Ineffa" -> "Yae Miko"
[account] ~ candidates.17.lineup.0: "Aino" -> "Chevreuse"
[account] ~ candidates.17.lineup.1: "Alyosha" -> "Fischl"
[account] ~ candidates.17.lineup.2: "Ineffa" -> "Xiangling"
[account] ~ candidates.17.lineup.3: "Sucrose" -> "Yae Miko"
[account] ~ candidates.17.ranking: 49.0 -> 48.7
[account] ~ candidates.17.route: "provisional_kit" -> "exact_community"
[account] ~ candidates.17.sd: 13.9 -> 3.6
[account] ~ candidates.17.template: "lunar_charged_offfield" -> "overloaded"
[account] ~ candidates.17.tier: "E" -> "B"
[account] ~ candidates.18.evidence_quality: "good" -> ""
[account] ~ candidates.18.evidence_state: "simulation" -> "kit-model"
[account] ~ candidates.18.expected: 51.1 -> 58.0
[account] ~ candidates.18.fit_source: "pairmodel" -> "model"
[account] ~ candidates.18.label: "Yae Miko dual carry · Overloaded from Xiangling" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.18.lead: "Yae Miko" -> "Ineffa"
[account] ~ candidates.18.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.18.lineup.1: "Fischl" -> "Alyosha"
[account] ~ candidates.18.lineup.2: "Xiangling" -> "Ineffa"
[account] ~ candidates.18.lineup.3: "Yae Miko" -> "Sucrose"
[account] ~ candidates.18.ranking: 48.7 -> 48.5
[account] ~ candidates.18.route: "exact_community" -> "provisional_kit"
[account] ~ candidates.18.sd: 3.6 -> 14.2
[account] ~ candidates.18.template: "overloaded" -> "lunar_charged_offfield"
[account] ~ candidates.18.tier: "B" -> "E"
[account] ~ candidates.19.evidence_quality: "" -> "unconfirmed"
[account] ~ candidates.19.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.19.expected: 51.8 -> 51.9
[account] ~ candidates.19.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.19.label: "Razor dual carry · incidental Vaporize, Overloaded" -> "Razor dual carry · Overloaded from Xiangling"
[account] ~ candidates.19.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.19.lineup.1: "Ineffa" -> "Fischl"
[account] ~ candidates.19.lineup.3: "Xingqiu" -> "Xiangling"
[account] ~ candidates.19.route: "pair_model" -> "exact_community"
[account] ~ candidates.19.sd: 5.0 -> 5.2
[account] ~ candidates.19.template: "auto_electro_charged_electro_carry" -> "auto_overloaded_electro_carry"
[account] ~ candidates.19.tier: "C" -> "B"
[account] ~ candidates.20.evidence_quality: "unconfirmed" -> ""
[account] ~ candidates.20.evidence_state: "simulation" -> "interpolation"
[account] ~ candidates.20.expected: 51.9 -> 51.5
[account] ~ candidates.20.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.20.label: "Razor dual carry · Overloaded from Xiangling" -> "Razor dual carry · incidental Vaporize, Overloaded"
[account] ~ candidates.20.lineup.0: "Chevreuse" -> "Bennett"
[account] ~ candidates.20.lineup.1: "Fischl" -> "Ineffa"
[account] ~ candidates.20.lineup.3: "Xiangling" -> "Xingqiu"
[account] ~ candidates.20.ranking: 48.5 -> 48.2
[account] ~ candidates.20.route: "exact_community" -> "pair_model"
[account] ~ candidates.20.sd: 5.2 -> 4.9
[account] ~ candidates.20.template: "auto_overloaded_electro_carry" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.20.tier: "B" -> "C"
[account] ~ candidates.21.expected: 51.3 -> 51.7
[account] ~ candidates.21.label: "Yoimiya hypercarry · Melt" -> "No single carry dual carry · incidental Electro-Charged"
[account] ~ candidates.21.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.21.lineup.0: "Bennett" -> "Ineffa"
[account] ~ candidates.21.lineup.1: "Chevreuse" -> "Raiden Shogun"
[account] ~ candidates.21.lineup.2: "Citlali" -> "Razor"
[account] ~ candidates.21.lineup.3: "Yoimiya" -> "Xingqiu"
[account] ~ candidates.21.ranking: 47.9 -> 48.1
[account] ~ candidates.21.sd: 5.0 -> 5.3
[account] ~ candidates.21.template: "auto_melt_pyro_carry" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.22.expected: 52.4 -> 52.0
[account] ~ candidates.22.ranking: 47.9 -> 47.6
[account] ~ candidates.22.sd: 6.6 -> 6.5
[account] ~ candidates.23.expected: 51.4 -> 50.6
[account] ~ candidates.23.label: "No single carry dual carry · incidental Electro-Charged" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.23.lineup.0: "Ineffa" -> "Fischl"
[account] ~ candidates.23.lineup.1: "Raiden Shogun" -> "Ineffa"
[account] ~ candidates.23.ranking: 47.8 -> 47.1
[account] ~ candidates.23.sd: 5.4 -> 5.3
[account] ~ candidates.24.evidence_quality: "" -> "good"
[account] ~ candidates.24.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.24.expected: 50.8 -> 49.1
[account] ~ candidates.24.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.24.label: "Razor dual carry · incidental Electro-Charged" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.24.lead: "Razor" -> "Yoimiya"
[account] ~ candidates.24.lineup.0: "Fischl" -> "Bennett"
[account] ~ candidates.24.lineup.1: "Ineffa" -> "Chevreuse"
[account] ~ candidates.24.lineup.2: "Razor" -> "Fischl"
[account] ~ candidates.24.lineup.3: "Xingqiu" -> "Yoimiya"
[account] ~ candidates.24.ranking: 47.2 -> 46.8
[account] ~ candidates.24.route: "pair_model" -> "exact_community"
[account] ~ candidates.24.sd: 5.4 -> 3.4
[account] ~ candidates.24.template: "auto_electro_charged_electro_carry" -> "auto_overloaded_pyro_carry"
[account] ~ candidates.24.tier: "C" -> "B"
[account] ~ candidates.25.expected: 53.6 -> 55.7
[account] ~ candidates.25.label: "Razor dual carry · incidental Electro-Charged" -> "Flins dual carry · Lunar-Charged"
[account] ~ candidates.25.lead: "Razor" -> "Flins"
[account] ~ candidates.25.lineup.0: "Chevreuse" -> "Aino"
[account] ~ candidates.25.lineup.1: "Ineffa" -> "Diona"
[account] ~ candidates.25.lineup.2: "Razor" -> "Flins"
[account] ~ candidates.25.lineup.3: "Xingqiu" -> "Ineffa"
[account] ~ candidates.25.ranking: 47.0 -> 46.7
[account] ~ candidates.25.sd: 9.7 -> 13.4
[account] ~ candidates.25.template: "auto_electro_charged_electro_carry" -> "lunar_charged"
[account] ~ candidates.25.tier: "D" -> "C"
[account] ~ candidates.26.evidence_quality: "good" -> ""
[account] ~ candidates.26.evidence_state: "simulation" -> "interpolation"
[account] ~ candidates.26.expected: 49.1 -> 50.1
[account] ~ candidates.26.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.26.label: "Yoimiya dual carry · Overloaded" -> "Razor dual carry · Overloaded"
[account] ~ candidates.26.lead: "Yoimiya" -> "Razor"
[account] ~ candidates.26.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.26.lineup.1: "Chevreuse" -> "Fischl"
[account] ~ candidates.26.lineup.2: "Fischl" -> "Raiden Shogun"
[account] ~ candidates.26.lineup.3: "Yoimiya" -> "Razor"
[account] ~ candidates.26.ranking: 46.8 -> 46.5
[account] ~ candidates.26.route: "exact_community" -> "pair_model"
[account] ~ candidates.26.sd: 3.4 -> 5.4
[account] ~ candidates.26.template: "auto_overloaded_pyro_carry" -> "auto_overloaded_electro_carry"
[account] ~ candidates.26.tier: "B" -> "C"
[account] ~ candidates.27.expected: 55.9 -> 50.1
[account] ~ candidates.27.label: "Flins dual carry · Lunar-Charged" -> "Ineffa hypercarry · incidental Lunar-Charged, Swirl"
[account] ~ candidates.27.lead: "Flins" -> "Ineffa"
[account] ~ candidates.27.lineup.1: "Diona" -> "Beidou"
[account] ~ candidates.27.lineup.2: "Flins" -> "Ineffa"
[account] ~ candidates.27.lineup.3: "Ineffa" -> "Sucrose"
[account] ~ candidates.27.ranking: 46.6 -> 45.7
[account] ~ candidates.27.sd: 13.7 -> 6.6
[account] ~ candidates.28.expected: 50.8 -> 51.7
[account] ~ candidates.28.label: "Razor on-field · Overloaded" -> "Razor dual carry · incidental Electro-Charged"
[account] ~ candidates.28.lineup.1: "Fischl" -> "Ineffa"
[account] ~ candidates.28.lineup.3: "Zhongli" -> "Xingqiu"
[account] ~ candidates.28.ranking: 46.6 -> 45.4
[account] ~ candidates.28.sd: 6.2 -> 9.2
[account] ~ candidates.28.template: "auto_overloaded_electro_carry" -> "auto_electro_charged_electro_carry"
[account] ~ candidates.28.tier: "C" -> "D"
[account] ~ candidates.29.expected: 49.5 -> 48.3
[account] ~ candidates.29.fit_source: "pairmodel" -> "model"
[account] ~ candidates.29.label: "Razor on-field · incidental Overloaded" -> "Fischl dual carry · Quicken · incidental Swirl, Electro-Charged"
[account] ~ candidates.29.lead: "Razor" -> "Fischl"
[account] ~ candidates.29.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.29.lineup.1: "Chevreuse" -> "Sucrose"
[account] ~ candidates.29.lineup.2: "Razor" -> "Xingqiu"
[account] ~ candidates.29.lineup.3: "Zhongli" -> "Yaoyao"
[account] ~ candidates.29.ranking: 46.5 -> 45.1
[account] ~ candidates.29.sd: 4.5 -> 4.7
[account] ~ candidates.29.template: "auto_overloaded_electro_carry" -> "hyperbloom"
[account] ~ candidates.30.expected: 49.7 -> 47.8
...
```

## 2026-10-18 02:48, model 6.6

model 6.6 mechanics layer: reviewed kits give Chevreuse's party condition its 'at least one Pyro and one Electro' clause (official kit text), so all-Pyro Chevreuse lineups now take the fitted unmet-condition term (Diluc/Bennett/Chevreuse/Xiangling 37.6 -> 32.7, Arlecchino/Bennett/Chevreuse/Xiangling 50.5 -> 43.8); Arlecchino's Abyss team and Columbina's pull gain follow. No training lineup changed flag, so the pair model is unchanged.

923 changed values in 2 outputs: account, roster_mavuika_sidegrade_for_arlecchino.

```
[account] ~ candidates.108.expected: 37.6 -> 36.9
[account] ~ candidates.108.label: "Diluc dual carry" -> "Yae Miko and Fischl dual carry · incidental Overloaded"
[account] ~ candidates.108.lead: "Diluc" -> "Yae Miko"
[account] ~ candidates.108.lineup.1: "Chevreuse" -> "Fischl"
[account] ~ candidates.108.lineup.2: "Diluc" -> "Kujou Sara"
[account] ~ candidates.108.lineup.3: "Xiangling" -> "Yae Miko"
[account] ~ candidates.108.sd: 4.6 -> 3.5
[account] ~ candidates.108.template: "auto_mono_pyro" -> "auto_mono_electro"
[account] ~ candidates.109.expected: 36.9 -> 38.7
[account] ~ candidates.109.label: "Yae Miko and Fischl dual carry · incidental Overloaded" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.109.lead: "Yae Miko" -> "Yoimiya"
[account] ~ candidates.109.lineup.0: "Bennett" -> "Citlali"
[account] ~ candidates.109.lineup.1: "Fischl" -> "Kaedehara Kazuha"
[account] ~ candidates.109.lineup.2: "Kujou Sara" -> "Sucrose"
[account] ~ candidates.109.lineup.3: "Yae Miko" -> "Yoimiya"
[account] ~ candidates.109.sd: 3.5 -> 6.2
[account] ~ candidates.109.template: "auto_mono_electro" -> "auto_melt_pyro_carry"
[account] ~ candidates.109.tier: "C" -> "D"
[account] ~ candidates.110.expected: 38.7 -> 36.9
[account] ~ candidates.110.label: "Yoimiya hypercarry · Melt" -> "Fischl and Keqing dual carry · Aggravate + Quicken + Overloaded"
[account] ~ candidates.110.lead: "Yoimiya" -> "Fischl"
[account] ~ candidates.110.lineup.0: "Citlali" -> "Fischl"
[account] ~ candidates.110.lineup.1: "Kaedehara Kazuha" -> "Keqing"
[account] ~ candidates.110.lineup.2: "Sucrose" -> "Xiangling"
[account] ~ candidates.110.lineup.3: "Yoimiya" -> "Yaoyao"
[account] ~ candidates.110.ranking: 34.5 -> 34.4
[account] ~ candidates.110.sd: 6.2 -> 3.8
[account] ~ candidates.110.template: "auto_melt_pyro_carry" -> "aggravate"
[account] ~ candidates.110.tier: "D" -> "C"
[account] ~ candidates.111.expected: 36.9 -> 36.7
[account] ~ candidates.111.label: "Fischl and Keqing dual carry · Aggravate + Quicken + Overloaded" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.111.lead: "Fischl" -> "Yoimiya"
[account] ~ candidates.111.lineup.0: "Fischl" -> "Bennett"
[account] ~ candidates.111.lineup.1: "Keqing" -> "Rosaria"
[account] ~ candidates.111.lineup.2: "Xiangling" -> "Sucrose"
[account] ~ candidates.111.lineup.3: "Yaoyao" -> "Yoimiya"
[account] ~ candidates.111.ranking: 34.4 -> 34.3
[account] ~ candidates.111.sd: 3.8 -> 3.5
[account] ~ candidates.111.template: "aggravate" -> "auto_melt_pyro_carry"
[account] ~ candidates.112.expected: 36.7 -> 36.9
[account] ~ candidates.112.label: "Yoimiya hypercarry · Melt" -> "Raiden Shogun dual carry · Hyperbloom + Burgeon + Vaporize · incidental Overloaded, Quicken"
[account] ~ candidates.112.lead: "Yoimiya" -> "Raiden Shogun"
[account] ~ candidates.112.lineup.1: "Rosaria" -> "Collei"
[account] ~ candidates.112.lineup.2: "Sucrose" -> "Raiden Shogun"
[account] ~ candidates.112.lineup.3: "Yoimiya" -> "Xingqiu"
[account] ~ candidates.112.ranking: 34.3 -> 34.2
[account] ~ candidates.112.sd: 3.5 -> 4.0
[account] ~ candidates.112.template: "auto_melt_pyro_carry" -> "auto_hyperbloom_electro_carry"
[account] ~ candidates.113.evidence_quality: "" -> "unconfirmed"
[account] ~ candidates.113.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.113.expected: 36.9 -> 36.5
[account] ~ candidates.113.label: "Raiden Shogun dual carry · Hyperbloom + Burgeon + Vaporize · incidental Overloaded, Quicken" -> "Yae Miko hypercarry · incidental Overloaded"
[account] ~ candidates.113.lead: "Raiden Shogun" -> "Yae Miko"
[account] ~ candidates.113.lineup.1: "Collei" -> "Kaedehara Kazuha"
[account] ~ candidates.113.lineup.2: "Raiden Shogun" -> "Kujou Sara"
[account] ~ candidates.113.lineup.3: "Xingqiu" -> "Yae Miko"
[account] ~ candidates.113.ranking: 34.2 -> 34.1
[account] ~ candidates.113.route: "pair_model" -> "exact_community"
[account] ~ candidates.113.sd: 4.0 -> 3.6
[account] ~ candidates.113.template: "auto_hyperbloom_electro_carry" -> "auto_mono_electro"
[account] ~ candidates.113.tier: "C" -> "B"
[account] ~ candidates.114.evidence_quality: "unconfirmed" -> ""
[account] ~ candidates.114.evidence_state: "simulation" -> "interpolation"
[account] ~ candidates.114.expected: 36.5 -> 36.8
[account] ~ candidates.114.label: "Yae Miko hypercarry · incidental Overloaded" -> "Chiori hypercarry"
[account] ~ candidates.114.lead: "Yae Miko" -> "Chiori"
[account] ~ candidates.114.lineup.1: "Kaedehara Kazuha" -> "Chiori"
[account] ~ candidates.114.lineup.2: "Kujou Sara" -> "Rosaria"
[account] ~ candidates.114.lineup.3: "Yae Miko" -> "Zhongli"
[account] ~ candidates.114.ranking: 34.1 -> 34.0
[account] ~ candidates.114.route: "exact_community" -> "pair_model"
[account] ~ candidates.114.sd: 3.6 -> 4.1
[account] ~ candidates.114.template: "auto_mono_electro" -> "auto_geo_carry"
[account] ~ candidates.114.tier: "B" -> "C"
[account] ~ candidates.115.expected: 36.8 -> 36.2
[account] ~ candidates.115.label: "Chiori hypercarry" -> "Yoimiya hypercarry · Melt"
[account] ~ candidates.115.lead: "Chiori" -> "Yoimiya"
[account] ~ candidates.115.lineup.1: "Chiori" -> "Chevreuse"
[account] ~ candidates.115.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.115.ranking: 34.0 -> 33.9
[account] ~ candidates.115.sd: 4.1 -> 3.5
[account] ~ candidates.115.template: "auto_geo_carry" -> "auto_melt_pyro_carry"
[account] ~ candidates.116.evidence_quality: "" -> "unconfirmed"
[account] ~ candidates.116.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.116.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.116.label: "Yoimiya hypercarry · Melt" -> "Chiori dual carry · incidental Overloaded"
[account] ~ candidates.116.lead: "Yoimiya" -> "Chiori"
[account] ~ candidates.116.lineup.1: "Chevreuse" -> "Chiori"
[account] ~ candidates.116.lineup.2: "Rosaria" -> "Fischl"
[account] ~ candidates.116.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.116.ranking: 33.9 -> 33.8
[account] ~ candidates.116.route: "pair_model" -> "exact_community"
[account] ~ candidates.116.sd: 3.5 -> 3.6
[account] ~ candidates.116.template: "auto_melt_pyro_carry" -> "auto_geo_carry"
[account] ~ candidates.116.tier: "C" -> "B"
[account] ~ candidates.117.label: "Chiori dual carry · incidental Overloaded" -> "Yoimiya hypercarry · Vaporize"
[account] ~ candidates.117.lead: "Chiori" -> "Yoimiya"
[account] ~ candidates.117.lineup.1: "Chiori" -> "Sucrose"
[account] ~ candidates.117.lineup.2: "Fischl" -> "Xingqiu"
[account] ~ candidates.117.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.117.template: "auto_geo_carry" -> "vaporize_pyro"
[account] ~ candidates.118.evidence_quality: "unconfirmed" -> ""
[account] ~ candidates.118.evidence_state: "simulation" -> "interpolation"
[account] ~ candidates.118.expected: 36.2 -> 36.1
[account] ~ candidates.118.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.118.label: "Yoimiya hypercarry · Vaporize" -> "Yoimiya dual carry · incidental Overloaded"
[account] ~ candidates.118.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.118.lineup.1: "Sucrose" -> "Xiangling"
[account] ~ candidates.118.lineup.2: "Xingqiu" -> "Yoimiya"
[account] ~ candidates.118.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.118.route: "exact_community" -> "pair_model"
[account] ~ candidates.118.sd: 3.6 -> 3.5
[account] ~ candidates.118.template: "vaporize_pyro" -> "auto_overloaded_pyro_carry"
[account] ~ candidates.118.tier: "B" -> "C"
[account] ~ candidates.119.evidence_quality: "" -> "unconfirmed"
[account] ~ candidates.119.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.119.label: "Yoimiya dual carry · incidental Overloaded" -> "Yae Miko and Raiden Shogun dual carry · incidental Overloaded"
[account] ~ candidates.119.lead: "Yoimiya" -> "Yae Miko"
[account] ~ candidates.119.lineup.0: "Fischl" -> "Bennett"
[account] ~ candidates.119.lineup.1: "Xiangling" -> "Kaedehara Kazuha"
[account] ~ candidates.119.lineup.2: "Yoimiya" -> "Raiden Shogun"
[account] ~ candidates.119.lineup.3: "Zhongli" -> "Yae Miko"
[account] ~ candidates.119.ranking: 33.8 -> 33.7
[account] ~ candidates.119.route: "pair_model" -> "exact_community"
[account] ~ candidates.119.sd: 3.5 -> 3.6
[account] ~ candidates.119.template: "auto_overloaded_pyro_carry" -> "electro_hypercarry"
[account] ~ candidates.119.tier: "C" -> "B"
[account] ~ candidates.120.evidence_quality: "unconfirmed" -> ""
[account] ~ candidates.120.evidence_state: "simulation" -> "kit-model"
[account] ~ candidates.120.expected: 36.1 -> 40.3
[account] ~ candidates.120.fit_source: "pairmodel" -> "model"
[account] ~ candidates.120.label: "Yae Miko and Raiden Shogun dual carry · incidental Overloaded" -> "Raiden Shogun and Fischl dual carry · incidental Swirl"
[account] ~ candidates.120.lead: "Yae Miko" -> "Raiden Shogun"
[account] ~ candidates.120.lineup.0: "Bennett" -> "Fischl"
[account] ~ candidates.120.lineup.1: "Kaedehara Kazuha" -> "Iansan"
[account] ~ candidates.120.lineup.2: "Raiden Shogun" -> "Kaedehara Kazuha"
[account] ~ candidates.120.lineup.3: "Yae Miko" -> "Raiden Shogun"
[account] ~ candidates.120.route: "exact_community" -> "provisional_kit"
[account] ~ candidates.120.sd: 3.6 -> 9.8
[account] ~ candidates.120.tier: "B" -> "E"
[account] ~ candidates.121.evidence_state: "kit-model" -> "interpolation"
[account] ~ candidates.121.expected: 40.3 -> 38.1
[account] ~ candidates.121.fit_source: "model" -> "pairmodel"
[account] ~ candidates.121.label: "Raiden Shogun and Fischl dual carry · incidental Swirl" -> "Kamisato Ayaka hypercarry · Freeze"
[account] ~ candidates.121.lead: "Raiden Shogun" -> "Kamisato Ayaka"
[account] ~ candidates.121.lineup.0: "Fischl" -> "Kamisato Ayaka"
[account] ~ candidates.121.lineup.1: "Iansan" -> "Kujou Sara"
[account] ~ candidates.121.lineup.2: "Kaedehara Kazuha" -> "Mona"
[account] ~ candidates.121.lineup.3: "Raiden Shogun" -> "Shenhe"
[account] ~ candidates.121.route: "provisional_kit" -> "pair_model"
[account] ~ candidates.121.sd: 9.8 -> 6.6
[account] ~ candidates.121.template: "electro_hypercarry" -> "freeze"
[account] ~ candidates.121.tier: "E" -> "C"
[account] ~ candidates.122.evidence_quality: "" -> "unconfirmed"
[account] ~ candidates.122.evidence_state: "interpolation" -> "simulation"
[account] ~ candidates.122.expected: 38.1 -> 36.1
[account] ~ candidates.122.fit_source: "pairmodel" -> "gcsim"
[account] ~ candidates.122.label: "Kamisato Ayaka hypercarry · Freeze" -> "Ganyu on-field · Melt"
[account] ~ candidates.122.lead: "Kamisato Ayaka" -> "Ganyu"
[account] ~ candidates.122.lineup.0: "Kamisato Ayaka" -> "Bennett"
[account] ~ candidates.122.lineup.1: "Kujou Sara" -> "Ganyu"
[account] ~ candidates.122.lineup.2: "Mona" -> "Xiangling"
[account] ~ candidates.122.lineup.3: "Shenhe" -> "Zhongli"
[account] ~ candidates.122.ranking: 33.7 -> 33.6
[account] ~ candidates.122.route: "pair_model" -> "exact_community"
[account] ~ candidates.122.sd: 6.6 -> 3.6
[account] ~ candidates.122.template: "freeze" -> "melt"
[account] ~ candidates.122.tier: "C" -> "B"
[account] ~ candidates.123.expected: 36.1 -> 36.0
[account] ~ candidates.123.label: "Ganyu on-field · Melt" -> "Chiori dual carry · incidental Superconduct"
[account] ~ candidates.123.lead: "Ganyu" -> "Chiori"
[account] ~ candidates.123.lineup.0: "Bennett" -> "Chiori"
[account] ~ candidates.123.lineup.1: "Ganyu" -> "Fischl"
[account] ~ candidates.123.lineup.2: "Xiangling" -> "Rosaria"
[account] ~ candidates.123.template: "melt" -> "auto_geo_carry"
[account] ~ candidates.124.evidence_quality: "unconfirmed" -> ""
[account] ~ candidates.124.evidence_state: "simulation" -> "interpolation"
[account] ~ candidates.124.expected: 36.0 -> 35.8
[account] ~ candidates.124.fit_source: "gcsim" -> "pairmodel"
[account] ~ candidates.124.label: "Chiori dual carry · incidental Superconduct" -> "Yoimiya dual carry · incidental Overloaded"
[account] ~ candidates.124.lead: "Chiori" -> "Yoimiya"
[account] ~ candidates.124.lineup.0: "Chiori" -> "Bennett"
[account] ~ candidates.124.lineup.2: "Rosaria" -> "Raiden Shogun"
[account] ~ candidates.124.lineup.3: "Zhongli" -> "Yoimiya"
[account] ~ candidates.124.ranking: 33.6 -> 33.5
[account] ~ candidates.124.route: "exact_community" -> "pair_model"
[account] ~ candidates.124.sd: 3.6 -> 3.5
[account] ~ candidates.124.template: "auto_geo_carry" -> "auto_overloaded_pyro_carry"
[account] ~ candidates.124.tier: "B" -> "C"
[account] ~ candidates.125.label: "Yoimiya dual carry · incidental Overloaded" -> "Yoimiya dual carry · Overloaded"
[account] ~ candidates.125.lineup.0: "Bennett" -> "Chevreuse"
[account] ~ candidates.125.lineup.2: "Raiden Shogun" -> "Yoimiya"
[account] ~ candidates.125.lineup.3: "Yoimiya" -> "Zhongli"
[account] ~ candidates.125.ranking: 33.5 -> 33.3
[account] ~ candidates.125.sd: 3.5 -> 3.7
[account] ~ candidates.126.expected: 35.8 -> 35.5
[account] ~ candidates.126.label: "Yoimiya dual carry · Overloaded" -> "Kamisato Ayato and Ineffa dual carry · incidental Swirl, Lunar-Charged"
[account] ~ candidates.126.lead: "Yoimiya" -> "Kamisato Ayato"
[account] ~ candidates.126.lineup.0: "Chevreuse" -> "Ineffa"
[account] ~ candidates.126.lineup.1: "Fischl" -> "Kaedehara Kazuha"
...
```

