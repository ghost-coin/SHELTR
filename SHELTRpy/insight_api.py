import asyncio  # important!!
import json, time, random
from html.parser import HTMLParser

from SHELTRpy.request import request

from functools import wraps


def timeoutPing(func):
    @wraps(func)
    async def decorator(*args, **kwargs):
        try:
            results = await asyncio.wait_for(func(*args, **kwargs), timeout=10)
            return results
        except asyncio.TimeoutError:
            return (args[1], -1)
        except Exception as e:
            return (args[1], -1)
    return decorator

def timeout(func):
    @wraps(func)
    async def decorator(*args, **kwargs):
        if not args[0].BASE_URL:
            await args[0].getNodes()
        
        retry_count = 0
        
        while True:
            try:
                results = await asyncio.wait_for(func(*args, **kwargs), timeout=30)
                return results
            except asyncio.TimeoutError:
                nodes = await args[0].getNodes()
                if retry_count >= 3:
                    return -1
                retry_count += 1
                if not nodes:
                    return -1
            except Exception as e:
                nodes = await args[0].getNodes()
                if retry_count >= 3:
                    return -1
                retry_count += 1
                if not nodes:
                    return -1
    
    return decorator


class Api:
    def __init__(self):
        self.headers = {"Content-type": "application/json; charset=utf-8"}
        
        self.BASE_URL = None
        self.urls = []
        
        self.nodes = ["https://api.tuxprint.com", "https://api2.tuxprint.com", "https://socket.tuxprint.com:52555", "https://api3.tuxprint.com"]

    async def randomNode(self):
        self.BASE_URL = random.choice(self.urls)

    async def getNodes(self):
        tasks = []
        for url in self.nodes:
            tasks.append(self.pingNode(url))
        
        results = sorted(await asyncio.gather(*tasks), key=lambda a: a[1])
        
        
        for node in results.copy():
            if node[1] < 0:
                results.remove(node)
        self.BASE_URL = results[0][0]
        self.urls = [url[0] for url in results]
        
        return [url[0] for url in results]
    
    @timeout
    async def getBlock(self, blockHash):
        response = await request(f"{self.BASE_URL}/api/block/{blockHash}/", method="GET", headers=self.headers)
        blockinfo = await response.json()

        return blockinfo
    
    @timeout
    async def getBlockHash(self, blockIndex):
        response = await request(f"{self.BASE_URL}/api/block-index/{blockIndex}/", method="GET", headers=self.headers)
        blockHash = await response.json()

        return blockHash['blockHash']

    @timeout
    async def getTx(self, txid):
        response = await request(f"{self.BASE_URL}/api/tx/{txid}/", method="GET", headers=self.headers)
        txinfo = await response.json()

        return txinfo

    @timeout
    async def getAddrHistory(self, addr):
        response = await request(f"{self.BASE_URL}/api/addr/{addr}/", method="GET", headers=self.headers)
        addrinfo = await response.json()

        return addrinfo

    @timeout
    async def getAddrBalance(self, addr):
        response = await request(f"{self.BASE_URL}/api/addr/{addr}/balance/", method="GET", headers=self.headers)
        addrBalance = await response.json()

        return addrBalance

    @timeout
    async def getAddrReceived(self, addr):
        response = await request(f"{self.BASE_URL}/api/addr/{addr}/totalReceived/", method="GET", headers=self.headers)
        totalReceived = await response.json()

        return totalReceived

    @timeout
    async def getAddrSent(self, addr):
        response = await request(f"{self.BASE_URL}/api/addr/{addr}/totalSent/", method="GET", headers=self.headers)
        totalSent = await response.json()

        return totalSent

    @timeout
    async def getAddrUnconfirmedBalance(self, addr):
        response = await request(f"{self.BASE_URL}/api/addr/{addr}/unconfirmedBalance/", method="GET", headers=self.headers)
        unconfirmedBalance = await response.json()

        return unconfirmedBalance

    @timeout
    async def getAddrUtxo(self, addr):
        response = await request(f"{self.BASE_URL}/api/addr/{addr}/utxo/", method="GET", headers=self.headers)
        utxo = await response.json()

        return utxo

    @timeout
    async def getMultiAddrUtxo(self, addr):
        response = await request(f"{self.BASE_URL}/api/addrs/{addr}/utxo/", method="GET", headers=self.headers)
        utxo = await response.json()

        return utxo

    @timeout
    async def getMultiAddrTx(self, addr, startIdx=0, endIdx=0):
        response = await request(f"{self.BASE_URL}/api/addrs/{addr}/txs?from={startIdx}&to={endIdx}/", method="GET", headers=self.headers)
        tx = await response.json()

        return tx

    @timeout
    async def getTxByBlock(self, blockHash):
        response = await request(f"{self.BASE_URL}/api/txs/?block={blockHash}/", method="GET", headers=self.headers)
        txs = await response.json()

        return txs

    @timeout
    async def getTxByAddr(self, addr):
        response = await request(f"{self.BASE_URL}/api/txs/?address={addr}/", method="GET", headers=self.headers)
        txs = await response.json()

        return txs
    
    @timeout
    async def getTxByAddrPost(self, addr, startIdx=0, endIdx=0):
        body = json.dumps({"addrs": addr, "from": startIdx, "to": endIdx})
        try:
            new_post = await request(f"{self.BASE_URL}/api/addrs/txs/", body=body, method="POST", headers=self.headers)
        except Exception as e:
            print(e)
        txs = await new_post.json()

        return txs

    @timeout
    async def sendTx(self, rawTx):
        body = json.dumps({"rawtx": rawTx})
        new_post = await request(f"{self.BASE_URL}/api/tx/send/", body=body, method="POST", headers=self.headers)
        txid = await new_post.json()

        return txid['txid']

    async def getVetlist(self):
        response = await request(f"https://explorer.myghost.org/ext/getvetlist/", method="GET", headers=self.headers)
        vets = await response.json()

        return vets['vetlist']

    async def getPrice(self, currency):
        response = await request(f"https://api.coingecko.com/api/v3/simple/price?vs_currencies={currency}&ids=ghost-by-mcafee", method="GET", headers=self.headers)
        price = await response.json()

        return price['ghost-by-mcafee'][currency]
    
    @timeout
    async def getMultiAddrUtxoPost(self, addr):
        body = json.dumps({"addrs": addr})
        try:
            new_post = await request(f"{self.BASE_URL}/api/addrs/utxo/", body=body, method="POST", headers=self.headers)
        except Exception as e:
            print(e)
        utxo = await new_post.json()

        return utxo

    async def getStakingInfo(self, pool, addr):
        apiSubs = {"пул.гост.рус": "www.апи.гост.рус"}

        if pool in apiSubs:
            pool = apiSubs[pool]

        response = await request(f"https://{pool}/api/address/{addr}/", method="GET", headers=self.headers)
        poolData = str(await response.bytes())

        parser = MyHTMLParser()
        parser.apiData = []
        parser.feed(poolData)

        keepNext = False
        nextKey = ""

        parsedHtml = {"Accumulated": "0.00000000", "" "Payout Pending": "0.00000000", "Paid Out": "0.00000000", "Last Total Staking": "0.00000000", "Current Total in Pool": "0.00000000"}

        for i in parser.apiData:
            if i[:-1] in parsedHtml:
                if keepNext:
                    parsedHtml[nextKey] = i
                    keepNext = False
                    nextKey = ""
                else:
                    keepNext = True
                    nextKey = i[:-1]
            
            else:
                if keepNext:
                        parsedHtml[nextKey] = i
                        keepNext = False
                        nextKey = ""
        
        return parsedHtml

    async def getPools(self):
        response = await request(f"https://raw.githubusercontent.com/ghost-coin/ghost-coldstaking-pools/master/list.json", method="GET", headers=self.headers)
        price = await response.json()

        return price

    async def getLang(self, lang):
        response = await request(f"/translations/{lang}.json", method="GET", headers=self.headers)
        translation = await response.json()

        return translation
    
    @timeoutPing
    async def pingNode(self, url):
        start = time.time()
        try:
            response = await request(f"{url}/ping/", method="GET", headers=self.headers)
        except:
            return (url, -1)
        return (url, time.time() - start)



class MyHTMLParser(HTMLParser):
    apiData = []
    
    def handle_data(self, data):
        self.apiData.append(data)