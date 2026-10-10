# token-diet

Mede e reduz o consumo de tokens de agentes de IA para programação (Claude
Code, OpenAI Codex, Cursor e outras ferramentas com AGENTS.md) sem baixar a
qualidade.

[English](README.md)

> Cada chamada ao modelo reenvia todo o contexto da sessão. O custo de uma
> ação é o tamanho do contexto naquele momento, não o tamanho da ação.

No [estudo de caso](docs/case-study.md) (em inglês), o limite de 5 horas do
Codex acabou em 11 minutos numa task que não terminou. Depois das mudanças
deste repositório, o mesmo tipo de task usou 8–13% do limite e foi aprovado
na revisão.

## O que tem aqui

| Peça | O que faz |
|---|---|
| `analyze_sessions.py` | Lê os logs locais de sessão do Claude Code e do Codex. Mostra tokens de entrada, tamanho do contexto por chamada (primeira/média/pico), compactações, polling, Fast mode e revisor por modelo, e marca cada achado com uma regra |
| `audit_context.py` | Lista o que toda sessão carrega antes de começar (cadeia de AGENTS.md, CLAUDE.md + @imports, rules sempre ativas, descrições de skills), com tamanhos e o que passou do teto |
| `session_guard.py` | Hook para Claude Code e Codex: uma task por sessão e um orçamento de tokens. Opcional; em caso de erro, libera |
| [Playbook](plugins/token-diet/skills/token-diet/references/playbook.md) | 12 regras independentes de ferramenta (TD-01…TD-12), cada uma com evidência |
| [Ciclo de melhoria](plugins/token-diet/skills/token-diet/references/improvement-loop.md) | Como transformar um aprendizado novo em mudança medida: linha de base → classificar → destino mais barato → aplicar → medir de novo |
| Skill `token-diet` | Junta tudo para o agente: modos `diagnose`, `audit`, `improve`, `guard` |

Tudo roda localmente com Python 3.8+, sem dependências. Nada é enviado para fora.

## Instalação

### Claude Code (plugin)

```bash
claude plugin marketplace add ThiagoAuquino/token-diet
claude plugin install token-diet@token-diet
```

Depois peça: "use o token-diet para diagnosticar minhas últimas sessões".

### Codex, Cursor e outras ferramentas (skill)

```bash
git clone https://github.com/ThiagoAuquino/token-diet.git ~/token-diet
mkdir -p ~/.agents/skills
ln -s ~/token-diet/plugins/token-diet/skills/token-diet ~/.agents/skills/token-diet
```

O Codex lê skills de `~/.agents/skills` e `.agents/skills`. Em ferramentas
sem skills, copie as formas curtas do playbook para o seu `AGENTS.md`.

### Só os scripts

```bash
S=~/token-diet/plugins/token-diet/skills/token-diet/scripts
python3 $S/analyze_sessions.py --last 10
python3 $S/audit_context.py caminho/do/projeto
```

## Session guard (opcional)

Fica desligado até um arquivo de configuração ligá-lo. Crie
`.token-diet.json` no projeto (ou `~/.config/token-diet/config.json` para
todos):

```json
{ "session_guard": { "enabled": true, "max_session_input_tokens": 3500000,
  "close_markers": ["Next step — Git"], "bypass_token": "#same-session" } }
```

- O agente termina a task com o marcador de fechamento → o próximo pedido na
  mesma sessão é bloqueado com "abra uma sessão nova". O marcador pode ser
  qualquer texto, por exemplo `"Próximo passo — Git"`.
- Acima do orçamento → o agente recebe uma única instrução para registrar
  checkpoint e fechar; novos pedidos são bloqueados.
- `#same-session` no texto libera (ex.: "escreva a mensagem de commit").
- Claude Code: os hooks vêm com o plugin. Codex: ver
  [adapters/codex](adapters/codex/README.md) (exige confiar em `/hooks`).

Calibre o orçamento com `analyze_sessions.py` nas suas tasks concluídas. O
padrão (3,5M tokens de entrada) vem do estudo de caso e é só um ponto de partida.

## Limites

- O formato dos logs de sessão não é interface pública estável. Os parsers
  ignoram o que não entendem; se o formato mudar, abra uma issue com uma
  amostra anonimizada.
- Hooks são documentados no Codex CLI; confirme que rodam na sua extensão de IDE.
- Nenhum fornecedor publica a fórmula exata de medição do plano. Compare
  sessões da mesma ferramenta entre si.

## Fontes e projetos relacionados

Ver [docs/research.md](docs/research.md): documentação oficial, estudos,
relatos de usuários e projetos semelhantes (ccusage, claude-context-optimizer
e outros).

## Contribuir

Aprendizados com números de antes/depois são bem-vindos. Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

[Apache License 2.0](LICENSE). Uso, alteração e redistribuição livres,
inclusive comercial. Quem redistribuir deve manter o arquivo [NOTICE](NOTICE)
com a atribuição do autor. A licença dá aos usuários uma licença das
patentes dos contribuidores e a encerra para quem processar por patente
sobre este trabalho.

Criado por **Thiago Auquino** ([Auquitech](https://github.com/ThiagoAuquino)).
