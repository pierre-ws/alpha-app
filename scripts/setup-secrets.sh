#!/usr/bin/env bash
set -euo pipefail

REPO="pierre-ws/alpha-app"
RG="policy-referential"
MSI_NAME="mi-deploy-team-alpha"

echo "Fetching AZURE_TENANT_ID..."
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "Fetching AZURE_SUBSCRIPTION_ID..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "Fetching DEPLOYER_MSI_CLIENT_ID from $MSI_NAME..."
MSI_CLIENT_ID=$(az identity show --name "$MSI_NAME" --resource-group "$RG" --query clientId -o tsv)

echo ""
echo "Setting secrets on $REPO:"
echo "  AZURE_TENANT_ID=$TENANT_ID"
echo "  AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
echo "  DEPLOYER_MSI_CLIENT_ID=$MSI_CLIENT_ID"
echo ""

gh secret set AZURE_TENANT_ID --repo "$REPO" --body "$TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO" --body "$SUBSCRIPTION_ID"
gh secret set DEPLOYER_MSI_CLIENT_ID --repo "$REPO" --body "$MSI_CLIENT_ID"

echo "✅ All secrets set on $REPO"
