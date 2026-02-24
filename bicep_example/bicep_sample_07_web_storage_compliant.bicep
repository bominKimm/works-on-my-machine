// bicep_transformer 출력 샘플 07: 웹앱 + 스토리지 (정책 준수에 가까운 구성)
// RedTeam/Policy 검증용 - HTTPS, TLS 1.2, NSG 제한

param location string = resourceGroup().location
param allowedSourcePrefix string = '10.0.0.0/24'

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-web'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowHTTPS'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          destinationPortRange: '443'
          sourceAddressPrefix: allowedSourcePrefix
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-app'
  location: location
  sku: { name: 'B1', tier: 'Basic' }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${uniqueString(resourceGroup().id)}'
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
