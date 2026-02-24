// bicep_transformer 출력 샘플 12: Storage Private Endpoint + Key Vault + VNet (사내 보안 정책 시뮬)
// RedTeam/Policy 검증용 - Storage 퍼블릭 차단, Private Endpoint, KV 참조, 일부 설정 누락

param location string = resourceGroup().location
param projectName string = 'dataplatform'
param allowedVnetPrefix string = '10.2.0.0/16'

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-${projectName}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: [allowedVnetPrefix] }
    subnets: [
      { name: 'subnet-app', properties: { addressPrefix: '10.2.1.0/24' } }
      { name: 'subnet-pe', properties: { addressPrefix: '10.2.2.0/24', privateEndpointNetworkPolicies: 'Disabled' } }
    ]
  }
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${projectName}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableSoftDelete: true
    enablePurgeProtection: true
    networkAcls: { defaultAction: 'Deny', bypass: 'AzureServices' }
    accessPolicies: []
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${projectName}${uniqueString(resourceGroup().id)}'
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
      ipRules: []
      virtualNetworkRules: []
    }
  }
}

resource storagePe 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: 'pe-storage-${projectName}'
  location: location
  properties: {
    subnet: { id: '${resourceId(resourceGroup().name, 'Microsoft.Network/virtualNetworks', vnet.name)}/subnets/subnet-pe' }
    privateLinkServiceConnections: [
      {
        name: 'pls-storage'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: ['blob']
        }
      }
    ]
  }
}

resource blobDns 'Microsoft.Network/privateDnsZones@2023-05-01' = {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
}

resource blobDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2023-05-01' = {
  parent: blobDns
  name: 'link-${projectName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}
