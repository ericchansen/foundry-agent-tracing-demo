#!/usr/bin/env bash
# infra/setup.sh
# Provisions a classic Azure OpenAI resource in West Europe with full tracing.
# Usage: bash infra/setup.sh <subscription-id> <resource-group>
# Example: bash infra/setup.sh f7858112-xxxx-xxxx-xxxx-xxxxxxxxxxxx rg-foundry-demo

set -euo pipefail

SUBSCRIPTION="${1:?Usage: setup.sh <subscription-id> <resource-group>}"
RG="${2:?Usage: setup.sh <subscription-id> <resource-group>}"
LOCATION="westeurope"
OPENAI_NAME="azure-openai-$(cat /dev/urandom | tr -dc 'a-z0-9' | head -c 6)"
LAW_NAME="law-foundry-${LOCATION}"
APPI_NAME="appi-foundry-${LOCATION}"
DEPLOYMENT="gpt-4o"

echo "=== Setting subscription ==="
az account set --subscription "$SUBSCRIPTION"

echo "=== Creating resource group ==="
az group create -n "$RG" -l "$LOCATION" -o table

echo "=== Creating Azure OpenAI resource (classic) ==="
az cognitiveservices account create \
  --subscription "$SUBSCRIPTION" \
  -g "$RG" -n "$OPENAI_NAME" \
  --kind OpenAI \
  --sku S0 \
  --location "$LOCATION" \
  --custom-domain "$OPENAI_NAME" \
  -o table

OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --subscription "$SUBSCRIPTION" -g "$RG" -n "$OPENAI_NAME" \
  --query properties.endpoint -o tsv)
echo "Endpoint: $OPENAI_ENDPOINT"

echo ""
echo "=== Deploying gpt-4o with DataZoneStandard SKU ==="
# IMPORTANT: In West Europe, use DataZoneStandard (not Standard)
# This matches GDPR Data Zone boundary requirements
az cognitiveservices account deployment create \
  --subscription "$SUBSCRIPTION" \
  -g "$RG" -n "$OPENAI_NAME" \
  --deployment-name "$DEPLOYMENT" \
  --model-name gpt-4o \
  --model-version "2024-11-20" \
  --model-format OpenAI \
  --sku-name DataZoneStandard \
  --sku-capacity 10 \
  -o table

echo ""
echo "=== Creating Log Analytics workspace ==="
az monitor log-analytics workspace create \
  --subscription "$SUBSCRIPTION" \
  -g "$RG" -n "$LAW_NAME" \
  --location "$LOCATION" \
  --sku PerGB2018 \
  -o table

LAW_ID=$(az monitor log-analytics workspace show \
  --subscription "$SUBSCRIPTION" -g "$RG" -n "$LAW_NAME" \
  --query id -o tsv)

LAW_CUSTOMER_ID=$(az monitor log-analytics workspace show \
  --subscription "$SUBSCRIPTION" -g "$RG" -n "$LAW_NAME" \
  --query customerId -o tsv)

echo ""
echo "=== Creating Application Insights (workspace-based) ==="
az monitor app-insights component create \
  --subscription "$SUBSCRIPTION" \
  -g "$RG" --app "$APPI_NAME" \
  --location "$LOCATION" \
  --kind web \
  --workspace "$LAW_ID" \
  -o table

echo ""
echo "=== Wiring diagnostic settings — Trace + RequestResponse + Metrics ==="
RESOURCE_ID=$(az cognitiveservices account show \
  --subscription "$SUBSCRIPTION" -g "$RG" -n "$OPENAI_NAME" \
  --query id -o tsv)

az monitor diagnostic-settings create \
  --subscription "$SUBSCRIPTION" \
  --resource "$RESOURCE_ID" \
  --name "foundry-tracing-law" \
  --workspace "$LAW_ID" \
  --logs '[
    {"category":"Trace","enabled":true},
    {"category":"RequestResponse","enabled":true},
    {"category":"AzureOpenAIRequestUsage","enabled":true},
    {"category":"Audit","enabled":true}
  ]' \
  --metrics '[{"category":"AllMetrics","enabled":true}]' \
  -o table

echo ""
echo "=== Done! Add these to your .env ==="
echo "AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT"
echo "AZURE_OPENAI_DEPLOYMENT=$DEPLOYMENT"
echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION"
echo "LOG_ANALYTICS_WORKSPACE_ID=$LAW_CUSTOMER_ID"
