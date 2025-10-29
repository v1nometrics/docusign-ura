import os

DS_JWT = {
    "ds_client_id": "04ccf572-a15f-449b-9bc5-c43c7a79000b",
    "ds_impersonated_user_id": "82810b50-8ef0-43b4-8e43-79397107ad3e",  # The id of the user.
    "private_key_file": "./app/private.key", # Create a new file in your repo source folder named private.key then copy and paste your RSA private key there and save it.
    "authorization_server": "account-d.docusign.com"
}

# AWS S3 Configuration
AWS_CONFIG = {
    "access_key_id": os.getenv('AWS_ACCESS_KEY_ID'),
    "secret_access_key": os.getenv('AWS_SECRET_ACCESS_KEY'),
    "region": os.getenv('AWS_REGION', 'us-east-1'),
    "bucket_name": os.getenv('TEMPLATE_TRIGGER_BUCKET', 'template-trigger-docusign'),
    "contracts_folder": "contratos-gerados/"
}