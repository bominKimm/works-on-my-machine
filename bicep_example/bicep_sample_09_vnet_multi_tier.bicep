// bicep_transformer 출력 샘플 09: 3-tier VNet (Web/App/DB 서브넷) + NSG
// RedTeam/Policy 검증용 - 세그멘테이션은 있으나 NSG 규칙에 '*' 포함

param location string = resourceGroup().location
param environment string = 'prod'

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-${environment}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.0.0.0/16'] }
    subnets: [
      { name: 'subnet-web', properties: { addressPrefix: '10.0.1.0/24' } }
      { name: 'subnet-app', properties: { addressPrefix: '10.0.2.0/24' } }
      { name: 'subnet-db', properties: { addressPrefix: '10.0.3.0/24' } }
    ]
  }
}

resource nsgWeb 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-web-${environment}'
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
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource nsgApp 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-app-${environment}'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowFromWeb'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: '10.0.1.0/24'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource nsgDb 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-db-${environment}'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowSqlFromApp'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          destinationPortRange: '1433'
          sourceAddressPrefix: '10.0.2.0/24'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}
