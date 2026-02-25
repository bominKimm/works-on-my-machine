// bicep_transformer 출력 샘플 05: Key Vault 네트워크 전체 허용 + 퍼지 미보호
// RedTeam/Policy 검증용 - defaultAction Allow, enablePurgeProtection false

param location string = resourceGroup().location
param env string = 'prod'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableSoftDelete: false
    enablePurgeProtection: false
    accessPolicies: []
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}
