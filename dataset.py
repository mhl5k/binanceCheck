# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging
import numpy as np

from binance.spot import Spot as SpotClient
from binance.error import ClientError
from mhl5k.settings import Settings
from mhl5k.colors import Colors
from mhl5k.files import Files
from mhl5k.app import App
from crypto import Crypto
from cryptoset import CryptoSet

DATASETDEBUG = False


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
        print("Gathering Spot/Order Assets...")

        for accountAsset in account["balances"]:
            name:str=accountAsset["asset"]
            free=float(accountAsset["free"])
            locked=float(accountAsset["locked"])
            # do not calc LD values, will be done in savings later
            amount=free+locked
            if amount>0.0 and not name.startswith("LD"):
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToWalletAndOrderValue(toAddFree=free,toAddLocked=locked)

        # Savings
        # -------
        print("Gathering Earn Locked...")
        locked = self.spotClient.get_locked_product_position(size=100)
        logging.debug(locked)
        for s in locked["rows"]:
            # print(s)
            name=s["asset"]
            crypto=newCryptoSet.getCryptoByName(name)
            crypto.addToLocked(float(s["amount"]))

        print("Gathering Earn Flexible...")
        flexible=self.spotClient.get_flexible_product_position(size=100)
        logging.debug(flexible)
        for s in flexible["rows"]:
            # print(s)
            name=s["asset"]
            crypto=newCryptoSet.getCryptoByName(name)
            crypto.addToFlexible(float(s["totalAmount"]))

            # check whether locked is possible to mark it
            lockedProductList=self.spotClient.get_simple_earn_locked_product_list(asset=name,size=10)
            logging.debug(lockedProductList)
            soldOut=0
            for s in lockedProductList["rows"]:
                if s["detail"]["isSoldOut"]==True:
                    soldOut+=1

            hasLockedCount=int(lockedProductList["total"])
            crypto.hasLockedPossibility=hasLockedCount>0 and soldOut<hasLockedCount
            logging.debug(f" {name} hasLockedCount: {hasLockedCount}, soldOut: {soldOut}, hasLockedPossibility: {crypto.hasLockedPossibility}")

        print("Gathering Plans...")
        plans=self.spotClient.get_list_of_plans(planType="PORTFOLIO")
        logging.debug(plans)
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
        print("Gathering FIAT Buy/Payment Deposits...")
        DEPOSIT_BUY=0
        # WITHDRAW_SELL=1
        fiatHistory=self.spotClient.fiat_payment_history(transactionType=DEPOSIT_BUY)
        logging.debug(json.dumps(fiatHistory, indent=4, sort_keys=False))
        if "data" in fiatHistory:
            for data in fiatHistory["data"]:
                logging.debug(json.dumps(data, indent=4, sort_keys=False))
                # get timestamp of fiat payment
                timestamp=int(data["updateTime"])/1000  # milliseconds to seconds
                paymentTimestamp = datetime.fromtimestamp(timestamp).timestamp()

                # timestamp between current and last time
                if lastTimestamp <= paymentTimestamp <= newCryptoSet.timestamp:
                    # get crypto from set
                    cryptoName=data["cryptoCurrency"]
                    crypto:Crypto=newCryptoSet.getCryptoByName(cryptoName)
                    amount=float(data["obtainAmount"])
                    crypto.addToPaymentDeposit(toDeposit=amount)
                    logging.debug("FIAT Buy/Payment found %s %s %.8f" % (cryptoName,paymentTimestamp,amount))

        # gather deposit crypto history and add to set if it is in that month
        # --------------------------------------------------------------------
        print("Gathering Crypto Deposits...")
        cryptoDepositHistory=self.spotClient.deposit_history()
        logging.debug(json.dumps(cryptoDepositHistory, indent=4, sort_keys=False))
        for data in cryptoDepositHistory:
            logging.debug(json.dumps(data, indent=4, sort_keys=False))
            # get timestamp of fiat payment
            timestamp=int(data["insertTime"])/1000  # milliseconds to seconds
            paymentTimestamp = datetime.fromtimestamp(timestamp).timestamp()

            # add only to this set when month is same
            logging.debug(f"Timestamps: last: {lastTimestamp} - payment: {paymentTimestamp} - new: {newCryptoSet.timestamp}")
            if lastTimestamp <= paymentTimestamp <= newCryptoSet.timestamp:
                # get crypto from set
                cryptoName=data["coin"]
                crypto:Crypto=newCryptoSet.getCryptoByName(cryptoName)
                amount=float(data["amount"])
                crypto.addToPaymentDeposit(toDeposit=amount)
                logging.debug("Deposit found %s %s %.8f" % (cryptoName,paymentTimestamp,amount))

        print("Gathering all crypto volume trends...")
        for crypto in newCryptoSet.allCryptos.values():
            try:
                volumeSymbol="USDC"
                try:
                    klines=self.spotClient.klines(symbol=f"{crypto.name}{volumeSymbol}", interval="1d", limit=100)
                except ClientError:
                    volumeSymbol="BTC"
                    klines=self.spotClient.klines(symbol=f"{crypto.name}{volumeSymbol}", interval="1d", limit=100)

                crypto.volumeSymbol=volumeSymbol

                # prepare volumes array, remove last unclosed and remove nan
                volumes = [float(k[5]) for k in klines[:-1]]
                arr = np.array(volumes)
                arr = arr[np.isfinite(arr)]
                crypto.volume1d=arr[-1]

                # Trend bestimmen (lineare Regression)
                if len(arr) < 2:
                    crypto.volume1dTrend="stable"
                else:
                    x = np.arange(len(volumes))
                    slope, _ = np.polyfit(x, volumes, 1)
                    crypto.volume1dTrend=np.where(slope < 0, "lowering", np.where(slope > 0, "rising", "stable"))

            except ClientError as E:
                logging.debug(f"ClientError: {E}")
                crypto.volume1d=-1.0

        # calculate total BTC of set after gathering all cryptos
        # ------------------------------------------------------
        if not DATASETDEBUG:
            newCryptoSet.updateTotalsOfSet()

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

    def _makeValidDate(self,givenDate:str) -> str:
        try:
            datetime.strptime(givenDate, '%Y-%m-%d')
        except ValueError:
            try:
                datetime.strptime(givenDate, '%Y-%m')
            except ValueError:
                try:
                    datetime.strptime(givenDate, '%Y')
                except ValueError:
                    App.errorExit(4,f"Invalid format for date {givenDate}. Please use YYYY, YYYY-MM, or YYYY-MM-DD format.")

        # check format
        givenDate += "-01-01" if len(givenDate) in [4, 7] else "-01"
        return givenDate

    def _getCryptoSetByDate(self,givenDate:str) -> CryptoSet:
        # get item of cryptoset which its date is lower and closest to given date
        retItem:CryptoSet=None
        item:CryptoSet=None
        # find the closest date which is lower or qual than the given date
        for item in self.cryptoSetList:
            # convert cryptoset time to YYYY-MM-DD
            t = datetime.strptime(item.time, "%Y-%m-%d %H:%M:%S.%f")
            if (str(t.date()) <= givenDate):
                retItem=item

        return retItem

    def analyzeGrowthAndShow(self,setOlderDate:str,setNewerDate:str):
        printSection("Analyze")

        # sort cryptoset list by date
        self.cryptoSetList.sort(key=lambda x: x.timestamp, reverse=False)

        # get first and last set
        first:CryptoSet=self.cryptoSetList[0]

        if setNewerDate == "latest":
            last:CryptoSet=self.cryptoSetList[-1]
        else:
            setNewerDate=self._makeValidDate(setNewerDate)
            last=self._getCryptoSetByDate(setNewerDate)

        if setOlderDate == "before":
            # get index of object "last" in list
            i=0
            for i, item in enumerate(self.cryptoSetList):
                if item == last:
                    break
            # get one object before
            before=self.cryptoSetList[i-1] if i>0 else first
        else:
            setOlderDate=self._makeValidDate(setOlderDate)
            before=self._getCryptoSetByDate(setOlderDate)

        # check if the earliest is not found
        if before is None or last is None:
            App.errorExit(5,f"Date cannot be found, earliest is {first.time}")

        # Swap last and before if needed
        if before.time > last.time:
            last, before = before, last

        logging.debug(f"Set1: {setOlderDate}, Set2: {setNewerDate}")

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
            days=1 if days < 1 else days

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

            # sort setNewer by name
            setNewer.sortByName()

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
                showValue("Total-Plan",cryptoNewer.getTotal()-cryptoNewer.earnPlan,cryptoOlder.getTotal()-cryptoOlder.earnPlan,days)
                showValue("Spot+Order",cryptoNewer.orderWalletTotal,cryptoOlder.orderWalletTotal,days)

                if cryptoNewer.orderWalletLocked>0.0 or cryptoOlder.orderWalletLocked>0.0:
                    showValue("Ord-Locked",cryptoNewer.orderWalletLocked,cryptoOlder.orderWalletLocked,days)

                if cryptoNewer.earnFlexible>0.0 or cryptoOlder.earnFlexible>0.0:
                    showValue("Earn-Flexible",cryptoNewer.earnFlexible,cryptoOlder.earnFlexible,days)

                if cryptoNewer.earnLocked>0.0 or cryptoOlder.earnLocked>0.0:
                    showValue("Earn-Locked",cryptoNewer.earnLocked,cryptoOlder.earnLocked,days)
                else:
                    if cryptoNewer.hasLockedPossibility:
                        print("%sEarn-Locked is available, but not used%s" % (Colors.CRED,Colors.CRESET))

                if cryptoNewer.liquidSwapValue>0.0 or cryptoOlder.liquidSwapValue>0.0:
                    showValue("Liquid",cryptoNewer.liquidSwapValue,cryptoOlder.liquidSwapValue,days)

                if cryptoNewer.earnPlan>0.0 or cryptoOlder.earnPlan>0.0:
                    showValue("Plan",cryptoNewer.earnPlan,cryptoOlder.earnPlan,days)

                if cryptoNewer.paymentDeposit>0.0 or cryptoOlder.paymentDeposit>0.0:
                    showValue("Deposit",cryptoNewer.paymentDeposit,cryptoOlder.paymentDeposit)
                if cryptoNewer.paymentWithdraw>0.0 or cryptoOlder.paymentWithdraw>0.0:
                    showValue("Withdraw",cryptoNewer.paymentWithdraw,cryptoOlder.paymentWithdraw)

                if cryptoNewer.volume1d > -1:
                    color=Colors.CGREEN
                    if any([
                        cryptoNewer.volume1d < 10000000 and cryptoNewer.volumeSymbol == "USDC",
                        cryptoNewer.volume1d < 10000000/120000 and cryptoNewer.volumeSymbol == "BTC",
                    ]) and cryptoNewer.volume1dTrend == "lowering":
                        color=Colors.CRED
                    formatted_volume = f"{cryptoNewer.volume1d:,.0f}".replace(",", ".")
                    print("%sVolume is %s with %s %s %s" % (color,cryptoNewer.volume1dTrend,formatted_volume,cryptoNewer.volumeSymbol,Colors.CRESET))
                else:
                    print("%sVolume for 1d not found for USDC nor BTC%s" % (Colors.CRED,Colors.CRESET))

            showValue("∑ BTC all",setNewer.totalBTC.total,setOlder.totalBTC.total,days,headerTitle=" ")
            n=setNewer.totalBTC.total-setNewer.totalBTC.deposit
            o=setOlder.totalBTC.total-setOlder.totalBTC.deposit
            showValue("∑ BTC -Depo",n,o,days)

            showValue("∑ USDC all",setNewer.totalUSDC.total,setOlder.totalUSDC.total,days)
            n=setNewer.totalUSDC.total-setNewer.totalUSDC.deposit
            o=setOlder.totalUSDC.total-setOlder.totalUSDC.deposit
            showValue("∑ USDC -Depo",n,o,days)

        # differenc growth between last and first and last and before
        printSection(f"Last to first... {last.time} to {first.time}")
        showDiff(last,first)
        printSection(f"Last to before... {last.time} to {before.time}")
        showDiff(last,before)

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
