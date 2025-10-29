#!/usr/bin/env python3
"""
Google Sheets Integration Module
Sistema de Assinatura de Contratos

Este módulo gerencia a integração com Google Sheets para armazenar
links de contratos DocuSign gerados.
"""

import json
import os
import boto3
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class GoogleSheetsHelper:
    """Classe para gerenciar integração com Google Sheets"""

    def __init__(self, s3_bucket='jsoninnovatis', s3_key='chave2.json'):
        """
        Inicializa a conexão com Google Sheets

        Args:
            s3_bucket (str): Nome do bucket S3 onde estão as credenciais
            s3_key (str): Chave do arquivo de credenciais no S3
        """
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.client = None
        self.worksheet = None
        self._connect()

    def _connect(self):
        """Estabelece conexão com Google Sheets via credenciais do S3"""
        try:
            logger.info("Connecting to Google Sheets...")

            # Configurar credenciais AWS das variáveis de ambiente
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'us-east-1')

            if not aws_access_key_id or not aws_secret_access_key:
                raise ValueError("AWS credentials not found in environment variables. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")

            boto3.setup_default_session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region
            )

            # Conectar ao S3 para obter credenciais (usando método compatível com código anterior)
            s3 = boto3.resource('s3')
            obj = s3.Bucket(self.s3_bucket).Object(self.s3_key).get()

            # Ler e decodificar credenciais
            creds_json = json.loads(obj['Body'].read().decode('utf-8'))
            logger.info("Google credentials loaded from S3")

            # Definir escopo de acesso
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]

            # Criar credenciais e autorizar
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
            self.client = gspread.authorize(creds)
            logger.info("Google Sheets authorized")

            # Conectar à planilha específica
            self._connect_to_worksheet()

            logger.info("Google Sheets connection successful")

        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise

    def _connect_to_worksheet(self):
        """Conecta à worksheet específica"""
        try:
            # Tentar conectar à planilha "URA_Backend" e worksheet "URA_Tickets"
            spreadsheet = self.client.open("URA_Backend")
            self.worksheet = spreadsheet.worksheet("URA_Tickets")

            # Ler cabeçalho para mapear colunas
            self._map_columns()

            logger.info("Connected to worksheet: URA_Backend > URA_Tickets")

        except Exception as e:
            logger.error(f"Failed to connect to worksheet: {e}")
            raise

    def _map_columns(self):
        """Mapeia as colunas da planilha dinamicamente"""
        try:
            # Ler primeira linha (cabeçalho)
            header_row = self.worksheet.row_values(1)

            # Criar mapeamento de colunas
            self.column_map = {}
            for col_num, header in enumerate(header_row, start=1):
                header_clean = header.strip().lower() if header else ""
                self.column_map[header_clean] = col_num

            # Verificar colunas obrigatórias (cliente_nome em vez de nome)
            required_columns = ['cliente_nome', 'email', 'link_contrato']
            missing_columns = [col for col in required_columns if col not in self.column_map]

            if missing_columns:
                logger.warning(f"Missing required columns in worksheet: {missing_columns}")
                logger.warning(f"Available columns: {list(self.column_map.keys())}")
            else:
                logger.info(f"Column mapping successful: {self.column_map}")

        except Exception as e:
            logger.error(f"Failed to map columns: {e}")
            # Fallback para mapeamento padrão
            self.column_map = {
                'cliente_nome': 1,  # Atualizado para cliente_nome
                'email': 2,
                'contrato': 3,
                'link_contrato': 4,
                'data_criacao': 5,
                'status': 6,
                'contrato_assinado': 7  # Nova coluna para status de assinatura
            }

    def add_or_update_contract_link(self, contract_data):
        """
        Adiciona ou atualiza um link de contrato na planilha baseado no nome/email

        Args:
            contract_data (dict): Dados do contrato contendo:
                - name: Nome do signatário (extraído do PDF)
                - email: Email do signatário (extraído do PDF)
                - contract_filename: Nome do arquivo do contrato
                - signing_link: Link de assinatura DocuSign
                - created_at: Data/hora de criação (opcional)
                - status: Status do contrato (opcional)
        """
        try:
            name = contract_data.get('name', '').strip()
            email = contract_data.get('email', '').strip()

            if not name or not email:
                logger.error("Name and email are required to add/update contract link")
                raise ValueError("Name and email are required")

            # Verificar se já existe uma linha com este nome/email
            existing_row = self._find_row_by_name_email(name, email)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if existing_row:
                # Atualizar linha existente - focar no link_contrato
                signing_link = contract_data.get('signing_link', '')

                if signing_link:
                    # Atualizar especificamente o campo link_contrato
                    self._update_contract_link(existing_row, signing_link, timestamp)
                    logger.info(f"Contract link updated in Google Sheets: {email} (row {existing_row})")
                else:
                    logger.warning(f"No signing link provided for update: {email}")
            else:
                # Inserir nova linha completa usando mapeamento dinâmico
                self._insert_new_contract_row(name, email, contract_data, timestamp)
                logger.info(f"New contract added to Google Sheets: {email}")

        except Exception as e:
            logger.error(f"Failed to add/update contract link to Google Sheets: {e}")
            raise

    def update_contract_status(self, name: str, email: str, status: str) -> bool:
        """
        Atualiza o status de assinatura de um contrato

        Args:
            name (str): Nome do signatário
            email (str): Email do signatário
            status (str): Novo status ('assinado' ou 'aguardando')

        Returns:
            bool: True se atualizado com sucesso
        """
        try:
            # Encontrar a linha do contrato
            row_num = self._find_row_by_name_email(name, email)

            if not row_num:
                logger.warning(f"Contrato não encontrado para atualização: {name} ({email})")
                return False

            # Verificar se coluna contrato_assinado existe
            if 'contrato_assinado' not in self.column_map:
                logger.error("Coluna 'contrato_assinado' não encontrada na planilha")
                return False

            # Atualizar status
            col_num = self.column_map['contrato_assinado']
            self.worksheet.update_cell(row_num, col_num, status)

            logger.info(f"Status do contrato atualizado: {name} ({email}) -> {status}")
            return True

        except Exception as e:
            logger.error(f"Erro ao atualizar status do contrato: {e}")
            return False

    def _update_contract_link(self, row_num, signing_link, timestamp):
        """
        Atualiza especificamente o campo link_contrato de uma linha existente

        Args:
            row_num (int): Número da linha (1-indexed)
            signing_link (str): Link de assinatura DocuSign
            timestamp (str): Timestamp da atualização
        """
        try:
            # Verificar se coluna link_contrato existe
            if 'link_contrato' not in self.column_map:
                logger.error("Column 'link_contrato' not found in worksheet")
                raise ValueError("Required column 'link_contrato' not found")

            # Atualizar link_contrato
            link_col = self.column_map['link_contrato']
            self.worksheet.update_cell(row_num, link_col, signing_link)

            # Atualizar data_criacao se a coluna existir e estiver vazia
            if 'data_criacao' in self.column_map:
                created_col = self.column_map['data_criacao']
                current_created = self.worksheet.cell(row_num, created_col).value
                if not current_created or current_created == '':
                    self.worksheet.update_cell(row_num, created_col, timestamp)

            # Atualizar status para 'Enviado' se a coluna existir
            if 'status' in self.column_map:
                status_col = self.column_map['status']
                self.worksheet.update_cell(row_num, status_col, 'Enviado')

            logger.info(f"Updated contract link: row {row_num}, column {link_col}, link: {signing_link[:50]}...")

        except Exception as e:
            logger.error(f"Failed to update contract link: {e}")
            raise

    def _insert_new_contract_row(self, name, email, contract_data, timestamp):
        """
        Insere uma nova linha na planilha usando mapeamento dinâmico de colunas

        Args:
            name (str): Nome do signatário
            email (str): Email do signatário
            contract_data (dict): Dados do contrato
            timestamp (str): Timestamp da criação
        """
        try:
            # Determinar quantas colunas temos
            max_col = max(self.column_map.values()) if self.column_map else 6

            # Criar lista vazia para todas as colunas
            row_data = [''] * max_col

            # Preencher colunas conhecidas (cliente_nome em vez de nome)
            if 'cliente_nome' in self.column_map:
                row_data[self.column_map['cliente_nome'] - 1] = name
            if 'email' in self.column_map:
                row_data[self.column_map['email'] - 1] = email
            if 'contrato' in self.column_map:
                row_data[self.column_map['contrato'] - 1] = contract_data.get('contract_filename', '')
            if 'link_contrato' in self.column_map:
                row_data[self.column_map['link_contrato'] - 1] = contract_data.get('signing_link', '')
            if 'data_criacao' in self.column_map:
                row_data[self.column_map['data_criacao'] - 1] = contract_data.get('created_at', timestamp)
            if 'status' in self.column_map:
                row_data[self.column_map['status'] - 1] = contract_data.get('status', 'Pendente')
            if 'contrato_assinado' in self.column_map:
                row_data[self.column_map['contrato_assinado'] - 1] = 'aguardando'

            # Inserir linha
            self.worksheet.append_row(row_data, value_input_option='RAW')

        except Exception as e:
            logger.error(f"Failed to insert new contract row: {e}")
            raise

    def _find_row_by_name_email(self, name, email):
        """
        Encontra uma linha na planilha baseada no nome e email

        Args:
            name (str): Nome do signatário
            email (str): Email do signatário

        Returns:
            int: Número da linha (1-indexed) ou None se não encontrado
        """
        try:
            # Buscar todas as linhas
            all_records = self.worksheet.get_all_records()

            # Procurar por correspondência exata de nome e email
            # O gspread normalmente usa os nomes das colunas como chaves
            for row_num, record in enumerate(all_records, start=2):  # Começar da linha 2 (após cabeçalho)
                record_name = record.get('cliente_nome', '').strip().lower()  # Atualizado para cliente_nome
                record_email = record.get('email', '').strip().lower()

                if (record_name == name.lower() and record_email == email.lower()):
                    return row_num

            return None

        except Exception as e:
            logger.warning(f"Error finding row by name/email: {e}")
            return None

    def add_contract_link(self, contract_data):
        """
        Método legado - redireciona para add_or_update_contract_link
        """
        return self.add_or_update_contract_link(contract_data)

    def get_contract_links(self, email=None, limit=50):
        """
        Busca links de contratos da planilha

        Args:
            email (str, optional): Filtrar por email específico
            limit (int): Número máximo de registros a retornar

        Returns:
            list: Lista de contratos encontrados
        """
        try:
            # Buscar todos os registros
            records = self.worksheet.get_all_records()

            if email:
                # Filtrar por email
                records = [r for r in records if r.get('email', '').lower() == email.lower()]

            # Limitar resultados
            return records[:limit]

        except Exception as e:
            logger.error(f"Failed to get contract links from Google Sheets: {e}")
            return []

    def update_contract_status(self, email, status):
        """
        Atualiza o status de um contrato

        Args:
            email (str): Email do contrato a atualizar
            status (str): Novo status
        """
        try:
            # Buscar célula com o email
            cell = self.worksheet.find(email)

            if cell:
                # A coluna de status é a 6ª coluna (índice 5)
                status_cell = f"F{cell.row}"
                self.worksheet.update(status_cell, status)

                logger.info(f"Contract status updated for {email}: {status}")
            else:
                logger.warning(f"Contract not found for email: {email}")

        except Exception as e:
            logger.error(f"Failed to update contract status: {e}")
            raise

    def test_connection(self):
        """
        Testa a conexão com Google Sheets

        Returns:
            bool: True se conexão OK, False caso contrário
        """
        try:
            # Verificar se worksheet está disponível
            if not hasattr(self, 'worksheet') or self.worksheet is None:
                logger.error("Worksheet not initialized")
                return False

            # Tentar ler uma linha da planilha
            records = self.worksheet.get_all_records()
            logger.info(f"Google Sheets test successful. Found {len(records)} records.")
            return True

        except Exception as e:
            logger.error(f"Google Sheets test failed: {e}")
            return False

# Função utilitária para uso direto
def get_google_sheets_helper():
    """Retorna uma instância do GoogleSheetsHelper"""
    return GoogleSheetsHelper()
