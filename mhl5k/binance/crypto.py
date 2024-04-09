# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

import json
import logging

from binance.spot import Spot as SpotClient


class Crypto:
    # shared across instances
    expectedGrowthPercentage:float=0.001

    def getTotal(self) -> float:
        return self.orderWalletTotal+self.liquidSwapValue+self.earnFlexible+self.earnStaking+self.earnPlan

    def addToWalletAndOrderValue(self,toAddFree:float,toAddLocked:float):
        self.orderWalletFree+=toAddFree
        self.orderWalletLocked+=toAddLocked
        self.orderWalletTotal+=toAddFree+toAddLocked

    def addToLiquidityValue(self,toAdd:float):
        self.liquidSwapValue+=toAdd

    def addToFlexible(self,toAdd:float):
        self.earnFlexible+=toAdd

    def addToStaking(self,toAdd:float):
        self.earnStaking+=toAdd

    def addToPlan(self,toAdd:float):
        self.earnPlan+=toAdd
        
    def addToPaymentDeposit(self,toAdd:float):
        self.paymentDeposit+=toAdd

    def addToPaymentWithdraw(self,toAdd:float):
        self.paymentWithdraw+=toAdd

    def updateTotalBTC(self):
        self.totalBTCValue=self.getPriceForCrypto(self.name,self.getTotal())
        self.totalBTCValueWithoutDeposits=self.totalBTCValue-self.getPriceForCrypto(self.name,self.paymentDeposit)

    def printValues(self):
        total=self.getTotal()
        print("%s: orderWallet: %.8f, liquidValue: %.8f, savingsValue: %.8f" % (self.name,self.orderWalletTotal,self.liquidSwapValue,self.earnFlexible))
        print("total: %.8f, grow0.1: %.8f inBTC: %.8f, growBTC0.1: %.8f" % (total, total*self.expectedGrowthPercentage, self.totalBTCValue, self.totalBTCValue*self.expectedGrowthPercentage))

    def toJSON(self) -> dict:
        jsonDict = {
            # V1
            "asset": self.name,
            "orderWalletFree": "{:.8f}".format(self.orderWalletFree),
            "orderWalletLocked": "{:.8f}".format(self.orderWalletLocked),
            "orderWalletTotal": "{:.8f}".format(self.orderWalletTotal),
            "savingsWalletFlexible": "{:.8f}".format(self.earnFlexible),
            "liquidSwapValue": "{:.8f}".format(self.liquidSwapValue),
            "totalValue": "{:.8f}".format(self.getTotal()),
            "expectedGrowthPercentage": "{:.8f}".format(self.getTotal()*self.expectedGrowthPercentage),
            "totalBTCValue": "{:.8f}".format(self.totalBTCValue),
            # V2
            "paymentDeposit": "{:.8f}".format(self.paymentDeposit),
            # V3
            "earnStaking": "{:.8f}".format(self.earnStaking),
            "earnPlan": "{:.8f}".format(self.earnPlan),
        }
        logging.debug(json.dumps(jsonDict, indent=4, sort_keys=False))
        return jsonDict

    def fromJSON(self, jsonContent:dict):
        self.name=jsonContent["asset"]
        self.orderWalletFree=float(jsonContent["orderWalletFree"])
        self.orderWalletLocked=float(jsonContent["orderWalletLocked"])
        self.orderWalletTotal=float(jsonContent["orderWalletTotal"])
        self.liquidSwapValue=float(jsonContent["liquidSwapValue"])
        self.earnFlexible=float(jsonContent["savingsWalletFlexible"])
        self.totalBTCValue=float(jsonContent["totalBTCValue"])
        # version 2
        if "paymentDeposit" in jsonContent:
            self.paymentDeposit=float(jsonContent["paymentDeposit"])
        # version 3
        if "earnStaking" in jsonContent:
            self.earnStaking=float(jsonContent["earnStaking"])
        if "earnPlan" in jsonContent:
            self.earnPlan=float(jsonContent["earnPlan"])

    # return price/value for a given crypto name and amount
    # default conversion is to BTC, but can every crypto
    # if not found, function will try to convert over USDT
    # can be called from outside
    def getPriceForCrypto(self,fromCrypto: str, fromCryptoAmount: float, toCrypto: str = "BTC") -> float:
        valueForCrypto=0.0
        retry=True
        while retry:
            retry=False
            logging.debug("Try to convert %.8f %s to %s" % (fromCryptoAmount, fromCrypto, toCrypto))
            if fromCrypto==toCrypto:
                ticker=toCrypto+" given, no conversion ;-)"
                valueForCrypto=fromCryptoAmount
            else:
                try:
                    # try e.g. CRYPTO-BTC first
                    ticker=self.spotClient.ticker_price(fromCrypto+toCrypto)
                    valueForCrypto=fromCryptoAmount*float(ticker["price"])
                except:
                    try:
                        # not found, then try e.g. BTC-CRYPTO second
                        ticker=self.spotClient.ticker_price(toCrypto+fromCrypto)
                        valueForCrypto=fromCryptoAmount/float(ticker["price"])
                    except:
                        # not found, go to check whether crypto USDT ticker exisits
                        # if yes, convert to USDT and then repeat again to check against 
                        # given conversion crypto
                        # if USDT not found return with not found
                        if toCrypto=="BTC":
                            usdtValue=self.getPriceForCrypto(fromCrypto,fromCryptoAmount,toCrypto="USDT")
                            if (usdtValue>0.0):
                                retry=True
                                fromCrypto="USDT"
                                fromCryptoAmount=usdtValue
                            else:
                                ticker="Ticker conversion "+fromCrypto+ " to "+toCrypto+" not found"
                        else:
                            ticker="Ticker conversion "+fromCrypto+ " to "+toCrypto+" not found"

        logging.debug(ticker)
        logging.debug("%s price: %.8f" % (toCrypto,valueForCrypto) )
        return valueForCrypto

    def __init__(self, setName:str, setSpotClient:SpotClient):
        self.name=setName
        self.spotClient=setSpotClient

        self.totalBTCValue:float = 0.0
        self.totalBTCValueWithoutDeposits:float = 0.0

        self.orderWalletLocked:float=0.0
        self.orderWalletFree:float=0.0
        self.orderWalletTotal:float = 0.0

        self.liquidSwapValue:float = 0.0
        self.earnFlexible:float = 0.0
        self.earnStaking:float = 0.0
        self.earnPlan:float = 0.0

        self.paymentDeposit:float = 0.0
        self.paymentWithdraw:float = 0.0
