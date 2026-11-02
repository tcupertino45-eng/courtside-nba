# Courtside NBA

Painel pessoal de dados da NBA: jogos do dia com placar ao vivo, box score com métricas avançadas e perfil de carreira de cada jogador.

## O que tem nesta versão

- **Jogos**: rodada do dia (ou qualquer data), com placar que se atualiza sozinho a cada 20 s enquanto houver jogo ao vivo.
- **Jogo**: placar estilo arena, comparação entre as equipes, box score completo dos dois times com **TS%** e **eFG%** calculados por jogador, e as últimas jogadas.
- **Jogadores**: todos os atletas dos 30 elencos atuais, com busca por nome e filtro por equipe.
- **Jogador**: ficha (idade, altura, draft, universidade…), aviso se ele está jogando agora, gráfico de evolução (PTS/REB/AST por temporada) e tabela de carreira com TS% e eFG%.

## De onde vêm os dados

API pública da ESPN, sem chave e sem cadastro. Ela não é oficial: a ESPN pode mudar os formatos sem aviso. Todos os endereços ficam no topo do script, no objeto `API`, para facilitar a troca no futuro.

## Como abrir no seu computador

Dê dois cliques em `index.html`. Ele abre no navegador e já busca os dados.

Se a página mostrar erro de carregamento, rode um servidor local simples dentro da pasta e acesse `http://localhost:8000`:

```
python -m http.server 8000
```

## Como ter uma URL (grátis)

**Opção mais fácil: Netlify Drop**
1. Acesse https://app.netlify.com/drop
2. Arraste a pasta `nba-courtside` para a página.
3. Pronto: você recebe uma URL pública (dá para renomear depois, criando conta grátis).

**Opção GitHub Pages** (bom para ir evoluindo o projeto com histórico de versões)
1. Crie um repositório no GitHub e envie o `index.html`.
2. Em *Settings → Pages*, escolha a branch `main` e a pasta raiz.
3. A URL fica `https://SEU-USUARIO.github.io/NOME-DO-REPO/`.

## Dados de defesa (automação diária)

O aproveitamento dos adversários quando cada jogador marca (DFG% vs FG% normal) vem da NBA.com,
que não permite acesso direto pelo navegador. Por isso:

- `scripts/fetch_defense.py` baixa esses dados e salva em `data/defense.json`;
- `.github/workflows/defense.yml` roda esse script todo dia às 08:17 (horário de Brasília) no GitHub;
- o site lê `data/defense.json` (só funciona no site publicado, não abrindo o arquivo do computador).

Para rodar na hora: aba **Actions** do repositório → **Atualizar dados de defesa** → **Run workflow**.

Se a NBA.com bloquear os servidores do GitHub (a execução aparece em vermelho na aba Actions),
dá para rodar o mesmo script no seu computador: `python scripts/fetch_defense.py` e enviar o
`data/defense.json` gerado.

## Ideias para as próximas versões

- Classificação das conferências e líderes da liga
- Comparar dois jogadores lado a lado
- Gráfico de probabilidade de vitória durante o jogo
- Game log (jogo a jogo) da temporada atual
- Métricas mais avançadas (USG%, PER, Net Rating) com uma segunda fonte de dados
