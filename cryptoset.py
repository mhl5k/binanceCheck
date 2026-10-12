# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging
import uuid

from binance_sdk_wallet import Wallet
from crypto import Crypto, PriceUnavailableError


class CryptoSet:

    class CryptoSetTotal:

        def __init__(self, currencyName:str):
            self.name:str=currencyName
            self.total:float=0.0
            self.deposit:float=0.0

        def updateTotals(self,allCryptos:dict):
            self.total = 0.0
            self.deposit = 0.0
            # update all cryptos totals
            c:Crypto = None
            for c in allCryptos.values():
                try:
                    logging.debug(f"Updating crypto {c.name}")
                    currentTotal=c.updateTotalIn(self.name)
                    self.total+=currentTotal.total
                    self.deposit+=currentTotal.deposit
                except PriceUnavailableError as E:
                    if self.name in ("USDC", "USDT"):
                        unavailable = c.getConvertedTotalByName(self.name)
                        if unavailable is None:
                            unavailable = Crypto.ConvertedTotal(self.name)
                            c.allTotals.append(unavailable)
                        unavailable.set(None, None)
                    logging.error(f"Error updating crypto {c.name}: {E}")

            logging.debug(f"{self.name} Total: {self.total:.8f}, Total-Deposit: {self.deposit:.8f}")

        def toJSON(self) -> dict:
            jsonDict = {
                # v4
                "name": self.name,
                "total": "{:.8f}".format(self.total),
                "deposit": "{:.8f}".format(self.deposit),
            }

            logging.debug(json.dumps(jsonDict, indent=4, sort_keys=False))
            return jsonDict

        def fromJSON(self, jsonContent:dict):
            self.name=jsonContent["name"]
            self.total=float(jsonContent["total"])
            self.deposit=float(jsonContent["deposit"])

    def getCryptoByName(self, name:str) -> Crypto:
        if name in self.allCryptos:
            return self.allCryptos[name]
        else:
            newCrypto=Crypto(setName=name,setWalletClient=self.walletClient)
            self.allCryptos[name]=newCrypto
            return newCrypto

    def sortByName(self):
        # sort the dict
        self.allCryptos = dict(sorted(self.allCryptos.items(), key=lambda x: x[0]))

    @property
    def cryptoCount(self) -> int:
        # Derive from holdings so older datasets and newly gathered sets agree.
        return sum(crypto.getTotal() > 0 for crypto in self.allCryptos.values())

    def updateTotalsOfSet(self):
        print("Updating all crypto values to BTC and FIAT...")
        self.totalBTC.updateTotals(self.allCryptos)
        self.totalUSDC.updateTotals(self.allCryptos)
        fallbackCryptos = {
            name: crypto for name, crypto in self.allCryptos.items()
            if crypto.getConvertedTotalByName("USDC").total is None
        }
        self.totalUSDT.updateTotals(fallbackCryptos)

    def toJSON(self) -> dict:
        cryptoList:list = []
        for crypto in self.allCryptos.values():
            cryptoList.append(crypto.toJSON())

        jsonDict = {
            # v4
            "uuid": "%s" % (self.uuid),
            "timestamp": "%s" % (self.timestamp),
            "time": "%s" % (self.time),
            "crypto": cryptoList,
            "totals": {
                "BTC": self.totalBTC.toJSON(),
                "USDC": self.totalUSDC.toJSON(),
                "USDT": self.totalUSDT.toJSON()
            }
        }

        logging.debug(json.dumps(jsonDict, indent=4, sort_keys=False))
        return jsonDict

    def fromJSON(self, jsonContent:dict):
        # v1
        if "uuid" in jsonContent:
            self.uuid=jsonContent["uuid"]
        self.timestamp=float(jsonContent["timestamp"])
        self.time=jsonContent["time"]
        # go through all cryptos
        cryptoDict=jsonContent["crypto"]
        for cryptoContent in cryptoDict:
            asset=cryptoContent["asset"]
            newCrypto=Crypto(setName=asset,setWalletClient=self.walletClient)
            newCrypto.fromJSON(cryptoContent)
            self.allCryptos[asset]=newCrypto
        # v1
        if "totalBTC" in jsonContent:
            self.totalBTC.total=float(jsonContent["totalBTC"])
        # v3
        if "totals" in jsonContent:
            if "BTC" in jsonContent["totals"]:
                self.totalBTC.fromJSON(jsonContent["totals"]["BTC"])
            if "USDT" in jsonContent["totals"]:
                self.totalUSDT.fromJSON(jsonContent["totals"]["USDT"])
            # v4
            if "USDC" in jsonContent["totals"]:
                self.totalUSDC.fromJSON(jsonContent["totals"]["USDC"])

    def __init__(self, setWalletClient:Wallet):
        # binance client object
        self.walletClient=setWalletClient

        currentdatetime = datetime.now()
        self.time:str=str(currentdatetime)
        self.timestamp:float=currentdatetime.timestamp()

        # dict for all cryptos
        self.allCryptos:dict[str, Crypto] = {}

        # uuid
        self.uuid=uuid.uuid4()

        # totals in different currencies
        self.totalBTC=CryptoSet.CryptoSetTotal("BTC")
        self.totalUSDC=CryptoSet.CryptoSetTotal("USDC")
        self.totalUSDT=CryptoSet.CryptoSetTotal("USDT")
