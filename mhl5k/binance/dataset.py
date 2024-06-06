# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging

from binance.spot import Spot as SpotClient
from binance.error import ClientError
from ..settings import Settings
from ..colors import Colors
from ..files import Files
from ..app import App
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

    def analyzeGrowth(self,set1Date:str,set2Date:str):
        printSection("Analyze")

        # sort cryptoset list by date
        self.cryptoSetList.sort(key=lambda x: x.timestamp, reverse=False)

        # get first and last set
        first:CryptoSet=self.cryptoSetList[0]

        if set2Date == "latest":
            last:CryptoSet=self.cryptoSetList[-1]
        else:
            set2Date=self._makeValidDate(set2Date)
            last=self._getCryptoSetByDate(set2Date)

        if set1Date == "before":
            # get index of object "last" in list
            i=0
            for i, item in enumerate(self.cryptoSetList):
                if item == last:
                    break
            # get one object before
            before=self.cryptoSetList[i-1] if i>0 else first
        else:
            set1Date=self._makeValidDate(set1Date)
            before=self._getCryptoSetByDate(set1Date)

        # check if the earliest is not found
        if before is None or last is None:
            App.errorExit(5,f"Date cannot be found, earliest is {first.time}")

        # Swap last and before if needed
        if before.time > last.time:
            last, before = before, last

        logging.debug(f"Set1: {set1Date}, Set2: {set2Date}")

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
