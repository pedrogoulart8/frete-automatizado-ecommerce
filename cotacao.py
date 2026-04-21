"""
cotacao.py — Automação do site FM Transportes com Playwright
"""

import os
import re
from typing import Optional
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, BrowserContext, Playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

TIMEOUT = 60_000  # 60 segundos


class CotacaoSession:

    def __init__(self, config: dict):
        self.config = config
        self.login = os.getenv("TRANSPORTADORA_LOGIN")
        self.senha = os.getenv("TRANSPORTADORA_SENHA")
        self.headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").strip().lower() != "false"
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        browser = self._playwright.chromium.launch(headless=self.headless, slow_mo=200)
        self._context = browser.new_context()
        self._page = self._context.new_page()
        self._fazer_login()
        return self

    def __exit__(self, *args):
        try:
            if self._context:
                self._context.browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    def _fill(self, selector: str, valor: str, descricao: str):
        """
        Preenche um campo pelo seletor CSS.
        Usa fill() direto — evita problemas com labels flutuantes que interceptam cliques.
        """
        page = self._page
        try:
            # Aguarda o campo estar presente no DOM
            page.wait_for_selector(selector, timeout=10_000)
            loc = page.locator(selector).first
            # Foca o elemento e limpa antes de preencher
            loc.focus()
            page.keyboard.press("Control+a")
            loc.fill(valor)
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)
            print(f"[COTACAO] '{descricao}' = '{valor}'")
        except Exception as e:
            print(f"[COTACAO] AVISO: '{descricao}' não preenchido — {e}")

    def _fazer_login(self):
        url = self.config["transportadora"]["url"]
        page = self._page

        print(f"[COTACAO] Acessando {url}...")
        page.goto(url, timeout=TIMEOUT)
        page.wait_for_selector("input", timeout=TIMEOUT)

        if page.locator("input[type='password']").count() > 0:
            print("[COTACAO] Tela de login detectada. Fazendo login...")
            self._preencher_login()
        else:
            print("[COTACAO] Já autenticado.")

    def _preencher_login(self):
        page = self._page

        # Campo usuário — não clica, usa fill direto para evitar label flutuante
        for selector in [
            "input[type='text']",
            "input:not([type='password']):not([type='hidden']):not([type='submit'])",
        ]:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.focus()
                loc.first.fill(self.login)
                print(f"[COTACAO] Usuário '{self.login}' preenchido.")
                break

        # Campo senha
        senha_loc = page.locator("input[type='password']").first
        senha_loc.focus()
        senha_loc.fill(self.senha)
        print("[COTACAO] Senha preenchida.")

        # Botão LOGIN
        for selector in ["button:has-text('LOGIN')", "button:has-text('Entrar')", "button[type='submit']"]:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.click()
                print("[COTACAO] Botão LOGIN clicado.")
                break

        # Aguarda tela de login desaparecer
        try:
            page.wait_for_selector("input[type='password']", state="hidden", timeout=TIMEOUT)
        except Exception:
            pass

        page.wait_for_timeout(3000)
        print("[COTACAO] Login concluído.")

    def _navegar_para_cotacao(self):
        """Recarrega a URL de cotação para garantir formulário limpo a cada pedido."""
        page = self._page
        url = self.config["transportadora"]["url"]
        print("[COTACAO] Recarregando página de cotação...")
        page.goto(url, timeout=TIMEOUT)
        page.wait_for_selector("input[name='client']", timeout=TIMEOUT)
        print("[COTACAO] Formulário de cotação carregado.")

    def _preencher_remetente(self, remetente: str):
        """
        Preenche o campo Remetente (autocomplete):
        1. Limpa o campo completamente (para forçar o dropdown mesmo se já tiver valor)
        2. Digita o nome caractere a caractere para disparar o autocomplete
        3. Aguarda o dropdown aparecer
        4. Clica na primeira opção que corresponde ao nome
        """
        page = self._page
        print(f"[COTACAO] Preenchendo Remetente (autocomplete): '{remetente}'")

        campo = page.locator("input[name='client']").first
        campo.focus()

        # Limpa o campo completamente antes de digitar
        page.keyboard.press("Control+a")
        page.keyboard.press("Delete")
        page.wait_for_timeout(300)

        # Digita caractere a caractere para garantir que o React dispara o autocomplete
        campo.type(remetente, delay=80)
        page.wait_for_timeout(1500)  # aguarda dropdown aparecer

        # Tenta clicar na opção do dropdown que contém o texto do remetente
        # Dropdowns React costumam usar li, div com role=option, ou divs simples
        seletores_opcao = [
            f"li:has-text('{remetente}')",
            f"div[role='option']:has-text('{remetente}')",
            f"[class*='option']:has-text('{remetente}')",
            f"[class*='suggestion']:has-text('{remetente}')",
            f"[class*='item']:has-text('{remetente}')",
            f"[class*='list'] div:has-text('{remetente}')",
        ]

        for selector in seletores_opcao:
            try:
                loc = page.locator(selector)
                if loc.count() > 0:
                    loc.first.click()
                    print(f"[COTACAO] Remetente '{remetente}' selecionado no dropdown.")
                    page.wait_for_timeout(500)
                    return
            except Exception:
                continue

        # Fallback: tenta via JavaScript buscando elemento visível com o texto
        try:
            clicou = page.evaluate(f"""
                () => {{
                    const texto = '{remetente}'.toLowerCase();
                    const todos = Array.from(document.querySelectorAll('li, [role="option"], [class*="option"], [class*="item"]'));
                    const opcao = todos.find(el => el.offsetParent !== null && el.textContent.trim().toLowerCase().includes(texto));
                    if (opcao) {{ opcao.click(); return true; }}
                    return false;
                }}
            """)
            if clicou:
                print(f"[COTACAO] Remetente selecionado via JavaScript.")
                page.wait_for_timeout(500)
                return
        except Exception:
            pass

        print(f"[COTACAO] AVISO: opção do dropdown para '{remetente}' não encontrada.")

    def _preencher_volume_popup(self, volume_cfg: dict):
        page = self._page

        print("[COTACAO] Aguardando popup 'Adicionar Volume'...")
        page.wait_for_selector("input[name='quantity']", timeout=TIMEOUT)
        page.wait_for_timeout(500)

        # Campos do popup com name exatos confirmados pelo usuário
        campos = [
            ("input[name='quantity']",   str(volume_cfg["quantidade"]),     "Quantidade"),
            ("input[name='realWeight']", str(volume_cfg["peso_kg"]),        "Peso Real Total (kg)"),
            ("input[name='length']",     str(volume_cfg["comprimento_cm"]), "Comprimento (cm)"),
            ("input[name='height']",     str(volume_cfg["altura_cm"]),      "Altura (cm)"),
            ("input[name='width']",      str(volume_cfg["largura_cm"]),     "Largura (cm)"),
        ]

        for selector, valor, nome in campos:
            self._fill(selector, valor, nome)

        page.wait_for_timeout(500)

        # Clica em ADICIONAR via JavaScript usando o ID exato do dialog
        # O texto real no DOM é "Adicionar" — o CSS aplica text-transform:uppercase visualmente
        print("[COTACAO] Clicando em ADICIONAR via JavaScript...")
        try:
            page.evaluate("""
                () => {
                    const btn = document.querySelector('#confirm-dialog footer button:first-child');
                    if (btn) btn.click();
                }
            """)
            print("[COTACAO] Botão ADICIONAR clicado.")
        except Exception as e:
            print(f"[COTACAO] ERRO ao clicar ADICIONAR: {e}")

        # Aguarda popup fechar
        try:
            page.wait_for_selector("input[name='quantity']", state="hidden", timeout=10_000)
            print("[COTACAO] Popup fechado.")
        except Exception:
            print("[COTACAO] AVISO: popup pode não ter fechado.")

        page.wait_for_timeout(500)

    def _capturar_frete(self) -> Optional[str]:
        page = self._page
        page.wait_for_timeout(4000)

        for selector in [
            "td:has-text('R$')",
            "span:has-text('R$')",
            "strong:has-text('R$')",
            "b:has-text('R$')",
            "[class*='price']",
            "[class*='valor']",
            "div:has-text('R$')",
        ]:
            try:
                loc = page.locator(selector)
                if loc.count() > 0:
                    texto = loc.first.inner_text().strip()
                    match = re.search(r"R\$\s*[\d.,]+", texto)
                    if match:
                        return match.group(0).strip()
            except Exception:
                continue

        # Fallback no texto visível da página
        try:
            content = page.inner_text("body")
            for m in re.findall(r"R\$\s*[\d.,]+", content):
                num = re.sub(r"[^\d,]", "", m).replace(",", ".")
                try:
                    if 5.0 <= float(num) <= 500.0:
                        return m.strip()
                except ValueError:
                    continue
        except Exception:
            pass

        return None

    def cotar(self, cep_destino: str, valor_declarado: str) -> Optional[str]:
        page = self._page
        cfg_transp = self.config["transportadora"]
        remetente = cfg_transp["remetente"]
        volume_cfg = cfg_transp["volume"]
        cep_limpo = re.sub(r"\D", "", cep_destino)

        try:
            self._navegar_para_cotacao()

            # Remetente — campo autocomplete: digita e seleciona a opção no dropdown
            self._preencher_remetente(remetente)
            self._fill("input[name='totalValue']",         valor_declarado, "Valor Total")
            self._fill("input[name='zipCodeDestination']", cep_limpo,       "Cep de Destino")

            # Abre popup de volume
            print("[COTACAO] Abrindo popup 'Adicionar Volume'...")
            abriu = False
            for selector in [
                "button:has-text('Adicionar Volume')",
                "button:has-text('ADICIONAR VOLUME')",
                "button:has-text('+ Volume')",
                "[title*='olume']",
            ]:
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0:
                        loc.first.click()
                        abriu = True
                        print("[COTACAO] Popup aberto.")
                        break
                except Exception:
                    continue

            if not abriu:
                print("[COTACAO] AVISO: botão 'Adicionar Volume' não encontrado.")

            self._preencher_volume_popup(volume_cfg)

            # Clica em PESQUISAR via JavaScript (busca case-insensitive)
            print("[COTACAO] Clicando em PESQUISAR via JavaScript...")
            page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const btn = buttons.find(b => b.textContent.trim().toLowerCase().includes('pesquisar'));
                    if (btn) btn.click();
                }
            """)
            print("[COTACAO] PESQUISAR clicado.")

            valor_frete = self._capturar_frete()

            if valor_frete:
                # Remove "R$ ", troca vírgula por ponto → ex: "19.87"
                valor_frete = re.sub(r"R\$\s*", "", valor_frete).strip().replace(",", ".")
                print(f"[COTACAO] Frete obtido: {valor_frete}")
            else:
                print("[COTACAO] Valor do frete não encontrado na página.")

            return valor_frete

        except PlaywrightTimeout as e:
            print(f"[COTACAO] Timeout: {e}")
            return None
        except RuntimeError as e:
            print(f"[COTACAO] Erro de navegação: {e}")
            return None
        except Exception as e:
            print(f"[COTACAO] Erro inesperado: {e}")
            return None
