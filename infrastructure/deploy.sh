#!/bin/bash

# Script de Deployment para Arquitetura de Microsserviços
# Sistema de Assinatura de Contratos

set -e

echo "🚀 Iniciando deployment da arquitetura de microsserviços..."

# Verificar se terraform está instalado
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform não encontrado. Instale o Terraform primeiro."
    echo "   https://developer.hashicorp.com/terraform/downloads"
    exit 1
fi

# Verificar se AWS CLI está configurado
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI não configurado. Configure suas credenciais AWS."
    echo "   aws configure"
    exit 1
fi

# Verificar se terraform.tfvars existe
if [ ! -f "terraform.tfvars" ]; then
    echo "⚠️  Arquivo terraform.tfvars não encontrado."
    echo "   Copiando terraform.tfvars.example..."
    cp terraform.tfvars.example terraform.tfvars
    echo "   Edite o arquivo terraform.tfvars com suas configurações."
    echo ""
    echo "   Principais configurações:"
    echo "   - aws_region: Região AWS (ex: us-east-1)"
    echo "   - project_name: Nome do projeto"
    echo "   - environment: Ambiente (dev, staging, prod)"
    echo "   - s3_bucket_name: Nome do bucket S3 existente"
    echo ""
    read -p "Pressione ENTER após editar terraform.tfvars..."
fi

echo "🔨 Construindo pacotes Lambda..."
chmod +x build.sh
./build.sh

echo ""
echo "📦 Inicializando Terraform..."
terraform init

echo "🔍 Verificando plano de execução..."
terraform plan -out=tfplan

echo "📋 Plano de execução:"
terraform show -no-color tfplan

echo ""
read -p "Deseja aplicar as mudanças? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelado."
    exit 0
fi

echo "🏗️  Aplicando infraestrutura..."
terraform apply tfplan

echo "✅ Deployment concluído com sucesso!"

echo ""
echo "📋 Recursos criados:"
echo "===================="
echo ""

# Mostrar outputs importantes
echo "🔗 S3 Bucket Contratos:"
terraform output -raw s3_bucket_contratos
echo ""

echo "📦 S3 Bucket Resultados:"
terraform output -raw s3_bucket_resultados
echo ""

echo "📨 SQS Queue URL:"
terraform output -raw sqs_queue_url
echo ""

echo "🔧 Lambda Monitor ARN:"
terraform output -raw lambda_monitor_arn
echo ""

echo "⚙️  Lambda Processor ARN:"
terraform output -raw lambda_processor_arn
echo ""

echo "📢 SNS Topic ARN:"
terraform output -raw sns_topic_arn
echo ""

echo "🌐 API Gateway URL:"
terraform output -raw api_gateway_url
echo ""

echo "🔗 Lambda API ARN:"
terraform output -raw lambda_api_arn
echo ""

echo ""
echo "🎯 Próximos passos:"
echo "=================="
echo ""
echo "1. 📤 Faça upload de contratos PDF para a pasta 'contratos-gerados/' no bucket S3"
echo "2. 🤖 O sistema irá automaticamente:"
echo "   - Detectar o novo contrato via Lambda Monitor"
echo "   - Extrair nome e email do nome do arquivo"
echo "   - Enviar para processamento via SQS"
echo "   - Processar contrato e gerar link DocuSign via Lambda Processor"
echo "   - Salvar resultados no bucket de resultados"
echo ""
echo "3. 📊 Monitore os logs das funções Lambda no CloudWatch"
echo "4. 📧 Configure subscribers para o tópico SNS se desejar notificações"
echo ""

echo "✅ Sistema pronto para uso!"
echo ""
echo "Para destruir a infraestrutura:"
echo "terraform destroy"
