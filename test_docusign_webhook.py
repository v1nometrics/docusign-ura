#!/usr/bin/env python3
"""
Teste do Webhook DocuSign
Sistema de Assinatura de Contratos
"""

import json
import requests
from datetime import datetime

def test_webhook_endpoint():
    """Testa o endpoint do webhook DocuSign"""

    # URL da API (ajuste conforme necessrio)
    api_url = "http://localhost:5000/webhook/docusign"

    # Exemplo de payload de webhook do DocuSign para envelope completado
    webhook_payload = {
        "event": "envelope-completed",
        "data": {
            "envelopeId": "b8f2d556-99c1-4251-ae49-decab5ec9fe1",
            "status": "completed",
            "statusChangedDateTime": "2025-10-28T13:47:30.0000000Z",
            "documents": [
                {
                    "documentId": "1",
                    "name": "contrato.pdf",
                    "type": "content"
                }
            ],
            "recipients": {
                "signers": [
                    {
                        "recipientId": "1",
                        "email": "cliente@email.com",
                        "name": "Cliente Exemplo",
                        "status": "completed",
                        "signedDateTime": "2025-10-28T13:47:25.0000000Z"
                    }
                ]
            }
        },
        "eventData": {
            "accountId": "123456",
            "envelopeId": "b8f2d556-99c1-4251-ae49-decab5ec9fe1",
            "envelopeSummary": {
                "status": "completed",
                "emailSubject": "Contrato para Assinatura",
                "envelopeId": "b8f2d556-99c1-4251-ae49-decab5ec9fe1",
                "statusChangedDateTime": "2025-10-28T13:47:30.0000000Z"
            }
        }
    }

    try:
        print(" Testando webhook DocuSign...")
        print(f" URL: {api_url}")
        print(f" Payload: {json.dumps(webhook_payload, indent=2, ensure_ascii=False)}")
        print()

        # Enviar requisio POST
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'DocuSign-Webhook/1.0'
        }

        response = requests.post(api_url, json=webhook_payload, headers=headers, timeout=30)

        print("Resposta recebida:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")

        try:
            response_data = response.json()
            print(f"   Body: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Body (raw): {response.text}")

        # Verificar se foi sucesso
        if response.status_code == 200:
            print("\n TESTE APROVADO!")
            print("    Webhook processado com sucesso")
            print("    Status deve ter sido atualizado no Google Sheets")
            print("    Email de notificao deve ter sido enviado")
        else:
            print(f"\n TESTE REPROVADO - Status Code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f" ERRO DE CONEXO: {e}")
        print("\n VERIFICAES:")
        print("    API est rodando? (python api/run_api.py)")
        print("    Porta 5000 est livre?")
        print("    Firewall bloqueando?")

    except Exception as e:
        print(f" ERRO INESPERADO: {e}")

def test_webhook_locally():
    """Testa o webhook localmente sem fazer requisio HTTP"""

    print(" Testando webhook localmente...")
    print("=" * 50)

    try:
        from api.webhook_docusign import handle_webhook

        # Mesmo payload de teste
        webhook_payload = {
            "event": "envelope-completed",
            "data": {
                "envelopeId": "b8f2d556-99c1-4251-ae49-decab5ec9fe1",
                "status": "completed"
            }
        }

        print(" Testando com payload:")
        print(json.dumps(webhook_payload, indent=2))
        print()

        result = handle_webhook(webhook_payload)

        print(" Resultado:")
        print(json.dumps(result, indent=2))

        if result.get('statusCode') == 200:
            print("\n TESTE LOCAL APROVADO!")
        else:
            print(f"\n  Status Code: {result.get('statusCode')}")

    except Exception as e:
        print(f" ERRO NO TESTE LOCAL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        test_webhook_locally()
    else:
        test_webhook_endpoint()
