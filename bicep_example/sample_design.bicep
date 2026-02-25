// ============================================================
// 예시: 이미지에서 변환된 것처럼 가정한 "개발 설계" Bicep
// 의도적으로 사내 보안 정책 위반을 포함 (RAG 검토 데모용)
// ============================================================

param location string = resourceGroup().location
param environment string = 'prod'

// [위반 예시 1] NSG에서 sourceAddressPrefix '*' 사용
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-web'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowAllHTTPS'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// [위반 예시 2] 스토리지: HTTP 허용, TLS 미설정, Blob 공개 접근
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${environment}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: false
    allowBlobPublicAccess: true
  }
}

// [위반 예시 3] 웹앱: HTTPS 전용 미설정
resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${environment}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    siteConfig: {
      minTlsVersion: '1.0'
      ftpsState: 'AllAllowed'
    }
  }
}
