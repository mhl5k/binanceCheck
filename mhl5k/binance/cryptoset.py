# class to handle Binance crypto values
# License: MIT
# Author: mhl5k
#  

from binance.spot import Spot as SpotClient
from ..binance.crypto import Crypto
from datetime import datetime
import json
import logging
import uuid

        
class CryptoSet:

    def getCryptoByName(self, name:str) -> Crypto:
        if name in self.allCryptos:
            return self.allCryptos[name]
        else:
            newCrypto=Crypto(setName=name,setSpotClient=self.spotClient)
            self.allCryptos[name]=newCrypto
            return newCrypto


    def printValues(self):
        for key in self.allCryptos:
            crypto=self.getCryptoByName(key)
            crypto.printValues()
            
        print("Total: %.8f BTC" % ( self.totalBTC ) )
        print("0,1 percent grow/day: %.8f BTC" % (self.totalBTC*Crypto.expectedGrowthPercentage ) )


    def updateTotalBTCofSet(self):
        print("Updating all crypto BTC values...")
        self.totalBTC=0.0
        self.totalBTCwithoutDeposits=0.0
        for key in self.allCryptos:
            crypto=self.getCryptoByName(key)
            crypto.updateTotalBTC()
            self.totalBTC+=crypto.totalBTCValue
            self.totalBTCwithoutDeposits+=crypto.totalBTCValueWithoutDeposits
            logging.debug("%s Total-BTC: %.8f" % (key, self.totalBTC))
            logging.debug("%s Total-BTC-No-Depos: %.8f" % (key, self.totalBTCwithoutDeposits))


    def toJSON(self) -> dict:
        jsonList:list = []
        for key in self.allCryptos:
            crypto:Crypto=self.allCryptos[key]
            jsonList.append(crypto.toJSON())

        jsonDict = {
            "uuid": "%s" % (self.uuid),
            "timestamp": "%s" % (self.timestamp),
            "time": "%s" % (self.time),
            "totalBTC": "{:.8f}".format(self.totalBTC),
            "totalBTCwithoutDeposits": "{:.8f}".format(self.totalBTCwithoutDeposits),
            "crypto": jsonList
        }

        logging.debug(json.dumps(jsonDict, indent=4, sort_keys=False))
        return jsonDict

    def fromJSON(self, jsonContent:dict):
        if "uuid" in jsonContent: self.uuid=jsonContent["uuid"]
        self.timestamp=float(jsonContent["timestamp"])
        self.time=jsonContent["time"]
        self.totalBTC=float(jsonContent["totalBTC"])
        logging.debug("fromJson-Total-BTC: %.8f" % (self.totalBTC))
        # version 2
        if "totalBTCwithoutDeposits" in jsonContent:
            self.totalBTCwithoutDeposits=float(jsonContent["totalBTCwithoutDeposits"])

        cryptoDict=jsonContent["crypto"]
        for cryptoContent in cryptoDict:
            asset=cryptoContent["asset"]
            newCrypto=Crypto(setName=asset,setSpotClient=self.spotClient)
            newCrypto.fromJSON(cryptoContent)
            self.allCryptos[asset]=newCrypto

    def __init__(self, setSpotClient:SpotClient):
        # binance client object
        self.spotClient=setSpotClient

        self.time:str=datetime.now()
        self.timestamp:float=self.time.timestamp()
            
        # totalBTC amount of all cryptos
        self.totalBTC:float=0.0

        # total without deposits
        self.totalBTCwithoutDeposits:float=0.0

        # dict for all cryptos
        self.allCryptos:dict = dict()

        # uuid
        self.uuid=uuid.uuid4()

