import {
  EthereumClient,
  w3mConnectors,
  w3mProvider,
  WagmiCore,
  WagmiCoreChains,
  WagmiCoreConnectors,
  WagmiCoreProviders,
} from "https://unpkg.com/@web3modal/ethereum@2.7.1";

import { Web3Modal } from "https://unpkg.com/@web3modal/html@2.7.1";

// 0. Import wagmi dependencies
const { mainnet, polygon, avalanche, arbitrum, polygonMumbai } =
  WagmiCoreChains;
const {
  configureChains,
  createConfig,
  fetchBalance,
  getAccount,
  readContract,
  writeContract,
  fetchFeeData,
  watchAccount,
  watchContractEvent,
} = WagmiCore;
const { jsonRpcProvider } = WagmiCoreProviders;

// 1. Define chains
const chains = [polygon];
const projectId = "fa49146b404b5e95b7f6237c331c03e8";

// 2. Configure wagmi client
const { publicClient } = configureChains(chains, [
  jsonRpcProvider({
    rpc: (chain) => ({
      http: `https://polygon.gateway.tenderly.co/public`,
    }),
  }),
]);
const wagmiConfig = createConfig({
  autoConnect: true,
  connectors: [...w3mConnectors({ chains, version: 2, projectId })],
  publicClient,
});

// 3. Create ethereum and modal clients
const ethereumClient = new EthereumClient(wagmiConfig, chains);
export const web3Modal = new Web3Modal(
  {
    projectId,
    themeMode: "dark",
    themeVariables: {
      "--w3m-font-family": "Roboto, sans-serif",
      "--w3m-accent-color": "#aeff00",
      "--w3m-accent-fill-color": "#171a1a",
      "--w3m-background-color": "#aeff00",
      "--w3m-overlay-backdrop-filter": "blur(3px)",
    },
    tokenContracts: {
      137: "0xb5e0CFe1B4dB501aC003B740665bf43192cC7853",
    },
    tokenImages: {
      WGhost: "/icons/wghost-32x32.png",
    },
    defaultChain: polygon,
    metadata: {
      name: "SHELTR",
      description: "Ghost Coin Wallet",
      url: "https://ghostbyjohnmcafee.com",
      icons: ["icons/android-chrome-192x192.png"],
    },
  },
  ethereumClient
);

export const acct_info = getAccount;
export const fetchBalancePoly = fetchBalance;
export const read_rontract = readContract;
export const write_contract = writeContract;
export const fee_data = fetchFeeData;
export const watch_account = watchAccount;
export const watch_contract_event = watchContractEvent;

window.fetchBalancePoly = fetchBalance;
window.acct_info = getAccount;
window.read_contract = readContract;
window.write_contract = writeContract;
window.fee_data = fetchFeeData;
window.watch_account = watchAccount;
window.watch_contract_event = watchContractEvent;
