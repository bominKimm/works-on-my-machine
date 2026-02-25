// bicep_transformer 출력 샘플 13: Front Door + 다중 Web App + Storage + SQL (복합 웹/API 구조)
// RedTeam/Policy 검증용 - CDN/라우팅, 여러 백엔드, DB·스토리지 혼재

@secure()
param sqlAdminPassword string

param location string = resourceGroup().location
param env string = 'prod'

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-web-${env}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.3.0.0/16'] }
    subnets: [
      { name: 'subnet-web', properties: { addressPrefix: '10.3.1.0/24' } }
      { name: 'subnet-sql', properties: { addressPrefix: '10.3.2.0/24' } }
    ]
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stweb${env}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: false
    allowBlobPublicAccess: true
    minimumTlsVersion: 'TLS1_0'
  }
}

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: 'sql-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    version: '12.0'
  }
}

resource sqlFirewall 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAzure'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-web-${env}'
  location: location
  sku: { name: 'P1v2', tier: 'P1v2' }
}

resource webMain 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-web-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      httpsOnly: false
      minTlsVersion: '1.0'
      ftpsState: 'AllAllowed'
    }
  }
}

resource webApi 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-api-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      httpsOnly: true
      minTlsVersion: '1.2'
    }
  }
}

resource frontdoor 'Microsoft.Cdn/profiles@2023-05-01' = {
  name: 'fd-${env}-${uniqueString(resourceGroup().id)}'
  location: 'global'
  sku: { name: 'Standard_Microsoft' }
  properties: {
    originResponseTimeoutSeconds: 60
  }
}

resource fdEndpoint 'Microsoft.Cdn/profiles/afdEndpoints@2023-05-01' = {
  parent: frontdoor
  name: 'default'
  location: 'global'
}
