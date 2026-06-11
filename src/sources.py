"""Список RSS-источников игровых новостей.
Формат: (Человекочитаемое имя, URL RSS-ленты).
Можно свободно добавлять/удалять источники.
"""

FEEDS = [
    # --- Крупные мировые игровые СМИ ---
    ("IGN", "https://feeds.ign.com/ign/games-all"),
    ("PC Gamer", "https://www.pcgamer.com/rss/"),
    ("Eurogamer", "https://www.eurogamer.net/feed"),
    ("Polygon", "https://www.polygon.com/rss/index.xml"),
    ("GameSpot", "https://www.gamespot.com/feeds/news/"),
    ("Kotaku", "https://kotaku.com/rss"),
    ("VG247", "https://www.vg247.com/feed"),
    ("Rock Paper Shotgun", "https://www.rockpapershotgun.com/feed"),
    ("Game Informer", "https://www.gameinformer.com/news.xml"),
    ("Nintendo Life", "https://www.nintendolife.com/feeds/latest"),
    ("Push Square", "https://www.pushsquare.com/feeds/latest"),
    ("PCGamesN", "https://www.pcgamesn.com/mainrss.xml"),
    ("Engadget", "https://www.engadget.com/rss.xml"),

    # --- Русскоязычные ресурсы ---
    ("DTF", "https://dtf.ru/rss/all"),
    ("StopGame", "https://rss.stopgame.ru/rss_news.xml"),
    ("3DNews", "https://3dnews.ru/games/rss/"),
    ("VGTimes", "https://vgtimes.ru/rss/"),
]
