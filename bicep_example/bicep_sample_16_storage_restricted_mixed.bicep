// bicep_transformer 출력 샘플 16: 사내 보안 정책 시뮬 - Storage 제한(Private/방화벽) + 실수로 하나 공개
// RedTeam/Policy 검증용 - 정책상 Storage는 막혀야 하는데, 캐시용 계정은 공개 설정된 혼재 케이스

param location string = resourceGroup().location
param appName string = 'order-service'
param allowedIpRange string = '10.5.0.0/16'

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-${appName}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: [allowedIpRange] }
    subnets: [
      { name: 'subnet-app', properties: { addressPrefix: '10.5.1.0/24' } }
      { name: 'subnet-pe', properties: { addressPrefix: '10.5.2.0/24', privateEndpointNetworkPolicies: 'Disabled' } }
    ]
  }
}

// 사내 정책: 메인 데이터는 Private Endpoint + 방화벽만
resource storageMain 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${appName}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      virtualNetworkRules: [
        { id: '${vnet.id}/subnets/subnet-app' }
      ]
    }
  }
}

resource peMain 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: 'pe-storage-main'
  location: location
  properties: {
    subnet: { id: '${resourceId(resourceGroup().name, 'Microsoft.Network/virtualNetworks', vnet.name)}/subnets/subnet-pe' }
    privateLinkServiceConnections: [
      { name: 'pls-main', properties: { privateLinkServiceId: storageMain.id, groupIds: ['blob', 'file'] } }
    ]
  }
}

// 실수: 캐시용 Storage를 공개 설정 (사내 정책 위반)
resource storageCache 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stcache${appName}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: false
    allowBlobPublicAccess: true
    minimumTlsVersion: 'TLS1_0'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-${appName}'
  location: location
  sku: { name: 'B1', tier: 'Basic' }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${appName}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      httpsOnly: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
    }
  }
}
