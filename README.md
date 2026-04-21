# Automação de Cotação de Frete

Script Python que lê pedidos sem frete no Google Sheets, acessa o site da FM Transportes, cota o frete automaticamente e salva o resultado de volta na planilha.

---

## Pré-requisitos

- Python 3.11 ou superior
- Conta de serviço Google com acesso às planilhas (arquivo `credentials.json`)

---

## Instalação

### 1. Instalar dependências Python

```bash
cd frete
pip install -r requirements.txt
```

### 2. Instalar o navegador do Playwright

```bash
playwright install chromium
```

### 3. Configurar variáveis de ambiente

Copie `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

O arquivo `.env` deve ficar assim:
```
GOOGLE_CREDENTIALS_PATH=credentials.json
TRANSPORTADORA_LOGIN=seu_usuario
TRANSPORTADORA_SENHA=sua_senha
PLAYWRIGHT_HEADLESS=false
```

### 4. Adicionar o arquivo de credenciais Google

Coloque o arquivo `credentials.json` da conta de serviço na pasta `frete/`.

> **Como obter:** Google Cloud Console → IAM → Contas de serviço → Criar chave → JSON

Compartilhe as duas planilhas com o e-mail da conta de serviço (com permissão de **editor**).

### 5. Ajustar o config.json

Abra `config.json` e confirme os nomes das abas (guias) das planilhas:

```json
"planilha_vendas": {
    "sheet_name": "Vendas",          ← nome exato da aba no Google Sheets
    "coluna_numero_pedido": "NUMERO PEDIDO"  ← nome exato da coluna de ID do pedido
},
"planilha_pedidos": {
    "sheet_name": "Pedidos",         ← nome exato da aba no Google Sheets
    "coluna_numero_pedido": "NUMERO PEDIDO"  ← deve ser o mesmo identificador
}
```

---

## Como usar

```bash
python main.py
```

O script vai:
1. Ler todas as linhas da Planilha de Vendas com a coluna `FRETE` vazia
2. Buscar o CEP e valor declarado na Planilha de Pedidos pelo número do pedido
3. Abrir o navegador, fazer login na FM Transportes e cotar o frete
4. Salvar o valor cotado na coluna `FRETE` da Planilha de Vendas
5. Exibir um resumo no terminal

---

## Estrutura do Projeto

```
frete/
├── main.py           # Orquestra o fluxo completo
├── sheets.py         # Leitura e escrita no Google Sheets
├── cotacao.py        # Automação do site da transportadora
├── config.json       # Configurações editáveis
├── requirements.txt  # Dependências Python
├── .env.example      # Modelo de variáveis de ambiente
├── .env              # Suas credenciais (NÃO commitar no git)
└── credentials.json  # Chave da conta de serviço Google (NÃO commitar)
```

---

## Observações importantes

- O script **nunca sobrescreve** um valor de frete já preenchido
- Rode com `PLAYWRIGHT_HEADLESS=false` para ver o navegador e depurar
- Se os seletores do site da transportadora mudarem, edite `cotacao.py`
