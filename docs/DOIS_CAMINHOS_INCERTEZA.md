# Dois caminhos de incerteza — distinção permanente

**Status:** normativo  
**Commit de referência da correção de cobertura diagnóstica:** `2bfe8b8`  
**Última verificação por código:** 2026-08-15  

Este documento existe para impedir a confusão entre:

1. o caminho de **diagnóstico de cobertura prequential** (métrica de aceite / UI), e  
2. o caminho de **simulações de produção** que alimenta Risk Engine, VaR, CVaR e stockout.

Os dois caminhos **não compartilham** a construção do intervalo. Alterar um não altera o outro automaticamente.

---

## 1. Diagrama do pipeline (evidência de chamada)

```
run_backtest(data)
  ├─ residuals                    ← 24 resíduos OOS concatenados (4×6)
  ├─ actuals_by_winner_fold       ← lista de 4 vetores
  ├─ predictions_by_winner_fold   ← lista de 4 vetores
  ├─ prequential_interval_quality ← CAMINHO A (diagnóstico)
  │     └─ _prequential_interval_quality(..., volatility_conditioned=False)
  │           └─ Split Conformal simétrico (commit 2bfe8b8)
  │
  └─ (retorno do dict backtest)

make_forecast(data, backtest)                    # src/analysis.py
  └─ build_probabilistic_forecast(               # src/probabilistic_forecast.py
         point_forecast,
         oos_residuals=backtest["residuals"],    # 24 resíduos OOS agregados
         actuals_by_fold=...,
         predictions_by_fold=...,
     )
       ├─ calibrate_error_methods(...)           # escolhe método
       ├─ select_error_method(...)               # → moving_block (run atual)
       └─ draw_errors(selected, residuals, ...)  # CAMINHO B (produção)
             └─ simulations (replicas × horizon)

app.py
  ├─ run_forecast_cached → make_forecast → forecast, simulations
  ├─ run_risk_cached(simulations) → run_risk_engine(...)   # CAMINHO B
  ├─ backtest["prequential_interval_quality"]              # CAMINHO A (UI + Decisão)
  └─ decision_intelligence(coverage_p10_p90=CAMINHO A)
```

Evidência de grep (símbolos e arquivos):

| Símbolo | Arquivo | Papel |
|---------|---------|-------|
| `make_forecast` → `build_probabilistic_forecast` | `src/analysis.py` | Produção de quantis/simulações |
| `oos_residuals=backtest["residuals"]` | `src/analysis.py` (`make_forecast`) | Resíduos OOS agregados |
| `calibrate_error_methods` / `select_error_method` / `draw_errors` | `src/probabilistic_forecast.py` | Calibração e amostragem |
| `prequential_interval_quality` em `run_backtest` | `src/analysis.py` | Diagnóstico apenas |
| `_prequential_interval_quality` + Split Conformal | `src/analysis.py` | Diagnóstico apenas |
| `run_risk_engine(simulations)` | `app.py`, `src/risk_engine.py` | Consome **somente** CAMINHO B |
| UI cobertura prequential | `app.py` | Lê **somente** CAMINHO A |
| Decisão `coverage_p10_p90` | `app.py` | Lê **somente** CAMINHO A |

`make_forecast` **não** chama `prequential_interval_quality`.  
`run_risk_engine` **não** importa nem lê `_prequential_interval_quality`.

---

## 2. Tabela permanente — Caminho A vs Caminho B

| Dimensão | **Caminho A — Diagnóstico prequential** | **Caminho B — Simulações de produção** |
|----------|------------------------------------------|----------------------------------------|
| Função principal | `_prequential_interval_quality` | `build_probabilistic_forecast` → `draw_errors` |
| Arquivo | `src/analysis.py` | `src/probabilistic_forecast.py` |
| Propósito | Métrica de aceite de cobertura; card da UI; sinal na Decisão | Gerar `simulations` para quantis do forecast e Risk Engine |
| Método de intervalo / erro | **Split Conformal simétrico** (quantil dos \|resíduos\| de dobras anteriores, correção finita-sample; `volatility_conditioned=False`) | Um de: `normal`, `student_t`, `iid_bootstrap`, **`moving_block`** |
| Método ativo no run verificado | Split Conformal | **`moving_block`** (menor score em `calibrate_error_methods`) |
| Resíduos usados | Por dobra: só dobras **anteriores** à dobra avaliada (walk-forward estrito) | Vetor **agregado** `backtest["residuals"]` = concatenação OOS do vencedor |
| Origem dos resíduos | Out-of-sample walk-forward (nunca in-sample de treino) | Out-of-sample walk-forward agregados (nunca in-sample de treino) |
| Tamanho da amostra de resíduos | Até 6 / 12 / 18 conforme a dobra de teste (3 dobras pontuadas) | **24** observações OOS (4 dobras × 6 meses) no run padrão |
| Validação de cobertura **neste** caminho | Sim — a própria métrica `coverage_p10_p90` **é** a cobertura prequential; após 2bfe8b8 ≈ **83,3 %** | Calibração prequential **entre métodos** (`calibrate_error_methods`): compara coverage/pinball com resíduos de dobras anteriores só para **escolher** o método; **não** aplica Split Conformal nem porta a cobertura 83,3 % para as simulações |
| Cobertura observada na calibração de métodos (run verificado) | — | Todos os quatro métodos ~**66,7 %** na calibração interna; vence `moving_block` por pinball |
| Consumidores | Aba Mercado & Forecast (metric); `decision_intelligence` (`coverage_p10_p90`) | `forecast` (P10–P90); `run_risk_engine` (VaR, CVaR, stockout, backlog); robust planning |
| Afetado pelo commit `2bfe8b8`? | **Sim** | **Não** |

---

## 3. Detalhe do Caminho B (`build_probabilistic_forecast`)

### 3.1 Calibração ativa

`ProbabilisticForecastConfig.candidate_methods`:

```python
("normal", "student_t", "iid_bootstrap", "moving_block")
```

`calibrate_error_methods(actuals_by_fold, predictions_by_fold)`:

- Para cada método, percorre as dobras em ordem.
- Só pontua uma dobra se já existir `pool` de resíduos de dobras anteriores.
- Gera erros simulados com `draw_errors`, forma quantis 0.10 / 0.50 / 0.90, mede coverage e pinball.
- Score = `pinball_loss + abs(coverage - coverage_nominal_target)`.

`select_error_method` escolhe o menor score.  
**Run verificado (snapshot local, 4×6):** selecionado **`moving_block`**.

### 3.2 Resíduos da amostragem final

```text
draw_errors(selected, residuals=oos_residuals, ...)
```

onde `oos_residuals` vem de:

```python
np.asarray(backtest["residuals"], dtype=float)  # make_forecast
```

e `backtest["residuals"]` é a concatenação dos erros OOS do modelo vencedor no walk-forward (**24** pontos no protocolo 4 dobras × 6 meses).  
Docstring do módulo: *baseado exclusivamente em resíduos out-of-sample*.  
Não há resíduos in-sample de treino neste vetor.

### 3.3 Validação de cobertura no Caminho B

- Existe calibração prequential **comparativa entre métodos** (coverage + pinball).
- **Não** existe aplicação do Split Conformal do Caminho A às simulações.
- A cobertura ~83,3 % do Caminho A **não** é um gate que altere `draw_errors` ou `run_risk_engine`.
- Por isso VaR / CVaR / stockout podem permanecer inalterados após `2bfe8b8` — comportamento esperado pela arquitetura atual, não anomalia numérica.

---

## 4. Detalhe do Caminho A (`_prequential_interval_quality`)

- Avalia, para cada dobra de teste com histórico prévio, se o realizado cai em `[pred + lower, pred + upper]`.
- Com `volatility_conditioned=False` (padrão do diagnóstico operacional), lower/upper vêm do quantil dos **valores absolutos** dos resíduos anteriores (Split Conformal simétrico + correção finita-sample), implementado no commit `2bfe8b8`.
- Resultado verificado: **coverage_p10_p90 = 0.8333** (18 observações em 3 dobras).
- Não gera matriz `simulations` e não é lido por `run_risk_engine`.

---

## 5. Regras de comunicação (UI e relatórios)

1. Qualquer menção a **cobertura prequential 83 %** refere-se **somente** ao Caminho A.
2. Qualquer menção a **VaR, CVaR, stockout, capacity-at-risk** refere-se **somente** ao Caminho B (simulações).
3. É incorreto afirmar que a correção Split Conformal alargou os intervalos do Risk Engine enquanto o Caminho B permanecer em `moving_block` / bootstrap sobre os 24 resíduos agregados sem conformal.
4. Para propagar intervalos mais largos/honestos ao risco, é necessário alterar explicitamente o Caminho B (`probabilistic_forecast.py` / `draw_errors` ou pós-processamento das simulações), não apenas o Caminho A.

---

## 6. Critério de aceite deste documento

- Pipeline `make_forecast` → `build_probabilistic_forecast` → `draw_errors` → `run_risk_engine` documentado com símbolos e arquivos citados.
- Método ativo de calibração/amostragem no Caminho B identificado por execução (`moving_block`).
- Resíduos: OOS walk-forward; n=24 no protocolo padrão.
- Distinção Caminho A vs B inequívoca e permanente neste arquivo sob `docs/`.
