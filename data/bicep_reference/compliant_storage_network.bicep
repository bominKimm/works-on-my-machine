// ============================================================
// 정책 준수 참조 Bicep 예시
// - HTTPS 전용, TLS 1.2, NSG 소스 제한, 스토리지 암호화 등
// ============================================================

@description('리소스 배포 위치')
param location string = resourceGroup().location

@description('허용할 관리용 IP 대역 (정책: 특정 IP로 제한)')
param allowedSourcePrefix string = '10.0.0.0/24'

// 네트워크: NSG에 특정 소스만 허용 (정책: sourceAddressPrefix '*' 금지)
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-compliant'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowHTTPSFromRestricted'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: allowedSourcePrefix
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// 스토리지: HTTPS 전용 + TLS 1.2 (정책: 전송 암호화, TLS 1.2 이상)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stcompliant${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// App Service Plan (웹앱 부모 리소스)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-compliant'
  location: location
  sku: { name: 'B1', tier: 'Basic' }
}

// 웹 앱: HTTPS 전용 + 최소 TLS (정책: HTTPS 의무, TLS 1.2 이상)
resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-compliant-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      httpsOnly: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
    }
  }
}
