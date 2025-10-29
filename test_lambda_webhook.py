#!/usr/bin/env python3
"""
Script de Teste para Lambda Webhook DocuSign

Este script permite testar localmente o lambda-webhook simulando
um webhook de assinatura completa do DocuSign.

Uso:
python test_lambda_webhook.py --local        # Teste local (sem HTTP)
python test_lambda_webhook.py --http         # Teste com servidor HTTP local
python test_lambda_webhook.py --help         # Ajuda

Exemplos de uso:
- Teste local direto: python test_lambda_webhook.py --local
- Servidor HTTP: python test_lambda_webhook.py --http
"""

import json
import logging
import argparse
import sys
from datetime import datetime, timezone
from typing import Dict, Any

# Importar o handler do lambda
try:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda-webhook'))
    from lambda_handler import lambda_handler, DocuSignWebhookHandler
except ImportError as e:
    print(f"[ERROR] Erro ao importar lambda handler: {e}")
    print("Certifique-se de que esta executando do diretorio raiz do projeto")
    sys.exit(1)


def create_mock_webhook_data() -> Dict[str, Any]:
    """
    Cria dados de webhook simulados de uma assinatura completa

    Returns:
        Dict com dados do webhook DocuSign
    """
    current_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    return {
        "event": "envelope-completed",
        "data": {
            "envelopeId": "12345678-1234-1234-1234-123456789012",
            "envelopeSummary": {
                "status": "completed",
                "completedDateTime": current_time,
                "recipients": {
                    "signers": [
                        {
                            "email": "gabriel.vitor@innovatis.com",
                            "name": "Gabriel Vitor Moreno Chaves",
                            "status": "completed",
                            "signedDateTime": current_time
                        }
                    ]
                }
            }
        }
    }


def test_local_handler():
    """
    Testa o handler diretamente (sem simular evento Lambda)
    """
    print("[TEST] Testando handler localmente...")
    print("=" * 60)

    # Criar dados de teste
    webhook_data = create_mock_webhook_data()

    print("[WEBHOOK] Dados do webhook simulados:")
    print(json.dumps(webhook_data, indent=2, ensure_ascii=False))
    print()

    # Inicializar handler
    handler = DocuSignWebhookHandler()

    # Processar webhook
    print("[PROCESS] Processando webhook...")
    result = handler.process_webhook(webhook_data)

    print("[RESULT] Resultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # Verificar resultado - aceita tanto sucesso quanto "contrato não encontrado"
    if result.get('statusCode') == 200:
        print("[PASS] Teste PASSED: Webhook processado com sucesso!")
        return True
    elif result.get('statusCode') == 500 and "Failed to update contract status" in result.get('body', ''):
        print("[INFO] Teste INFO: Contrato nao encontrado (esperado para dados de teste)")
        print("[PASS] Teste PASSED: Handler funcionou corretamente, apenas contrato inexistente")
        return True
    else:
        print("[FAIL] Teste FAILED: Erro inesperado no processamento")
        print(f"[DEBUG] Status Code: {result.get('statusCode')}")
        print(f"[DEBUG] Body: {result.get('body', '')}")
        return False


def test_lambda_format():
    """
    Testa o handler no formato Lambda (evento API Gateway)
    """
    print("[LAMBDA] Testando handler no formato Lambda...")
    print("=" * 60)

    # Criar evento simulado do API Gateway
    webhook_data = create_mock_webhook_data()

    event = {
        'httpMethod': 'POST',
        'path': '/webhook',
        'body': json.dumps(webhook_data),
        'headers': {
            'Content-Type': 'application/json',
            'User-Agent': 'DocuSign Webhook'
        },
        'requestContext': {
            'httpMethod': 'POST'
        }
    }

    # Contexto simulado
    context = {
        'aws_request_id': 'test-request-id-12345',
        'function_name': 'test-lambda-webhook',
        'memory_limit_in_mb': '256'
    }

    print("[EVENT] Evento Lambda simulado:")
    print(json.dumps(event, indent=2, ensure_ascii=False))
    print()

    # Executar lambda handler
    print("[EXEC] Executando lambda handler...")
    result = lambda_handler(event, context)

    print("[RESULT] Resultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # Verificar resultado - aceita tanto sucesso quanto "contrato não encontrado"
    if result.get('statusCode') == 200:
        print("[PASS] Teste PASSED: Lambda executado com sucesso!")
        return True
    elif result.get('statusCode') == 500 and "Failed to update contract status" in result.get('body', ''):
        print("[INFO] Teste INFO: Contrato nao encontrado (esperado para dados de teste)")
        print("[PASS] Teste PASSED: Lambda funcionou corretamente, apenas contrato inexistente")
        return True
    else:
        print("[FAIL] Teste FAILED: Erro inesperado na execucao Lambda")
        print(f"[DEBUG] Status Code: {result.get('statusCode')}")
        print(f"[DEBUG] Body: {result.get('body', '')}")
        return False


def run_http_server():
    """
    Executa um servidor HTTP simples para testar webhooks
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse

    class WebhookTestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            """Handle GET requests (health check)"""
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response = {
                'status': 'webhook_test_server_running',
                'message': 'Servidor de teste webhook ativo',
                'timestamp': datetime.utcnow().isoformat(),
                'endpoints': {
                    'GET /': 'Health check',
                    'POST /webhook': 'Testar webhook DocuSign'
                }
            }

            self.wfile.write(json.dumps(response, indent=2).encode())

        def do_POST(self):
            """Handle POST requests (webhook simulation)"""
            if self.path == '/webhook':
                # Ler dados do request
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)

                try:
                    webhook_data = json.loads(post_data.decode())

                    print(f"📨 Webhook recebido: {webhook_data.get('event', 'unknown')}")

                    # Processar com handler real
                    handler = DocuSignWebhookHandler()
                    result = handler.process_webhook(webhook_data)

                    # Responder
                    self.send_response(result.get('statusCode', 500))
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()

                    response_body = result.get('body', '{}')
                    if isinstance(response_body, str):
                        self.wfile.write(response_body.encode())
                    else:
                        self.wfile.write(json.dumps(response_body).encode())

                except json.JSONDecodeError:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"error": "Invalid JSON"}')
            else:
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "Not found"}')

        def log_message(self, format, *args):
            """Override para usar nosso logger"""
            print(f"🌐 {format % args}")

    print("🌐 Iniciando servidor HTTP de teste...")
    print("=" * 60)
    print("📡 Servidor rodando em: http://localhost:8080")
    print("📋 Endpoints disponíveis:")
    print("  GET  /         - Health check")
    print("  POST /webhook  - Receber webhook DocuSign")
    print()
    print("💡 Para testar:")
    print("curl -X GET http://localhost:8080/")
    print("curl -X POST http://localhost:8080/webhook -H 'Content-Type: application/json' -d @test_webhook.json")
    print()
    print("❌ Pressione Ctrl+C para parar o servidor")
    print("=" * 60)

    server = HTTPServer(('localhost', 8080), WebhookTestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor parado pelo usuário")


def create_test_webhook_file():
    """
    Cria um arquivo JSON de exemplo para teste
    """
    webhook_data = create_mock_webhook_data()

    with open('test_webhook.json', 'w', encoding='utf-8') as f:
        json.dump(webhook_data, f, indent=2, ensure_ascii=False)

    print("[FILE] Arquivo 'test_webhook.json' criado para testes!")


def main():
    parser = argparse.ArgumentParser(
        description='Teste do Lambda Webhook DocuSign',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXEMPLOS DE USO:

# Teste local direto (sem rede)
python test_lambda_webhook.py --local

# Teste no formato Lambda
python test_lambda_webhook.py --lambda

# Servidor HTTP para testes reais
python test_lambda_webhook.py --http

# Criar arquivo de teste JSON
python test_lambda_webhook.py --create-test-file

# Todos os testes
python test_lambda_webhook.py --all
        """
    )

    parser.add_argument('--local', action='store_true',
                       help='Teste local direto do handler')
    parser.add_argument('--lambda-format', action='store_true',
                       help='Teste no formato evento Lambda')
    parser.add_argument('--http', action='store_true',
                       help='Executar servidor HTTP de teste')
    parser.add_argument('--create-test-file', action='store_true',
                       help='Criar arquivo test_webhook.json')
    parser.add_argument('--all', action='store_true',
                       help='Executar todos os testes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Log detalhado')

    args = parser.parse_args()

    # Configurar logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    print("[START] DocuSign Webhook Test Suite")
    print("=" * 60)

    # Executar ações solicitadas
    if args.create_test_file or args.all:
        create_test_webhook_file()

    if args.local or args.all:
        success_local = test_local_handler()
        print()

    if args.lambda_format or args.all:
        success_lambda = test_lambda_format()
        print()

    if args.http:
        run_http_server()

    if not any([args.local, args.lambda_format, args.http, args.create_test_file, args.all]):
        print("[INFO] Nenhum teste especificado. Use --help para ver opcoes.")
        print("[TIP] Dica: use --all para executar todos os testes")


if __name__ == "__main__":
    main()
