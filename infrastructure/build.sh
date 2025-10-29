#!/bin/bash

# Script de Build para Lambdas AWS
# Prepara os pacotes ZIP para deploy via Terraform

set -e

echo "🏗️  Construindo pacotes Lambda..."

# Criar diretório de build se não existir
mkdir -p build

# =============================================================================
# LAMBDA MONITOR
# =============================================================================

echo "📦 Preparando Lambda Monitor..."

cd lambda_monitor

# Instalar dependências em diretório temporário
mkdir -p package
pip install --target ./package -r requirements.txt

# Copiar código fonte
cp lambda_handler.py package/

# Criar ZIP
cd package
zip -r ../../infrastructure/lambda_monitor.zip .
cd ../..

# Limpar
rm -rf package

echo "✅ Lambda Monitor pronto!"

# =============================================================================
# LAMBDA PROCESSOR
# =============================================================================

echo "📦 Preparando Lambda Processor..."

cd processor

# Instalar dependências em diretório temporário
mkdir -p package
pip install --target ./package -r requirements.txt

# Copiar código fonte
cp contrato_processor.py package/

# Copiar dependências compartilhadas
cp -r ../shared/* package/

# Criar ZIP
cd package
zip -r ../../infrastructure/lambda_processor.zip .
cd ../..

# Limpar
rm -rf package

echo "✅ Lambda Processor pronto!"

# =============================================================================
# LAMBDA API
# =============================================================================

echo "📦 Preparando Lambda API..."

cd api

# Instalar dependências em diretório temporário
mkdir -p package
pip install --target ./package -r requirements.txt

# Copiar código fonte
cp contract_api.py package/
cp webhook_manager.py package/

# Copiar dependências compartilhadas
cp -r ../shared/* package/

# Criar ZIP
cd package
zip -r ../../infrastructure/lambda_api.zip .
cd ../..

# Limpar
rm -rf package

echo "✅ Lambda API pronta!"

# =============================================================================
# FINALIZAR
# =============================================================================

cd ..

echo ""
echo "🎉 Build concluído!"
echo ""
echo "Arquivos gerados:"
echo "  - infrastructure/lambda_monitor.zip"
echo "  - infrastructure/lambda_processor.zip"
echo "  - infrastructure/lambda_api.zip"
echo ""
echo "Execute: cd infrastructure && terraform apply"
