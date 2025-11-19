# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

import json
import logging

from binance.spot import Spot as SpotClient
# import binance api exceptions
from binance.error import ClientError


class Crypto:

    class ConvertedTotal:
        def __init__(self, name:str):
            self.name:str=name
            self.total:float=0.0
            self.deposit:float=0.0

        def set(self, total:float, deposit:float):
            self.total=total
            self.deposit=deposit

        def toJSON(self) -> dict:
            jsonDict = {
                # v4
                "name": self.name,
                "total": "{:.8f}".format(self.total),
                "deposit": "{:.8f}".format(self.deposit),
            }

            return jsonDict

        def fromJSON(self, jsonContent:dict):
            self.name=jsonContent["name"]
            self.total=float(jsonContent["total"])
            self.deposit=float(jsonContent["deposit"])

    # shared across instances
    expectedGrowthPercentage:float=0.001

    def getTotal(self) -> float:
        return self.orderWalletTotal+self.liquidSwapValue+self.earnFlexible+self.earnLocked

    def addToWalletAndOrderValue(self,toAddFree:float,toAddLocked:float):
        self.orderWalletFree+=toAddFree
        self.orderWalletLocked+=toAddLocked
        self.orderWalletTotal+=toAddFree+toAddLocked

    def addToLiquidityValue(self,toAdd:float):
        self.liquidSwapValue+=toAdd

    def addToFlexible(self,toAdd:float):
        self.earnFlexible+=toAdd

    def addToLocked(self,toAdd:float):
        self.earnLocked+=toAdd

    def addToPlan(self,toAdd:float):
        self.earnPlan+=toAdd

    def addToPaymentDeposit(self,toDeposit:float):
        self.paymentDeposit+=toDeposit

    def addToPaymentWithdraw(self,toWithdraw:float):
        self.paymentWithdraw+=toWithdraw

    def updateTotalIn(self,toSymbol:str) -> ConvertedTotal:
        try:
            logging.debug(f"Updating total {toSymbol} for {self.name}")
            total:float=self._getPriceForCrypto(self.name,self.getTotal(),toSymbol)

            logging.debug("Updating total Deposit in {toSymbol} for {self.name}")
            deposit:float=self._getPriceForCrypto(self.name,self.paymentDeposit,toSymbol)

            t:Crypto.ConvertedTotal=Crypto.ConvertedTotal(toSymbol)
            t.set(total,deposit)
            self.allTotals.append(t)

            return t

        except ClientError as E:
            raise E

    def toJSON(self) -> dict:
        totalList:list = []
        entry:Crypto.ConvertedTotal = None
        for entry in self.allTotals:
            totalList.append(entry.toJSON())

        jsonDict = {
            # V1
            "asset": self.name,
            "orderWalletFree": "{:.8f}".format(self.orderWalletFree),
            "orderWalletLocked": "{:.8f}".format(self.orderWalletLocked),
            "orderWalletTotal": "{:.8f}".format(self.orderWalletTotal),
            "liquidSwapValue": "{:.8f}".format(self.liquidSwapValue),
            "totalValue": "{:.8f}".format(self.getTotal()),
            "expectedGrowthPercentage": "{:.8f}".format(self.getTotal()*self.expectedGrowthPercentage),
            # V2
            "paymentDeposit": "{:.8f}".format(self.paymentDeposit),
            # V3
            "earnPlan": "{:.8f}".format(self.earnPlan),
            # V4
            "convertedTotal": totalList,
            # V5
            "earnFlexible": "{:.8f}".format(self.earnFlexible),
            "earnLocked": "{:.8f}".format(self.earnLocked),
            # V6
            "growth": self.growth
        }

        logging.debug(json.dumps(jsonDict, indent=4, sort_keys=False))
        return jsonDict

    def fromJSON(self, jsonContent:dict):
        self.name=jsonContent["asset"]
        self.orderWalletFree=float(jsonContent["orderWalletFree"])
        self.orderWalletLocked=float(jsonContent["orderWalletLocked"])
        self.orderWalletTotal=float(jsonContent["orderWalletTotal"])
        self.liquidSwapValue=float(jsonContent["liquidSwapValue"])
        # version 1, migrated in 4 to convertedTotal
        if "savingsWalletFlexible" in jsonContent:
            self.earnFlexible=float(jsonContent["savingsWalletFlexible"])
        if "totalBTCValue" in jsonContent:
            totalBTCValue=float(jsonContent["totalBTCValue"])
            btcTotal=Crypto.ConvertedTotal("BTC")
            btcTotal.set(totalBTCValue,0.0)
            self.allTotals.append(btcTotal)

        # version 3
        if "earnStaking" in jsonContent:
            self.earnLocked=float(jsonContent["earnStaking"])
        if "earnPlan" in jsonContent:
            self.earnPlan=float(jsonContent["earnPlan"])
        # version 4
        if "convertedTotal" in jsonContent:
            clist:list=jsonContent["convertedTotal"]
            for entry in clist:
                c=Crypto.ConvertedTotal(entry["name"])
                c.fromJSON(entry)
                self.allTotals.append(c)
        # version 5
        if "earnFlexible" in jsonContent:
            self.earnFlexible=float(jsonContent["earnFlexible"])
        if "earnLocked" in jsonContent:
            self.earnLocked=float(jsonContent["earnLocked"])
        # version 6
        if "growth" in jsonContent:
            self.growth = str(jsonContent["growth"])

    def _getPriceFromBinance(self,symbol: str) -> float:
        # get price from gathered tickers if possible
        if symbol in self.allGatheredPriceTickers:
            logging.debug(f"Found price for {symbol} in gathered tickers: {self.allGatheredPriceTickers[symbol]}")
            return self.allGatheredPriceTickers[symbol]
        else:
            # get price from binance
            try:
                logging.debug(f"Getting price from binance for {symbol}")
                ticker=self.spotClient.ticker_price(symbol)
                price:float = float(ticker["price"])
                self.allGatheredPriceTickers[symbol]=price
                logging.debug(f"Gathering price for {symbol}: {price}")
                return float(price)
            except ClientError as E:
                raise E

    # return price/value for a given crypto name and amount
    # default conversion is to BTC, but can every crypto
    # if not found, function will try to convert over USDC
    # can be called from outside
    def _getPriceForCrypto(self,fromCrypto:str, fromCryptoAmount:float, toCrypto:str) -> float:
        valueForCrypto=0.0

        # try to convert
        logging.debug(f"--- getPriceForCrypto --- {fromCrypto}{toCrypto}  ---")
        logging.debug(f"Try to convert {fromCryptoAmount:.8f} {fromCrypto} to {toCrypto}")

        # try to get price for given crypto
        if fromCrypto==toCrypto:
            logging.debug(toCrypto+" given, no conversion required ;)")
            valueForCrypto=fromCryptoAmount
        else:
            try:
                # try e.g. CRYPTO-BTC first
                price=self._getPriceFromBinance(fromCrypto+toCrypto)
                valueForCrypto=fromCryptoAmount*float(price)
            except ClientError:
                try:
                    # not found, then try other way around: e.g. BTC-CRYPTO
                    logging.debug(f"Ticker not found {fromCrypto} to {toCrypto}!")
                    logging.debug(f"Trying to get {toCrypto} to {fromCrypto}")
                    price=self._getPriceFromBinance(toCrypto+fromCrypto)
                    valueForCrypto=fromCryptoAmount/float(price)
                except ClientError:
                    # nothing found, raise error
                    logging.debug(f"Ticker not found {toCrypto} to {fromCrypto}!")
                    if toCrypto!="USDC" and fromCrypto!="USDC":
                        logging.debug("Trying to get a USDC variant")
                        USDCValue=self._getPriceForCrypto(fromCrypto, fromCryptoAmount, "USDC")
                        # has USDC then USDC to btc
                        valueForCrypto=self._getPriceForCrypto("USDC", USDCValue, "BTC")
                    else:
                        # trading to BTC or USDC does not exists
                        valueForCrypto=0.0

        logging.debug(f"{fromCrypto} to {toCrypto} price: {valueForCrypto:.8f}")
        return valueForCrypto

    def __init__(self, setName:str, setSpotClient:SpotClient):
        self.name=setName
        self.spotClient=setSpotClient

        self.orderWalletLocked:float=0.0
        self.orderWalletFree:float=0.0
        self.orderWalletTotal:float = 0.0

        self.liquidSwapValue:float = 0.0
        self.earnFlexible:float = 0.0
        self.earnLocked:float = 0.0
        self.earnPlan:float = 0.0

        self.paymentDeposit:float = 0.0
        self.paymentWithdraw:float = 0.0

        # dict of all gathered ticker prices
        self.allGatheredPriceTickers:dict = {}

        # dict for all totals in different currencies
        self.allTotals:list = []

        # set whether crypto has a earn flexible or locked possibility
        self.hasFlexiblePossibility:bool = False
        self.canUseFlexible:bool = False
        self.hasLockedPossibility:bool = False
        self.canUseLocked:bool = False

        # volumes
        self.growth:str = "none"
