"""ON/OFF a partir do play-by-play oficial da NBA (cdn.nba.com).
Para cada jogo encerrado da temporada regular: reconstrói os 5 em quadra de cada time e soma, por formação,
segundos, pontos a favor/contra e posses (contadas pelo campo oficial "possession" de cada jogada).
Acumula em data/lineups.json; a cada execução processa só os jogos que faltam (REBUILD=1 refaz tudo)."""
import datetime as dt, gzip, json, os, re, sys, time, urllib.request

CDN = "https://cdn.nba.com/static/json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "lineups.json")


def get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as r:
                raw = r.read()
                return json.loads(gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw)
        except Exception as e:
            if k == tries - 1:
                raise RuntimeError(f"{url}: {e}")
            time.sleep(3 * (k + 1))


def clock(s):  # "PT11M48.00S" -> segundos restantes
    m = re.match(r"PT(\d+)M([\d.]+)S", s or "")
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None


def plen(n):
    return 720 if n <= 4 else 300


def team_lineups(box, actions, side):
    team, opp = box[side], box["awayTeam" if side == "homeTeam" else "homeTeam"]
    tid, oid = team["teamId"], opp["teamId"]
    roster = {p["personId"] for p in team["players"]}
    starters = [p["personId"] for p in team["players"] if str(p.get("starter")) == "1"]
    if len(starters) != 5:
        return None, None
    by_p = {}
    for a in actions:
        by_p.setdefault(a.get("period", 0), []).append(a)
    mine = lambda a: [x for x in (a.get("personIdsFilter") or [a.get("personId")]) if x in roster]
    is_sub = lambda a: a.get("actionType") == "substitution" and a.get("teamId") == tid

    def starters_of(lst, prev):
        start, entered = [], set()
        for a in lst:
            if is_sub(a):
                pid = a.get("personId")
                if a.get("subType") == "out" and pid not in entered and pid not in start:
                    start.append(pid)
                elif a.get("subType") == "in":
                    entered.add(pid)
            else:
                for pid in mine(a):
                    if pid not in entered and pid not in start:
                        start.append(pid)
            if len(start) >= 5:
                break
        for pid in prev or []:
            if len(start) >= 5:
                break
            if pid not in start and pid not in entered:
                start.append(pid)
        return start[:5]

    agg, on, prev_end = {}, list(starters), None
    last_h = last_a = 0
    home = side == "homeTeam"

    full = [list(starters)]  # última formação completa (entre a saída e a entrada de uma troca há só 4 em quadra)

    def b():
        if len(on) == 5:
            full[0] = list(on)
        k = ",".join(str(x) for x in sorted(full[0]))
        return agg.setdefault(k, [0.0, 0, 0, 0, 0])  # seg, pts a favor, pts contra, posses a favor, posses contra

    for n in sorted(p for p in by_p if p > 0):
        lst = by_p[n]
        if n > 1:
            on = starters_of(lst, prev_end)
            if len(on) == 5:
                full[0] = list(on)
        t_last, poss = plen(n), None
        for a in lst:
            rem = clock(a.get("clock"))
            if rem is not None and rem <= t_last:
                b()[0] += t_last - rem
                t_last = rem
            h, w = int(a.get("scoreHome") or last_h), int(a.get("scoreAway") or last_a)
            dh, da = h - last_h, w - last_a
            last_h, last_a = h, w
            if dh or da:
                r = b(); r[1] += dh if home else da; r[2] += da if home else dh
            p = a.get("possession")
            if p and poss and p != poss:  # posse terminou: credita a quem estava com a bola
                r = b(); r[3 if poss == tid else 4] += 1
            if p:
                poss = p
            if is_sub(a):
                pid = a.get("personId")
                if a.get("subType") == "out" and pid in on:
                    on.remove(pid)
                elif a.get("subType") == "in" and pid not in on:
                    on.append(pid)
        if t_last > 0:
            b()[0] += t_last
        if poss in (tid, oid):
            b()[3 if poss == tid else 4] += 1  # última posse do período
        prev_end = list(on)
    names = {str(p["personId"]): p.get("name") or f'{p.get("firstName", "")} {p.get("familyName", "")}'.strip() for p in team["players"]}
    # Conferência com o box score oficial (minutos por jogador)
    err = []
    for p in team["players"]:
        mins = clock(p.get("statistics", {}).get("minutes") or "PT0M0S") or 0
        if mins <= 0:
            continue
        mine_sec = sum(v[0] for k, v in agg.items() if str(p["personId"]) in k.split(","))
        err.append(abs(mine_sec - mins) / 60)
    return {"lu": {k: [round(v[0], 1)] + v[1:] for k, v in agg.items()}, "names": names}, err


def main():
    season_sched = get(f"{CDN}/staticData/scheduleLeagueV2.json")["leagueSchedule"]
    season = season_sched.get("seasonYear")
    games = [g for d in season_sched["gameDates"] for g in d["games"] if str(g["gameId"]).startswith("002") and g.get("gameStatus") == 3]
    data = {"games": [], "teams": {}}
    if os.path.exists(OUT) and not os.environ.get("REBUILD"):
        with open(OUT, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("season") != season:
            data = {"games": [], "teams": {}}
    done = set(data["games"])
    todo = [g for g in games if g["gameId"] not in done]
    print(f"Temporada {season}: {len(games)} jogos encerrados, {len(todo)} novos para processar")
    errs, pts_ok, n_ok = [], 0, 0
    for g in todo:
        gid = g["gameId"]
        try:
            box = get(f"{CDN}/liveData/boxscore/boxscore_{gid}.json")["game"]
            acts = sorted(get(f"{CDN}/liveData/playbyplay/playbyplay_{gid}.json")["game"]["actions"], key=lambda a: a.get("orderNumber", a.get("actionNumber", 0)))
        except Exception as e:
            print("  falhou", gid, e)
            continue
        et = (g.get("gameDateEst") or g.get("gameDateTimeEst") or "")[:10]
        both = {side: team_lineups(box, acts, side) for side in ("homeTeam", "awayTeam")}
        if not all(r for r, _ in both.values()):
            print("  sem titulares no box score, fica para a próxima", gid)
            continue
        for side, (res, err) in both.items():
            tri = box[side]["teamTricode"]
            t = data["teams"].setdefault(tri, {"names": {}, "lu": {}, "dates": []})
            t["names"].update(res["names"])
            for k, v in res["lu"].items():
                cur = t["lu"].setdefault(k, [0, 0, 0, 0, 0])
                for i in range(5):
                    cur[i] = round(cur[i] + v[i], 1)
            t["dates"].append(et)
            errs += err
            pf = sum(v[1] for v in res["lu"].values())
            pts_ok += int(pf == int(box[side]["score"]))
            n_ok += 1
        data["games"].append(gid)
        time.sleep(0.3)
    data.update({"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "season": season,
                 "source": "NBA.com play-by-play oficial"})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    if errs:
        print(f"Conferência: {n_ok} times-jogo; pontos batendo {pts_ok}/{n_ok}; minutos até 0,5 min de diferença: "
              f"{100 * sum(e <= 0.5 for e in errs) / len(errs):.1f}%; até 1 min: {100 * sum(e <= 1 for e in errs) / len(errs):.1f}%; maior diferença {max(errs):.1f} min")
    print(f"OK: data/lineups.json com {len(data['games'])} jogos, {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERRO:", e)
        sys.exit(1)
