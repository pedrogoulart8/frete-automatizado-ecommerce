"""
inspect_api.py — Intercepta requisições de rede durante uma cotação no site FM Transportes.
Objetivo: descobrir se existe uma API REST sendo chamada por baixo do React.

Execução: python inspect_api.py
"""

import os
import json
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

LOGIN    = os.getenv("TRANSPORTADORA_LOGIN", "brunoxavier")
SENHA    = os.getenv("TRANSPORTADORA_SENHA", "@Xavier13")
URL_SITE = "https://alpha.fmtransportes.com.br/quote/client"

# CEP e valor de teste — ajuste se quiser
CEP_TESTE   = "01310100"   # Av. Paulista, SP
VALOR_TESTE = "100"

capturadas = []


def registrar(request_or_response, tipo: str):
    url = request_or_response.url
    # Ignora recursos estáticos irrelevantes
    if re.search(r"\.(js|css|png|jpg|svg|woff|ico|map)(\?|$)", url):
        return
    if "google" in url or "analytics" in url or "hotjar" in url:
        return

    entrada = {"tipo": tipo, "url": url}

    if tipo == "REQUEST":
        entrada["method"] = request_or_response.method
        try:
            entrada["post_data"] = request_or_response.post_data
        except Exception:
            pass

    if tipo == "RESPONSE":
        entrada["status"] = request_or_response.status
        try:
            body = request_or_response.body()
            # Tenta decodificar como JSON
            try:
                entrada["body_json"] = json.loads(body)
            except Exception:
                text = body.decode("utf-8", errors="replace")
                if len(text) < 2000:
                    entrada["body_text"] = text
        except Exception:
            pass

    capturadas.append(entrada)
    simbolo = "→" if tipo == "REQUEST" else "←"
    method  = entrada.get("method", "")
    status  = entrada.get("status", "")
    print(f"  {simbolo} [{tipo}] {method or status} {url}")


def fazer_login(page):
    print("\n[1] Acessando site...")
    page.goto(URL_SITE, timeout=60_000)
    page.wait_for_selector("input", timeout=60_000)

    if page.locator("input[type='password']").count() > 0:
        print("[2] Fazendo login...")
        # Usuário
        for sel in ["input[type='text']", "input:not([type='password']):not([type='hidden'])"]:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.fill(LOGIN)
                break
        # Senha
        page.locator("input[type='password']").first.fill(SENHA)
        # Botão
        for sel in ["button:has-text('LOGIN')", "button:has-text('Entrar')", "button[type='submit']"]:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                break
        page.wait_for_selector("input[type='password']", state="hidden", timeout=60_000)
        page.wait_for_timeout(3000)
        print("[2] Login OK.")
    else:
        print("[2] Já autenticado.")


def preencher_e_cotar(page):
    print("\n[3] Aguardando página estabilizar após login...")
    page.wait_for_timeout(4000)

    # Navega explicitamente para a página de cotação (pode ter redirecionado)
    print("[3] Navegando para página de cotação...")
    page.goto(URL_SITE, timeout=60_000)
    page.wait_for_timeout(3000)

    print("[3] Aguardando formulário...")
    # Tenta vários seletores possíveis para o campo remetente
    formulario_ok = False
    for sel in ["input[name='client']", "input[placeholder*='emetente']", "input[placeholder*='Remetente']"]:
        try:
            page.wait_for_selector(sel, timeout=15_000)
            formulario_ok = True
            print(f"[3] Formulário encontrado via '{sel}'.")
            break
        except Exception:
            continue

    if not formulario_ok:
        print("[3] AVISO: formulário não encontrado pelo seletor esperado. Tentando continuar mesmo assim...")
        page.wait_for_timeout(3000)

    # Remetente (autocomplete)
    print("[3] Preenchendo remetente...")
    campo = page.locator("input[name='client']").first
    campo.focus()
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    campo.type("Vesty Prata", delay=80)
    page.wait_for_timeout(1500)
    for sel in ["li:has-text('Vesty')", "div[role='option']:has-text('Vesty')", "[class*='option']:has-text('Vesty')"]:
        loc = page.locator(sel)
        if loc.count() > 0:
            loc.first.click()
            break

    # Valor e CEP
    page.locator("input[name='totalValue']").first.fill(VALOR_TESTE)
    page.locator("input[name='zipCodeDestination']").first.fill(CEP_TESTE)
    page.wait_for_timeout(500)

    # Abre popup de volume
    print("[3] Abrindo popup de volume...")
    for sel in ["button:has-text('Adicionar Volume')", "button:has-text('ADICIONAR VOLUME')"]:
        loc = page.locator(sel)
        if loc.count() > 0:
            loc.first.click()
            break
    page.wait_for_selector("input[name='quantity']", timeout=30_000)
    page.wait_for_timeout(500)

    # Preenche popup
    for sel, val in [
        ("input[name='quantity']",   "1"),
        ("input[name='realWeight']", "0,01"),
        ("input[name='length']",     "12"),
        ("input[name='height']",     "4"),
        ("input[name='width']",      "12"),
    ]:
        loc = page.locator(sel).first
        loc.focus()
        page.keyboard.press("Control+a")
        loc.fill(val)
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)

    # Clica ADICIONAR
    page.evaluate("() => { const btn = document.querySelector('#confirm-dialog footer button:first-child'); if (btn) btn.click(); }")
    page.wait_for_selector("input[name='quantity']", state="hidden", timeout=10_000)
    page.wait_for_timeout(500)

    # PESQUISAR
    print("[3] Clicando PESQUISAR...")
    page.evaluate("""
        () => {
            const btn = Array.from(document.querySelectorAll('button'))
                .find(b => b.textContent.trim().toLowerCase().includes('pesquisar'));
            if (btn) btn.click();
        }
    """)
    print("[3] Aguardando resultado...")
    page.wait_for_timeout(5000)


def main():
    print("=" * 65)
    print("  FM Transportes — Inspetor de API")
    print("=" * 65)
    print(f"  CEP teste  : {CEP_TESTE}")
    print(f"  Valor teste: R$ {VALOR_TESTE}")
    print("=" * 65)
    print("\nMonitorando requisições de rede...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context()
        page    = context.new_page()

        # Intercepta requests e responses
        page.on("request",  lambda r: registrar(r, "REQUEST"))
        page.on("response", lambda r: registrar(r, "RESPONSE"))

        fazer_login(page)
        preencher_e_cotar(page)

        browser.close()

    # Filtra apenas chamadas de API (JSON / XHR / fetch)
    api_calls = [
        c for c in capturadas
        if c.get("method") in ("POST", "GET", "PUT", "PATCH")
        or (c.get("tipo") == "RESPONSE" and isinstance(c.get("body_json"), (dict, list)))
    ]

    print("\n" + "=" * 65)
    print("  RESULTADO — Chamadas de API detectadas")
    print("=" * 65)

    if not api_calls:
        print("  Nenhuma chamada de API detectada.")
    else:
        for c in api_calls:
            print(f"\n  [{c['tipo']}]")
            print(f"  URL    : {c['url']}")
            if c.get("method"):
                print(f"  Method : {c['method']}")
            if c.get("post_data"):
                print(f"  Body   : {c['post_data'][:500]}")
            if c.get("status"):
                print(f"  Status : {c['status']}")
            if c.get("body_json"):
                print(f"  JSON   : {json.dumps(c['body_json'], ensure_ascii=False, indent=2)[:800]}")

    # Salva resultado completo em arquivo
    with open("api_inspect_result.json", "w", encoding="utf-8") as f:
        json.dump(api_calls, f, ensure_ascii=False, indent=2)
    print(f"\n  Resultado completo salvo em: api_inspect_result.json")
    print("=" * 65)


if __name__ == "__main__":
    main()
