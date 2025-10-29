import base64
from os import path
import logging

from docusign_esign import EnvelopesApi, EnvelopeDefinition, Document, Signer, CarbonCopy, SignHere, Tabs, Recipients

from ...jwt_helpers import create_api_client
from ...aws_s3_helper import S3Helper
from ...jwt_config import AWS_CONFIG


class Eg002SigningViaEmailS3Controller:

    @classmethod
    def worker(cls, args, contract_name=None):
        """
        1. Create the envelope request object
        2. Send the envelope

        Args:
            args: Arguments containing envelope and account info
            contract_name: Optional specific contract name to use from S3
        """
        logger = logging.getLogger(__name__)

        #ds-snippet-start:eSign2Step3
        envelope_args = args["envelope_args"]
        logger.debug(" Iniciando criao de envelope DocuSign")

        # Initialize S3 helper
        logger.debug(" Inicializando helper S3...")
        s3_helper = S3Helper(
            access_key=AWS_CONFIG["access_key_id"],
            secret_key=AWS_CONFIG["secret_access_key"],
            region=AWS_CONFIG["region"],
            bucket_name=AWS_CONFIG["bucket_name"]
        )

        # Create the envelope request object
        logger.debug(" Criando definio do envelope...")
        envelope_definition = cls.make_envelope_s3(envelope_args, s3_helper, contract_name)
        api_client = create_api_client(base_path=args["base_path"], access_token=args["access_token"])

        # Call Envelopes::create API method
        # Exceptions will be caught by the calling function
        logger.debug(" Enviando envelope para DocuSign...")
        envelopes_api = EnvelopesApi(api_client)
        results = envelopes_api.create_envelope(account_id=args["account_id"], envelope_definition=envelope_definition)

        envelope_id = results.envelope_id
        logger.info(f" Envelope criado com sucesso - ID: {envelope_id}")

        # Generate signing link for the signer
        logger.debug(" Gerando link de assinatura...")
        recipient_view_request = {
            "returnUrl": envelope_args.get("return_url", "https://www.docusign.com"),
            "authenticationMethod": "email",
            "email": envelope_args["signer_email"],
            "userName": envelope_args["signer_name"]
        }

        # Get the signing URL
        envelope_api = EnvelopesApi(api_client)
        view_url = envelope_api.create_recipient_view(
            account_id=args["account_id"],
            envelope_id=envelope_id,
            recipient_view_request=recipient_view_request
        )

        logger.info(f" Link de assinatura gerado: {view_url.url[:50]}...")
        return {
            "envelope_id": envelope_id,
            "signing_url": view_url.url
        }
        #ds-snippet-end:eSign2Step3

    @classmethod
    #ds-snippet-start:eSign2Step2
    def make_envelope_s3(cls, args, s3_helper, contract_name=None):
        """
        Creates envelope using PDF from S3 bucket

        Args:
            args: Envelope arguments
            s3_helper: S3Helper instance
            contract_name: Optional specific contract name
        """
        logger = logging.getLogger(__name__)

        # Get contract from S3
        logger.debug(" Buscando contrato no S3...")
        if contract_name:
            logger.debug(f" Procurando contrato especfico: {contract_name}")
            contract_info = s3_helper.get_contract_by_name(contract_name, AWS_CONFIG["contracts_folder"])
            if not contract_info:
                logger.error(f" Contrato {contract_name} no encontrado no bucket S3")
                raise ValueError(f"Contract {contract_name} not found in S3 bucket")
        else:
            # Get the latest contract
            logger.debug(" Procurando contrato mais recente...")
            contract_info = s3_helper.get_latest_contract(AWS_CONFIG["contracts_folder"])
            if not contract_info:
                logger.error(" Nenhum contrato encontrado no bucket S3")
                raise ValueError("No contracts found in S3 bucket")

        # Download contract as base64
        logger.debug(f" Baixando contrato: {contract_info['key']}")
        contract_b64 = s3_helper.get_file_as_base64(contract_info['key'])
        if not contract_b64:
            logger.error(f" Falha ao baixar contrato: {contract_info['key']}")
            raise ValueError(f"Failed to download contract {contract_info['key']}")

        logger.debug(f" Contrato preparado: {len(contract_b64)} caracteres base64")

        # create the envelope definition
        logger.debug(" Criando definio do envelope...")
        env = EnvelopeDefinition(
            email_subject="Por favor, assine este contrato"
        )

        # Create the document model from S3 PDF
        contract_filename = path.basename(contract_info['key'])
        document = Document(
            document_base64=contract_b64,
            name=contract_filename,
            file_extension="pdf",
            document_id="1"
        )

        # The order in the docs array determines the order in the envelope
        env.documents = [document]
        logger.debug(f" Documento adicionado ao envelope: {contract_filename}")

        # Create the signer recipient model
        signer1 = Signer(
            email=args["signer_email"],
            name=args["signer_name"],
            recipient_id="1",
            routing_order="1"
        )

        # Create signHere fields (also known as tabs) on the documents,
        # We're using anchor (autoPlace) positioning
        #
        # Common anchor strings for Brazilian contracts
        sign_here_tabs = []

        # Try different common anchor strings
        common_anchors = ["/sn1/", "**assinatura**", "**signature**", "/assinatura/"]

        for anchor in common_anchors:
            sign_here = SignHere(
                anchor_string=anchor,
                anchor_units="pixels",
                anchor_y_offset="10",
                anchor_x_offset="20"
            )
            sign_here_tabs.append(sign_here)

        # If no anchor found, place signature at bottom of first page
        if not sign_here_tabs:
            sign_here = SignHere(
                page_number="1",
                x_position="100",
                y_position="700",  # Bottom of A4 page
                document_id="1"
            )
            sign_here_tabs.append(sign_here)

        # Add the tabs model to the signer
        signer1.tabs = Tabs(sign_here_tabs=sign_here_tabs)

        # Add the recipients to the envelope object
        recipients = Recipients(signers=[signer1])
        env.recipients = recipients

        # Request that the envelope be sent by setting |status| to "sent".
        # To request that the envelope be created as a draft, set to "created"
        env.status = args["status"]

        return env
    #ds-snippet-end:eSign2Step2
