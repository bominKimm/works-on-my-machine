// bicep_transformer 출력 샘플 14: 이벤트 기반 (Function + Service Bus + Storage Queue + Logic App)
// RedTeam/Policy 검증용 - 메시지 큐, 트리거, 복잡한 연동

param location string = resourceGroup().location
param env string = 'prod'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stfunc${env}${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource sbNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: 'sb-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard', tier: 'Standard' }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    networkRuleSets: {
      defaultAction: 'Allow'
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource sbQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'orders-queue'
  properties: {
    maxDeliveryCount: 10
    lockDuration: 'PT5M'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-func-${env}'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  kind: 'functionapp'
}

resource funcApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'func-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      netFrameworkVersion: 'v6.0'
      ftpsState: 'AllAllowed'
      minTlsVersion: '1.0'
    }
  }
}

resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-${env}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {}
      actions: {}
    }
  }
}
