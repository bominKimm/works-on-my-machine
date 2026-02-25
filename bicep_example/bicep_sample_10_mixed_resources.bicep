// bicep_transformer 출력 샘플 10: 혼합 리소스 (Storage, Web, Key Vault, 진단 없음)
// RedTeam/Policy 검증용 - 여러 리소스 타입, 일부 위반

param location string = resourceGroup().location
param env string = 'staging'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${env}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableSoftDelete: true
    enablePurgeProtection: false
    accessPolicies: []
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-${env}'
  location: location
  sku: { name: 'B1', tier: 'Basic' }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      httpsOnly: false
      minTlsVersion: '1.0'
      ftpsState: 'Disabled'
    }
  }
}
