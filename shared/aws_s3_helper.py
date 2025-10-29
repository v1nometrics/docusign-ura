import boto3
import base64
from io import BytesIO
import logging
from botocore.exceptions import ClientError


class S3Helper:
    def __init__(self, access_key, secret_key, region, bucket_name):
        self.logger = logging.getLogger(__name__)
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.bucket_name = bucket_name

        self.logger.debug(f" Inicializando S3Helper - Bucket: {bucket_name}, Regio: {region}")
        self.s3_client = self._create_client()

    def _create_client(self):
        """Cria e retorna cliente S3"""
        self.logger.debug(" Criando cliente S3...")
        try:
            client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            self.logger.debug(" Cliente S3 criado com sucesso")
            return client
        except Exception as e:
            self.logger.error(f" Erro ao criar cliente S3: {str(e)}")
            raise

    def list_files_in_folder(self, folder_prefix):
        """
        Lista todos os arquivos em uma pasta especfica do bucket

        Args:
            folder_prefix (str): Prefixo da pasta (ex: "contratos-gerados/")

        Returns:
            list: Lista de objetos S3 com informaes dos arquivos
        """
        self.logger.debug(f" Listando arquivos na pasta: {folder_prefix}")
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=folder_prefix
            )

            files = []
            if 'Contents' in response:
                pdf_count = 0
                for obj in response['Contents']:
                    # Filtrar apenas arquivos PDF
                    if obj['Key'].lower().endswith('.pdf'):
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified']
                        })
                        pdf_count += 1

                self.logger.debug(f" Encontrados {pdf_count} arquivos PDF")
            else:
                self.logger.warning(f" Pasta vazia ou no encontrada: {folder_prefix}")

            return files

        except ClientError as e:
            self.logger.error(f" Erro ao listar arquivos: {e}")
            return []

    def download_file(self, file_key):
        """
        Baixa um arquivo do S3

        Args:
            file_key (str): Chave do arquivo no S3

        Returns:
            bytes: Contedo do arquivo em bytes
        """
        self.logger.debug(f" Baixando arquivo: {file_key}")
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            file_content = response['Body'].read()
            self.logger.debug(f" Arquivo baixado com sucesso: {len(file_content)} bytes")
            return file_content

        except ClientError as e:
            self.logger.error(f" Erro ao baixar arquivo {file_key}: {e}")
            return None

    def get_file_as_base64(self, file_key):
        """
        Baixa um arquivo do S3 e retorna em base64

        Args:
            file_key (str): Chave do arquivo no S3

        Returns:
            str: Contedo do arquivo em base64
        """
        file_content = self.download_file(file_key)
        if file_content:
            return base64.b64encode(file_content).decode("ascii")
        return None

    def get_latest_contract(self, folder_prefix="contratos-gerados/"):
        """
        Retorna o contrato mais recente da pasta especificada

        Args:
            folder_prefix (str): Prefixo da pasta

        Returns:
            dict: Informaes do arquivo mais recente ou None se no encontrar
                  Inclui nome e email extrados do nome do arquivo (formato: nome_email.pdf)
        """
        self.logger.debug(f" Buscando contrato mais recente em: {folder_prefix}")
        files = self.list_files_in_folder(folder_prefix)

        if not files:
            self.logger.warning(f" Nenhum contrato encontrado em: {folder_prefix}")
            return None

        # Ordenar por data de modificao (mais recente primeiro)
        files.sort(key=lambda x: x['last_modified'], reverse=True)
        latest_file = files[0]

        # Extrair nome e email do nome do arquivo (formato: nome_email.pdf)
        filename = latest_file['key'].replace(folder_prefix, '').replace('.pdf', '')

        # Verificar se o arquivo tem o formato esperado (nome_email)
        if '_' in filename:
            # Dividir no ltimo underscore para separar nome do email
            name_part, email_part = filename.rsplit('_', 1)

            # Converter nome (substituir hfens por espaos e capitalizar)
            extracted_name = name_part.replace('-', ' ').title()

            # Processar email: underscores viram pontos, e hfens viram @ apenas se for o padro de domnio
            extracted_email = email_part.replace('_', '.')

            # Se no tem @, pode ser que use hfen como separador de domnio
            if '@' not in extracted_email:
                if '-' in extracted_email:
                    # ltimo hfen separa domnio
                    parts = extracted_email.rsplit('-', 1)
                    if len(parts) == 2:
                        extracted_email = f"{parts[0]}@{parts[1]}"
                else:
                    # Formato j est correto, adicionar @ se necessrio
                    pass

            latest_file['extracted_name'] = extracted_name
            latest_file['extracted_email'] = extracted_email

            self.logger.info(f" Contrato mais recente: {latest_file['key']}")
            self.logger.info(f" Nome extrado: {extracted_name}")
            self.logger.info(f" Email extrado: {extracted_email}")
        else:
            self.logger.warning(f" Nome do arquivo no segue padro esperado: {filename}")
            latest_file['extracted_name'] = None
            latest_file['extracted_email'] = None

        return latest_file

    def get_contract_by_name(self, contract_name, folder_prefix="contratos-gerados/"):
        """
        Busca um contrato especfico por nome

        Args:
            contract_name (str): Nome do contrato (com ou sem extenso .pdf)
            folder_prefix (str): Prefixo da pasta

        Returns:
            dict: Informaes do arquivo ou None se no encontrar
        """
        if not contract_name.lower().endswith('.pdf'):
            contract_name += '.pdf'

        file_key = f"{folder_prefix}{contract_name}"

        files = self.list_files_in_folder(folder_prefix)
        for file_info in files:
            if file_info['key'] == file_key:
                return file_info

        return None
