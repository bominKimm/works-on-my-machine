// bicep_transformer 출력 샘플 11: API Management + 백엔드 App Service + Storage (복잡한 API 구조)
// RedTeam/Policy 검증용 - API 게이트웨이, 다중 백엔드, VNet 내부/외부 혼재

param location string = resourceGroup().location
param environment string = 'prod'
param apimPublisherEmail string = 'api@company.com'

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-apim-${environment}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.1.0.0/16'] }
    subnets: [
      { name: 'subnet-apim', properties: { addressPrefix: '10.1.0.0/24' } }
      { name: 'subnet-backend', properties: { addressPrefix: '10.1.1.0/24' } }
    ]
  }
}

resource nsgBackend 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-backend-${environment}'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowFromApim'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: '10.1.0.0/24'
          destinationPortRange: '443'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowManagement'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: '*'
          destinationPortRange: '3443'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stapi${environment}${uniqueString(resourceGroup().id)}'
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
    }
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-api-${environment}'
  location: location
  sku: { name: 'P1v2', tier: 'P1v2' }
}

resource apiApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-api-${environment}-${uniqueString(resourceGroup().id)}'
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

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: 'apim-${environment}-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Developer', capacity: 1 }
  properties: {
    publisherEmail: apimPublisherEmail
    publisherName: 'Contoso'
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'false'
    }
  }
}
