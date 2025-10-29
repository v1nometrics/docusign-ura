#!/usr/bin/env python3
"""
AWS Lambda para processamento de webhooks do DocuSign

Este lambda é exposto via API Gateway e recebe webhooks quando
contratos são assinados no DocuSign, atualizando status no Google Sheets.

Função principal: lambda_handler(event, context)
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Imports locais
from shared.google_sheets_helper import GoogleSheetsHelper

# Configurações do Lambda
LAMBDA_CONFIG = {
    "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    "notification_email": os.environ.get("NOTIFICATION_EMAIL", ""),
    "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
    "smtp_username": os.environ.get("SMTP_USERNAME", ""),
    "smtp_password": os.environ.get("SMTP_PASSWORD", "")
}


class DocuSignWebhookHandler:
    """Handler para webhooks do DocuSign"""

    def __init__(self):
        self.sheets_helper = None
        self.logger = logging.getLogger(__name__)
        self._init_google_sheets()

    def _init_google_sheets(self):
        """Inicializa conexão com Google Sheets"""
        try:
            self.sheets_helper = GoogleSheetsHelper()
            self.logger.info("Google Sheets initialized for webhook processing")
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Sheets: {e}")
            self.sheets_helper = None

    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa webhook recebido do DocuSign

        Args:
            webhook_data: Dados do webhook

        Returns:
            Dict com resultado do processamento
        """
        try:
            self.logger.info("Processing DocuSign webhook")

            # Verificar se é um evento de envelope completado
            event_type = webhook_data.get('event')
            if event_type != 'envelope-completed':
                self.logger.info(f"Ignoring non-completion event: {event_type}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Event ignored'})
                }

            # Extrair informações do envelope
            envelope_data = self._extract_envelope_info(webhook_data)
            if not envelope_data:
                self.logger.warning("Could not extract envelope information")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid envelope data'})
                }

            # Atualizar status no Google Sheets
            success = self._update_contract_status(envelope_data)

            # Enviar notificação por email
            self._send_notification_email(envelope_data)

            if success:
                self.logger.info(f"Contract completion processed: {envelope_data['email']}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Contract completion processed successfully',
                        'envelope_id': envelope_data['envelope_id'],
                        'signer_email': envelope_data['email']
                    })
                }
            else:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to update contract status'})
                }

        except Exception as e:
            self.logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Webhook processing failed: {str(e)}'})
            }

    def _extract_envelope_info(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extrai informações do envelope do webhook

        Args:
            webhook_data: Dados do webhook

        Returns:
            Dict com informações do envelope ou None se erro
        """
        try:
            # Estrutura típica do webhook do DocuSign
            envelope_data = {
                'envelope_id': webhook_data.get('data', {}).get('envelopeId'),
                'status': webhook_data.get('data', {}).get('envelopeSummary', {}).get('status'),
                'completed_date': webhook_data.get('data', {}).get('envelopeSummary', {}).get('completedDateTime'),
                'email': None,
                'name': None
            }

            # Extrair informações do signatário
            recipients = webhook_data.get('data', {}).get('envelopeSummary', {}).get('recipients', {}).get('signers', [])
            if recipients and len(recipients) > 0:
                signer = recipients[0]  # Primeiro signatário
                envelope_data['email'] = signer.get('email')
                envelope_data['name'] = signer.get('name')

            # Validar dados obrigatórios
            if not envelope_data['envelope_id'] or not envelope_data['email']:
                self.logger.error("Missing required envelope data")
                return None

            return envelope_data

        except Exception as e:
            self.logger.error(f"Error extracting envelope info: {str(e)}")
            return None

    def _update_contract_status(self, envelope_data: Dict[str, Any]) -> bool:
        """
        Atualiza status do contrato no Google Sheets

        Args:
            envelope_data: Dados do envelope

        Returns:
            True se atualizado com sucesso
        """
        if not self.sheets_helper:
            self.logger.warning("Google Sheets not available")
            return False

        try:
            # Atualizar status diretamente
            email = envelope_data['email']
            status = 'Assinado'

            success = self.sheets_helper.update_contract_status(email, status)
            if success:
                self.logger.info(f"Contract status updated for {envelope_data['email']}")
            else:
                self.logger.error(f"Failed to update contract status for {envelope_data['email']}")

            return success

        except Exception as e:
            self.logger.error(f"Error updating contract status: {str(e)}")
            return False

    def _send_notification_email(self, envelope_data: Dict[str, Any]):
        """
        Envia notificação por email sobre conclusão do contrato

        Args:
            envelope_data: Dados do envelope
        """
        try:
            # Implementar envio de email se necessário
            # Por enquanto, apenas log
            self.logger.info(f"Notification email would be sent for {envelope_data['email']}")

            # TODO: Implementar envio real de email se necessário
            # if LAMBDA_CONFIG["notification_email"]:
            #     send_email(...)

        except Exception as e:
            self.logger.error(f"Error sending notification email: {str(e)}")


# Instância global do handler
webhook_handler = None


def get_webhook_handler():
    """Obtém instância singleton do webhook handler"""
    global webhook_handler
    if webhook_handler is None:
        webhook_handler = DocuSignWebhookHandler()
    return webhook_handler


def lambda_handler(event, context):
    """
    Função principal do AWS Lambda para webhooks do DocuSign

    Args:
        event: Evento do API Gateway com dados do webhook
        context: Contexto do Lambda

    Returns:
        Dict com resposta HTTP
    """
    # Configurar logging
    log_level = getattr(logging, LAMBDA_CONFIG["log_level"])
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

    logger.info("[START] Iniciando Lambda Webhook DocuSign")

    try:
        # Verificar método HTTP
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('httpMethod', 'POST'))

        if http_method == 'GET':
            # Endpoint de saúde/verificação
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'healthy',
                    'service': 'DocuSign Webhook Lambda',
                    'timestamp': datetime.utcnow().isoformat()
                })
            }

        elif http_method == 'POST':
            # Processar webhook do DocuSign
            if 'body' not in event:
                logger.warning("No body in webhook request")
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'No body provided'})
                }

            # Parse do body
            if isinstance(event['body'], str):
                webhook_data = json.loads(event['body'])
            else:
                webhook_data = event['body']

            logger.info(f"DocuSign webhook received: {webhook_data.get('event', 'unknown')}")

            # Processar webhook
            handler = get_webhook_handler()
            result = handler.process_webhook(webhook_data)

            return result

        else:
            # Método não suportado
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }

    except json.JSONDecodeError as e:
        logger.error(f"[ERROR] Invalid JSON in webhook request: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid JSON format in request body'})
        }

    except Exception as e:
        logger.error(f"[ERROR] Critical error in webhook processing: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': 'Webhook processing failed'
            })
        }
