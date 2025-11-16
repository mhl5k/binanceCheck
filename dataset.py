# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging

from binance.spot import Spot as SpotClient
from binance.error import ClientError
from mhl5k.settings import Settings
from mhl5k.colors import Colors
from mhl5k.files import Files
from crypto import Crypto
from cryptoset import CryptoSet

DATASET_SAVE = True


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

                # check whether flexible is available
                flexibleProductList=self.spotClient.get_simple_earn_flexible_product_list(asset=name,size=20)
                logging.debug(flexibleProductList)
                soldOut=0
                for s in flexibleProductList["rows"]:
                    soldOut += 1 if s["isSoldOut"]==True else 0

                hasFlexibleCount=int(flexibleProductList["total"])
                crypto.hasFlexiblePossibility=hasFlexibleCount>0 and soldOut<hasFlexibleCount
                logging.debug(f" {name} hasFlexibleCount: {hasFlexibleCount}, soldOut: {soldOut}, hasFlexiblePossibility: {crypto.hasFlexiblePossibility}")

        # Savings
        # -------
        print("Gathering Earn Locked...")
        count=1
        maxcount=1
        while count<=maxcount:
            locked = self.spotClient.get_locked_product_position(current=count,size=100)
            logging.debug(locked)
            amount:int=int(locked["total"])
            # roundup amount/100
            maxcount = (amount + 99) // 100
            for s in locked["rows"]:
                # print(s)
                name=s["asset"]
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToLocked(float(s["amount"]))

            count+=1

        print("Gathering Earn Flexible...")
        count=1
        maxcount=1
        while count<=maxcount:
            flexible=self.spotClient.get_flexible_product_position(current=count,size=100)
            logging.debug(flexible)
            amount:int=int(flexible["total"])
            # roundup amount/100
            maxcount = (amount + 99) // 100
            for s in flexible["rows"]:
                # print(s)
                name=s["asset"]
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToFlexible(float(s["totalAmount"]))

                # check whether locked is possible to mark it
                lockedProductList=self.spotClient.get_simple_earn_locked_product_list(asset=name,size=20)
                logging.debug(lockedProductList)
                soldOut=0
                for s in lockedProductList["rows"]:
                    soldOut += 1 if s["detail"]["isSoldOut"]==True else 0

                hasLockedCount=int(lockedProductList["total"])
                crypto.hasLockedPossibility=hasLockedCount>0 and soldOut<hasLockedCount
                logging.debug(f" {name} hasLockedCount: {hasLockedCount}, soldOut: {soldOut}, hasLockedPossibility: {crypto.hasLockedPossibility}")

            count+=1

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

        print("Gathering all crypto volume price growth values...")
        for crypto in newCryptoSet.allCryptos.values():
            try:
                volumeSymbol="USDC"
                try:
                    klines=self.spotClient.klines(symbol=f"{crypto.name}{volumeSymbol}", interval="1M", limit=14)
                except ClientError:
                    volumeSymbol="BTC"
                    klines=self.spotClient.klines(symbol=f"{crypto.name}{volumeSymbol}", interval="1M", limit=14)

                crypto.volumeSymbol=volumeSymbol

                if not klines:
                    close_growth_str = "3M: — | 6M: — | 12M: —"
                    volume_growth_str = "3M: — | 6M: — | 12M: —"
                else:
                    # Drop last candle, because it is incomplete (an issue at beginning of month)
                    klines=klines[:-1]
                    closes = [float(k[4]) for k in klines]   # close an Index 4
                    volumes = [float(k[5]) for k in klines]   # volume an Index 5

                    def _formatNumberWithSuffix(value):
                        a=""
                        if abs(value) >= 1_000_000:
                            a=f" ({value / 1_000_000:.2f}M)"
                        elif abs(value) >= 1_000:
                            a=f" ({value / 1_000:.2f}K)"
                        else:
                            a=f" ({value:.2f})"
                        return a

                    def _build_growth_str(series, label="Wert", horizons=(3, 6, 9, 12), showabs=True):
                        parts = []
                        for m in horizons:
                            if len(series) > m:
                                last = series[-1 - m + 3]
                                prev = series[-1 - m]
                                if prev != 0:
                                    pct = (last - prev) / prev * 100
                                    color = Colors.CGREEN if pct >= 0 else Colors.CRED
                                    abs_str = _formatNumberWithSuffix(last) if showabs else ""
                                    parts.append(f"{label} {m}M: {color}{pct:+.1f}%{abs_str}{Colors.CRESET}")
                                else:
                                    parts.append(f"{label} {m}M: —")
                            else:
                                parts.append(f"{label} {m}M: —")
                        return " | ".join(parts)

                    close_growth_str = _build_growth_str(closes, "Close")
                    volume_growth_str = _build_growth_str(volumes, "Volume", showabs=True)

                # store strings
                crypto.growth = f"Price: {close_growth_str} \r\nVolume: {volume_growth_str}"

            except ClientError as E:
                logging.debug(f"ClientError: {E}")

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

    def _getCryptoSetByDate(self,timestampToFind) -> CryptoSet:
        # get item of cryptoset which its date is lower and closest to given date
        item:CryptoSet=None
        # find the closest date which is lower or equal than the given date
        last:CryptoSet=None
        for item in self.cryptoSetList:
            if item.timestamp < timestampToFind:
                last=item
            else:
                return last

    def analyzeGrowthAndShow(self,compareNrOfDays:int):
        printSection("Analyze")

        # sort cryptoset list by date
        self.cryptoSetList.sort(key=lambda x: x.timestamp, reverse=False)

        # get first and last set
        first:CryptoSet=self.cryptoSetList[0]
        last:CryptoSet=self.cryptoSetList[-1] if len(self.cryptoSetList)>1 else first
        before:CryptoSet=self.cryptoSetList[-2] if len(self.cryptoSetList)>1 else last

        # if before or last is none set to first
        before = last if before is None else before

        # get timestamp of last gathered set
        lastTimestamp = last.timestamp

        # when compareNrOfDays is set, use it
        if (compareNrOfDays>0):
            beforeTimestamp = lastTimestamp - compareNrOfDays*24*60*60
            # get set with this timestamp
            before = self._getCryptoSetByDate(beforeTimestamp)

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
                if cryptoNewer.orderWalletFree>0.0:
                    if cryptoNewer.hasFlexiblePossibility:
                        print("%sEarn-Flexible is available, but not used%s" % (Colors.CYELLOW,Colors.CRESET))

                if cryptoNewer.earnLocked>0.0 or cryptoOlder.earnLocked>0.0:
                    showValue("Earn-Locked",cryptoNewer.earnLocked,cryptoOlder.earnLocked,days)
                if cryptoNewer.earnFlexible>0.0:
                    if cryptoNewer.hasLockedPossibility:
                        print("%sEarn-Locked is available, but not used%s" % (Colors.CYELLOW,Colors.CRESET))

                if cryptoNewer.liquidSwapValue>0.0 or cryptoOlder.liquidSwapValue>0.0:
                    showValue("Liquid",cryptoNewer.liquidSwapValue,cryptoOlder.liquidSwapValue,days)

                if cryptoNewer.earnPlan>0.0 or cryptoOlder.earnPlan>0.0:
                    showValue("Plan",cryptoNewer.earnPlan,cryptoOlder.earnPlan,days)

                if cryptoNewer.paymentDeposit>0.0 or cryptoOlder.paymentDeposit>0.0:
                    showValue("Deposit",cryptoNewer.paymentDeposit,cryptoOlder.paymentDeposit)
                if cryptoNewer.paymentWithdraw>0.0 or cryptoOlder.paymentWithdraw>0.0:
                    showValue("Withdraw",cryptoNewer.paymentWithdraw,cryptoOlder.paymentWithdraw)

                # show growth info
                if cryptoNewer.growth!="none":
                    print(cryptoNewer.growth)

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
