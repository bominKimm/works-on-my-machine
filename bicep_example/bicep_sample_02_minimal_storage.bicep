// bicep_transformer 출력 샘플 02: 스토리지 단일 리소스 (최소 구성)
// RedTeam/Policy 검증용 - 스토리지만 있는 단순 설계

param location string = resourceGroup().location

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: false
    allowBlobPublicAccess: true
  }
}
