"""
sheets.py — Funções de leitura e escrita no Google Sheets
"""

import os
from typing import Optional
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service():
    """Cria e retorna o cliente autenticado do Google Sheets."""
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def _col_letter(index: int) -> str:
    """Converte índice (0-based) para letra de coluna (A, B, ..., Z, AA, ...)."""
    result = ""
    while True:
        result = chr(65 + index % 26) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def _get_header_index(headers: list, col_name: str) -> int:
    """Retorna o índice (0-based) de uma coluna pelo nome. Lança erro se não encontrar."""
    normalized = [h.strip().upper() for h in headers]
    target = col_name.strip().upper()
    if target not in normalized:
        raise ValueError(
            f"Coluna '{col_name}' não encontrada. Colunas disponíveis: {headers}"
        )
    return normalized.index(target)


def ler_pedidos_sem_frete(config: dict) -> list:
    """
    Lê todas as linhas da Planilha de Vendas onde a coluna FRETE está vazia.

    Retorna lista de dicts com:
        - row_index: número da linha na planilha (1-based, incluindo header = linha 1)
        - nome_cliente: valor da coluna de cliente (usado para cruzar com Planilha de Pedidos)
    """
    service = _get_service()
    cfg = config["planilha_vendas"]
    spreadsheet_id = cfg["spreadsheet_id"]
    sheet_name = cfg["sheet_name"]
    col_frete = cfg["coluna_frete"]
    col_cliente = cfg["coluna_cliente"]

    range_name = f"'{sheet_name}'!A:ZZ"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    rows = result.get("values", [])

    if not rows:
        print("[SHEETS] Planilha de Vendas está vazia.")
        return []

    headers = rows[0]
    idx_frete = _get_header_index(headers, col_frete)
    idx_cliente = _get_header_index(headers, col_cliente)

    pedidos_pendentes = []
    for i, row in enumerate(rows[1:], start=2):  # linha 2 em diante (header = linha 1)
        frete_val = row[idx_frete].strip() if idx_frete < len(row) else ""
        cliente_val = row[idx_cliente].strip() if idx_cliente < len(row) else ""

        if not frete_val and cliente_val:
            pedidos_pendentes.append({
                "row_index": i,
                "nome_cliente": cliente_val,
            })

    print(f"[SHEETS] {len(pedidos_pendentes)} pedido(s) sem frete encontrado(s).")
    return pedidos_pendentes


def buscar_dados_pedido(nome_cliente: str, config: dict) -> Optional[dict]:
    """
    Busca CEP e VALOR DECLARADO na Planilha de Pedidos pelo nome do cliente.

    Retorna dict com 'cep' e 'valor_declarado', ou None se não encontrado.
    """
    service = _get_service()
    cfg = config["planilha_pedidos"]
    spreadsheet_id = cfg["spreadsheet_id"]
    sheet_name = cfg["sheet_name"]
    col_cep = cfg["coluna_cep"]
    col_valor = cfg["coluna_valor_declarado"]
    col_cliente = cfg["coluna_cliente"]

    range_name = f"'{sheet_name}'!A:ZZ"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    rows = result.get("values", [])

    if not rows:
        print("[SHEETS] Planilha de Pedidos está vazia.")
        return None

    headers = rows[0]
    idx_cliente = _get_header_index(headers, col_cliente)
    idx_cep = _get_header_index(headers, col_cep)
    idx_valor = _get_header_index(headers, col_valor)

    nome_busca = nome_cliente.strip().upper()
    for row in rows[1:]:
        cliente_val = row[idx_cliente].strip().upper() if idx_cliente < len(row) else ""
        if cliente_val == nome_busca:
            cep = row[idx_cep].strip() if idx_cep < len(row) else ""
            valor = row[idx_valor].strip() if idx_valor < len(row) else ""
            return {"cep": cep, "valor_declarado": valor}

    print(f"[SHEETS] Cliente '{nome_cliente}' não encontrado na Planilha de Pedidos.")
    return None


def salvar_frete(row_index: int, valor_frete: str, config: dict) -> bool:
    """
    Insere o valor do frete na coluna FRETE da linha indicada na Planilha de Vendas.
    Nunca sobrescreve células que já possuem valor.

    Retorna True se salvo com sucesso, False caso contrário.
    """
    service = _get_service()
    cfg = config["planilha_vendas"]
    spreadsheet_id = cfg["spreadsheet_id"]
    sheet_name = cfg["sheet_name"]
    col_frete = cfg["coluna_frete"]

    # Descobre a letra da coluna FRETE
    range_header = f"'{sheet_name}'!A1:ZZ1"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_header)
        .execute()
    )
    headers = result.get("values", [[]])[0]
    idx_frete = _get_header_index(headers, col_frete)
    col_letter = _col_letter(idx_frete)

    cell_range = f"'{sheet_name}'!{col_letter}{row_index}"

    # Verificação de segurança: não sobrescreve valor existente
    check = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=cell_range)
        .execute()
    )
    existing = check.get("values", [[""]])[0][0] if check.get("values") else ""
    if existing.strip():
        print(f"[SHEETS] Linha {row_index}: célula já preenchida com '{existing}'. Pulando.")
        return False

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=cell_range,
        valueInputOption="USER_ENTERED",
        body={"values": [[valor_frete]]},
    ).execute()

    print(f"[SHEETS] Linha {row_index}: frete '{valor_frete}' salvo com sucesso.")
    return True
