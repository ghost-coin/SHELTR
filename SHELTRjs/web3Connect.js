import {
  EthereumClient,
  w3mConnectors,
  w3mProvider,
  WagmiCore,
  WagmiCoreChains,
  WagmiCoreConnectors,
} from "https://unpkg.com/@web3modal/ethereum@2.7.1";

import { Web3Modal } from "https://unpkg.com/@web3modal/html@2.7.1";

// 0. Import wagmi dependencies
const { mainnet, polygon, avalanche, arbitrum, polygonMumbai } = WagmiCoreChains;
const { configureChains, createConfig, fetchBalance, getAccount, readContract, writeContract, fetchFeeData } = WagmiCore;

// 1. Define chains
const chains = [polygonMumbai];
const projectId = "fa49146b404b5e95b7f6237c331c03e8";

// 2. Configure wagmi client
const { publicClient } = configureChains(chains, [w3mProvider({ projectId })]);
const wagmiConfig = createConfig({
  autoConnect: true,
  connectors: [
    ...w3mConnectors({ chains, version: 2, projectId }),
  ],
  publicClient,
});

// 3. Create ethereum and modal clients
const ethereumClient = new EthereumClient(wagmiConfig, chains);
export const web3Modal = new Web3Modal(
  {
    projectId,
    themeMode: 'dark',
    themeVariables:{
    '--w3m-backdrop-image-url': "icons/to_the_moon.jpg",
    '--w3m-font-family': 'Roboto, sans-serif',
    '--w3m-accent-color': '#aeff00',
    '--w3m-accent-fill-color': '#171a1a',
    '--w3m-background-color': '#aeff00',

  },
  tokenContracts: {
    80001: '0x6e599da09133cAEeE5B7C123A61620d098E45C7b'
  },
  tokenImages: {
    WGhost: "/icons/wghost-32x32.png",
  },
  defaultChain: polygonMumbai,
  },
  ethereumClient
);

export const acct_info = getAccount;
export const fetchBalancePoly = fetchBalance;
export const read_rontract = readContract;
export const write_contract = writeContract;
export const fee_data = fetchFeeData;

window.fetchBalancePoly = fetchBalance;
window.acct_info = getAccount;
window.read_contract = readContract;
window.write_contract = writeContract;
window.fee_data = fetchFeeData;
