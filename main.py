"""
main.py — Ponto de entrada da automação de cotação de frete 
"""

import json
import sys
import time

from sheets import ler_pedidos_sem_frete, buscar_dados_pedido, salvar_frete
from cotacao import CotacaoSession


def carregar_config(path: str = "config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("  E-commerce — Automação de Cotação de Frete")
    print("=" * 60)

    config = carregar_config()

    # 1. Lê pedidos sem frete na Planilha de Vendas
    pedidos = ler_pedidos_sem_frete(config)

    if not pedidos:
        print("\nNenhum pedido pendente. Encerrando.")
        sys.exit(0)

    total = len(pedidos)
    sucessos = 0
    falhas = 0
    falhas_detalhes = []

    # 2. Abre o navegador UMA VEZ e faz login
    print("\n[INFO] Abrindo navegador e fazendo login na transportadora...")
    with CotacaoSession(config) as session:

        for i, pedido in enumerate(pedidos, start=1):
            nome_cliente = pedido["nome_cliente"]
            row_index = pedido["row_index"]

            print(f"\n[{i}/{total}] Processando cliente '{nome_cliente}' (linha {row_index})...")

            # 2a. Busca CEP e valor na Planilha de Pedidos
            dados = buscar_dados_pedido(nome_cliente, config)
            if not dados:
                msg = f"Cliente '{nome_cliente}': não encontrado na Planilha de Pedidos."
                print(f"[AVISO] {msg}")
                falhas += 1
                falhas_detalhes.append(msg)
                continue

            cep = dados["cep"]
            valor_declarado = dados["valor_declarado"]

            if not cep:
                msg = f"Cliente '{nome_cliente}': CEP vazio na Planilha de Pedidos."
                print(f"[AVISO] {msg}")
                falhas += 1
                falhas_detalhes.append(msg)
                continue

            # 2b. Cota o frete reutilizando a sessão já autenticada
            try:
                valor_frete = session.cotar(cep, valor_declarado)
            except Exception as e:
                msg = f"Cliente '{nome_cliente}': erro ao cotar frete — {e}"
                print(f"[ERRO] {msg}")
                falhas += 1
                falhas_detalhes.append(msg)
                continue

            if not valor_frete:
                msg = f"Cliente '{nome_cliente}' — CEP {cep}: frete não retornado pelo site."
                print(f"[AVISO] {msg}")
                falhas += 1
                falhas_detalhes.append(msg)
                continue

            print(f"  >> Cliente '{nome_cliente}' — CEP {cep} — Frete: {valor_frete}")

            # 2c. Salva o frete na Planilha de Vendas
            salvo = salvar_frete(row_index, valor_frete, config)
            if salvo:
                sucessos += 1
            else:
                falhas += 1
                falhas_detalhes.append(f"Cliente '{nome_cliente}': falha ao salvar na planilha.")

            # Pausa entre pedidos para não sobrecarregar o site
            if i < total:
                time.sleep(1)

    # 3. Resumo final
    print("\n" + "=" * 60)
    print("  RESUMO FINAL")
    print(f"  Total processado : {total}")
    print(f"  Cotados com exito: {sucessos}")
    print(f"  Falhas           : {falhas}")
    if falhas_detalhes:
        print("\n  Detalhes das falhas:")
        for detalhe in falhas_detalhes:
            print(f"    - {detalhe}")
    print("=" * 60)


if __name__ == "__main__":
    main()
