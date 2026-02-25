// bicep_transformer 출력 샘플 04: SQL Server + 방화벽 전체 개방
// RedTeam/Policy 검증용 - 0.0.0.0 ~ 255.255.255.255 허용

@secure()
param sqlAdminPassword string

param location string = resourceGroup().location
param environment string = 'prod'

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: 'sql-${environment}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    version: '12.0'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: 'db-main'
  location: location
  sku: { name: 'Basic', tier: 'Basic' }
}

resource sqlFirewall 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAll'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}
