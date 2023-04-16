import asyncio  # important!!
import json
from SHELTRpy.request import request  # import our request function.
import time
from js import (getMnemonic, storeData, getData, generateTx, getAddrFromXpub, isValidMnemonic,
importMnemonic, txMonitor, browserType, validateAddress, getOS, generateTxScript, buildColdstakeScript,
getCsAddrInfo, handleTouchStart, handleTouchMove, isValidURI, decodeURI, isDupe, idleTimer, screenHideEvent,
disconnectSocket, scanQRCode, stopScanner, txMonitorAnon, signMessage)

from SHELTRpy.ghostCrypto import password_decrypt, password_encrypt, getToken

from SHELTRpy.wallet import ImportWallet, Wallet
from SHELTRpy.insight_api import Api


from SHELTRpy.transaction import TransactionHistory, TransactionInputs
from datetime import datetime

from pyodide.ffi import to_js
import js, pyodide
import re, math, random

import SHELTRpy.ecc

VERSION = "v0.2b"

api = Api()

displayedTXID = []
displayedUsedAddr = []

def runMnemonic():
    global mnemonic
    mnemonic = getMnemonic()

    for index, word in enumerate(mnemonic.words.split()):
        newWords = Element(f"words{index}")
        newWords.write(word)
    Element("continue-words").element.disabled = False


def copyWords():
    js.navigator.clipboard.writeText(mnemonic.words)


async def startScanner():
    zap_button = Element("send-tab-zap-button")
    zap_button.element.disabled = True
    send_button = Element("send-tab-send-button")
    send_button.element.disabled = True

    Element("message-box").element.innerHTML = f'''
                                               <div style="height:100%;width:100%;" class="camera-stream" id="camera-stream"></div>
                                               <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                                               '''
    scanQRCode()
    await showMessageBox(isScanner=True)


async def parseScanner(addr):
    # scan qr code
    addr_input = Element("send-tab-input")
    amount_input = Element("send-tab-amount")

    if validateAddress(addr):
        addr_input.element.value = addr
        await closeMessageBox()
    elif isValidURI(addr):
        uri = decodeURI(addr)
        addr_input.element.value = uri.address
        if uri.amount:
            amount_input.element.value = txHistory.util.convertFromSat(uri.amount)
        await closeMessageBox()
    else:
        Element("message-box").element.innerHTML = f'''
                                               <div>Not A valid Ghost address or URI.</div>
                                               <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                                               '''
        stopScanner()
        await asyncio.sleep(3)

        Element("message-box").element.innerHTML = f'''
                                               <div style="height:100%;width:100%;" id="camera-stream"></div>
                                               <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                                               '''
        scanQRCode()


async def pasteAddr():
    # paste from os
    addr_input = Element("send-tab-input")
    amount_input = Element("send-tab-amount")
    addr = addr_input.element.value.strip()
    addr_input.clear()

    if validateAddress(addr):
        addr_input.element.value = addr
    elif isValidURI(addr):
        uri = decodeURI(addr)
        addr_input.element.value = uri.address
        if uri.amount:
            amount_input.element.value = txHistory.util.convertFromSat(uri.amount)
    else:
        addr_input.element.style.borderColor = "#ff4d4d"
        await shakeIt(addr_input)
        addr_input.element.style.borderColor = "#aeff00" 


def check_password_strength(password):

    '''
    Check the strength of the password entered by the user and return back the same
    :param password: password entered by user in New Password
    :return: password strength Weak or Medium or Strong
    '''
    password = password
    n = math.log(len(set(password)))
    num = re.search("[0-9]", password) is not None and re.match("^[0-9]*$", password) is None
    caps = password != password.upper() and password != password.lower()
    extra = re.match("^[a-zA-Z0-9]*$", password) is None
    score = len(password)*(n + caps + num + extra)/20
    password_strength = {0:"Weak",1:"Medium",2:"Strong",3:"Very Strong"}
    return min(3, int(score))


def add_password_event(e):
    password_strength = {0:"Weak",1:"Medium",2:"Strong",3:"Very Strong"}
    if password_input.element.value == "":
        Element("password-strength-meter").element.value = str(0)
        Element("meter-text").element.innerHTML = ""
    else:
        strength = check_password_strength(password_input.element.value)
        Element("password-strength-meter").element.value = str(strength+1)
        Element("meter-text").element.innerHTML = password_strength[int(strength)]

    if confirm_password_input.element.value == "":
        Element("new-pass-confirm").element.style.background = ""
        Element("new-pass-button").element.disabled = True
    elif confirm_password_input.element.value == password_input.element.value:
        Element("new-pass-confirm").element.style.background = "#aeff00"
        Element("new-pass-button").element.disabled = False
    else:
        Element("new-pass-button").element.disabled = True
        Element("new-pass-confirm").element.style.background = ""


def check_words_event(e):
    words = import_word_text.element.value.strip()

    try:
        if isValidMnemonic(words.lower()):
            Element("import-word-button").element.disabled = False
        else:
            Element("import-word-button").element.disabled = True
    except:
        Element("import-word-button").element.disabled = True


async def importWords():
    global mnemonic
    Element("import-word-box").element.style.display = "none"
    Element("loading").element.style.display = "block"

    loading_message.element.innerText = "Generating master keys..."  
    await asyncio.sleep(0.1)
    
    words = import_word_text.element.value.strip()
    mnemonic = importMnemonic(words.lower())
    Element("loading").element.style.display = "none"
    Element("set-password").element.style.display = "block"
    await asyncio.sleep(0.1)
    import_word_text.clear()


async def getMax():
    if txHistory.showMessage:
        return
    if not txHistory.wallet.utxo:
        return
    maxAmount = await TransactionInputs(txHistory, 0, spendColdStake=spendCSOut).getMax()

    if maxAmount >= MIN_TX:
        Element("send-tab-amount").element.value = txHistory.util.convertFromSat(maxAmount)



async def doZap():
    zap_button = Element("send-tab-zap-button")
    zap_button.element.disabled = True
    send_button = Element("send-tab-send-button")
    send_button.element.disabled = True

    password_input = Element("send-tab-password")

    csInfo = txHistory.wallet.coldstaking

    if not csInfo['isActive']:
        zap_button.element.disabled = False
        send_button.element.disabled = False
        return

    if not (password := password_input.element.value) or not await isValidPass(password):
        js.console.log("Invalid Password")
        password_input.element.style.borderColor = "#ff4d4d"
        
        await shakeIt(password_input)
        
        zap_button.element.disabled = False
        send_button.element.disabled = False
        return
    else:
        password_input.element.style.borderColor = "#aeff00"
        password_input.clear()
    
    Element("message-box").element.innerHTML = f'''<h3>{locale['processing-transaction']}</h3><p>{locale['pool']}:</p><p class="message-box-secondary"></p><p>{locale['send-tab-amount']}:</p><p class="message-box-secondary"></p>
                                                <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['cancel']}</button>'''
    await showMessageBox()
    
    maxAmount = txHistory.util.convertFromSat(await TransactionInputs(txHistory, 0, spendColdStake=spendCSOut).getMax())

    if txHistory.util.convertToSat(maxAmount) <= MIN_TX:
        await closeMessageBox()
        amount_input = Element("send-tab-amount")
        js.console.log("Invalid Amount")
        amount_input.element.style.borderColor = "#ff4d4d"
        
        await shakeIt(amount_input)
        
        zap_button.element.disabled = False
        send_button.element.disabled = False
        return
    
    pool = txHistory.wallet.coldstaking["guiSelection"]

    Element("message-box").element.innerHTML = f'''<h3>{locale['please-confirm-zapping']}</h3><p>Pool:</p><p class="message-box-secondary">{csInfo['poolKey'] if pool == "custom" else pool}</p><p>{locale['send-tab-amount']}:</p><p class="message-box-secondary">{maxAmount:,.8f}</p>
                                                <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['cancel']}</button>
                                                <button class="cancel-confirm-send-button" id="confirm-send-button" onclick="finalizeSendTx()" type="button">{locale['send-tab-send-button']}</button>'''
    
    Element("confirm-send-button").element.disabled = True
    Element("confirm-send-button").element.style.opacity = "0.2"

    stakeAddr = csInfo['poolKey']
    spendAddr = txHistory.wallet.coldstaking['spendKey']

    if getCsAddrInfo(stakeAddr).type == "xpub":
        stakeAddr = getAddrFromXpub(stakeAddr, 0)

    script = buildColdstakeScript(spendAddr, stakeAddr)

    if not txHistory.walletCls.isCsOut(script):
        await closeMessageBox()
        js.console.log(str(f"Error building coldstake script.\nScript: {script}"))
        js.alert(str("Error building Coldstake script!"))
        zap_button.element.disabled = False
        send_button.element.disabled = False
        return

    inputDetails = TransactionInputs(txHistory, maxAmount, spendColdStake=spendCSOut, isZap=True, script=script)

    privKeys = inputDetails.getPrivateKeys(password)
    
    outScript = txHistory.util.splitCsOutputs(inputDetails.amount, script)

    try:

        rawTx = generateTxScript(to_js(inputDetails.inputs, dict_converter=js.Object.fromEntries), spendAddr,
                       to_js(outScript), to_js(privKeys), inputDetails.fee, stakeAddr)

    except Exception as e:
        await closeMessageBox()
        print(e)
        zap_button.element.disabled = False
        send_button.element.disabled = False
        return

    txHistory.pendingTxOut = rawTx
    Element("confirm-send-button").element.disabled = False
    Element("confirm-send-button").element.style.opacity = "1"
    

async def sendTx():
    send_button = Element("send-tab-send-button")
    send_button.element.disabled = True
    zap_button = Element("send-tab-zap-button")
    zap_button.element.disabled = True
    addr_input = Element("send-tab-input")
    amount_input = Element("send-tab-amount")
    password_input = Element("send-tab-password")

    if not (addr := addr_input.element.value.strip()) or not validateAddress(addr):
        js.console.log("Invalid Address")
        addr_input.element.style.borderColor = "#ff4d4d"
        
        await shakeIt(addr_input)
        
        send_button.element.disabled = False
        zap_button.element.disabled = False
        return
    else:
        addr_input.element.style.borderColor = "#aeff00"

    if not (password := password_input.element.value) or not await isValidPass(password):
        js.console.log("Invalid Password")
        password_input.element.style.borderColor = "#ff4d4d"
        
        await shakeIt(password_input)
        
        send_button.element.disabled = False
        zap_button.element.disabled = False
        return
    else:
        password_input.element.style.borderColor = "#aeff00"
        password_input.clear()
    
    if not (amount := amount_input.element.value):
        js.console.log("Invalid Amount")
        amount_input.element.style.borderColor = "#ff4d4d"
        
        await shakeIt(amount_input)
        
        send_button.element.disabled = False
        zap_button.element.disabled = False
        return
    else:
        try:
            amount = round(float(amount), 8)

            if txHistory.util.convertToSat(amount) < MIN_TX:
                raise

            amount_input.element.style.borderColor = "#aeff00"

        except:
            js.console.log("Invalid Amount")
            amount_input.element.style.borderColor = "#ff4d4d"
            
            await shakeIt(amount_input)

            send_button.element.disabled = False
            zap_button.element.disabled = False
            return

    Element("message-box").element.innerHTML = f'''<h3>{locale['processing-transaction']}</h3><p>{locale['menu-tab-item-address-label']}:</p><p class="message-box-secondary"></p><p>{locale['send-tab-amount']}:</p><p class="message-box-secondary"></p>
                                                <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['cancel']}</button>'''


    await showMessageBox()
        
    inputDetails = TransactionInputs(txHistory, amount, spendColdStake=spendCSOut)
    
    
    if inputDetails.fee + inputDetails.amount > (txHistory.wallet.totalBalance - (txHistory.wallet.coldstakingBalance if not spendCSOut else 0)):
        js.console.log("Invalid Amount")
        await closeMessageBox()
        amount_input.element.style.borderColor = "#ff4d4d"
        
        await shakeIt(amount_input)
        
        send_button.element.disabled = False
        zap_button.element.disabled = False
        return
    

    Element("message-box").element.innerHTML = f'''<h3>{locale['please-confirm-sending']}</h3><p>{locale['menu-tab-item-address-label']}:</p><p class="message-box-secondary">{addr}</p><p>{locale['send-tab-amount']}:</p><p class="message-box-secondary">{amount:,.8f}</p>
                                                <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['cancel']}</button>
                                                <button class="cancel-confirm-send-button" id="confirm-send-button" onclick="finalizeSendTx()" type="button">{locale['send-tab-send-button']}</button>'''


    Element("confirm-send-button").element.disabled = True
    Element("confirm-send-button").element.style.opacity = "0.2"
    
    privKeys = inputDetails.getPrivateKeys(password)

    csInfo = txHistory.wallet.coldstaking

    change_addr = random.choice(txHistory.wallet.change_addresses)

    stake_addr = False

    if csInfo['isActive']:
        stake_addr = csInfo['poolKey']

        if getCsAddrInfo(stake_addr).type == "xpub":
            stake_addr = getAddrFromXpub(stake_addr, 0)
        
        change_addr = txHistory.wallet.coldstaking['spendKey']
        

    try:
        rawTx = generateTx(to_js(inputDetails.inputs, dict_converter=js.Object.fromEntries), change_addr,
                       addr, to_js(privKeys), inputDetails.amount, inputDetails.fee, stake_addr)

    except Exception as e:
        print(e)
        send_button.element.disabled = False
        zap_button.element.disabled = False
        return

    
    txHistory.pendingTxOut = rawTx

    Element("confirm-send-button").element.disabled = False
    Element("confirm-send-button").element.style.opacity = "1"


async def finalizeSendTx():
    if not txHistory.pendingTxOut:
        return
    
    rawTx = txHistory.pendingTxOut

    send_button = Element("send-tab-send-button")
    zap_button = Element("send-tab-zap-button")
    message_box = Element("message-box")
     
    try:
        txid = await txHistory.api.sendTx(str(rawTx))
    except Exception as e:
        message_box.element.innerHTML = f'''<h3>{locale['error']}</h3>
                                                   <br>
                                                   <p>{e}</p>
                                                   <br>
                                                   <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                                                '''
        js.console.log(str(e))
        send_button.element.disabled = False
        zap_button.element.disabled = False
        return

    message_box.element.innerHTML = f'''<h3>{locale['success']}</h3>
                                                   <br>
                                                   <p>{txid}</p>
                                                   <br>
                                                   <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox(isTxSuccess=true)" type="button">{locale['close']}</button>
                                                '''
    
    await clearSendTab()

    send_label = Element("send-tab-label")

    send_label.element.innerText = locale['success']
    send_label.element.style.color = "#aeff00"

    await asyncio.sleep(5)

    send_label.element.innerText = locale['send-tab-label']
    send_label.element.style.color = "#fafafa"

    send_button.element.disabled = False
    zap_button.element.disabled = False


async def closeMessageBox(isTxSuccess=False):
    if not txHistory.showMessage:
        return

    if txHistory.showTxInfo:
        txHistory.showTxInfo = ''

    send_button = Element("send-tab-send-button")
    zap_button = Element("send-tab-zap-button")
    message_box = Element("message-box")

    send_button.element.disabled = False
    zap_button.element.disabled = False

    Element("send-tab-clear-button").element.disabled = False
    Element("send-tab-scan-button").element.disabled = False

    Element("send-tab-checkbox").element.disabled = False
    js.jQuery("#message-box").fadeOut(150)
    await asyncio.sleep(0.15)
    message_box.element.style.display = "none"
    txHistory.pendingTxOut = None
    txHistory.showMessage = False

    if isTxSuccess:
        await tabBrowser('overview-container', 'overview-button')
    
    stopScanner()


async def showMessageBox(showTxInfo='', isScanner=False):
    if txHistory.showMessage:
        return
    
    if showTxInfo:
        txHistory.showTxInfo = showTxInfo

    Element("send-tab-checkbox").element.disabled = True
    js.jQuery("#message-box").fadeIn(150)
    await asyncio.sleep(0.15)

    if browserName == "safari" and isScanner:
        Element("message-box").element.style.display = "table"
    else:
        Element("message-box").element.style.display = "block"
    
    Element("send-tab-clear-button").element.disabled = True
    Element("send-tab-scan-button").element.disabled = True
    txHistory.showMessage = True


async def shakeIt(shake_element):
    shake_element.element.style.animation = "shake 0.82s cubic-bezier(.36,.07,.19,.97) both"
    shake_element.element.style.WebkitAnimation = "shake 0.82s cubic-bezier(.36,.07,.19,.97) both"
    await asyncio.sleep(0.82)
    shake_element.element.style.animation = ""
    shake_element.element.style.WebKitAnimation = ""


async def setSpendCS():
    global spendCSOut

    checkbox = Element("send-tab-checkbox")

    if checkbox.element.checked:
        spendCSOut = True
    else:
        spendCSOut = False


async def isValidPass(password):
    try:
        token = str(password_decrypt(str(await getData("TOKEN").then(lambda x: x)), password))
        return True
    except Exception as e:
        return False
    

async def clearSendTab():
    addr_input = Element("send-tab-input")
    amount_input = Element("send-tab-amount")
    password_input = Element("send-tab-password")
    checkbox = Element("send-tab-checkbox")
    
    addr_input.clear()
    amount_input.clear()
    password_input.clear()

    addr_input.element.style.borderColor = "#aeff00"
    amount_input.element.style.borderColor = "#aeff00"
    password_input.element.style.borderColor = "#aeff00"

    checkbox.element.checked = False
    await setSpendCS()



async def genWallet():
    Element("new-pass-button").element.disabled = True
    Element("loading").element.style.display = "block"
    Element("set-password").element.style.display = "none"

    loading_message.element.innerText = "Generating wallet..."
    await asyncio.sleep(0.1)
    
    wallet = {
        "receiving_addresses": [],
        "receiving_addresses_256": [],
        "lookahead_addresses": [],
        "lookahead_addresses_256": [],
        "master_address_list": [],
        "change_addresses": [],
        "change_lookahead_addresses": [],
        "change_master_address_list": [],
        "used_addresses": [],
        "master_xpub": str(mnemonic.xpub),
        "master_xpriv": str(password_encrypt(str(mnemonic.xpriv).encode(), password_input.element.value)),
        "xpub": str(mnemonic.derived_xpub),
        "xpriv": str(password_encrypt(str(mnemonic.derived_xpriv).encode(), password_input.element.value)),
        "xpub_change": str(mnemonic.derived_xpub_change),
        "xpriv_change": str(password_encrypt(str(mnemonic.derived_xpriv_change).encode(), password_input.element.value)),
        "words": str(password_encrypt(str(mnemonic.words).encode(), password_input.element.value)),
        "utxo": [],
        "totalBalance": 0,
        "unconfirmedBalance": 0,
        "coldstakingBalance": 0,
        "qr_standard_addr": None,
        "qr_256_addr": None,
        "coldstaking": {"isActive": False, "guiSelection": "disabled", "poolKey": "", "spendKey": ""},
        "options": {"fiat": None, "explorer": "ghostscan"}
    }

    importWallet = ImportWallet(wallet)
    token = getToken()

    await storeData("wallet", str(password_encrypt(json.dumps(vars(importWallet)['wallet']).encode(), token), "utf-8"))
    await storeData("TOKEN", str(password_encrypt(token.encode(), password_input.element.value), "utf-8"))
    
    Element("loading").element.style.display = "none"
    Element("content-body").element.style.display = "flex"


failPass = 0

async def checkPass():
    global failPass
    Element("pass-submit-button").element.disabled = True

    token = None

    if not new_password_input.element.value:
        Element("pass-submit-button").element.disabled = False
        return False
    try:
        token = str(password_decrypt(str(await getData("TOKEN").then(lambda x: x)), new_password_input.element.value))
        new_password_input.clear()
        await asyncio.sleep(0.01)

    except Exception as e:
        failPass += 1
        
        new_password_input.element.style.borderColor = "#ff4d4d"
        await shakeIt(new_password_input)
        new_password_input.element.style.borderColor = "#aeff00"
        
        new_password_input.clear()
        Element("pass-submit-button").element.disabled = False

    if token:
        await runWallet(token)

async def enter_password_event(e):
    if "key" in dir(e) and e.key == "Enter":
        if new_password_input.element.value:
            await checkPass()


async def runWallet(TOKEN):
    
    global txHistory
    if txHistory:
        return
    Element("content-body").element.style.display = "none"
    Element("loading").element.style.display = "block"
    loading_message.element.innerText = "Initializing wallet..."
    await asyncio.sleep(0.05)

    wallet = Wallet(TOKEN, api)
    await wallet.initialize()

    txHistory = TransactionHistory(wallet)
    
    
    await txHistory.task_runner()
    loading_message.element.innerText = "Gathering transaction history..."
    await txHistory.processTxHistory()
    loading_message.element.innerText = "Processing transactions..."
    await displayTx()
    nodes = await api.getNodes()
    random.shuffle(nodes)
    txMonitor(to_js(nodes))

    if browserName == "safari":
        Element("send-tab").element.style.webkitAlignItems = "center"
    else:
        Element("send-tab").element.style.alignItems = "center"
    
    Element("loading").element.style.display = "none"
    Element("overview-button").element.style.backgroundColor = "#aeff00"
    Element("overview-button").element.style.color = "#171a1a"
    Element("main-window").element.style.display = "flex"

    #await api.getNodes()
    #print(wallet.wallet)

    await asyncio.gather(setAddrQrDisplay(), insertUsedAddresses(), insertPools(), insertVets(),
                        insertFiat(), checkExplorer(), insertLang(), clearSendTab())
    idleTimer()

    if clientOS in ["Android", "iOS"]:
        screenHideEvent()


async def tabBrowser(nextTab, button):
    if txHistory.showMessage:
        return
    currentTab = txHistory.currentTab
    currentButton = txHistory.currentButton

    fadeTime = 125

    if nextTab == currentTab:
        return
    js.jQuery(f"#{currentTab}").fadeOut(fadeTime)
    
    if not currentButton:
        Element("hamburger").element.src = "icons/hamburger-menu-icon.png"
    else:
        Element(f"{currentButton}").element.style.backgroundColor = "#171a1a"
        Element(f"{currentButton}").element.style.color = "#aeff00"
    
    
    if not button:
        Element("hamburger").element.src = "icons/hamburger-menu-icon-active.png"
    else:
        Element(f"{button}").element.style.backgroundColor = "#aeff00"
        Element(f"{button}").element.style.color = "#171a1a"
    
    await asyncio.sleep(fadeTime / 1000)
    Element(f"{currentTab}").element.style.display = "none"
    js.jQuery(f"#{nextTab}").fadeIn(fadeTime)
    Element(f"{nextTab}").element.style.display = "flex"
    
    txHistory.currentButton = button
    txHistory.currentTab = nextTab


async def swipeLeft():
    if not txHistory:
        return
    
    currentTab = txHistory.currentTab

    if currentTab == "overview-container":
        await tabBrowser("send-tab", "send-button")
    elif currentTab == "send-tab":
        await tabBrowser("receive-tab", "receive-button")
    elif currentTab == "receive-tab":
        return
    else:
        return

async def swipeRight():
    if not txHistory:
        return
    
    currentTab = txHistory.currentTab

    if currentTab == "overview-container":
        return
    elif currentTab == "send-tab":
        await tabBrowser("overview-container", "overview-button")
    elif currentTab == "receive-tab":
        await tabBrowser("send-tab", "send-button")
    else:
        return


async def expandSettings(setting):
    isExpanded = txHistory.settingsExpanded[setting]
    setting_item = Element(setting)

    fadeTime = 350
    
    if isExpanded:
        js.jQuery(f"#{setting}").animate(to_js({"height":"40px"}, dict_converter=js.Object.fromEntries), fadeTime)
        await txHistory.setExpanded(setting, False)

    else:
        if setting == "menu-tab-item-agvr" and txHistory.wallet.totalBalance < 2000000000000: # 20,000
            return

        height = js.jQuery(f"#{setting}").prop("scrollHeight") + 5
        js.jQuery(f"#{setting}").animate(to_js({"height":f"{height}px"}, dict_converter=js.Object.fromEntries), fadeTime)
        await txHistory.setExpanded(setting, True)

async def checkExplorer():
    selection = txHistory.wallet.options['explorer']

    Element(f"{selection}").element.checked = True

async def insertVets():
    if txHistory.wallet.totalBalance < 2000000000000:
        return
    
    current_vet_addr = Element("current-vet-addr-container")
    pending_vet_addr = Element("pending-vet-addr-container")
    menu_tab_item_agvr_label = Element("menu-tab-item-agvr-label")

    pending_vet_table = Element("pending-vet-table")

    vetlist = await txHistory.api.getVetlist()

    addrs = txHistory.wallet.receiving_addresses + txHistory.wallet.receiving_addresses_256 + txHistory.wallet.change_addresses

    curVets = []
    pendVets = []


    for vet in vetlist:
        if vet['address'] in addrs:
            if not vet['pending']:
                curVets.append(vet)
            else:
                pendVets.append(vet)
                break
    
    if curVets:
        current_vet_addr.element.style.display = "block"

        for vet in curVets:

            if vet['address'] in txHistory.currentVet:
                continue
            if vet['address'] in txHistory.pendingVet:
                Element(f"pend-vet-{vet['address']}").element.remove()
                txHistory.pendingVet.remove(vet['address'])
            
            template = Element(f"current-vet-addr-template").select(".addr-current-vet-item", from_content=True)

            vet_html = template.clone(f"curr-vet-template-{vet['address']}")

            vet_html.element.innerText = vet['address']
            vet_html.element.id = f"curr-vet-{vet['address']}"

            current_vet_addr.element.append(vet_html.element)
            txHistory.currentVet.append(vet['address'])

    if pendVets:
        pending_vet_addr.element.style.display = "block"

        for vet in pendVets:
            if vet['address'] in txHistory.pendingVet:
                continue
            if vet['address'] in txHistory.currentVet:
                Element(f"curr-vet-{vet['address']}").element.remove()
                txHistory.currentVet.remove(vet['address'])

            row = pending_vet_table.element.insertRow(0)

            cell1 = row.insertCell(0)
            cell2 = row.insertCell(1)

            row.id = f"pend-vet-{vet['address']}"
            
            
            cell1.innerHTML = vet['address']
            cell2.innerHTML = vet['remaining']

            txHistory.pendingVet.append(vet['address'])


    tmpVets = []

    for addr in curVets:
        tmpVets.append(addr['address'])

    currentVets = txHistory.currentVet.copy()
    
    for vetAddr in currentVets:
        if vetAddr not in tmpVets:
            try:
                Element(f"curr-vet-{vetAddr}").element.remove()
            except Exception as e:
                print(e)
            txHistory.currentVet.remove(vetAddr)
    
    tmpVets = []

    for addr in pendVets:
        tmpVets.append(addr['address'])

    pendingVets = txHistory.pendingVet.copy()
    
    for vetAddr in pendingVets:
        if vetAddr not in tmpVets:
            try:
                Element(f"pend-vet-{vetAddr}").element.remove()
            except Exception as e:
                print(e)
            txHistory.pendingVet.remove(vetAddr)
    
    if not txHistory.currentVet:
        current_vet_addr.element.style.display = "none"
    
    if not txHistory.pendingVet:
        pending_vet_addr.element.style.display = "none"

    if curVets:
        menu_tab_item_agvr_label.element.style.color = "#aeff00"
    else:
        menu_tab_item_agvr_label.element.style.color = "#fafafa"
            

async def insertPools():
    pool_container = Element("pool-button-container")
    isChecked = False
    disabled_check = Element("coldstake-pool-option-disabled")
    custom_check = Element("coldstake-pool-option-custom")

    stakingInfo = txHistory.wallet.coldstaking

    for pool in txHistory.poolList:
        template =  Element(f"coldstake-pool-template").select(".menu-tab-coldstake-radio-label", from_content=True)
        pool_html = template.clone(f"template-{pool['public_key']}")
        coldstake_pool_name = pool_html.select(".coldstake-pool-option")
        coldstake_pool_button = pool_html.select(".coldstake-radio-button")

        poolURL = pool['website']
        poolName = await stripURL(poolURL)

        coldstake_pool_name.element.innerHTML = f'{poolName} <a href="{poolURL}" target="_blank">info</a>'
        coldstake_pool_button.element.value = f"{poolName}"

        if pool['public_key'] == stakingInfo['poolKey']:
            coldstake_pool_button.element.checked = True
            isChecked = True

        pool_container.element.append(pool_html.element)

    if not isChecked:
        if stakingInfo['isActive']:
            custom_check.element.checked = True
            custom_pool_input.element.value = stakingInfo['poolKey']

            custom_pool_input.element.style.backgroundColor = "#aeff00"
            custom_pool_input.element.style.color = "#171a1a"
        else:
            disabled_check.element.checked = True

    if stakingInfo['isActive']:
        menu_tab_coldstake_label = Element("menu-tab-item-coldstake-label")
        menu_tab_coldstake_label.element.style.color = '#aeff00'

    if not txHistory.wallet.coldstaking.get("spendKey"):
        txHistory.wallet.coldstaking["spendKey"] = txHistory.wallet.receiving_addresses_256[0]
        await txHistory.walletCls.flushWallet()
    
    Element("pool-spend-addr").element.innerText = txHistory.wallet.coldstaking["spendKey"]


async def setSpendAddr(addr):

    if addr not in txHistory.wallet.receiving_addresses_256 + txHistory.wallet.lookahead_addresses_256:
        return
    
    last_selection = txHistory.wallet.coldstaking["spendKey"]

    if addr == last_selection:
        return

    Element(f"template-cs-{last_selection}").element.style.color = "#fafafa"
    Element(f"template-cs-{addr}").element.style.color = "#aeff00"

    txHistory.wallet.coldstaking["spendKey"] = addr
    await txHistory.walletCls.flushWallet()
    
    Element("pool-spend-addr").element.innerText = txHistory.wallet.coldstaking["spendKey"]

async def spendAddrSelection():
    message_box = Element("message-box")
    spend_addr = txHistory.wallet.coldstaking["spendKey"]

    availableAddr256 = txHistory.wallet.receiving_addresses_256 # + txHistory.wallet.lookahead_addresses_256
    
    addrSelectHTML = f'''
                    <h3>{locale['coldstaking-spend-address']}</h3>
                    <br>
                    <div id="cs-addr-container" class="cs-addr-container"></div>
                    <br>
                    <button class="cancel-confirm-send-button" id="cancel-send-button" style="margin-top:0px;" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                    '''

    message_box.clear()
    message_box.element.innerHTML = addrSelectHTML

    cs_addr_container = Element("cs-addr-container")
    
    for addr in availableAddr256:
        template =  Element(f"new-cs-address").select(".menu-tab-coldstake-radio-label", from_content=True)
        addr_html = template.clone(f"template-cs-{addr}")
        
        addr_name = addr_html.select(".cs-address")
        addr_button = addr_html.select(".new-cs-address-button")

        addr_name.element.innerText = f'{addr}'
        addr_button.element.value = f"{addr}"

        if addr == spend_addr:
            addr_button.element.checked = True
            addr_html.element.style.color = "#aeff00"

        cs_addr_container.element.append(addr_html.element)
    
    await showMessageBox()


async def copyCsSpendAddr():
    spend_addr = Element("pool-spend-addr")
    js.navigator.clipboard.writeText(str(txHistory.wallet.coldstaking["spendKey"]))

    spend_addr.element.innerText = locale['qr_text_copy']
    await asyncio.sleep(3)
    spend_addr.element.innerText = txHistory.wallet.coldstaking["spendKey"]


async def setPoolOption(selected):
    stakingInfo = txHistory.wallet.coldstaking

    if selected == stakingInfo['guiSelection']:
        return

    menu_tab_coldstake_label = Element("menu-tab-item-coldstake-label")
    
    if selected == 'disabled':
        txHistory.wallet.coldstaking['isActive'] = False
        txHistory.wallet.coldstaking['guiSelection'] = selected
        txHistory.wallet.coldstaking['poolKey'] = ""
        menu_tab_coldstake_label.element.style.color = '#fafafa'
        custom_pool_input.element.disabled = True
        custom_pool_input.element.style.backgroundColor = "#232728"
        custom_pool_input.element.style.color = "#fafafa"
    
    elif selected == 'custom':

        txHistory.wallet.coldstaking['guiSelection'] = selected
        custom_pool_input.element.disabled = False

        if custom_pool_input.element.value != '':
            if getCsAddrInfo(custom_pool_input.element.value).isValid:
                custom_pool_input.element.style.backgroundColor = "#aeff00"
                custom_pool_input.element.style.color = "#171a1a"


                menu_tab_coldstake_label.element.style.color = '#aeff00'

                txHistory.wallet.coldstaking['isActive'] = True
                txHistory.wallet.coldstaking['poolKey'] = custom_pool_input.element.value
            else:
                custom_pool_input.element.style.backgroundColor = "#232728"
                custom_pool_input.element.style.color = "fafafa"
                menu_tab_coldstake_label.element.style.color = '#fafafa'
        else:
            custom_pool_input.element.style.backgroundColor = "#232728"
            custom_pool_input.element.style.color = "fafafa"
    
    else:
        txHistory.wallet.coldstaking['isActive'] = True
        txHistory.wallet.coldstaking['guiSelection'] = selected
        menu_tab_coldstake_label.element.style.color = '#aeff00'
        custom_pool_input.element.disabled = True
        custom_pool_input.element.style.backgroundColor = "#232728"
        custom_pool_input.element.style.color = "fafafa"

        for pool in txHistory.poolList:
            if await stripURL(pool['website']) == selected:
                txHistory.wallet.coldstaking['poolKey'] = pool['public_key']
                break

    await txHistory.walletCls.flushWallet()


async def getPoolStats():
    message_box = Element("message-box")
    current_pool = txHistory.wallet.coldstaking['guiSelection']
    spend_addr = txHistory.wallet.coldstaking["spendKey"]
    message_box.clear()


    if current_pool in ["custom", 'disabled']:
        return

    message_box.element.innerHTML = f'''
                                        <h3>{locale['fetching-pool-stats']}</h3><p></p><p class="message-box-secondary"></p><p></p><p class="message-box-secondary"></p>
                                        <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['cancel']}</button>
                                    '''
    await showMessageBox()


    try:
        poolStats = await txHistory.api.getStakingInfo(current_pool, spend_addr)
    except Exception as e:
        print(e)
        message_box.element.innerHTML = f'''<h3>{locale['error']}</h3>
                                                   <br>
                                                   <p>{e}</p>
                                                   <br>
                                                   <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                                                '''
        return
    
    message_box.element.innerHTML =f'''
                                    <h3>Pool Staking Stats</h3>
                                    <br>
                                    <table><tr><td>Accumulated:</td><td>{poolStats['Accumulated']}</td></tr><tr><td>Payout Pending:</td><td>{poolStats['Payout Pending']}</td></tr><tr><td>Paid Out:</td><td>{poolStats['Paid Out']}</td></tr><tr><td>Last Total Staking:</td><td>{poolStats['Last Total Staking']}</td></tr><tr><td>Current Total in Pool:</td><td>{poolStats['Current Total in Pool']}</td></tr></table>
                                    <br>
                                    <button class="cancel-confirm-send-button" id="cancel-send-button" style="margin-top:0px;" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                                    '''




async def setFiatOption(selected):
    fiat_selection = txHistory.wallet.options['fiat']

    if selected == "None":
        selected = None

    if fiat_selection == selected:
        return
    
    txHistory.wallet.options['fiat'] = selected

    await txHistory.walletCls.flushWallet()

    asyncio.gather(getPrice())


async def setExplorerOption(selected):

    explorer_selection = txHistory.wallet.options['explorer']

    if explorer_selection == selected:
        return
    
    txHistory.wallet.options['explorer'] = selected

    await txHistory.walletCls.flushWallet()

    explorer_url = f"https://{explore_dict[txHistory.wallet.options['explorer']]}/tx/"

    for txid in displayedTXID:
        Element(f"link-{txid}").element.href = f"{explorer_url}{txid}"


async def setLangOption(selected):
    lang = locale['lang']

    if lang == selected:
        return
        
    await doTranslation(requested_locale=selected)
    

async def insertLang():
    lang = locale['lang']
    lang_container = Element("lang-button-container")

    lang_choice = await api.getLang("index")
    
    for lang_item in lang_choice['langs']:
        template =  Element(f"lang-template").select(".menu-tab-coldstake-radio-label", from_content=True)
        lang_html = template.clone(f"template-{lang_item}")

        lang_name = lang_html.select(".lang-option")
        lang_button = lang_html.select(".lang-radio-button")

        lang_name.element.innerText = f'{lang_item.upper()} {lang_choice["flags"][lang_item]}'
        lang_button.element.value = f"{lang_item}"

        if lang == lang_item:
            lang_button.element.checked = True
        
        lang_container.element.append(lang_html.element)



async def insertFiat():
    fiat_container = Element("fiat-button-container")
    fiat_selection = txHistory.wallet.options['fiat']

    with open("currencies.json") as f:
        currList = json.loads(f.read())['CoinGecko']
    
    for curr in currList:
        template =  Element(f"fiat-template").select(".menu-tab-coldstake-radio-label", from_content=True)
        fiat_html = template.clone(f"template-{curr}")
        
        curr_name = fiat_html.select(".fiat-option")
        curr_button = fiat_html.select(".fiat-radio-button")


        curr_name.element.innerText = f'{curr}'
        curr_button.element.value = f"{curr}"

        if curr == fiat_selection:
            curr_button.element.checked = True

        fiat_container.element.append(fiat_html.element)


async def stripURL(url):
    if url.startswith("https://"):
        url = url.replace("https://", "")
    elif url.startswith("http://"):
        url = url.replace("http://", "")

    url = url.replace('/', '')

    return url


async def pasteCSAddr(e=None):
    
    if not custom_pool_input.element.value:
        return
    
    menu_tab_coldstake_label = Element("menu-tab-item-coldstake-label")
    
    if getCsAddrInfo(custom_pool_input.element.value).isValid:

        custom_pool_input.element.style.backgroundColor = "#aeff00"
        custom_pool_input.element.style.color = "#171a1a"

        menu_tab_coldstake_label.element.style.color = '#aeff00'

        txHistory.wallet.coldstaking['isActive'] = True
        txHistory.wallet.coldstaking['poolKey'] = custom_pool_input.element.value
        txHistory.wallet.coldstaking['guiSelection'] = "custom"
        custom_pool_input.element.disabled = True

    else:
        txHistory.wallet.coldstaking['isActive'] = False
        custom_pool_input.element.style.backgroundColor = "#232728"
        custom_pool_input.element.style.color = "fafafa"
        menu_tab_coldstake_label.element.style.color = '#fafafa'

    await txHistory.walletCls.flushWallet()


async def setAddrQrDisplay():
    qr_img_std = Element("qr-code-standard-img")
    qr_img_256 = Element("qr-code-256-img")
    qr_text_std = Element("qr-code-standard-text")
    qr_text_256 = Element("qr-code-256-text")
    qr_base_url = "https://explorer.myghost.org/qr/"

    std_addr_index = txHistory.wallet.qr_standard_addr
    addr_256_index = txHistory.wallet.qr_256_addr

    if std_addr_index == None:
        addr_std = await txHistory.getNewAddr("std")
    else:
        addr_std = txHistory.wallet.receiving_addresses[txHistory.wallet.qr_standard_addr]
    qr_img_std.element.src = f"{qr_base_url}{addr_std}"
    qr_text_std.element.innerText = addr_std

    if addr_256_index == None:
        addr_256 = await txHistory.getNewAddr(256)
    else:
        addr_256 = txHistory.wallet.receiving_addresses_256[txHistory.wallet.qr_256_addr]
    qr_img_256.element.src = f"{qr_base_url}{addr_256}"
    qr_text_256.element.innerText = addr_256

    if addr_std in txHistory.wallet.used_addresses:
        Element("new-address-button-standard").element.disabled = False
    else:
        Element("new-address-button-standard").element.disabled = True
    
    if addr_256 in txHistory.wallet.used_addresses:
        Element("new-address-button-256").element.disabled = False
    else:
        Element("new-address-button-256").element.disabled = True


async def getNewAddr(addrType):
    await txHistory.getNewAddr(addrType)
    await setAddrQrDisplay()

async def copyAddr(addrType):
    qr_text_std = Element("qr-code-standard-text")
    qr_text_256 = Element("qr-code-256-text")

    if addrType == "std":
        js.navigator.clipboard.writeText(str(txHistory.wallet.receiving_addresses[txHistory.wallet.qr_standard_addr]))
        qr_text_std.element.innerText = locale['qr_text_copy']
        qr_text_std.element.style.color = "#aeff00"
        await asyncio.sleep(3)
        qr_text_std.element.innerText = str(txHistory.wallet.receiving_addresses[txHistory.wallet.qr_standard_addr])
        qr_text_std.element.style.color = "#fafafa"

    elif addrType == 256:
        js.navigator.clipboard.writeText(str(txHistory.wallet.receiving_addresses_256[txHistory.wallet.qr_256_addr]))
        qr_text_256.element.innerText = locale['qr_text_copy']
        qr_text_256.element.style.color = "#aeff00"
        await asyncio.sleep(3)
        qr_text_256.element.innerText = str(txHistory.wallet.receiving_addresses_256[txHistory.wallet.qr_256_addr])
        qr_text_256.element.style.color = "#fafafa"

async def insertUsedAddresses():
    if set(txHistory.wallet.used_addresses) == set(displayedUsedAddr):
        return

    addr_list_used = Element("addr-list-used")

    for addr in txHistory.wallet.used_addresses:
        if addr in displayedUsedAddr:
            continue
        new_html = f'<div class="addr-list-used-item" onclick="copyUsedAddrjs(`{addr}`)">{addr}</div>'

        template =  Element(f"used-addr-template").select(".addr-list-used-item", from_content=True)
        addr_html = template.clone(f"template-{addr}")
        
        addr_list_used.element.append(addr_html.element)
        Element(f"template-{addr}").element.innerHTML = new_html
        displayedUsedAddr.append(addr)


async def toggleExtBal(isExtBal):
    bal_label = Element("balance-label")
    bal_amt = Element("overview-balance-major")
    bal_ext = Element("overview-balance-extended")

    if not isExtBal:
        bal_amt.element.style.display = "none"
        bal_label.element.style.display = "none"

        bal_ext.element.style.display = "inline-block"
    
    else:
        bal_amt.element.style.display = "block"
        bal_label.element.style.display = "block"

        bal_ext.element.style.display = "none"


async def copyUsedAddr(addr):
    js.navigator.clipboard.writeText(str(addr))
    addr_element = Element(f"template-{addr}")
    
    addr_element.element.innerText = locale['qr_text_copy']
    addr_element.element.style.color = "#aeff00"
    await asyncio.sleep(3)
    addr_element.element.innerText = str(addr)
    addr_element.element.style.color = "#fafafa"

async def displayTx():

    tx_list = Element("overview-tx-history")

    sortedHistory = sorted(txHistory.txHistory, key=lambda d: d['time'])

    for i in sortedHistory:

        await processNewTx(i)
    await insertShowMoreTx()


    await updateBalanceDisplay()


async def newTx(txData):
    txData = txData.to_py()
    tryCount = 0
    isMine = False

    if txData['isCoinStake']:
        while True:
            try:
                await newBlock()
                return
            except Exception as e:
                print(e)
                if tryCount < 5:
                    tryCount += 1
                    await asyncio.sleep(1)
                else:
                    return

    for i in list(txData['inputs'].keys()) + list(txData['outputs'].keys()):
        if i in txHistory.wallet.receiving_addresses + txHistory.wallet.receiving_addresses_256 + txHistory.wallet.change_addresses:
            isMine = True
        
        elif i in txHistory.wallet.lookahead_addresses + txHistory.wallet.lookahead_addresses_256 + txHistory.wallet.change_lookahead_addresses:
            await asyncio.sleep(1)
            await txHistory.task_runner()
            isMine = True
    if isMine:

        while True:
            try:
                await asyncio.sleep(1)
                networkTx = await txHistory.processNetworkTx(txData['txid'])

                if not networkTx:
                    return

                await processNewTx(networkTx)
                await updateNextTxPage()
                await updateBalanceDisplay()
                break
            except Exception as e:
                print(e)
                if tryCount < 5:
                    tryCount += 1
                    await asyncio.sleep(1)
                else:
                    return


async def updateBalanceDisplay():
    await txHistory.walletCls.processUTXO()
    convertFromSat = txHistory.util.convertFromSat
    
    bal = str(round(convertFromSat(txHistory.wallet.totalBalance), 8)).split(".")

    bal_small = "00"

    if len(bal) > 1 and bal[1] != "0":
        bal_small = bal[1]

    Element("overview-balance-major").element.innerHTML = f'<span class="balance-display" style="">{int(bal[0]):,}</span><span>.{bal_small}</span>'

    bal_spend = Element("balance-spendable")
    bal_cs = Element("balance-coldstake")
    bal_unconf = Element("balance-unconfirmed")
    bal_staked = Element("balance-staked")

    staked = 0
    cs_staked = 0

    for utxo in txHistory.wallet.utxo:
        if utxo['txid'] in txHistory.unmatureUTXO:
            if utxo['confirmations'] <= 100:
                staked += utxo['satoshis']
                if txHistory.walletCls.isCsOut(utxo['script']):
                    cs_staked += utxo['satoshis']
            else:
                txHistory.unmatureUTXO.remove(utxo['txid'])

    spendable = round(convertFromSat(txHistory.wallet.totalBalance - txHistory.wallet.unconfirmedBalance - staked), 8)
    cold_bal = round(convertFromSat(txHistory.wallet.coldstakingBalance - cs_staked), 8)
    unconf_bal = round(convertFromSat(txHistory.wallet.unconfirmedBalance), 8)
    staked_bal = round(convertFromSat(staked), 8)

    bal_spend.element.innerText = '0.00' if not spendable else f"{spendable:,}"
    bal_cs.element.innerText = '0.00' if not cold_bal else f"{cold_bal:,}"
    bal_unconf.element.innerText = '0.00' if not unconf_bal else f"{unconf_bal:,}"
    bal_staked.element.innerText = '0.00' if not staked_bal else f"{staked_bal:,}"

    if txHistory.wallet.qr_standard_addr != None and txHistory.wallet.receiving_addresses[txHistory.wallet.qr_standard_addr] in txHistory.wallet.used_addresses:
        Element("new-address-button-standard").element.disabled = False
    else:
        Element("new-address-button-standard").element.disabled = True
    
    if txHistory.wallet.qr_256_addr != None and txHistory.wallet.receiving_addresses_256[txHistory.wallet.qr_256_addr] in txHistory.wallet.used_addresses:
        Element("new-address-button-256").element.disabled = False
    else:
        Element("new-address-button-256").element.disabled = True

    asyncio.gather(getPrice(), insertVets(), insertUsedAddresses())


async def newBlock():
    global txHistory
    unconfTx = txHistory.unconfirmedTx
    tryCount = 0
    pendingIDs = []

    for tx in unconfTx:
        txElement = Element(f"confirm-{tx['txid']}")

        while True:
            checkTx = await txHistory.processNetworkTx(tx['txid'], ignoreExisting=True)
            if (netConf := checkTx['confirmations']) == tx['confirmations']:
                if tryCount > 3:
                    break
                await asyncio.sleep(3)
                tryCount += 1
            else:
                break
        if netConf >= 12:
            confirms = 12
        elif netConf <= 0:
            confirms = 0
        else:
            confirms = netConf

        if netConf < 0:
            Element(f"tx-icon-{tx['txid']}").element.src = template_dict['orphaned']
            Element(f"tx-icon-{tx['txid']}").element.alt = 'Orphaned'
            txElement.element.innerText = f"{confirm_dict['orphaned']['text']}"
            txElement.element.style.color = f"{confirm_dict['orphaned']['color']}"
            txHistory.unconfirmedTx.remove(tx)
        else:
            txElement.element.innerText = f'{confirm_dict[confirms]["text"]}'
            txElement.element.style.color = f"{confirm_dict[confirms]['color']}"


        if netConf >= 12:
            txHistory.unconfirmedTx.remove(tx)
        else:
            tx['confirmations'] = netConf
            pendingIDs.append(tx['txid'])

    await txHistory.processTxHistory()
    await displayTx()
    await updateHistoryConfirms(pendingIDs)


async def updateHistoryConfirms(pendingTx):

    for tx in txHistory.txHistory:
        if tx['txid'] not in pendingTx:
            tx['confirmations'] += 1

        if tx['txid'] == txHistory.showTxInfo:
            Element(f"msg-box-conf-{tx['txid']}").element.innerText = tx['confirmations']

async def processNewTx(tx, isOldTx=False):

    if not tx or tx['txid'] in displayedTXID:
        return

    if (netConf := tx['confirmations']) >= 12:
        confirms = 12
    elif netConf <= 0:
        confirms = 0
    else:
        confirms = netConf

    tx_list = Element("overview-tx-history")

    explorer_url = f"https://{explore_dict[txHistory.wallet.options['explorer']]}/tx/"

    template = Element(f"tx-history-template").select(".tx-history-item", from_content=True)

    tx_html = template.clone(f"template-{tx['txid']}")

    tx_html_amount = tx_html.select(".tx-amount")
    tx_html_date = tx_html.select(".tx-date")
    tx_html_link = tx_html.select(".txid-item")
    tx_html_icon = tx_html.select(".tx-type-icon")

    txTime = datetime.fromtimestamp(tx['time'], tz=None)

    tx_html_date.element.innerHTML = f"{'0' if txTime.day < 10 else ''}{txTime.day}•{'0' if txTime.month < 10 else ''}{txTime.month}•{str(txTime.year)[2:]} {'0' if txTime.hour < 10 else ''}{txTime.hour}:{'0' if txTime.minute < 10 else ''}{txTime.minute} " + f'<div class="confirm-progress" onclick="clickTXIDjs(`{tx["txid"]}`);" id="confirm-{tx["txid"]}" style="color: {confirm_dict[confirms]["color"]}">{confirm_dict[confirms]["text"]} </div>'
    
    tx_html_amount.element.innerHTML = f"{'+' if tx['txValue'] > 0 else ''}{tx['txValue']:,.8f} " + f'<div class="coin-name" id="coin-name">GHOST</div>'
    tx_html_link.element.innerHTML = f'<div style="color:#aeff00;cursor:pointer;" id="link-{tx["txid"]}" onclick="txInfojs(`{tx["txid"]}`)">{tx["txid"][:23]}...</div>'
    tx_html_icon.element.innerHTML = f'<img class="tx-type-icon" id="tx-icon-{tx["txid"]}" src="{template_dict[tx["txType"]]}" alt="{tx["txType"].title()}">'
    
    if not isOldTx:
        tx_list.element.prepend(tx_html.element)
    else:
        tx_list.element.append(tx_html.element)

    displayedTXID.append(tx['txid'])


async def updateNextTxPage():
    show_more = Element("template-show-more")

    total_tx = txHistory.txHistoryTotalItems
    best_tx = txHistory.txHistoryTopIndex

    if not total_tx:
        return

    dif_tx = total_tx - best_tx

    if not show_more.element:
        return

    show_more.element.innerHTML = f'''{'<img class="down-arrow" style="cursor: pointer;" onclick="getNextTxPagejs()" src="icons/bottom-arrow.png">' if dif_tx else ''}
    <span class="tx-count" style="cursor: pointer;" {'onclick="getNextTxPagejs()"' if dif_tx else ''}>{best_tx} / {total_tx} </span>{'<img class="down-arrow" style="cursor: pointer;" onclick="getNextTxPagejs()" src="icons/bottom-arrow.png">' if dif_tx else ''}'''



async def txInfo(txid):
    tx = await txHistory.getTxByTXID(txid)

    explorer_url = f"https://{explore_dict[txHistory.wallet.options['explorer']]}/tx/"

    txTime = datetime.fromtimestamp(tx['time'], tz=None)

    txDetailHTML = f'''
                    <h3>{locale['transaction-info']}</h3>
                    <br>
                    <p style="font-size:12pt;">TXID:</p>
                    <p class="message-box-secondary">{txid}</p>
                    <p style="font-size:12pt;">{locale['time']}:</p>
                    <p class="message-box-secondary">{'0' if txTime.day < 10 else ''}{txTime.day}•{'0' if txTime.month < 10 else ''}{txTime.month}•{str(txTime.year)[2:]} {'0' if txTime.hour < 10 else ''}{txTime.hour}:{'0' if txTime.minute < 10 else ''}{txTime.minute}</p>
                    <p style="font-size:12pt;">{locale['confirmations']}:</p>
                    <p class="message-box-secondary" id="msg-box-conf-{txid}">{tx['confirmations']}</p>
                    <p style="font-size:12pt;">{locale['send-tab-amount']}:</p>
                    <p class="message-box-secondary" style="{'color:#ff4d4d;' if tx['txValue'] < 0 else ''}">{tx['txValue']}</p>
                    <p style="font-size:12pt;">{locale['type']}:</p>
                    <p class="message-box-secondary">{tx['txType'].title()}</p>
                    '''
    
    cfs = txHistory.util.convertFromSat
    txIns = await sortTxAddr(tx['inAddr'])
    txOuts = await sortTxAddr(tx['outAddr'])
    

    txDetailHTML += f'''
                    <div style="padding-bottom:8px;"></div><p style="font-size:12pt;">{locale['input-addresses']} ({len(txIns)}):</p>
                    <div class="" id="tx-info-inputs" style="white-space:nowrap;max-height:100px;overflow:auto;border-radius: 10px;">
                    '''
    
    for addr in txIns:
        amt = cfs(addr['amount'])
        if addr['isMine']:
            txDetailHTML += f'''<p id="my-tx-in" style="color:#aeff00;">{addr['addr']}: {amt}</p>'''
        else:
            txDetailHTML += f'''<p  style="color:#fafafa;">{addr['addr']}: {amt}</p>'''
    txDetailHTML += "</div><br>"

    txDetailHTML += f'''
                    <p style="font-size:12pt;">{locale['output-addresses']} ({len(txOuts)}):</p>
                    <div id="tx-info-outputs" class="" style="white-space:nowrap;max-height:100px;overflow:auto;border-radius:10px;">
                    '''

    for addr in txOuts:
        amt = cfs(addr['amount'])
        if addr['isMine']:
                txDetailHTML += f'''<p id="my-tx-out" style="color:#aeff00;" style="">{addr['addr']}: {amt}</p>'''
        else:
            txDetailHTML += f'''<p style="color:#fafafa;">{addr['addr']}: {amt}</p>'''
    txDetailHTML += "</div>"
    

    txDetailHTML += f'''
                     <br>
                     <a class="message-box-secondary" style="font-size:10pt;" href="{explorer_url}{tx["txid"]}" target="_blank">{locale['view-on-explorer']}</a>
                     <br>
                     <button class="cancel-confirm-send-button" id="cancel-send-button" onclick="closeMessageBox()" type="button">{locale['close']}</button>
                     '''
   
    Element("message-box").element.innerHTML = txDetailHTML
    
    await showMessageBox(showTxInfo=txid)
    
    offsetOut = Element("my-tx-out").element.offsetTop - Element("tx-info-outputs").element.offsetTop
    Element("tx-info-outputs").element.scrollTop = offsetOut - 42

    offsetIn = Element("my-tx-in").element.offsetTop - Element("tx-info-inputs").element.offsetTop
    Element("tx-info-inputs").element.scrollTop = offsetIn - 42
   


async def sortTxAddr(addrDict):
    newList = []
    
    for i in addrDict:
        newList.append({"addr": i, "amount": addrDict[i], "isMine": await txHistory.walletCls.isMine(i)})
    
    return newList # sorted(newList, key= lambda d:d['isMine'], reverse=True)


async def insertShowMoreTx():
    tx_list = Element("overview-tx-history")
    show_more = Element("template-show-more")

    total_tx = txHistory.txHistoryTotalItems
    best_tx = txHistory.txHistoryTopIndex

    if not total_tx:
        return

    if show_more.element:
        show_more.element.remove()
    
    template = Element(f"overview-tx-next-page").select(".next-page-item", from_content=True)

    tx_html = template.clone(f"template-show-more")
    
    
    dif_tx = total_tx - best_tx

    if dif_tx > 50:
        dif_tx = 50

    tx_html.element.innerHTML = f'''{'<img class="down-arrow" style="cursor: pointer;" onclick="getNextTxPagejs()" src="icons/bottom-arrow.png">' if dif_tx else ''}
    <span id="tx-count" class="tx-count" style="cursor: pointer;" {'onclick="getNextTxPagejs()"' if dif_tx else ''}>{best_tx} / {total_tx} </span>{'<img class="down-arrow" style="cursor: pointer;" onclick="getNextTxPagejs()" src="icons/bottom-arrow.png">' if dif_tx else ''}'''

    tx_list.element.append(tx_html.element)


async def getNextTxPage():
    total_tx = txHistory.txHistoryTotalItems
    best_tx = txHistory.txHistoryTopIndex
    tx_count = Element("tx-count")

    dif_tx = total_tx - best_tx
    
    if not dif_tx:
        return

    tx_count.element.style.color = "#aeff00"
    await asyncio.sleep(0.01)

    if dif_tx > 50:
        dif_tx = 50

    await txHistory.processTxHistory(startIdx=best_tx, endIdx=best_tx+50, advanceTopIndex=True)
    
    sortedHistory = sorted(txHistory.txHistory, key=lambda d: d['time'], reverse=True)

    for i in sortedHistory:
        await processNewTx(i, isOldTx=True)
    await insertShowMoreTx()


async def getPrice():
    overview_price = Element("overview-price-container")
    fiat = txHistory.wallet.options['fiat']

    if fiat:
        price = await txHistory.api.getPrice(fiat.lower())
        total_price = round(price * txHistory.util.convertFromSat(txHistory.wallet.totalBalance), 6)

        overview_price.element.innerText = f"{locale['one']} GHOST ~{round(price, 6):f} {fiat} Bal: {total_price} {fiat}"
    else:
        overview_price.element.innerText = ""


async def clickTXID(txid):
    Element(f"link-{txid}").element.click()


async def main():
    if not isDupe:
        Element("loading").element.style.display = "none"

        if await getData("TOKEN").then(lambda x: x):
            Element("content-body").element.style.display = "flex"
        else:
            #Element("new-question").element.style.display = "block"
            Element("beta-message").element.style.display = "block"
    else:
        Element("dupe-tab-warning").element.style.display = "block"


async def doTranslation(requested_locale=None):
    global locale
    if requested_locale:
        lang = requested_locale
        await storeData("lang", lang)
    else:
        lang = await getData("lang").then(lambda x: x)

    if not lang:
        lang = js.navigator.language
        await storeData("lang", lang)

    # import the translation

    if lang.lower() in ['en-us', 'en-gb', 'en', 'en-au', 'en-bz', 'en-ca',
                        'en-ie', 'en-jm', 'en-nz', 'en-ph', 'en-za', 'en-tt', 'en-zw']:
        locale_code = "en"
    elif lang.lower() in ['ru', 'ru-mo']:
        locale_code = "ru"
    elif lang.lower() in ['de', 'de-de', 'de-at', 'de-li', 'de-lu', 'de-ch']:
        locale_code = "de"
    elif lang.lower() in ['fr', 'fr-be', 'fr-ca', 'fr-fr', 'fr-lu', 'fr-mc', 'fr-ch']:
        locale_code = "fr"
    elif lang.lower() in ['es', 'es-ar', 'es-bo', 'es-cl', 'es-co', 'es-cr', 'es-do', 'es-ec',
                          'es-sv', 'es-gt', 'es-hn', 'es-mx', 'es-ni', 'es-pa', 'es-py', 'es-pe',
                          'es-pr', 'es-es', 'es-uy', 'es-ve']:
        locale_code = "es"
    elif lang.lower() in ['id']:
        locale_code = "id"
    elif lang.lower() in ['ja']:
        locale_code = "ja"
    elif lang.lower() in ['ko', 'ko-kp', 'ko-kr', 'kr']:
        locale_code = "ko"
    elif lang.lower() in ['tr']:
        locale_code = "tr"
    elif lang.lower() in ['ua', 'uk']:
        locale_code = "uk"
    elif lang.lower() in ['bg']:
        locale_code = "bg"
    elif lang.lower() in ['bn']:
        locale_code = "bn"
    elif lang.lower() in ['hi']:
        locale_code = "hi"
    elif lang.lower() in ['kk']:
        locale_code = "kk"
    elif lang.lower() in ['nl', 'nl-be']:
        locale_code = "nl"
    elif lang.lower() in ['kk']:
        locale_code = "kk"
    elif lang.lower() in ['pl']:
        locale_code = "pl"
    elif lang.lower() in ['pt', 'pt-br']:
        locale_code = "pt"
    elif lang.lower() in ['sv', 'sv-fi', 'sv-sv']:
        locale_code = "sv"
    elif lang.lower() in ['zh', 'zh-hk', 'zh-cn', 'zh-sg', 'zh-tw']:
        locale_code = "zh"
    
    else:
        locale_code = "en"

    
    
    locale = await api.getLang(locale_code)

    # translations for new or import screen
    Element("question-text").element.innerHTML = locale['question-text']
    Element("import-button").element.innerText = locale['import-button']
    Element("new-button").element.innerText = locale['new-button']

    # translations for words page

    Element("continue-words").element.innerText = locale['continue-words']
    Element("words-disclamer").element.innerText = locale['words-disclamer']

    # Translation for import words page

    Element("import-word-button").element.innerText = locale['import-word-button']
    Element("import-messsage").element.innerHTML = locale['import-messsage']

    # translations for new pass screen

    Element("new-pass-input").element.placeholder = locale['new-pass-input']
    Element("new-pass-confirm").element.placeholder = locale['new-pass-confirm']
    Element("new-pass-button").element.innerText = locale['new-pass-button']
    Element("pass-warning").element.innerHTML = locale['pass-warning']


    # translate the password prompt
    new_password_input.element.placeholder = locale['password-input-placeholder']
    Element("pass-submit-button").element.innerText = locale['pass-submit-button']
    Element("password-input-link").element.innerText = locale['password-input-link']

    # translations for main window tab buttons

    Element("overview-button").element.innerText = locale['overview-button']
    Element("send-button").element.innerText = locale['send-button']
    Element("receive-button").element.innerText = locale['receive-button']

    # translations for balance display

    Element("balance-label").element.innerText = locale['balance-label']
    Element("balance-spendable-text").element.innerText = locale['balance-spendable-text']
    Element("balance-coldstake-text").element.innerText = locale['balance-coldstake-text']
    Element("balance-unconfirmed-text").element.innerText = locale['balance-unconfirmed-text']
    Element("balance-staked-text").element.innerText = locale['balance-staked-text']
    Element("tx-history-label").element.innerText = locale['tx-history-label']

    # Translations for send tab

    Element("send-tab-label").element.innerText = locale['send-tab-label']
    Element("send-tab-input").element.placeholder = locale['send-tab-input']
    Element("send-tab-amount").element.placeholder = locale['send-tab-amount']
    Element("send-tab-password").element.placeholder = locale['send-tab-password']
    Element("send-tab-toggle-label").element.innerText = locale['send-tab-toggle-label']
    Element("send-tab-max").element.innerText = locale['send-tab-max']
    Element("send-tab-scan-button").element.innerText = locale['send-tab-scan-button']
    Element("send-tab-send-button").element.innerText = locale['send-tab-send-button']
    Element("send-tab-zap-button").element.innerText = locale['send-tab-zap-button']
    Element("send-tab-clear-button").element.innerText = locale['send-tab-clear-button']


    # translations for the menu

    Element("menu-tab-label").element.innerText = locale['menu-tab-label']
    Element("menu-tab-item-lang-label").element.innerText = locale['menu-tab-item-lang-label']
    Element("menu-tab-item-address-label").element.innerText = locale['menu-tab-item-address-label']
    Element("new-address-button-standard").element.innerText = locale['new-address-button-standard']
    Element("new-address-button-256").element.innerText = locale['new-address-button-256']
    Element("addr-list-used-text").element.innerText = locale['addr-list-used-text']
    Element("menu-tab-item-coldstake-label").element.innerText = locale['menu-tab-item-coldstake-label']
    Element("coldstake-pool-option-disabled-label").element.innerText = locale["coldstake-pool-option-disabled"]
    Element("coldstake-pool-option-custom-label").element.innerText = locale['coldstake-pool-option-custom']
    Element("pool-spend-addr-text").element.innerText = locale['pool-spend-addr-text']
    Element("current-vet-addr-label").element.innerText = locale['current-vet-addr-label']
    Element("pending-vet-addr-label").element.innerText = locale['pending-vet-addr-label']
    Element("menu-tab-item-fiat-label").element.innerText = locale['menu-tab-item-fiat-label']
    Element("menu-tab-item-explorer-label").element.innerText = locale['menu-tab-item-explorer-label']
    Element("pool-stats-button").element.innerText = locale['pool-stats-button']
    Element("new-cs-spend-button").element.innerText = locale['new-cs-spend-button']
    Element("menu-tab-item-version-label").element.innerText = VERSION


    # translations for the "more" tab

    Element("more-in-development-header").element.innerText = locale['more-in-development-header']
    Element("more-li-1").element.innerText = locale['more-li-1']
    Element("more-li-2").element.innerText = locale['more-li-2']
    Element("more-li-3").element.innerText = locale['more-li-3']
    Element("more-stay-tuned").element.innerText = locale['more-stay-tuned']





    # define confirms dict

    global confirm_dict

    confirm_dict = {
        0: {
            "text": locale['unconfirmed'],
            "color": "#ff4d4d"
        },
        1: {
            "text": "1 / 12",
            "color": "#f85c47"
        },
        2: {
            "text": "2 / 12",
            "color": "#f16b40"
        },
        3: {
            "text": "3 / 12",
            "color": "#eb7a3a"
        },
        4: {
            "text": "4 / 12",
            "color": "#e48833"
        },
        5: {
            "text": "5 / 12",
            "color": "#dd972d"
        },
        6: {
            "text": "6 / 12",
            "color": "#d7a627"
        },
        7: {
            "text": "7 / 12",
            "color": "#d0b520"
        },
        8: {
            "text": "8 / 12",
            "color": "#c9c41a"
        },
        9: {
            "text": "9 / 12",
            "color": "#c2d313"
        },
        10: {
            "text": "10 / 12",
            "color": "#bbe10d"
        },
        11: {
            "text": "11 / 12",
            "color": "#b5f006"
        },
        12: {
            "text": locale['confirmed'],
            "color": "#aeff00"
        },
        "orphan": {
            "text": locale['orphaned'],
            "color": "#ff4d4d"
        }
    }

    # update the tx history

    if txHistory:
        for tx in txHistory.txHistory:
            if tx['txid'] not in displayedTXID:
                continue
            if tx['confirmations'] >= 12:
                Element(f"confirm-{tx['txid']}").element.innerText = confirm_dict[12]['text']
            elif tx['confirmations'] <= 0:
                Element(f"confirm-{tx['txid']}").element.innerText = confirm_dict[0]['text']



if __name__ == "__main__":
    txHistory = None
    spendCSOut = False
    loading_message = Element("loading-message")
    loading_message.element.innerText = "Initializing SHELTR..."
    asyncio.gather(doTranslation(), api.getNodes())
    browserName = browserType()
    #print(browserName)
    clientOS = getOS()
    #print(clientOS)

    MIN_TX = 1000 # 0.00001
    
    password_input = Element("new-pass-input")
    confirm_password_input = Element("new-pass-confirm")
    new_password_input = Element("password-input")
 
    import_word_text = Element("import-word-text")

    custom_pool_input = Element("custom-pool-input")

    confirm_password_input.element.oninput = add_password_event
    password_input.element.oninput = add_password_event
    import_word_text.element.oninput = check_words_event

    new_password_input.element.onkeyup = enter_password_event

    template_dict = {
        "incoming": "icons/In-icon.png",
        "outgoing": "icons/Out-icon.png",
        "internal": "icons/Convert-icon.png",
        "stake": "icons/Staked-icon.png",
        "agvr": "icons/Agvr-icon.png",
        "orphaned": "icons/Orphaned-icon.png",
        "pool reward": "icons/Pool-staked-icon.png",
        "zap": "icons/Zap-icon.png"
        }

    explore_dict = {
        "myghost": "explorer.myghost.org",
        "ghostscan": "ghostscan.io",
        "ghostin": "cloud.ghostin.io/#"
    }

    js.document.addEventListener('touchstart', handleTouchStart, False)        
    js.document.addEventListener('touchmove', handleTouchMove, False)

    asyncio.create_task(main())
