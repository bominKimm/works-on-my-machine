// bicep_transformer 출력 샘플 06: VM + 공용 IP + RDP 개방
// RedTeam/Policy 검증용 - Linux/Windows VM, 공개 접근

@secure()
param adminPassword string

param location string = resourceGroup().location
param vmName string = 'vm-web-01'

resource publicIP 'Microsoft.Network/publicIPAddresses@2023-05-01' = {
  name: 'pip-${vmName}'
  location: location
  sku: { name: 'Basic' }
  properties: { publicIPAllocationMethod: 'Static' }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-main'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.0.0.0/16'] }
    subnets: [{ name: 'default', properties: { addressPrefix: '10.0.0.0/24' } }]
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2023-05-01' = {
  name: 'nic-${vmName}'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: { id: publicIP.id }
          subnet: { id: vnet.properties.subnets[0].id }
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2023-07-01' = {
  name: vmName
  location: location
  properties: {
    hardwareProfile: { vmSize: 'Standard_B2s' }
    osProfile: {
      computerName: 'webvm'
      adminUsername: 'azureuser'
      adminPassword: adminPassword
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
        managedDisk: { storageAccountType: 'Standard_LRS' }
      }
    }
    networkProfile: {
      networkInterfaces: [{ id: nic.id }]
    }
  }
}
