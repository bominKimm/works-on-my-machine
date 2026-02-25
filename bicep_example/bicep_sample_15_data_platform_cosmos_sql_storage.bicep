// bicep_transformer 출력 샘플 15: 데이터 플랫폼 (Cosmos DB + SQL + Storage + Key Vault)
// RedTeam/Policy 검증용 - 다중 데이터 저장소, 키 관리, 방화벽·네트워크 혼재

@secure()
param sqlPassword string

param location string = resourceGroup().location
param projectCode string = 'dp01'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${projectCode}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableSoftDelete: true
    enablePurgeProtection: false
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
    accessPolicies: []
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${projectCode}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    isHnsEnabled: true
  }
}

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: 'sql-${projectCode}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlPassword
    version: '12.0'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: 'db-analytics'
  location: location
  sku: { name: 'S0', tier: 'Standard' }
}

resource sqlFw 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAllAzure'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: 'cosmos-${projectCode}-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      { locationName: location, failoverPriority: 0 }
    ]
    publicNetworkAccess: 'Enabled'
    disableKeyBasedMetadataWriteAccess: false
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmos
  name: 'telemetry-db'
  properties: {
    resource: { id: 'telemetry' }
  }
}
