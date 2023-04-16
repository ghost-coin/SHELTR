import asyncio  # important!!
import json
from SHELTRpy.request import request  # import our request function.
import time
from binascii import unhexlify
import random

from js import storeData, getData, getAddrFromXpub, estimateFee, getPrivKeyFromXpriv, isValidAddr256, getPubKeyFromXpub, estimateFeeScript

from SHELTRpy.ghostCrypto import password_decrypt, password_encrypt


from pyodide.ffi import to_js
import js, pyodide

from pyscript import Element

GAP_LIMIT = 20


class TransactionHistory:
    def __init__(self, wallet):
        self.walletCls = wallet
        self.wallet = wallet.wallet
        self.token = wallet.token
        self.api = self.walletCls.api
        self.util = Util(self.wallet, self.api)
        self.currentTab = "overview-container"
        self.currentButton = "overview-button"

        self.settingsExpanded = {"menu-tab-item-address": False,
                                "menu-tab-item-coldstake": False,
                                "menu-tab-item-agvr": False,
                                "menu-tab-item-fiat": False,
                                "menu-tab-item-explorer": False,
                                "menu-tab-item-lang": False}

        self.txHistory = []
        self.knownTXID = []
        self.unconfirmedTx = []
        self.unmatureUTXO = []
        self.currentVet = []
        self.pendingVet = []
        self.pendingTxOut = None
        self.showMessage = False
        self.showTxInfo = ''

        self.txHistoryTopIndex = 0
        self.txHistoryTotalItems = 0

        with open("list.json") as f:
            self.poolList = json.loads(f.read())

    async def setExpanded(self, setting, isExpanded):
        self.settingsExpanded[setting] = isExpanded

    async def processTxHistory(self, startIdx=0, endIdx=50, collectAll=False, advanceTopIndex=False):
        currentAddrs = self.wallet.receiving_addresses + self.wallet.receiving_addresses_256 + self.wallet.change_addresses

        addrStr = ""
        for addr in currentAddrs:
            addrStr += f",{addr}"
        addrStr = addrStr[1:]

        addrHistory = await self.api.getTxByAddrPost(addrStr, startIdx, endIdx)

        self.txHistoryTotalItems = addrHistory['totalItems']

        if addrHistory['totalItems'] == len(self.txHistory):
            return

        continueLoop = True
        while continueLoop:
            if not self.txHistoryTopIndex or advanceTopIndex or collectAll:
                self.txHistoryTopIndex = addrHistory['to']

            addrHistoryLst = addrHistory['items']
            for tx in addrHistoryLst:
                if tx['txid'] in self.knownTXID:
                    continueLoop = False
                    break
                await self.parseTx(tx)
            if collectAll:
                if addrHistory['to'] < addrHistory['totalItems']:
                    if (addrHistory['totalItems'] - addrHistory['to']) < 50:
                        addrHistory = await self.api.getTxByAddrPost(addrStr, startIdx=addrHistory['to'],
                                                                    endIdx=addrHistory['totalItems'])
                    else:
                        addrHistory = await self.api.getTxByAddrPost(addrStr, startIdx=addrHistory['to'],
                                                                    endIdx=addrHistory['to']+50)
                else:
                    continueLoop = False
            else:
                continueLoop = False

    async def processNetworkTx(self, txid, ignoreExisting=False):

        if not txid:
            return None

        rawTx = await self.api.getTx(txid)
        
        if rawTx == "Not found":
            return None

        txDetails = await self.parseTx(rawTx, ignoreExisting=ignoreExisting)

        if not ignoreExisting:
            self.txHistoryTotalItems += 1 
            self.txHistoryTopIndex = len(self.txHistory)
        return txDetails

    
    async def parseTx(self, tx, ignoreExisting=False):
        currentAddrs = self.wallet.receiving_addresses + self.wallet.receiving_addresses_256 + self.wallet.change_addresses
        
        if tx['txid'] in self.knownTXID and not ignoreExisting:
            return None

        isStake = tx['isCoinStake'] if "isCoinStake" in tx else False
        isAGVR = tx['isAGVR'] if isStake else False
        hasOwnedCsOut = 0
        hasExternalOut = False
        hasScriptSendIn = False
        isPoolReward = False

        inAddr = {}
        outAddr = {}

        ownedInput = 0
        ownedOutput = 0

        for index, vin in enumerate(tx['vin']):

            if vin['addr']:
                if vin['addr'] in inAddr:
                    inAddr[vin['addr']] += int(vin['valueSat'])
                else:
                    inAddr[vin['addr']] = int(vin['valueSat'])
                
                if vin['addr'] in currentAddrs:
                    ownedInput += int(vin['valueSat'])
                    
                    if vin['addr'] not in self.wallet.used_addresses:
                        self.wallet.used_addresses.append(vin['addr'])
                else:
                    hasExternalIn = True
                    if vin['sequence'] == 4294967294:
                        hasScriptSendIn = True
            elif vin["type"] == "anon":
                inAddr[f"ANON-{index}"] = 0
        
        for vout in tx['vout']:
            if vout["type"] == "anon":
                outAddr[f"ANON-{vout['n']}"] = 0
            elif vout["type"] == "data":
                outAddr[f"DATA-{vout['n']}"] = 0
            
            elif "addresses" in vout['scriptPubKey']:
                if vout['scriptPubKey']['addresses'][0] in outAddr:
                    outAddr[vout['scriptPubKey']['addresses'][0]] += self.util.convertToSat(float(vout['value']))
                else:
                    outAddr[vout['scriptPubKey']['addresses'][0]] = self.util.convertToSat(float(vout['value']))
                
                if vout['scriptPubKey']['addresses'][0] in currentAddrs:
                    ownedOutput += self.util.convertToSat(float(vout['value']))
                    
                    if vout['scriptPubKey']['addresses'][0] in self.wallet.receiving_addresses_256:
                        if self.walletCls.isCsOut(vout['scriptPubKey']['hex']):
                            hasOwnedCsOut += 1
                        if len(vout) > 2 and hasScriptSendIn:
                            isPoolReward = True
                    if vout['scriptPubKey']['addresses'][0] not in self.wallet.used_addresses:
                        self.wallet.used_addresses.append(vout['scriptPubKey']['addresses'][0])
                else:
                    hasExternalOut = True
            
        
        transactedValue = round(self.util.convertFromSat(ownedOutput - ownedInput), 8)

        txType = ""
        if isStake:
            if tx['confirmations'] <= 100:
                self.unmatureUTXO.append(tx['txid'])
            if isAGVR:
                txType = "agvr"
            else:
                txType = "stake"
        elif isPoolReward:
            txType = "pool reward"
        elif ownedInput and not ownedOutput:
            txType = "outgoing"
        elif not ownedInput and ownedOutput:
            txType = 'incoming'
        elif ownedInput and ownedOutput:
            if (transactedValue < 0) and hasExternalOut:
                txType = 'outgoing'
            else:
                if len(tx['vout']) == hasOwnedCsOut:
                    txType = 'zap'
                else:
                    txType = 'internal'

        txDetails = {
            "txid": tx['txid'],
            "txValue": transactedValue,
            "time": tx['time'] if 'time' in tx else int(time.time()),
            "blockHeight": tx['height'] if 'height' in tx else int(time.time()),
            "txType": txType,
            "confirmations": tx['confirmations'] if 'confirmations' in tx else 0,
            "inAddr": inAddr,
            "outAddr": outAddr
        }
        
        
        if tx['txid'] not in self.knownTXID:
            self.knownTXID.append(tx['txid'])

            if txDetails not in self.txHistory:
                self.txHistory.append(txDetails)

            if txDetails['confirmations'] < 12:
                self.unconfirmedTx.append(txDetails)
        
        return txDetails


    async def getTxByTXID(self, txid):
        for tx in self.txHistory:
            if tx['txid'] == txid:
                return tx

    
    async def getNewAddr(self, addrType):
        index = 0
            
        if addrType == 256:
            qr_display_index = self.wallet.qr_256_addr
            if qr_display_index != None:
                index = qr_display_index + 1

            if not index <= len(self.wallet.receiving_addresses_256) - 1:
                transLst = self.wallet.lookahead_addresses_256
                self.wallet.receiving_addresses_256 += transLst[:1]
                self.wallet.lookahead_addresses_256 = transLst[1:]

                self.wallet.lookahead_addresses_256 += await self.util.getAddresses(len(self.wallet.lookahead_addresses_256) + len(self.wallet.receiving_addresses_256),
                                                                        (len(self.wallet.lookahead_addresses_256) + len(self.wallet.receiving_addresses_256)+1), is256=True)
            self.wallet.qr_256_addr = index
            new_addr = self.wallet.receiving_addresses_256[index]
            
        else:
            qr_display_index = self.wallet.qr_standard_addr
            if qr_display_index != None:
                index = qr_display_index + 1

            if index > len(self.wallet.receiving_addresses) - 1:
                transLst = self.wallet.lookahead_addresses
                self.wallet.receiving_addresses += transLst[:1]
                self.wallet.lookahead_addresses = transLst[1:]

                self.wallet.lookahead_addresses += await self.util.getAddresses(len(self.wallet.master_address_list), len(self.wallet.master_address_list)+1)
            self.wallet.qr_standard_addr = index
            new_addr = self.wallet.receiving_addresses[index]

        await self.walletCls.flushWallet()
        return new_addr


    async def task_runner(self):
        await self.util.checkGap()
        await self.walletCls.flushWallet()


class TransactionInputs:
    def __init__(self, txHistory, amount, spendColdStake=False, isZap=False, script=None):
        self.wallet = txHistory.wallet
        self.walletCls = txHistory.walletCls

        self.fee = None
        self.spendColdStake = spendColdStake
        self.isZap = isZap
        self.script = script
        self.inputs = []
        self.inputsValue = 0
        self.util = txHistory.util
        self.api = txHistory.api
        self.amount = int(self.util.convertToSat(amount))
        self.unmatureUTXO = txHistory.unmatureUTXO

        self.coinChooser()

    def coinChooser(self):
        utxo = self.wallet.utxo.copy()
        random.shuffle(utxo)
        utxoValue = 0
        testAddr = self.wallet.receiving_addresses[0]

        if not self.fee:
            for txOut in utxo:
                if not txOut['confirmations']:
                    continue

                if self.walletCls.isCsOut(txOut['script']):
                    if not self.spendColdStake:
                        continue
                
                if txOut['txid'] in self.unmatureUTXO and txOut['confirmations'] <= 100:
                    continue

                self.inputs.append(txOut)
                utxoValue += txOut['satoshis']

                if utxoValue >= self.amount:
                    break
            if not self.isZap:
                    
                estFee = estimateFee(to_js(self.inputs, dict_converter=js.Object.fromEntries),
                                    testAddr, testAddr, utxoValue) / 2
            else:
                outScript = self.util.splitCsOutputs(self.amount, self.script)

                estFee = estimateFeeScript(to_js(self.inputs, dict_converter=js.Object.fromEntries),
                                    testAddr, to_js(outScript)) / 2
            self.fee = estFee

        if utxoValue < self.fee + self.amount:
            for txOut in utxo:
                if txOut in self.inputs:
                    continue
                if not txOut['confirmations']:
                    continue

                if self.walletCls.isCsOut(txOut['script']):
                    if not self.spendColdStake:
                        continue

                if txOut['txid'] in self.unmatureUTXO and txOut['confirmations'] <= 100:
                    continue

                self.inputs.append(txOut)
                utxoValue += txOut['satoshis']

                if utxoValue >= self.amount + estFee:
                    break

        self.inputsValue = utxoValue


    async def getMax(self):

        testAddr = self.wallet.receiving_addresses[0]
        utxoValue = 0
        utxo = self.wallet.utxo
        max_utxo = []

        if not utxo:
            return 0
        

        for txOut in utxo:
            if not txOut['confirmations']:
                continue

            if self.walletCls.isCsOut(txOut['script']):
                if not self.spendColdStake:
                    continue

            if txOut['txid'] in self.unmatureUTXO and txOut['confirmations'] <= 100:
                    continue

            utxoValue += txOut['satoshis']
            max_utxo.append(txOut)

        estFee = estimateFee(to_js(max_utxo, dict_converter=js.Object.fromEntries), testAddr, testAddr, utxoValue) / 2

        self.fee = estFee

        return utxoValue - estFee

    def getPrivateKeys(self, password):
        privKeys = []

        if not password:
            return privKeys

        extPrivKey = password_decrypt(self.wallet.xpriv[2:-1], password).decode("utf-8")
        extPrivKeyChange = password_decrypt(self.wallet.xpriv_change[2:-1], password).decode("utf-8")

        for txOut in self.inputs:
            addrIndex = self.util.getIndexByAddress(txOut['address'])
            
            if self.util.isChangeAddr(txOut['address']):
                privKey = getPrivKeyFromXpriv(extPrivKeyChange, addrIndex)
            else:
                privKey = getPrivKeyFromXpriv(extPrivKey, addrIndex)

            if privKey not in privKeys:
                privKeys.append(privKey)

        return privKeys

    async def sendTx(self, rawTx):
        txid = await self.api.sendTx(rawTx)
        return txid


class Util:
    def __init__(self, wallet, api):
        self.wallet = wallet
        self.api = api

    async def lookAheadHasTX(self, is256, isChange):
        if isChange:
            futureAddrs = self.wallet.change_lookahead_addresses
        else:
            if is256:
                futureAddrs = self.wallet.lookahead_addresses_256
            else:
                futureAddrs = self.wallet.lookahead_addresses

        if futureAddrs == []:
            return {}
        addrStr = ""

        for addr in futureAddrs:
            addrStr += f",{addr}"
        addrStr = addrStr[1:]

        txs = await self.api.getTxByAddrPost(addrStr, 0, 50)

        if txs['items']:
            return txs
        else:
            return {}

    async def checkGap(self):
        truth_or_dare = [True, False, "change"]
        isChange = False
        message = Element("loading-message")
        message.element.innerText = "Checking for new addresses..."
        new_address_found = 0
        
        for truthieness in truth_or_dare:
            if truthieness == "change":
                isChange = True
                is256 = False
            else:
                is256 = truthieness

            while (lookAheadUTXO := await self.lookAheadHasTX(is256, isChange)) != {}:
                topIndex = 0

                for tx in lookAheadUTXO['items']:
                    for txout in tx['vout']:
                        if "type" in txout and txout['type'] in ['blind', 'data', 'anon']:
                            continue
                        if "addresses" in txout['scriptPubKey']:
                            addr = txout['scriptPubKey']['addresses'][0]

                            if isChange:
                                if addr in self.wallet.change_lookahead_addresses:
                                    addrIdx = self.wallet.change_lookahead_addresses.index(addr)
                                    
                                    if addr not in self.wallet.used_addresses:
                                        new_address_found += 1
                                        message.element.innerText = f"{new_address_found} new addresses found..."
                                        self.wallet.used_addresses.append(addr)

                                    if addrIdx > topIndex:
                                        topIndex = addrIdx

                                if addr in self.wallet.change_addresses:
                                    if addr not in self.wallet.used_addresses:
                                        new_address_found += 1
                                        message.element.innerText = f"{new_address_found} new addresses found..."
                                        self.wallet.used_addresses.append(addr)
                            else:
                                if is256:
                                    if addr in self.wallet.lookahead_addresses_256:
                                        addrIdx = self.wallet.lookahead_addresses_256.index(addr)
                                        
                                        if addr not in self.wallet.used_addresses:
                                            new_address_found += 1
                                            message.element.innerText = f"{new_address_found} new addresses found..."
                                            self.wallet.used_addresses.append(addr)
                                            
                                        if addrIdx > topIndex:
                                            topIndex = addrIdx

                                    if addr in self.wallet.receiving_addresses_256:
                                        if addr not in self.wallet.used_addresses:
                                            new_address_found += 1
                                            message.element.innerText = f"{new_address_found} new addresses found..."
                                            self.wallet.used_addresses.append(addr)
                                else:
                                    if addr in self.wallet.lookahead_addresses:
                                        addrIdx = self.wallet.lookahead_addresses.index(addr)
                                        
                                        if addr not in self.wallet.used_addresses:
                                            new_address_found += 1
                                            message.element.innerText = f"{new_address_found} new addresses found..."
                                            self.wallet.used_addresses.append(addr)

                                        if addrIdx > topIndex:
                                            topIndex = addrIdx

                                    if addr in self.wallet.receiving_addresses:
                                        if addr not in self.wallet.used_addresses:
                                            new_address_found += 1
                                            message.element.innerText = f"{new_address_found} new addresses found..."
                                            self.wallet.used_addresses.append(addr)
                            

                if isChange:
                    transLst = self.wallet.change_lookahead_addresses
                    self.wallet.change_addresses += transLst[:topIndex+1]
                    self.wallet.change_lookahead_addresses = transLst[topIndex+1:]

                    if len(self.wallet.change_lookahead_addresses) < GAP_LIMIT:
                        diffAmt = GAP_LIMIT - len(self.wallet.change_lookahead_addresses)
                        self.wallet.change_lookahead_addresses += await self.getAddresses(len(self.wallet.change_master_address_list),
                                                                                (len(self.wallet.change_master_address_list) + diffAmt), isChange=True)

                else:

                    if is256:
                        transLst = self.wallet.lookahead_addresses_256
                        self.wallet.receiving_addresses_256 += transLst[:topIndex+1]
                        self.wallet.lookahead_addresses_256 = transLst[topIndex+1:]

                        if len(self.wallet.lookahead_addresses_256) < GAP_LIMIT:
                            diffAmt = GAP_LIMIT - len(self.wallet.lookahead_addresses_256)
                            self.wallet.lookahead_addresses_256 += await self.getAddresses(len(self.wallet.lookahead_addresses_256 + self.wallet.receiving_addresses_256),
                                                                                    (len(self.wallet.lookahead_addresses_256 + self.wallet.receiving_addresses_256) + diffAmt), is256)
                    
                    else:
                        transLst = self.wallet.lookahead_addresses
                        self.wallet.receiving_addresses += transLst[:topIndex+1]
                        self.wallet.lookahead_addresses = transLst[topIndex+1:]

                        if len(self.wallet.lookahead_addresses) < GAP_LIMIT:
                            diffAmt = GAP_LIMIT - len(self.wallet.lookahead_addresses)
                            self.wallet.lookahead_addresses += await self.getAddresses(len(self.wallet.master_address_list),
                                                                                    (len(self.wallet.master_address_list) + diffAmt))
            
        message.element.innerText = f"{new_address_found} total new addresses found."

    async def getAddresses(self, startIdx, endIdx, is256=False, isChange=False):
        addresses = []
        for index in range(startIdx, endIdx):
            if not isChange:
                addr = getAddrFromXpub(str(self.wallet.xpub), index, is256)
            else:
                addr = getAddrFromXpub(str(self.wallet.xpub_change), index, is256)

            addresses.append(str(addr))
            if not is256 and not isChange:
                self.wallet.master_address_list.append(str(addr))
            elif isChange:
                self.wallet.change_master_address_list.append(str(addr))
        return addresses

    def isChangeAddr(self, addr):
        if addr in self.wallet.change_master_address_list:
            return True
        else:
            return False

    def convertFromSat(self, value):
        sat_readable = value / 10**8
        return sat_readable

    def convertToSat(self, value):
        sat_readable = value * 10**8
        return round(sat_readable)

    def getIndexByAddress(self, addr):
        if isValidAddr256(addr):
            return self.wallet.receiving_addresses_256.index(addr)
        else:
            if self.isChangeAddr(addr):
                return self.wallet.change_addresses.index(addr)
            else:
                return self.wallet.receiving_addresses.index(addr)


    def splitCsOutputs(self, amount, stakeScript):
        outScript = []
        zapAmount = amount
        outSize = 150000000000
        
        while zapAmount:
            if zapAmount >= outSize:
                outScript.append([stakeScript, outSize])
                zapAmount -= outSize
            else:
                outScript.append([stakeScript, zapAmount])
                break

        return outScript

