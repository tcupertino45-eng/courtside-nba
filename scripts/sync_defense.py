"""Coleta os dados de defesa da NBA.com e envia data/defense.json ao GitHub.
Feito para rodar no seu computador (a NBA.com bloqueia servidores na nuvem).

Primeira vez:  python sync_defense.py --configurar   (pede o token do GitHub e guarda só neste PC)
Dia a dia:     pythonw sync_defense.py               (roda escondido; registro em ultima_execucao.log)
"""
import base64, getpass, json, os, sys, urllib.request

REPO = "tcupertino45-eng/courtside-nba"
PATH = "data/defense.json"
HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(os.environ.get("APPDATA", HERE), "CourtsideNBA", "token.txt")
LOG = os.path.join(HERE, "..", "ultima_execucao.log")


def api(method, url, body=None, token=None):
    req = urllib.request.Request("https://api.github.com" + url, method=method,
                                 data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def configurar():
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    t = getpass.getpass("Cole o token do GitHub (não aparece na tela) e aperte Enter: ").strip()
    api("GET", f"/repos/{REPO}", token=t)  # testa o token antes de salvar
    with open(CONF, "w") as f:
        f.write(t)
    print("Token salvo e testado com sucesso.")


def main():
    if "--configurar" in sys.argv:
        return configurar()
    sys.path.insert(0, HERE)
    import fetch_defense
    fetch_defense.main()
    with open(fetch_defense.OUT, "rb") as f:
        novo = f.read()
    with open(CONF) as f:
        token = f.read().strip()
    atual = api("GET", f"/repos/{REPO}/contents/{PATH}", token=token)
    if base64.b64decode(atual.get("content", "")) == novo:
        print("Sem mudanças hoje.")
        return
    api("PUT", f"/repos/{REPO}/contents/{PATH}", token=token, body={
        "message": "Atualiza dados de defesa",
        "content": base64.b64encode(novo).decode(),
        "sha": atual["sha"],
    })
    print("Enviado ao GitHub.")


if __name__ == "__main__":
    interativo = sys.stdout is not None and sys.stdout.isatty()
    if not interativo:  # rodando escondido: grava tudo no registro
        sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8")
    try:
        main()
    except Exception as e:
        print("ERRO:", e)
        sys.exit(1)
