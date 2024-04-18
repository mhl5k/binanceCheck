# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging
from operator import itemgetter
import talib
import numpy

from binance.spot import Spot as SpotClient
from binance.error import ClientError
from ..settings import Settings
from ..colors import Colors
from ..files import Files
from .crypto import Crypto
from .cryptoset import CryptoSet


def printSection(sec: str):
    sep="-" * len(sec)
    print(f"\n{sep}")
    print(sec)
    print(sep)


class BinanceDataSet:

    def __init__(self, settings:Settings):
        self.spotClient = SpotClient(settings.current["apiKey"], settings.current["apiSecret"])

        self.cryptoSetList:list = []

    # Gathering data from binance, setup
    # ----------------------------------
    def gatherNewDataSet(self):
        # check whether API works, otherwise throw an early exception
        try:
            account=self.spotClient.account()
            logging.debug(json.dumps(account, indent=4, sort_keys=False))
        except ClientError as E:
            raise E

        # check whether a new dataset should be gathered
        lastTimestamp=0
        entrySet:CryptoSet
        for entrySet in self.cryptoSetList:
            entrySetTimestamp=entrySet.timestamp
            if entrySetTimestamp>lastTimestamp:
                lastTimestamp=entrySetTimestamp
            logging.debug("Found entry timestamp %f" %(entrySetTimestamp))

        currentTimestamp=datetime.now().timestamp()
        datasetTimeDifference:int=3600
        calcedDiff=currentTimestamp-lastTimestamp
        if calcedDiff<datasetTimeDifference:
            print("Last dataset is not older than %d secs (just %ds). Not gathering a new one." % (datasetTimeDifference, calcedDiff))
            return

        # Start gathering a new dataset from binance
        # ------------------------------------------

        # all crypto class
        newCryptoSet=CryptoSet(setSpotClient=self.spotClient)
        self.cryptoSetList.append(newCryptoSet)

        # Account & Order Wallet Assets
        # -----------------------------
        print("Gathering Account/Order Assets...")

        for accountAsset in account["balances"]:
            name=accountAsset["asset"]
            free=float(accountAsset["free"])
            locked=float(accountAsset["locked"])
            # do not calc LD values, will be done in savings later
            amount=free+locked
            if amount>0.0 and not name.startswith("LD"):
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToWalletAndOrderValue(toAddFree=free,toAddLocked=locked)

        # Savings
        # -------
        print("Gathering Earn Staking...")
        savings=self.spotClient.staking_product_position(product="STAKING")
        # print(savings)
        for s in savings:
            # print(s)
            name=s["asset"]
            crypto=newCryptoSet.getCryptoByName(name)
            crypto.addToStaking(float(s["amount"]))

        print("Gathering Earn Flexible...")
        savings=self.spotClient.get_flexible_product_position(size=100)
        # print(savings)
        for s in savings["rows"]:
            # print(s)
            name=s["asset"]
            crypto=newCryptoSet.getCryptoByName(name)
            crypto.addToFlexible(float(s["totalAmount"]))

        print("Gathering Plans...")
        plans=self.spotClient.get_list_of_plans(planType="PORTFOLIO")
        # print(plans)
        for s in plans["plans"]:
            planID=s["planId"]
            params={"planId": planID}
            planDetails=self.spotClient.query_holding_details_of_the_plan(**params)
            # print(planDetails)
            for assetDetail in planDetails["details"]:
                # print(assetDetail)
                name=assetDetail["targetAsset"]
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToPlan(float(assetDetail["purchasedAmount"]))

        # Liquidity Pool values
        # ---------------------
        # print("Gathering Liquidity Pools...")
        # swap=self.spotClient.bswap_liquidity()

        # for s in swap:
        #     poolName=s["poolName"]
        #     # poolID=s["poolId"]
        #     share=s["share"]
        #     shareAmount=float(share["shareAmount"])
        #     if (shareAmount>0.0):
        #         assets=share["asset"]
        #         for swapAsset in assets.keys():
        #             swapValue=float(assets[swapAsset])
        #             crypto=newCryptoSet.getCryptoByName(swapAsset)
        #             crypto.addToLiquidityValue(swapValue)
        #               logging.debug("%s - %s - %.8f" % (poolName, swapAsset, swapValue))

        # gather deposit fiat history and add to set if it is in that month
        # --------------------------------------------------------------------
        print("Gathering Fiat Buy/Payment Deposits...")
        fiatHistory=self.spotClient.fiat_payment_history(transactionType=0)
        logging.debug(fiatHistory)
        if "data" in fiatHistory:
            for data in fiatHistory["data"]:
                # get timestamp of fiat payment
                timestamp=int(data["updateTime"])/1000  # milliseconds to seconds
                paymentDate = datetime.fromtimestamp(timestamp)
                paymentMonth=paymentDate.year*100+paymentDate.month

                # get timestamp of current cryptoset
                setDate=datetime.fromtimestamp(newCryptoSet.timestamp)
                setDateMonth=setDate.year*100+setDate.month

                # add only to this set when month is same
                if paymentMonth == setDateMonth:
                    # get crypto from set
                    cryptoName=data["cryptoCurrency"]
                    crypto:Crypto=newCryptoSet.getCryptoByName(cryptoName)
                    amount=float(data["obtainAmount"])
                    crypto.addToPaymentDeposit(toAdd=amount)
                    logging.debug("Buy/Payment found %s %s %.8f" % (crypto,setDate,amount))

        # gather deposit crypto history and add to set if it is in that month
        # --------------------------------------------------------------------
        print("Gathering Crypto Deposits...")
        cryptoDepositHistory=self.spotClient.deposit_history()
        logging.debug(cryptoDepositHistory)
        for data in cryptoDepositHistory:
            # get timestamp of fiat payment
            timestamp=int(data["insertTime"])/1000  # milliseconds to seconds
            paymentDate = datetime.fromtimestamp(timestamp)
            paymentMonth=paymentDate.year*100+paymentDate.month

            # get timestamp of current cryptoset
            setDate=datetime.fromtimestamp(newCryptoSet.timestamp)
            setDateMonth=setDate.year*100+setDate.month

            # add only to this set when month is same
            if paymentMonth == setDateMonth:
                # get crypto from set
                cryptoName=data["coin"]
                crypto:Crypto=newCryptoSet.getCryptoByName(cryptoName)
                amount=float(data["amount"])
                crypto.addToPaymentDeposit(toAdd=amount)
                logging.debug("Deposit found %s %s %.8f" % (crypto,setDate,amount))

        # calculate total BTC of set after gathering all cryptos
        # ------------------------------------------------------
        newCryptoSet.updateTotalsOfSet()

    def showTradeTimeProgress(self,filterVal=""):
        def getCandleGrowth(candleData1, candleData2) -> float:
            return float(candleData2)/float(candleData1)*100.0-100.0

        # get all symbols and calc rate
        print("Gathering symbol tickers")
        # symbols=self.spotClient.ticker_price()
        symbols=self.spotClient.exchange_info()
        symbols=symbols["symbols"]

        nrOfSymbols=len(symbols)
        print("Found %d symbols" % nrOfSymbols)
        print("Sorting by name")
        symbols = sorted(symbols, key=itemgetter('symbol'))
        logging.debug(symbols)

        print("Gathering trading information...")
        unsortedSymbols:list=[]
        curNr=0
        for symbol in symbols:
            # name
            symbolName=symbol["symbol"]
            logging.debug(f"Checking symbol {symbolName}")
            logging.debug(f"{symbol}")

            # print out state of gathering
            curNr+=1
            print("%d/%d - %-20s" % (curNr,nrOfSymbols,symbolName), end="\r",flush=True)

            # get some properties
            isSpot:bool=symbol["isSpotTradingAllowed"]
            isTrading:bool=symbol["status"] == "TRADING"
            quoteAsset=symbol["quoteAsset"]

            # collect only when properties fit
            if filterVal in symbolName and isSpot is True and isTrading is True:

                newSymbol=dict()
                newSymbol["name"]=symbolName

                # candles for 5m
                candleData=self.spotClient.klines(symbol=symbolName,interval="5m",limit=2)
                if len(candleData) < 2:
                    continue
                # print(json.dumps(candleData1m, indent=4, sort_keys=False))
                growth5m:float=getCandleGrowth(candleData[0][4],candleData[1][4])
                newSymbol["5m"]=growth5m

                # candles for 1h
                candleData=self.spotClient.klines(symbol=symbolName,interval="1h",limit=2)
                if len(candleData) < 2:
                    continue
                growth1h:float=getCandleGrowth(candleData[0][4],candleData[1][4])
                newSymbol["1h"]=growth1h

                # candles for 1d
                candleData=self.spotClient.klines(symbol=symbolName,interval="1d",limit=2)
                if len(candleData) < 2:
                    continue
                growth1d:float=getCandleGrowth(candleData[0][4],candleData[1][4])
                newSymbol["1d"]=growth1d

                # volume rate of current 1d
                if len(candleData) < 2:
                    continue
                volume=candleData[1][7]
                newSymbol["volume"]=float(volume)
                newSymbol["quoteAsset"]=quoteAsset

                # candles for 1m -> just for calaculation of immediate interactions
                candleData=self.spotClient.klines(symbol=symbolName,interval="1m",limit=30)
                # get all highs, lows
                highs, lows, closes = [], [], []
                for candle in candleData:
                    highs.append(float(candle[2]))
                    lows.append(float(candle[3]))
                    closes.append(float(candle[4]))

                # aroon function
                aroondown, aroonup = talib.AROON(numpy.array(highs), numpy.array(lows), timeperiod=14)
                newSymbol["aroonup"] = aroonup[-1]
                newSymbol["aroondown"] = aroondown[-1]

                # RSI
                rsi = talib.RSI(numpy.array(closes), timeperiod=7)
                newSymbol["rsi"] = rsi[-1]

                # rate the symbol
                newSymbol["rated"]= growth1d*2 + growth1h*3 + growth5m*1

                # add to unsorted list
                unsortedSymbols.append(newSymbol)

        print("%d/%d symbols done %20s" % (len(unsortedSymbols),nrOfSymbols," "), flush=True)

        # sort them
        print("Sorting by rate")
        sortedList = sorted(unsortedSymbols, key=itemgetter('rated'))

        # show them
        for symbol in sortedList:
            symbolName=symbol["name"]
            vR=symbol["rated"]
            v1=symbol["5m"]
            v2=symbol["1h"]
            v3=symbol["1d"]
            colorR=Colors.getColorByGLTZero(vR)
            color1=Colors.getColorByGLTZero(v1)
            color2=Colors.getColorByGLTZero(v2)
            color3=Colors.getColorByGLTZero(v3)

            print("%8s %srate: %6.2f, %s5m: %6.2f%%, %s1h: %6.2f%%, %s1d: %6.2f%%%s, volume: %.0f %s, rsi: %.0f, aroonup: %.0f, aroondown: %.0f" % (symbolName,colorR,vR,color1,v1,color2,v2,color3,v3,Colors.CRESET,symbol["volume"],symbol["quoteAsset"],symbol["rsi"],symbol["aroonup"],symbol["aroondown"]))

    # Snapshots
    def snapshots(self):
        printSection("Account snaptshots:")
        coinInfo=self.spotClient.account_snapshot(type="SPOT")
        # print(coinInfo)
        for s in coinInfo["snapshotVos"]:
            # time, convert from milliseconds
            timestamp=s["updateTime"]/1000
            date = datetime.fromtimestamp(timestamp)

            btcValue=s["data"]["totalAssetOfBtc"]

            print("Time: %d - %s - BTC: %s" % (timestamp, date, btcValue))

    def analyzeGrowth(self,analyzeBefore:str,analyzeLast:str):
        printSection("Analyze")

        # sort cryptoset list by date
        self.cryptoSetList.sort(key=lambda x: x.timestamp, reverse=False)

        # get first and last set
        first:CryptoSet=self.cryptoSetList[0]
        last:CryptoSet=self.cryptoSetList[-1]
        # get before
        before=self.cryptoSetList[-2] if len(self.cryptoSetList) > 1 else first

        if (analyzeBefore != "before"):
            analyzeBefore += "-01-01" if len(analyzeBefore) in [4, 7] else "-01"

        if (analyzeLast != "latest"):
            analyzeLast += "-01-01" if len(analyzeLast) in [4, 7] else "-01"

        # get date of cryptoset.time which is close to date given by analyzeBefore
        # if 2023-01 is given, then the closests date must be <= than this date

        print(f"Before: {analyzeBefore}, Last: {analyzeLast}")

        # analyze
        print("First:  %s - %.8f - %s" % (first.time,first.totalBTC.total,first.uuid))
        print("Before: %s - %.8f - %s" % (before.time,before.totalBTC.total,before.uuid))
        print("Last:   %s - %.8f - %s" % (last.time,last.totalBTC.total,last.uuid))

        def showValue(starttext:str, NewerValue, OlderValue, days:int=0, headerTitle=""):
            diff=NewerValue-OlderValue
            perc=0.0
            if (OlderValue>0):
                perc=NewerValue/OlderValue*100-100

            color=Colors.getColorByGLTZero(diff)

            daystext=""
            if days<1:
                days=1
            percPerDay=perc/days
            daystext="%6d %9.4f%%" % (days,percPerDay)

            # header when requested
            if headerTitle!="":
                print("\n%-13s %17s %17s %17s %10s %6s %10s" % (headerTitle,"Newer","Older","Diff","Percent","Days","%/day"))

            # print values
            print("%-13s %17.8f %17.8f %s%17.8f %9.4f%% %s%s" % (starttext,NewerValue,OlderValue,color,diff,perc,daystext,Colors.CRESET))

        def showDiff(setNewer:CryptoSet, setOlder:CryptoSet):
            # days between these sets
            days:int=(setNewer.timestamp-setOlder.timestamp)/3600/24

            # show difference between both
            crypto:Crypto
            for crypto in setNewer.allCryptos:
                zeroCrypto=Crypto(setName=crypto,setSpotClient=self.spotClient)

                cryptoOlder=zeroCrypto
                if crypto in setOlder.allCryptos:
                    cryptoOlder:Crypto=setOlder.allCryptos[crypto]

                cryptoNewer=zeroCrypto
                if crypto in setNewer.allCryptos:
                    cryptoNewer:Crypto=setNewer.allCryptos[crypto]

                showValue("Total",cryptoNewer.getTotal(),cryptoOlder.getTotal(),days,headerTitle=crypto)
                showValue("Wall+Order",cryptoNewer.orderWalletTotal,cryptoOlder.orderWalletTotal,days)

                if cryptoNewer.orderWalletLocked>0.0 or cryptoOlder.orderWalletLocked>0.0:
                    showValue("Ord-Locked",cryptoNewer.orderWalletLocked,cryptoOlder.orderWalletLocked,days)

                if cryptoNewer.earnFlexible>0.0 or cryptoOlder.earnFlexible>0.0:
                    showValue("Flexible",cryptoNewer.earnFlexible,cryptoOlder.earnFlexible,days)

                if cryptoNewer.earnStaking>0.0 or cryptoOlder.earnStaking>0.0:
                    showValue("Staking",cryptoNewer.earnStaking,cryptoOlder.earnStaking,days)

                if cryptoNewer.liquidSwapValue>0.0 or cryptoOlder.liquidSwapValue>0.0:
                    showValue("Liquid",cryptoNewer.liquidSwapValue,cryptoOlder.liquidSwapValue,days)

                if cryptoNewer.earnPlan>0.0 or cryptoOlder.earnPlan>0.0:
                    showValue("Plan",cryptoNewer.earnPlan,cryptoOlder.earnPlan,days)

                if cryptoNewer.paymentDeposit>0.0 or cryptoOlder.paymentDeposit>0.0:
                    showValue("Deposit",cryptoNewer.paymentDeposit,cryptoOlder.paymentDeposit)
                if cryptoNewer.paymentWithdraw>0.0 or cryptoOlder.paymentWithdraw>0.0:
                    showValue("Withdraw",cryptoNewer.paymentWithdraw,cryptoOlder.paymentWithdraw)

            showValue("∑ BTC all",setNewer.totalBTC.total,setOlder.totalBTC.total,days,headerTitle=" ")
            showValue("∑ BTC NoDepo",setNewer.totalBTC.totalWithoutDeposits,setOlder.totalBTC.totalWithoutDeposits,days)
            showValue("∑ USDT all",setNewer.totalUSDT.total,setOlder.totalUSDT.total,days)
            showValue("∑ USDT NoDepo",setNewer.totalUSDT.totalWithoutDeposits,setOlder.totalUSDT.totalWithoutDeposits,days)

        # differenc growth between last and first and last and before
        printSection(f"Last to first... {last.time} to {first.time}")
        showDiff(last,first)
        printSection(f"Last to before... {last.time} to {before.time}")
        showDiff(last,before)

    # def printValues(self):
    #     jsonContent=self.toJSON()
    #     print(json.dumps(jsonContent, indent=4, sort_keys=False))

    def fromJSON(self,jsonContent):
        entry:dict
        for entry in jsonContent["binanceDataSet"]:
            newCryptoSet=CryptoSet(setSpotClient=self.spotClient)
            newCryptoSet.fromJSON(entry)
            self.cryptoSetList.append(newCryptoSet)

        print("Found %d datasets" % (len(self.cryptoSetList)))

    def toJSON(self) -> dict:
        jsonList:list=[]
        entry:CryptoSet

        for entry in self.cryptoSetList:
            jsonList.append(entry.toJSON())

        jsonDict = {
            "version": 4,
            "binanceDataSet": jsonList
        }

        return jsonDict

    def loadData(self):
        print("Loading data...")
        jsonContent:dict=dict()
        if Files.databaseExists():
            with open(Files.getDatabaseFilenameWithPath(), "r", encoding="utf8") as infile:
                jsonContent=json.load(infile)
                logging.debug(jsonContent)
                infile.close()

            self.fromJSON(jsonContent)

    def saveData(self):
        print("Saving data...")
        # print JSON for database
        jsonContent=self.toJSON()

        with open(Files.getDatabaseFilenameWithPath(), "w", encoding="utf8") as outfile:
            json.dump(jsonContent, outfile, indent=4, sort_keys=False)
            outfile.close()
