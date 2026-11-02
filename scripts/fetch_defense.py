"""
Baixa da NBA.com o aproveitamento dos adversários quando cada jogador é o defensor mais próximo
(DFG% vs FG% normal) e salva em data/defense.json, que o site lê.

Fonte: endpoint "leaguedashptdefend" do stats.nba.com (rastreamento óptico da NBA).
Usa só a biblioteca padrão do Python, então não precisa instalar nada.

Uso:  python scripts/fetch_defense.py
"""
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

URL = "https://stats.nba.com/stats/leaguedashptdefend"
# A NBA.com recusa pedidos que não pareçam vir do site dela.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "Connection": "keep-alive",
}
# Categoria da NBA.com -> chave usada no site
CATEGORIES = {
    "Overall": "geral",
    "2 Pointers": "fg2",
    "3 Pointers": "fg3",
    "Less Than 6Ft": "aro",
    "Greater Than 15Ft": "longe",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "defense.json")


def current_season(today=None):
    """Temporada no formato da NBA.com. Até setembro ainda vale a temporada que começou no ano anterior."""
    today = today or dt.date.today()
    start = today.year if today.month >= 10 else today.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def fetch(category, season, tries=4):
    params = {
        "DefenseCategory": category, "LeagueID": "00", "PerMode": "Totals", "Season": season,
        "SeasonType": "Regular Season", "College": "", "Conference": "", "Country": "", "DateFrom": "",
        "DateTo": "", "Division": "", "DraftPick": "", "DraftYear": "", "GameSegment": "", "Height": "",
        "LastNGames": "0", "Location": "", "Month": "0", "OpponentTeamID": "0", "Outcome": "", "PORound": "0",
        "Period": "0", "PlayerExperience": "", "PlayerID": "", "PlayerPosition": "", "SeasonSegment": "",
        "StarterBench": "", "TeamID": "0", "VsConference": "", "VsDivision": "", "Weight": "",
    }
    url = URL + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except Exception as e:  # noqa: BLE001 - qualquer falha de rede conta como tentativa
            last = e
            print(f"  tentativa {attempt} de {tries} falhou: {e}", file=sys.stderr)
            time.sleep(5 * attempt)
    raise RuntimeError(f"NBA.com não respondeu para '{category}': {last}")


def parse(payload):
    """Cada categoria tem nomes de coluna diferentes, mas sempre na mesma ordem depois de FREQ:
    cestas, tentativas, % contra o defensor, % normal dos arremessadores, diferença."""
    rs = payload["resultSets"][0]
    head = rs["headers"]
    i = head.index("FREQ")
    col = {h: n for n, h in enumerate(head)}
    out = {}
    for row in rs["rowSet"]:
        m, a, pct, norm, diff = row[i + 1:i + 6]
        out[str(row[col["CLOSE_DEF_PERSON_ID"]])] = {
            "name": row[col["PLAYER_NAME"]],
            "team": row[col["PLAYER_LAST_TEAM_ABBREVIATION"]],
            "g": row[col["G"]] if "G" in col else row[col["GP"]],
            "cat": [m, a, pct, norm, diff],
        }
    return out


def main():
    season = os.environ.get("NBA_SEASON") or current_season()
    print(f"Temporada {season}")
    players = {}
    for category, key in CATEGORIES.items():
        print(f"Baixando '{category}'...")
        for pid, d in parse(fetch(category, season)).items():
            p = players.setdefault(pid, {"id": pid, "name": d["name"], "team": d["team"], "g": d["g"], "c": {}})
            p["c"][key] = d["cat"]
        time.sleep(2)  # educação com o servidor
    if not players:
        raise RuntimeError("A NBA.com respondeu, mas sem jogadores. Nada foi salvo.")
    data = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "season": season,
        "fields": ["cestas", "tentativas", "pct_contra", "pct_normal", "diferenca"],
        "players": sorted(players.values(), key=lambda p: p["name"]),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(players)} jogadores salvos em data/defense.json")


if __name__ == "__main__":
    main()
