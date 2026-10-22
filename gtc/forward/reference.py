"""The diverse reference set (phase F): teams chosen to cover mechanics families, each with a community rotation
for the reveal. Characters are representatives of mechanics, not targets: nothing is tuned per name.

Kit files (gtc/forward/kitfreeze.py) never use these teams as sources, so every team here is a blind test.
"""
REFERENCE = [
    {"team": ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"], "family": "Freeze"},
    {"team": ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Furina"], "family": "Freeze + HP manipulation"},
    {"team": ["Kamisato Ayaka", "Shenhe", "Escoffier", "Furina"], "family": "Freeze + composition condition"},
    {"team": ["Kamisato Ayaka", "Shenhe", "Bennett", "Xiangling"], "family": "Melt"},
    {"team": ["Hu Tao", "Xingqiu", "Yelan", "Zhongli"], "family": "Vaporize + stance"},
    {"team": ["Raiden Shogun", "Xingqiu", "Xiangling", "Bennett"], "family": "National (Vaporize, Overloaded, EC) + resource"},
    {"team": ["Razor", "Fischl", "Bennett", "Chevreuse"], "family": "Overloaded + Hexerei"},
    {"team": ["Fischl", "Nahida", "Sucrose", "Yae Miko"], "family": "Aggravate / Spread"},
    {"team": ["Furina", "Kuki Shinobu", "Nahida", "Yelan"], "family": "Hyperbloom"},
    {"team": ["Neuvillette", "Furina", "Kaedehara Kazuha", "Baizhu"], "family": "Hypercarry + stacks + HP"},
    {"team": ["Nahida", "Raiden Shogun", "Razor", "Xingqiu"], "family": "Dual window"},
    {"team": ["Flins", "Aino", "Ineffa", "Sucrose"], "family": "Lunar / Moonsign"},
]
TEAMS = [r["team"] for r in REFERENCE]
CHARACTERS = sorted({m for t in TEAMS for m in t})
