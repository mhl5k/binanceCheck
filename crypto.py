# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

import json
import logging

from binance.spot import Spot as SpotClient


class PriceConversion:

    # all price tickers
    allAssets:list[str] = []
    allGatheredPriceTickers:dict[str, float] = {}

    @staticmethod
    def init(accountData,spotClient:SpotClient):
        logging.debug("Generating list of all assets")
        PriceConversion.allAssets = [entry["asset"] for entry in accountData["balances"]]

        logging.debug("Initializing price ticker once from binance...")
        rawlist=spotClient.ticker_price()
        # convert to dict with "ETHBTC":"0.03270000","LTCBTC":"0.00097200"
        PriceConversion.allGatheredPriceTickers = {
            entry["symbol"]: float(entry["price"]) for entry in rawlist
        }
        logging.debug(json.dumps(PriceConversion.allGatheredPriceTickers, indent=4, sort_keys=False))

    @staticmethod
    def _getPriceFromGatheredPriceTickers(symbolPair: str) -> float:
        # check whether symbol is in gathered tickers
        if symbolPair in PriceConversion.allGatheredPriceTickers:
            price:float = float(PriceConversion.allGatheredPriceTickers[symbolPair])
            logging.debug(f"Found price for {symbolPair} in gathered tickers: {price}")
            return price
        else:
            error=f"Price for {symbolPair} not found in gathered tickers!"
            logging.debug(error)
            raise ValueError(error)

    # return price/value for a given crypto name and amount
    # default conversion is to BTC, but can every crypto
    # if not found, function will try to convert over USDC
    # can be called from outside
    @staticmethod
    def getPriceForCrypto(fromCrypto:str, fromCryptoAmount:float, toCrypto:str, allowRoute:bool=True) -> float:
        # try to convert
        logging.debug(f"--- getPriceForCrypto --- {fromCrypto}{toCrypto}  ---")
        logging.debug(f"Try to convert {fromCryptoAmount:.8f} {fromCrypto} to {toCrypto}")

        # 1. No conversion needed
        if fromCrypto==toCrypto:
            logging.debug(toCrypto+" given, no conversion required.")
            return fromCryptoAmount

        # 2. Direct Pair: e.g. ETHBTC
        pair = fromCrypto + toCrypto
        try:
            price = PriceConversion._getPriceFromGatheredPriceTickers(pair)
            value_for_crypto = fromCryptoAmount * price
            logging.debug(f"Using direct pair {pair}: {value_for_crypto:.8f} {toCrypto}")
            return value_for_crypto
        except ValueError:
            logging.debug(f"Direct pair {pair} not found.")

        # 3. Reverse Pair: e.g. BTCETH
        reverse_pair = toCrypto + fromCrypto
        try:
            price = PriceConversion._getPriceFromGatheredPriceTickers(reverse_pair)
            value_for_crypto = fromCryptoAmount / price
            logging.debug(f"Using reverse pair {reverse_pair}: {value_for_crypto:.8f} {toCrypto}")
            return value_for_crypto
        except ValueError:
            logging.debug(f"Reverse pair {reverse_pair} not found.")

        # 4. Fallback: over USDC, if possible
        route_list = ["USDC", "USDT"]
        if allowRoute:
            for route_over in route_list:
                if fromCrypto != route_over and toCrypto != route_over:
                    try:
                        logging.debug(f"Trying to route over {route_over}...")
                        routed_value = PriceConversion.getPriceForCrypto(fromCrypto, fromCryptoAmount, route_over, False)
                        value_for_crypto = PriceConversion.getPriceForCrypto(route_over, routed_value, toCrypto, False)
                        logging.debug(f"{route_over} routed {fromCrypto}->{toCrypto}: {value_for_crypto:.8f} {toCrypto}")
                        return value_for_crypto
                    except ValueError:
                        logging.debug(f"Routing over {route_over} failed for {fromCrypto}->{toCrypto}!")

        # 5. Alles gescheitert -> Debughilfe + Fehler
        # mögliche Paare zum Debuggen ausgeben
        possible_pairs = []
        for key in PriceConversion.allGatheredPriceTickers:
            if key.startswith(fromCrypto) or key.endswith(fromCrypto):
                possible_pairs.append(key)

        # nach außen klar signalisieren: keine Conversion möglich
        raise ValueError(f"Cannot convert {fromCrypto} to {toCrypto}, possible pairs: {possible_pairs if len(possible_pairs)>0 else 'none'}")


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
            total:float=PriceConversion.getPriceForCrypto(self.name,self.getTotal(),toSymbol)

            logging.debug(f"Updating total Deposit in {toSymbol} for {self.name}")
            deposit:float=PriceConversion.getPriceForCrypto(self.name,self.paymentDeposit,toSymbol)

            t:Crypto.ConvertedTotal=Crypto.ConvertedTotal(toSymbol)
            t.set(total,deposit)
            self.allTotals.append(t)

            return t

        except ValueError as E:
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
            # V2
            "paymentDeposit": "{:.8f}".format(self.paymentDeposit),
            # V3
            "earnPlan": "{:.8f}".format(self.earnPlan),
            # V4
            "convertedTotal": totalList,
            # V5
            "earnFlexible": "{:.8f}".format(self.earnFlexible),
            "earnLocked": "{:.8f}".format(self.earnLocked),
            # V7
            "klines": self.monthKlines
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
            self.rating = str(jsonContent["growth"])
        # version 7
        if "klines" in jsonContent:
            self.monthKlines=jsonContent["klines"]

    def getConvertedTotalByName(self, totalSymbol: str) -> "Crypto.ConvertedTotal | None":
        """
        Returns the Crypto.ConvertedTotal object for the given crypto symbol.

        :param totalSymbol: the symbol of the crypto to find the total for
        :return: the Crypto.ConvertedTotal object for the given crypto symbol, or None if not found
        """
        for entry in self.allTotals:
            if entry.name == totalSymbol:
                return entry
        return None

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

        # dict for all totals in different currencies
        self.allTotals:list[Crypto.ConvertedTotal] = []

        # set whether crypto has a earn flexible or locked possibility
        self.hasFlexiblePossibility:bool = False
        self.canUseFlexible:bool = False
        self.hasLockedPossibility:bool = False
        self.canUseLocked:bool = False

        # monthly klines for volume and price calculations
        self.monthKlines:dict = {
            "symbol": "USDC",
            "volumes": [],
            "closes": []
        }

        # rating
        self.rating: str = "Rating not yet calculated"
