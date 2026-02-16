// ============================================================
// Azure 3-Tier 웹 애플리케이션 아키텍처 샘플
// 의도적으로 보안 취약점을 포함하고 있습니다 (RedTeam 테스트용)
// ============================================================

@description('리소스 배포 위치')
param location string = resourceGroup().location

@description('환경 구분')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('관리자 사용자 이름')
param adminUsername string = 'azureuser'

@description('관리자 비밀번호')
@secure()
param adminPassword string

@description('SQL Server 관리자 비밀번호')
@secure()
param sqlAdminPassword string

// ============================================================
// 네트워크 리소스
// ============================================================

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-${environment}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'subnet-web'
        properties: {
          addressPrefix: '10.0.1.0/24'
        }
      }
      {
        name: 'subnet-app'
        properties: {
          addressPrefix: '10.0.2.0/24'
        }
      }
      {
        name: 'subnet-db'
        properties: {
          addressPrefix: '10.0.3.0/24'
        }
      }
    ]
  }
}

// [취약점] NSG 규칙에서 모든 소스 IP를 허용
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-web-${environment}'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowHTTP'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '80'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowHTTPS'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      // [취약점] SSH를 모든 IP에서 허용
      {
        name: 'AllowSSH'
        properties: {
          priority: 120
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      // [취약점] RDP를 모든 IP에서 허용
      {
        name: 'AllowRDP'
        properties: {
          priority: 130
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '3389'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// [취약점] 공용 IP 주소가 VM에 직접 연결
resource publicIP 'Microsoft.Network/publicIPAddresses@2023-05-01' = {
  name: 'pip-web-${environment}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    publicIPAllocationMethod: 'Dynamic'
  }
}

// ============================================================
// 컴퓨팅 리소스
// ============================================================

resource nic 'Microsoft.Network/networkInterfaces@2023-05-01' = {
  name: 'nic-web-${environment}'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: {
            id: publicIP.id
          }
          subnet: {
            id: vnet.properties.subnets[0].id
          }
        }
      }
    ]
    networkSecurityGroup: {
      id: nsg.id
    }
  }
}

resource webVM 'Microsoft.Compute/virtualMachines@2023-07-01' = {
  name: 'vm-web-${environment}'
  location: location
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_B2s'
    }
    osProfile: {
      computerName: 'webserver'
      adminUsername: adminUsername
      adminPassword: adminPassword
      // [취약점] 비밀번호 인증 사용 (SSH 키 미사용)
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Standard_LRS'
        }
        // [취약점] 디스크 암호화 미설정
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
}

// ============================================================
// 스토리지 리소스
// ============================================================

// [취약점] HTTPS 전용이 아님, TLS 최소 버전 미설정
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${environment}${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: false  // [취약점] HTTP 트래픽 허용
    allowBlobPublicAccess: true      // [취약점] Blob 공개 접근 허용
  }
}

// ============================================================
// 데이터베이스 리소스
// ============================================================

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: 'sql-${environment}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    // [취약점] Azure AD 인증 미설정
    version: '12.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: 'db-app-${environment}'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    // [취약점] TDE(Transparent Data Encryption) 명시적 설정 누락
    // [취약점] 감사(Auditing) 설정 누락
  }
}

// [취약점] SQL Server 방화벽에서 모든 Azure 서비스 및 외부 IP 허용
resource sqlFirewall 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAllAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

// ============================================================
// 웹 앱 (App Service)
// ============================================================

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-${environment}'
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${environment}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      // [취약점] HTTPS 전용 미설정
      // [취약점] 최소 TLS 버전 미설정
      ftpsState: 'AllAllowed'  // [취약점] FTP 허용
      http20Enabled: false
    }
    // [취약점] httpsOnly 미설정
  }
}

// ============================================================
// Key Vault
// ============================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${environment}-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    accessPolicies: []
    // [취약점] 소프트 삭제 미설정 (최신 API에서는 기본 활성)
    // [취약점] 퍼지 보호 미설정
    enableSoftDelete: false
    enablePurgeProtection: false
    networkAcls: {
      defaultAction: 'Allow'  // [취약점] 모든 네트워크에서 접근 허용
      bypass: 'AzureServices'
    }
  }
}

// ============================================================
// 출력
// ============================================================

output vmPublicIP string = publicIP.properties.ipAddress
output storageAccountName string = storageAccount.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output keyVaultUri string = keyVault.properties.vaultUri
