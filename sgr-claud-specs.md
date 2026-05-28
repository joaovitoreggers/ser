# 📌 ESPECIFICAÇÃO DE CONTEXTO TÉCNICO: SGR (V1.0)
> **Stack Core:** Django 5.x Full Stack, PostgreSQL 16, Django Channels 4.x (Redis), HTMX 2.x, Alpine.js 3.x, Tailwind CSS.
> **Diretriz Geral:** Atue como um Arquiteto de Software Sênior. Siga à risca os schemas, as cascatas de signals e as regras de negócio multi-tenant imutáveis descritas abaixo.

---

## 1. DIRETRIZES DE ARQUITETURA & PADRÕES DE CÓDIGO
1. **Multi-tenancy Rígido:** Todas as tabelas operacionais possuem chave estrangeira (`FK`) para o modelo `Restaurante`. Consultas (`QuerySets`) globais sem filtro de Tenant são estritamente proibidas; use Mixins de Managers (`for_tenant(restaurante)`).
2. **Isonomia Funcional:** Todo ID primário (`PK`) de todo modelo deve usar obrigatoriamente `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.
3. **Anti N+1 Performance:** Views operacionais de alta concorrência (KDS, POS, Pedidos) devem usar explicitamente `select_related()` para FKs e `prefetch_related()` para Many-to-Many / Relacionamentos inversos. Alvo de TTFB: < 200ms.
4. **Desacoplamento via Signals:** Cálculos em cascata (custo médio, margem, disponibilidade) devem residir em Django Signals e métodos de modelo, isolados das Views.
5. **Dinamismo UI Limpo:** Use HTMX para substituições parciais de HTML no servidor e Alpine.js para gestão de estado reativa puramente em memória cliente (ex: cálculo ao vivo de troco, sliders e adição visual).

---

## 2. DICIONÁRIO DE DADOS COMPACTO (DJANGO MODELS)

### App: `core`
* **Restaurante:** `id` (UUID), `nome` (CharField 200), `cnpj` (CharField 18, unique), `margem_padrao` (DecimalField 5,2, default=60), `permitir_estoque_negativo` (BooleanField, default=True), `ativo` (BooleanField), `criado_em` (DateTimeField).
* **LogAuditoria:** `id` (UUID), `restaurante` (FK), `usuario` (FK User, null=True), `acao` (CharField 100), `entidade` (CharField 100), `entidade_id` (UUID, null=True), `dados_antes` (JSONField), `dados_depois` (JSONField), `ip` (GenericIPAddressField), `criado_em` (DateTimeField).

### App: `usuarios`
* **PerfilUsuario:** `id` (UUID), `user` (OneToOne User), `restaurante` (FK), `perfil` (CharField choices: `admin`, `gerente`, `garcom`, `cozinheiro`, `caixa`, `almoxarife`), `pin_hash` (CharField 128).

### App: `estoque`
* **CategoriaIngrediente:** `id` (UUID), `restaurante` (FK), `nome` (CharField 100). *Constraint:* `unique_together = ['restaurante', 'nome']`.
* **Ingrediente:** `id` (UUID), `restaurante` (FK), `categoria` (FK, null=True), `nome` (CharField 200), `unidade_medida` (CharField choices: `g`, `kg`, `ml`, `L`, `un`), `estoque_atual` (DecimalField 12,3, default=0), `estoque_minimo` (DecimalField 12,3, default=0), `custo_unitario` (DecimalField 12,4, default=0), `ativo` (BooleanField).
* **Fornecedor:** `id` (UUID), `restaurante` (FK), `nome` (CharField 200), `cnpj` (CharField 18, blank), `ativo` (BooleanField).
* **EntradaEstoque:** `id` (UUID), `restaurante` (FK), `ingrediente` (FK PROTECT), `fornecedor` (FK SET_NULL), `quantidade` (DecimalField 12,3), `custo_unitario` (DecimalField 12,4), `data_entrada` (DateField), `nota_fiscal` (CharField 60), `validade` (DateField, null=True), `usuario` (FK User).
* **AjusteEstoque:** `id` (UUID), `restaurante` (FK), `ingrediente` (FK PROTECT), `qtd_anterior` (DecimalField 12,3), `qtd_nova` (DecimalField 12,3), `motivo` (CharField choices: `inventario`, `avaria`, `vencimento`, `roubo`, `outros`), `descricao` (TextField), `usuario` (FK User).

### App: `fichas`
* **FichaTecnica:** `id` (UUID), `restaurante` (FK), `nome` (CharField 200), `rendimento` (PositiveIntegerField, default=1), `custo_total` (DecimalField 12,4, default=0), `custo_porcao` (DecimalField 12,4, default=0), `versao` (PositiveIntegerField, default=1), `ativo` (BooleanField).
* **FichaIngrediente:** `id` (UUID), `ficha` (FK CASCADE), `ingrediente` (FK PROTECT), `quantidade` (DecimalField 12,4), `unidade` (CharField 5), `principal` (BooleanField, default=True), `custo_snapshot` (DecimalField 12,4).
* **FichaTecnicaVersao:** `id` (UUID), `ficha` (FK CASCADE), `versao` (PositiveIntegerField), `dados` (JSONField).

### App: `cardapio`
* **CategoriaPrato:** `id` (UUID), `restaurante` (FK), `nome` (CharField 100), `ordem` (PositiveIntegerField, default=0), `hora_inicio` (TimeField, null=True), `hora_fim` (TimeField, null=True).
* **Prato:** `id` (UUID), `restaurante` (FK), `ficha` (OneToOne PROTECT), `categoria` (FK PROTECT), `nome` (CharField 200), `preco_venda` (DecimalField 10,2), `custo_atual` (DecimalField 12,4), `margem_lucro` (DecimalField 6,2), `disponivel` (BooleanField, default=True), `motivo_indisponivel` (TextField).
* **HistoricoPreco:** `id` (UUID), `prato` (FK CASCADE), `preco_anterior` (DecimalField 10,2), `preco_novo` (DecimalField 10,2), `usuario` (FK User), `criado_em` (DateTimeField).

### App: `pedidos`
* **Mesa:** `id` (UUID), `restaurante` (FK), `numero` (PositiveIntegerField), `status` (CharField choices: `livre`, `ocupada`, `aguardando_pedido`, `em_atendimento`, `aguardando_pagamento`). *Constraint:* `unique_together = ['restaurante', 'numero']`.
* **Pedido:** `id` (UUID), `restaurante` (FK), `mesa` (FK PROTECT, null=True), `usuario` (FK User), `tipo` (CharField choices: `mesa`, `balcao`, `delivery`), `status` (CharField choices: `aberto`, `em_atendimento`, `aguardando_pagamento`, `pago`, `fiado`, `cancelado`), `subtotal` (DecimalField 10,2, default=0), `desconto` (DecimalField 10,2, default=0), `total` (DecimalField 10,2, default=0), `criado_em` (DateTimeField), `fechado_em` (DateTimeField, null=True).
* **ItemPedido:** `id` (UUID), `pedido` (FK CASCADE), `prato` (FK PROTECT), `quantidade` (PositiveIntegerField), `preco_unitario` (DecimalField 10,2), `custo_unitario` (DecimalField 12,4), `subtotal` (DecimalField 10,2), `status` (CharField choices: `aguardando`, `em_preparo`, `pronto`, `entregue`, `cancelado`), `enviado_em` (DateTimeField), `pronto_em` (DateTimeField, null=True), `motivo_cancelamento` (TextField, blank).

### App: `financeiro`
* **TurnoCaixa:** `id` (UUID), `restaurante` (FK), `usuario` (FK User), `valor_abertura` (DecimalField 10,2), `valor_fechamento` (DecimalField 10,2, null=True), `status` (CharField choices: `aberto`, `fechado`).
* **MovimentacaoCaixa:** `id` (UUID), `turno` (FK PROTECT), `tipo` (CharField choices: `sangria`, `suprimento`), `valor` (DecimalField 10,2), `motivo` (TextField), `autorizado_por` (FK User, null=True), `usuario` (FK User).
* **Pagamento:** `id` (UUID), `pedido` (FK PROTECT), `forma` (CharField choices: `dinheiro`, `debito`, `credito`, `pix`, `voucher`, `fiado`), `valor` (DecimalField 10,2), `troco` (DecimalField 10,2, default=0), `usuario` (FK User).

---

## 3. LÓGICA MATEMÁTICA E CADEIA DE SIGNALS (ESTREITO)

Você DEVE implementar as seguintes equações explicitamente usando métodos de modelo acionados por Signals (`post_save`/`pre_save`):

### A. Recebimento de Insumo e Custo Médio Ponderada (CMP)
* **Evento:** `EntradaEstoque.post_save`
* **Ação:** Atualiza `Ingrediente.estoque_atual += quantidade_entrada` e calcula o novo `custo_unitario`:
    $$\text{Custo Novo} = \frac{(\text{Estoque Atual} \times \text{Custo Atual}) + (\text{Qtd Entrada} \times \text{Custo Entrada})}{\text{Estoque Atual} + \text{Qtd Entrada}}$$

### B. Cascata de Recálculo de Custos do Restaurante
* **Gatilho Inicial:** Alteração do `custo_unitario` do `Ingrediente`.
* **Cascata Nível 1:** Disparar `.recalcular_custo()` em todas as `FichaTecnica` que contêm o ingrediente (`principal=True`).
    $$\text{custo\_total} = \sum (\text{fi.quantidade} \times \text{ingrediente.custo\_unitario})$$
    $$\text{custo\_porcao} = \frac{\text{custo\_total}}{\text{rendimento}}$$
* **Cascata Nível 2:** O `post_save` da `FichaTecnica` dispara o `.atualizar_custo()` do `Prato` vinculado:
    $$\text{custo\_atual} = \text{ficha.custo\_porcao}$$
    $$\text{margem\_lucro} = \frac{\text{preco\_venda} - \text{custo\_atual}}{\text{preco\_venda}} \times 100$$
    *Se `margem_lucro` for menor que `Restaurante.margem_padrao`, emita evento WebSocket `"margem_alerta"`*.

### C. Baixa Automática e Alerta de Estoque Crítico
* **Evento:** `ItemPedido.post_save` filtrado por `status == 'pronto'`.
* **Ação:** Varre os ingredientes principais (`principal=True`) da Ficha Técnica do Prato e reduz o estoque:
    $$\text{ingrediente.estoque\_atual} -= (\text{fi.quantidade} \times \text{item\_pedido.quantidade})$$
* **Regra Relacionada:** Se `ingrediente.estoque_atual <= ingrediente.estoque_minimo`, envie evento WebSocket `"estoque_alerta"` para a navbar. Se `estoque_atual <= 0`, altere programmaticamente `Prato.disponivel = False` e publique `"prato_indisponivel"` via WS.

### D. Histórico Coerente de Preço do Cardápio
* **Evento:** `Prato.pre_save`.
* **Ação:** Se `instance.preco_venda` for modificado em relação ao banco de dados, crie instantaneamente um registo em `HistoricoPreco`.

---

## 4. INTEGRIDADE DE DADOS E REGRAS DE NEGÓCIO INVIOLÁVEIS

1.  **Imutabilidade Financeira Pós-Pago:** Um pedido com `status == 'pago'` torna-se um registro estritamente de **somente leitura**. Bloqueie modificações, adições ou exclusões de `ItemPedido` associados a nível de validação de modelo (`clean()`) e view.
2.  **Snapshot Isolado no ItemPedido:** Ao salvar um `ItemPedido` pela primeira vez, extraia `preco_venda` do prato para `preco_unitario`, e `custo_atual` para `custo_unitario`. Estes valores devem ser gravados como congelados (snapshots) e jamais recalculados, garantindo a integridade retroativa do CMV.
3.  **Fechamento Seguro de Pedidos:** A transição de um `Pedido` para `status = 'pago'` só é permitida se `⚙️ Valor Pago Total >= Pedido.total`. A equações de totais do pedido devem ser computadas no servidor ignorando dados do payload cliente.
4.  **Controle de Cancelamento Crítico:** Itens de pedido em status `aguardando` podem ser cancelados livremente pelo garçom. Se o status for `em_preparo`, `pronto` ou `entregue`, a requisição deve validar obrigatoriamente um `pin_hash` de um usuário com perfil `gerente` ou `admin`. Todo cancelamento exige um motivo em texto e gera logs detalhados em `LogAuditoria`.

---

## 5. MATRIZ DE AUTENTICAÇÃO E CONTROLE DE ACESSO (RBAC)

Mapeamento estrito baseado nos **Django Auth Groups**:

| Grupo Django | Redirecionamento Pós-Login | Permissões de Endpoint & Operação |
| :--- | :--- | :--- |
| `admin` | `/relatorios/dashboard/` | Acesso irrestrito a todos os objetos do banco e Django Admin. |
| `gerente` | `/relatorios/dashboard/` | Escrita/Leitura em estoque, cardápio, finanças e aprovação via PIN. |
| `garcom` | `/pedidos/mesas/` | Leitura do cardápio; Escrita (`add/change`) em `Pedido` e `ItemPedido`. |
| `cozinheiro` | `/pedidos/kds/` | Visualização do KDS; Escrita restrita ao campo `status` de `ItemPedido`. |
| `caixa` | `/pedidos/caixa/` | Leitura geral; Escrita em `TurnoCaixa`, `Pagamento` e fechar `Pedido`. |
| `almoxarife` | `/estoque/` | Escrita e Leitura em `Ingrediente`, `EntradaEstoque`, `AjusteEstoque`. |

*Nota: Telas operacionais de tablets (Garçom, Cozinha e Caixa) devem implementar autenticação direta por teclado numérico via Alpine.js validando contra o `pin_hash` criptografado no banco de dados*.

---

## 6. SCRIPT DE INFRAESTRUTURA DE ÍNDICES POSTGRESQL

Ao criar as migrações, certifique-se de que os seguintes índices SQL otimizados existam para suportar alta carga concorrente:

```sql
CREATE INDEX idx_pedido_restaurante_status ON pedidos_pedido(restaurante_id, status);
CREATE INDEX idx_pedido_mesa_aberto ON pedidos_pedido(mesa_id) WHERE status NOT IN ('pago', 'cancelado');
CREATE INDEX idx_item_pedido_status ON pedidos_itempedido(pedido_id, status);
CREATE INDEX idx_ingrediente_ativo ON estoque_ingrediente(restaurante_id) WHERE ativo = TRUE;
CREATE INDEX idx_prato_disponivel ON cardapio_prato(restaurante_id, categoria_id) WHERE disponivel = TRUE;
CREATE INDEX idx_log_entidade ON core_logauditoria(entidade, entidade_id, criado_em DESC);