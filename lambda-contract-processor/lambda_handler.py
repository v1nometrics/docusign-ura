#!/usr/bin/env python3
"""
AWS Lambda para geração de links de assinatura de contratos usando DocuSign e AWS S3

Este lambda é acionado por upload de contratos no S3 e:
1. Busca contratos no bucket S3
2. Cria envelopes de assinatura no DocuSign
3. Gera links de assinatura e atualiza Google Sheets

Função principal: lambda_handler(event, context)
"""

import json
import logging
import os
from docusign_esign import ApiClient
from docusign_esign.client.api_exception import ApiException

from app.jwt_helpers import get_jwt_token, get_private_key
from app.eSignature.examples.eg002_signing_via_email_s3 import Eg002SigningViaEmailS3Controller
from app.jwt_config import DS_JWT

# Importar Google Sheets helper
try:
    from shared.google_sheets_helper import GoogleSheetsHelper
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    print("⚠️  Google Sheets integration not available (missing dependencies)")

SCOPES = [
    "signature", "impersonation"
]

# Configurações do Lambda
LAMBDA_CONFIG = {
    "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    "return_url": os.environ.get("RETURN_URL", "https://www.docusign.com")
}


def get_token(private_key, api_client):
    """Obtém token JWT do DocuSign"""
    # Call request_jwt_user_token method
    token_response = get_jwt_token(private_key, SCOPES, DS_JWT["authorization_server"], DS_JWT["ds_client_id"],
                                   DS_JWT["ds_impersonated_user_id"])
    access_token = token_response.access_token

    # Save API account ID
    user_info = api_client.get_user_info(access_token)
    accounts = user_info.get_accounts()
    api_account_id = accounts[0].account_id
    base_path = accounts[0].base_uri + "/restapi"

    return {"access_token": access_token, "api_account_id": api_account_id, "base_path": base_path}


def get_latest_contract_data():
    """
    Busca dados do contrato mais recente e extrai nome/email do nome do arquivo

    Returns:
        dict: Dados do contrato ou None se não encontrar
    """
    logger = logging.getLogger(__name__)

    try:
        from app.aws_s3_helper import S3Helper
        from app.jwt_config import AWS_CONFIG

        s3_helper = S3Helper(
            access_key=AWS_CONFIG["access_key_id"],
            secret_key=AWS_CONFIG["secret_access_key"],
            region=AWS_CONFIG["region"],
            bucket_name=AWS_CONFIG["bucket_name"]
        )

        contract_data = s3_helper.get_latest_contract(AWS_CONFIG["contracts_folder"])
        return contract_data

    except Exception as e:
        logger.error(f"❌ Erro ao buscar contrato mais recente: {str(e)}")
        return None


def create_signing_envelope(signer_email=None, signer_name=None, contract_name=None, return_url="https://www.docusign.com", auto_extract=True, update_google_sheets=True):
    """
    Cria envelope de assinatura e retorna o link de assinatura

    Args:
        signer_email (str, optional): Email do signatário (auto-extraído se None)
        signer_name (str, optional): Nome do signatário (auto-extraído se None)
        contract_name (str, optional): Nome específico do contrato
        return_url (str): URL de retorno após assinatura
        auto_extract (bool): Se True, extrai nome/email do nome do arquivo mais recente
        update_google_sheets (bool): Se True, atualiza planilha Google Sheets com o link

    Returns:
        dict: Resultado com envelope_id e signing_url
    """
    logger = logging.getLogger(__name__)

    # Auto-extrair dados do contrato mais recente se necessário
    if auto_extract and (signer_email is None or signer_name is None):
        logger.info("🤖 Ativando extração automática de dados do contrato...")
        contract_data = get_latest_contract_data()

        if contract_data:
            if signer_email is None and contract_data.get('extracted_email'):
                signer_email = contract_data['extracted_email']
                logger.info(f"📧 Email extraído automaticamente: {signer_email}")

            if signer_name is None and contract_data.get('extracted_name'):
                signer_name = contract_data['extracted_name']
                logger.info(f"👤 Nome extraído automaticamente: {signer_name}")
        else:
            if signer_email is None or signer_name is None:
                return {
                    "success": False,
                    "error": "no_contract_data",
                    "message": "Não foi possível extrair dados do contrato. Forneça email e nome manualmente."
                }

    # Verificar se temos os dados necessários
    if not signer_email or not signer_name:
        return {
            "success": False,
            "error": "missing_parameters",
            "message": "Email e nome do signatário são obrigatórios"
        }

    logger.info("🔐 Inicializando autenticação DocuSign...")
    api_client = ApiClient()
    api_client.set_base_path(DS_JWT["authorization_server"])
    api_client.set_oauth_host_name(DS_JWT["authorization_server"])

    private_key = get_private_key(DS_JWT["private_key_file"]).encode("ascii").decode("utf-8")

    try:
        logger.debug("🔑 Gerando token JWT...")
        jwt_values = get_token(private_key, api_client)
        logger.debug("✅ Token JWT obtido com sucesso")
        logger.debug(f"🆔 Account ID: {jwt_values['api_account_id'][:10]}...")

        envelope_args = {
            "signer_email": signer_email,
            "signer_name": signer_name,
            "cc_email": "",  # Não usar CC por padrão
            "cc_name": "",
            "status": "sent",
            "return_url": return_url
        }

        args = {
            "account_id": jwt_values["api_account_id"],
            "base_path": jwt_values["base_path"],
            "access_token": jwt_values["access_token"],
            "envelope_args": envelope_args
        }

        logger.info("📤 Criando envelope de assinatura...")
        logger.debug(f"📧 Email: {signer_email}, Nome: {signer_name}")
        logger.debug(f"📄 Contrato: {contract_name or 'mais recente'}")
        logger.debug(f"🔗 Return URL: {return_url}")

        result = Eg002SigningViaEmailS3Controller.worker(args, contract_name)

        envelope_result = {
            "success": True,
            "envelope_id": result["envelope_id"],
            "signing_url": result["signing_url"],
            "message": "Link de assinatura gerado com sucesso"
        }

        # Atualizar Google Sheets se solicitado e disponível
        if update_google_sheets and GOOGLE_SHEETS_AVAILABLE:
            try:
                logger.info("Updating Google Sheets with contract link...")

                # Preparar dados para Google Sheets
                sheets_data = {
                    'name': signer_name,
                    'email': signer_email,
                    'contract_filename': contract_name or 'contrato_auto.pdf',
                    'signing_link': result["signing_url"],
                    'status': 'Enviado'
                }

                # Inicializar Google Sheets helper
                sheets_helper = GoogleSheetsHelper()
                sheets_helper.add_or_update_contract_link(sheets_data)

                logger.info("Google Sheets updated successfully!")
                envelope_result["google_sheets_updated"] = True

            except Exception as e:
                logger.warning(f"Google Sheets update failed: {str(e)}")
                envelope_result["google_sheets_error"] = str(e)
                # Não falha a operação se Google Sheets falhar

        return envelope_result

    except ApiException as err:
        body = err.body.decode('utf8')
        logger.error(f"🚨 Erro na API DocuSign: {body}")

        if "consent_required" in body:
            consent_url = get_consent_url()
            logger.warning("🔐 Consentimento necessário - gere URL de consentimento")
            return {
                "success": False,
                "error": "consent_required",
                "consent_url": consent_url,
                "message": "É necessário conceder consentimento para a aplicação. Acesse a URL fornecida."
            }

        return {
            "success": False,
            "error": "api_error",
            "message": f"Erro na API do DocuSign: {body}"
        }

    except ValueError as err:
        logger.error(f"❌ Erro de validação: {str(err)}")
        return {
            "success": False,
            "error": "validation_error",
            "message": str(err)
        }

    except Exception as err:
        logger.error(f"💥 Erro desconhecido: {str(err)}", exc_info=True)
        return {
            "success": False,
            "error": "unknown_error",
            "message": f"Erro desconhecido: {str(err)}"
        }


def get_consent_url():
    """Gera URL de consentimento do DocuSign"""
    url_scopes = "+".join(SCOPES)

    # Construct consent URL
    redirect_uri = "https://developers.docusign.com/platform/auth/consent"
    consent_url = f"https://{DS_JWT['authorization_server']}/oauth/auth?response_type=code&" \
                  f"scope={url_scopes}&client_id={DS_JWT['ds_client_id']}&redirect_uri={redirect_uri}"

    return consent_url


def lambda_handler(event, context):
    """
    Função principal do AWS Lambda

    Args:
        event: Evento do S3 (upload de contrato) ou chamada direta
        context: Contexto do Lambda

    Returns:
        Dict com resultado da operação
    """
    # Configurar logging
    log_level = getattr(logging, LAMBDA_CONFIG["log_level"])
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

    logger.info("[START] Iniciando Lambda Contract Processor")

    try:
        # Verificar se é um evento S3
        if 'Records' in event and event['Records']:
            record = event['Records'][0]
            if 's3' in record:
                # Evento de upload S3
                s3_info = record['s3']
                bucket_name = s3_info['bucket']['name']
                object_key = s3_info['object']['key']

                logger.info(f"📤 Upload detectado: s3://{bucket_name}/{object_key}")

                # Processar contrato automaticamente (extração de dados)
                result = create_signing_envelope(
                    signer_email=None,  # Será extraído do nome do arquivo
                    signer_name=None,   # Será extraído do nome do arquivo
                    contract_name=object_key,
                    return_url=LAMBDA_CONFIG["return_url"],
                    auto_extract=True,
                    update_google_sheets=GOOGLE_SHEETS_AVAILABLE
                )
            else:
                # Chamada direta (API Gateway ou outra)
                logger.info("📞 Chamada direta detectada")
                result = process_direct_call(event)
        else:
            # Chamada direta sem Records
            logger.info("📞 Chamada direta sem Records")
            result = process_direct_call(event)

        # Log do resultado
        if result["success"]:
            logger.info("✅ Envelope criado com sucesso!")
            logger.info(f"🆔 Envelope ID: {result['envelope_id']}")
            logger.info(f"🔗 Link de assinatura: {result['signing_url']}")
        else:
            logger.error(f"❌ Erro: {result['message']}")
            if 'error' in result:
                logger.error(f"🔍 Tipo de erro: {result['error']}")

        # Retornar resultado formatado para Lambda
        return {
            'statusCode': 200 if result['success'] else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result, ensure_ascii=False)
        }

    except Exception as e:
        logger.error(f"[ERROR] Erro crítico: {str(e)}", exc_info=True)
        error_result = {
            "success": False,
            "error": "critical_error",
            "message": f"Erro crítico: {str(e)}"
        }
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_result, ensure_ascii=False)
        }


def process_direct_call(event):
    """
    Processa chamada direta com parâmetros específicos

    Args:
        event: Dados da chamada (email, name, contract_name, etc.)

    Returns:
        Dict com resultado da operação
    """
    logger = logging.getLogger(__name__)

    # Extrair parâmetros do body ou query parameters
    if 'body' in event and event['body']:
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']
    else:
        body = event

    signer_email = body.get('email')
    signer_name = body.get('name')
    contract_name = body.get('contract')
    return_url = body.get('return_url', LAMBDA_CONFIG["return_url"])
    auto_extract = body.get('auto_extract', True)
    update_sheets = body.get('update_google_sheets', GOOGLE_SHEETS_AVAILABLE)

    logger.info("📧 Processando chamada direta")
    logger.info(f"📧 Email: {signer_email}")
    logger.info(f"👤 Nome: {signer_name}")
    logger.info(f"📄 Contrato: {contract_name or 'mais recente'}")

    return create_signing_envelope(
        signer_email=signer_email,
        signer_name=signer_name,
        contract_name=contract_name,
        return_url=return_url,
        auto_extract=auto_extract,
        update_google_sheets=update_sheets
    )
