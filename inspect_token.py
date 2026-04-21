"""
inspect_token.py — Captura a resposta completa do endpoint de login da FM Transportes.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

LOGIN = os.getenv("TRANSPORTADORA_LOGIN", "brunoxavier")
SENHA = os.getenv("TRANSPORTADORA_SENHA", "@Xavier13")
URL   = "https://alpha.fmtransportes.com.br/api/token"

print("=" * 55)
print("  FM Transportes — Inspetor de Token")
print("=" * 55)
print(f"  URL  : {URL}")
print(f"  Login: {LOGIN}")
print("=" * 55)

response = requests.post(
    URL,
    json={"login": LOGIN, "password": SENHA},
    headers={"Content-Type": "application/json"},
    timeout=15,
)

print(f"\nStatus HTTP : {response.status_code}")
print(f"Headers     : {dict(response.headers)}")
print(f"\nBody (raw)  :\n{response.text}")

try:
    data = response.json()
    print(f"\nBody (JSON) :\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    print("\n--- Campos encontrados no JSON ---")
    for key, value in data.items():
        preview = str(value)[:80] + "..." if len(str(value)) > 80 else str(value)
        print(f"  {key}: {preview}")
except Exception:
    print("\n[AVISO] Resposta não é JSON válido.")

print("\n" + "=" * 55)
