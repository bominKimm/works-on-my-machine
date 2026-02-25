// bicep_transformer 출력 샘플 08: Function App + Storage (HTTP 트리거 익명 가능)
// RedTeam/Policy 검증용 - Function, 스토리지 설정

param location string = resourceGroup().location
param appName string = 'func-app'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${replace(uniqueString(resourceGroup().id), '-', '')}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: false
    minimumTlsVersion: 'TLS1_0'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-func'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  kind: 'functionapp'
}

resource funcApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${appName}-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      netFrameworkVersion: 'v6.0'
      ftpsState: 'AllAllowed'
    }
  }
}
