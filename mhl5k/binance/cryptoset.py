# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging
import uuid

from binance.spot import Spot as SpotClient
from ..binance.crypto import Crypto


class CryptoSet:

    class CryptoSetTotal:

        def __init__(self, currencyName:str):
            self.name:str=currencyName
            self.total:float=0.0
            self.deposit:float=0.0
            self.totalWithoutDeposits:float=0.0

        def updateTotals(self,allCryptos:dict):

            # update all cryptos totals
            for ckey in allCryptos:
                c:Crypto=allCryptos[ckey]
                logging.debug("Updating crypto %s" % (ckey))
                currentTotal=c.updateTotalIn(self.name)
                self.total+=currentTotal.total
                self.deposit+=currentTotal.deposit
                self.totalWithoutDeposits+=currentTotal.totalWithoutDeposits

            logging.debug(f"{self.name} Totals: {self.total:.8f}, Total-WithoutDeposit: {self.totalWithoutDeposits:.8f}")

        def toJSON(self) -> dict:
            jsonDict = {
                # v4
                "name": self.name,
                "total": "{:.8f}".format(self.total),
                "deposit": "{:.8f}".format(self.deposit),
                "totalWithoutDeposits": "{:.8f}".format(self.totalWithoutDeposits)
            }

            logging.debug(json.dumps(jsonDict, indent=4, sort_keys=False))
            return jsonDict

        def fromJSON(self, jsonContent:dict):
            self.name=jsonContent["name"]
            self.total=float(jsonContent["total"])
            self.deposit=float(jsonContent["deposit"])
            self.totalWithoutDeposits=float(jsonContent["totalWithoutDeposits"])

    def getCryptoByName(self, name:str) -> Crypto:
        if name in self.allCryptos:
            return self.allCryptos[name]
        else:
            newCrypto=Crypto(setName=name,setSpotClient=self.spotClient)
            self.allCryptos[name]=newCrypto
            return newCrypto

    def updateTotalsOfSet(self):
        print("Updating all crypto values to BTC and FIAT...")
        self.totalBTC.updateTotals(self.allCryptos)
        self.totalUSDT.updateTotals(self.allCryptos)

    def toJSON(self) -> dict:
        cryptoList:list = []
        crypto:Crypto=None
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
            newCrypto=Crypto(setName=asset,setSpotClient=self.spotClient)
            newCrypto.fromJSON(cryptoContent)
            self.allCryptos[asset]=newCrypto
        # v1
        self.totalBTC.total=float(jsonContent["totalBTC"])
        # v2
        if "totalBTCwithoutDeposits" in jsonContent:
            self.totalBTC.totalWithoutDeposits=float(jsonContent["totalBTCwithoutDeposits"])
        # v3
        if "totals" in jsonContent:
            if "BTC" in jsonContent["totals"]:
                self.totalBTC.fromJSON(jsonContent["totals"]["BTC"])
            if "USDT" in jsonContent["totals"]:
                self.totalUSDT.fromJSON(jsonContent["totals"]["USDT"])

    def __init__(self, setSpotClient:SpotClient):
        # binance client object
        self.spotClient=setSpotClient

        self.time:str=datetime.now()
        self.timestamp:float=self.time.timestamp()

        # dict for all cryptos
        self.allCryptos:dict = dict()

        # uuid
        self.uuid=uuid.uuid4()

        # totals in different currencies
        self.totalBTC=CryptoSet.CryptoSetTotal("BTC")
        self.totalUSDT=CryptoSet.CryptoSetTotal("USDT")
