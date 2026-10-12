# class to handle Binance crypto values
# License: MIT
# Author: mhl5k

from datetime import datetime
import json
import logging
from pathlib import Path

from binance_sdk_wallet import Wallet, WALLET_REST_API_PROD_URL
from binance_sdk_spot import Spot
from binance_sdk_simple_earn import SimpleEarn
from binance_sdk_fiat import Fiat
from binance_common.errors import ClientError, BadRequestError
from binance_common.configuration import ConfigurationRestAPI
from mhl5k.settings import Settings
from mhl5k.colors import Colors
from mhl5k.files import Files
from crypto import Crypto, PriceConversion
from cryptoset import CryptoSet
from migrations import CURRENT_DATABASE_VERSION, migrateDatabase


def printSection(sec: str):
    sep="-" * len(sec)
    print(f"\n{sep}")
    print(sec)
    print(sep)


class BinanceDataSet:

    def __init__(self, settings:Settings):
        # set client
        configuration = ConfigurationRestAPI(settings.current["apiKey"], settings.current["apiSecret"], base_path=WALLET_REST_API_PROD_URL)
        self.walletClient = Wallet(config_rest_api=configuration)
        self.spotClient = Spot(config_rest_api=configuration)
        self.earnClient = SimpleEarn(config_rest_api=configuration)
        self.fiatClient = Fiat(config_rest_api=configuration)

        # list to hold all cryptosets of different times
        self.cryptoSetList:list = []

    # Gathering data from binance, setup
    # ----------------------------------
    def gatherNewDataSet(self):
        # check whether API works, otherwise throw an early exception
        try:
            account_info = self.spotClient.rest_api.get_account()
            account = account_info.data()
            logging.debug(account)
        except (ClientError, BadRequestError) as e:
            raise e

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

        # create new CryptoSet and add to list
        newCryptoSet=CryptoSet(setWalletClient=self.walletClient)
        self.cryptoSetList.append(newCryptoSet)

        # Gather all price tickers
        # ------------------------
        print("Gathering Assets and price tickers...")
        PriceConversion.init(accountData=account,spotClient=self.spotClient)

        # Account & Order Wallet Assets
        # -----------------------------
        print("Gathering Spot/Order Assets...")

        for accountAsset in account.balances:
            name:str=accountAsset.asset
            free=float(accountAsset.free)
            locked=float(accountAsset.locked)
            # do not calc LD values, will be done in savings later
            amount=free+locked
            if amount>0.0 and not name.startswith("LD"):
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToWalletAndOrderValue(toAddFree=free,toAddLocked=locked)

                # check whether flexible is available
                flexibleProductList=self.earnClient.rest_api.get_simple_earn_flexible_product_list(asset=name,size=20).data()
                logging.debug(flexibleProductList)
                soldOut=0
                for s in flexibleProductList.rows:
                    soldOut += 1 if s.is_sold_out==True else 0
                    if free >= float(s.min_purchase_amount):
                        crypto.canUseFlexible=True

                hasFlexibleCount=int(flexibleProductList.total)
                crypto.hasFlexiblePossibility=hasFlexibleCount>0 and soldOut<hasFlexibleCount
                logging.debug(f" {name} hasFlexibleCount: {hasFlexibleCount}, soldOut: {soldOut}, hasFlexiblePossibility: {crypto.hasFlexiblePossibility}, minPurchaseReached: {crypto.canUseFlexible}")

        # Savings
        # -------
        print("Gathering Earn Locked...")
        count=1
        maxcount=1
        while count<=maxcount:
            # Depending on model validation, the SDK can return either a model or a dict.
            locked = self.earnClient.rest_api.get_locked_product_position(current=count,size=100).data()
            logging.debug(locked)
            amount:int=int(locked["total"] if isinstance(locked, dict) else locked.total)
            # roundup amount/100
            maxcount = (amount + 99) // 100
            rows = locked["rows"] if isinstance(locked, dict) else locked.rows
            for s in rows:
                # print(s)
                name=s["asset"] if isinstance(s, dict) else s.asset
                crypto=newCryptoSet.getCryptoByName(name)
                crypto.addToLocked(float(s["amount"] if isinstance(s, dict) else s.amount))

            count+=1

        print("Gathering Earn Flexible...")
        count=1
        maxcount=1
        while count<=maxcount:
            flexible=self.earnClient.rest_api.get_flexible_product_position(current=count,size=100).data()
            logging.debug(flexible)
            amount:int=int(flexible.total)
            # roundup amount/100
            maxcount = (amount + 99) // 100
            for s in flexible.rows:
                # print(s)
                name=s.asset
                crypto=newCryptoSet.getCryptoByName(name)
                valueInFlexible=float(s.total_amount)
                crypto.addToFlexible(valueInFlexible)

                # check whether locked is possible to mark it
                lockedProductList=self.earnClient.rest_api.get_simple_earn_locked_product_list(asset=name,size=20).data()
                logging.debug(lockedProductList)
                soldOut=0
                for s in lockedProductList.rows:
                    detail = s.detail
                    quota = s.quota
                    soldOut += 1 if detail.is_sold_out==True else 0
                    if valueInFlexible >= float(quota.minimum):
                        crypto.canUseLocked=True

                hasLockedCount=int(lockedProductList.total)
                crypto.hasLockedPossibility=hasLockedCount>0 and soldOut<hasLockedCount
                logging.debug(f" {name} hasLockedCount: {hasLockedCount}, soldOut: {soldOut}, hasLockedPossibility: {crypto.hasLockedPossibility}, minPurchaseReached: {crypto.canUseLocked}")

            count+=1

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
        fiatHistory=self.fiatClient.rest_api.get_fiat_payments_history(transaction_type=str(DEPOSIT_BUY)).data()
        logging.debug(fiatHistory)
        if fiatHistory.data is not None:
            for data in fiatHistory.data:
                logging.debug(data)
                # get timestamp of fiat payment
                timestamp=int(data.update_time)/1000  # milliseconds to seconds
                paymentTimestamp = datetime.fromtimestamp(timestamp).timestamp()

                # timestamp between current and last time
                if lastTimestamp <= paymentTimestamp <= newCryptoSet.timestamp:
                    # get crypto from set
                    cryptoName=data.crypto_currency
                    crypto:Crypto=newCryptoSet.getCryptoByName(cryptoName)
                    amount=float(data.obtain_amount)
                    crypto.addToPaymentDeposit(toDeposit=amount)
                    logging.debug("FIAT Buy/Payment found %s %s %.8f" % (cryptoName,paymentTimestamp,amount))

        # gather deposit crypto history and add to set if it is in that month
        # --------------------------------------------------------------------
        print("Gathering Crypto Deposits...")
        cryptoDepositHistory=self.walletClient.rest_api.deposit_history().data()
        logging.debug(cryptoDepositHistory)
        for data in cryptoDepositHistory:
            logging.debug(data)
            # get timestamp of fiat payment
            timestamp=int(data.insert_time)/1000  # milliseconds to seconds
            paymentTimestamp = datetime.fromtimestamp(timestamp).timestamp()

            # add only to this set when month is same
            logging.debug(f"Timestamps: last: {lastTimestamp} - payment: {paymentTimestamp} - new: {newCryptoSet.timestamp}")
            if lastTimestamp <= paymentTimestamp <= newCryptoSet.timestamp:
                # get crypto from set
                cryptoName=data.coin
                crypto:Crypto=newCryptoSet.getCryptoByName(cryptoName)
                amount=float(data.amount)
                crypto.addToPaymentDeposit(toDeposit=amount)
                logging.debug("Deposit found %s %s %.8f" % (cryptoName,paymentTimestamp,amount))

        print("Gathering kline values...")
        for crypto in newCryptoSet.allCryptos.values():
            try:
                crypto.monthKlines["symbol"]="USDC"
                klines = []
                try:
                    klines=self.spotClient.rest_api.klines(symbol=f"{crypto.name}{crypto.monthKlines["symbol"]}", interval="1M", limit=14).data()
                except (ClientError, BadRequestError):
                    crypto.monthKlines["symbol"]="BTC"
                    klines=self.spotClient.rest_api.klines(symbol=f"{crypto.name}{crypto.monthKlines["symbol"]}", interval="1M", limit=14).data()

                # Do not drop last candle, maybe it is incomplete (an issue at beginning of month)
                # klines=klines[:-1]
                crypto.monthKlines["closes"] = [float(k[4]) for k in klines]   # close an Index 4
                crypto.monthKlines["volumes"] = [float(k[5]) for k in klines]   # volume an Index 5

            except (ClientError, BadRequestError) as E:
                logging.debug(f"ClientError: {E}")

        # Store BTC and USDC conversions from the snapshot's gathered tickers.
        # ------------------------------------------------------
        newCryptoSet.updateTotalsOfSet()

    # Snapshots
    def snapshots(self):
        printSection("Account snaptshots:")
        coinInfo=self.walletClient.rest_api.daily_account_snapshot(type="SPOT").data()
        # print(coinInfo)
        for s in coinInfo.snapshot_vos:
            # time, convert from milliseconds
            timestamp=s.update_time/1000
            date = datetime.fromtimestamp(timestamp)

            snapshotData = s.data
            btcValue=snapshotData.total_asset_of_btc

            print("Time: %d - %s - BTC: %s" % (timestamp, date, btcValue))

    def _getCryptoSetByDate(self,timestampToFind) -> CryptoSet:
        # get item of cryptoset which its date is lower and closest to given date
        item:CryptoSet=None
        # find the closest date which is lower or equal than the given date
        last:CryptoSet=None
        for item in self.cryptoSetList:
            if item.timestamp <= timestampToFind:
                last=item
            else:
                return last

    def analyzeGrowthAndShow(self,compareNrOfDays:int):
        printSection("Analyze datasets")

        # sort cryptoset list by date
        self.cryptoSetList.sort(key=lambda x: x.timestamp, reverse=False)

        # get first and last set
        first:CryptoSet=self.cryptoSetList[0]
        last:CryptoSet=self.cryptoSetList[-1] if len(self.cryptoSetList)>1 else first
        before:CryptoSet=self.cryptoSetList[-2] if len(self.cryptoSetList)>1 else last

        # get timestamp of last gathered set
        lastTimestamp = last.timestamp

        # when compareNrOfDays is set, use it
        if (compareNrOfDays>0):
            beforeTimestamp = lastTimestamp - compareNrOfDays*24*60*60
            # get set with this timestamp
            before = self._getCryptoSetByDate(beforeTimestamp)

        # if before is None, set it to first
        before = first if before is None else before

        def unitPrice(crypto:Crypto, currency:str) -> float | None:
            if crypto.name == currency:
                return 1.0
            converted = crypto.getConvertedTotalByName(currency)
            amount = crypto.getTotal()
            return converted.total / amount if converted is not None and converted.total is not None and amount > 0 else None

        def totalValue(crypto:Crypto, currency:str) -> float | None:
            converted = crypto.getConvertedTotalByName(currency)
            if converted is not None:
                return converted.total
            return 0.0 if crypto.getTotal() == 0 else None

        # analyze
        print("First:  %s - %.8f - %s" % (first.time,first.totalBTC.total,first.uuid))
        print("Before: %s - %.8f - %s" % (before.time,before.totalBTC.total,before.uuid))
        print("Last:   %s - %.8f - %s" % (last.time,last.totalBTC.total,last.uuid))

        def showValue(starttext:str, NewerValue, OlderValue, days:int=0, headerTitle="", integerValues:bool=False):
            # header when requested
            if headerTitle!="":
                print("\n%-13s %17s %17s %17s %10s %6s %10s" % (headerTitle,"Newer","Older","Diff","Percent","Days","%/day"))

            if OlderValue is None:
                newerText = f"{NewerValue:.8f}" if NewerValue is not None else "unavailable"
                olderText = "kein Bestand" if starttext.startswith("= Total") else ""
                print(f"{starttext:<13} {newerText:>17} {olderText:>17}".rstrip())
                return

            diff=NewerValue-OlderValue
            perc=0.0
            if (OlderValue>0):
                perc=NewerValue/OlderValue*100-100

            color=Colors.getColorByGLTZero(diff)

            daystext=""
            days=1 if days < 1 else days

            percPerDay=perc/days
            daystext="%6d %9.4f%%" % (days,percPerDay)

            # print values
            if integerValues:
                print("%-13s %17d %17d %s%+17d %9.4f%% %s%s" % (starttext,NewerValue,OlderValue,color,diff,perc,daystext,Colors.CRESET))
            else:
                print("%-13s %17.8f %17.8f %s%17.8f %9.4f%% %s%s" % (starttext,NewerValue,OlderValue,color,diff,perc,daystext,Colors.CRESET))

        def showDiff(setNewer:CryptoSet, setOlder:CryptoSet):
            # days between these sets
            days:int=(setNewer.timestamp-setOlder.timestamp)/3600/24

            # sort setNewer by name
            setNewer.sortByName()

            # show difference between both
            crypto:Crypto
            for crypto in setNewer.allCryptos.values():
                zeroCrypto=Crypto(setName=crypto.name,setWalletClient=self.walletClient)

                cryptoOlder=zeroCrypto
                if crypto.name in setOlder.allCryptos:
                    cryptoOlder:Crypto=setOlder.allCryptos[crypto.name]

                cryptoNewer=zeroCrypto
                if crypto.name in setNewer.allCryptos:
                    cryptoNewer:Crypto=setNewer.allCryptos[crypto.name]

                hasOlder = crypto.name in setOlder.allCryptos

                def showCryptoValue(label, newer, older, days=0, headerTitle=""):
                    showValue(label,newer,older if hasOlder else None,days,headerTitle=headerTitle)

                showCryptoValue("Spot",cryptoNewer.orderWalletFree,cryptoOlder.orderWalletFree,days,headerTitle=crypto.name)

                if cryptoNewer.orderWalletLocked>0.0 or cryptoOlder.orderWalletLocked>0.0:
                    showCryptoValue("In Order",cryptoNewer.orderWalletLocked,cryptoOlder.orderWalletLocked,days)

                if cryptoNewer.earnFlexible>0.0 or cryptoOlder.earnFlexible>0.0:
                    showCryptoValue("Earn-Flexible",cryptoNewer.earnFlexible,cryptoOlder.earnFlexible,days)
                if cryptoNewer.hasFlexiblePossibility and cryptoNewer.canUseFlexible:
                    print("%sEarn-Flexible is available, but not used%s" % (Colors.CYELLOW,Colors.CRESET))

                if cryptoNewer.earnLocked>0.0 or cryptoOlder.earnLocked>0.0:
                    showCryptoValue("Earn-Locked",cryptoNewer.earnLocked,cryptoOlder.earnLocked,days)
                if cryptoNewer.hasLockedPossibility and cryptoNewer.canUseLocked:
                    print("%sEarn-Locked is available, but not used%s" % (Colors.CYELLOW,Colors.CRESET))

                if cryptoNewer.liquidSwapValue>0.0 or cryptoOlder.liquidSwapValue>0.0:
                    showCryptoValue("Liquid",cryptoNewer.liquidSwapValue,cryptoOlder.liquidSwapValue,days)

                if cryptoNewer.earnPlan>0.0 or cryptoOlder.earnPlan>0.0:
                    showCryptoValue("Plan",cryptoNewer.earnPlan,cryptoOlder.earnPlan,days)

                showCryptoValue("= Total",cryptoNewer.getTotal(),cryptoOlder.getTotal(),days)

                if cryptoNewer.paymentDeposit>0.0 or cryptoOlder.paymentDeposit>0.0:
                    showCryptoValue("Deposit",cryptoNewer.paymentDeposit,cryptoOlder.paymentDeposit)
                if cryptoNewer.paymentWithdraw>0.0 or cryptoOlder.paymentWithdraw>0.0:
                    showCryptoValue("Withdraw",cryptoNewer.paymentWithdraw,cryptoOlder.paymentWithdraw)

                # Compare only values in the same currency, including USDT fallback.
                hasValuation = False
                for currency in ("USDC", "USDT"):
                    conversions = [c.getConvertedTotalByName(currency) for c in (cryptoNewer, cryptoOlder)]
                    if not any(c is not None and c.total is not None for c in conversions):
                        continue
                    hasValuation = True
                    for label, newer, older in (
                        (f"{currency}/Asset", unitPrice(cryptoNewer,currency), unitPrice(cryptoOlder,currency)),
                        (f"= Total {currency}", totalValue(cryptoNewer,currency), totalValue(cryptoOlder,currency)),
                    ):
                        if not hasOlder:
                            showCryptoValue(label,newer,None,days)
                        elif newer is not None and older is not None:
                            showValue(label,newer,older,days)
                        else:
                            newerText = (f"{newer:.8f}" if newer is not None else
                                         "kein Bestand" if crypto.name not in setNewer.allCryptos else "unavailable")
                            olderText = (f"{older:.8f}" if older is not None else
                                         "kein Bestand" if crypto.name not in setOlder.allCryptos else "unavailable")
                            print(f"{label:<13} {newerText:>17} {olderText:>17}")
                if not hasValuation:
                    print(f"{Colors.CYELLOW}USDC/USDT conversion unavailable{Colors.CRESET}")

                # show rating
                # ----------------
                cryptoNewer.rating = "There is not enough data to calculate growth"

                # if enough kline data is available
                if len(cryptoNewer.monthKlines["closes"]) <=1 or len(cryptoNewer.monthKlines["volumes"]) <=1:
                    cryptoNewer.rating = f"{Colors.CYELLOW}Not enough kline data to calculate growth{Colors.CRESET}"
                else:
                    closes = cryptoNewer.monthKlines["closes"]
                    volumes = cryptoNewer.monthKlines["volumes"]
                    ratingSymbol = cryptoNewer.monthKlines["symbol"]

                    def _formatNumberWithSuffix(value: float) -> str:
                        if abs(value) >= 1_000_000:
                            return f"{value / 1_000_000:.2f}M"
                        elif abs(value) >= 1_000:
                            return f"{value / 1_000:.2f}K"
                        else:
                            return f"{value:.2f}"

                    def _trend_pct(series: list[float], months: int) -> float | None:
                        """Prozentänderung über 'months' zwischen letztem und Wert vor months."""
                        if len(series) <= months:
                            return None
                        last = series[-1]
                        prev = series[-1 - months]
                        if prev == 0:
                            return None
                        return (last - prev) / prev * 100

                    def _trend_and_keep(pct: float | None) -> tuple[str, str, str]:
                        if pct is None:
                            return "❓", "REVIEW", Colors.CYELLOW
                        if pct >= 20:
                            return "⬆️ ⬆️ ", "KEEP", Colors.CGREEN
                        if pct >= 5:
                            return "⬆️ ", "KEEP", Colors.CGREEN
                        if pct <= -20:
                            return "⬇️ ⬇️ ", "DROP", Colors.CRED
                        if pct <= -5:
                            return "⬇️ ", "REVIEW", Colors.CYELLOW
                        # default sideway right
                        return "➡️ ", "REVIEW", Colors.CYELLOW

                    months = 6
                    # check whether enough data
                    if len(closes) < months+1:
                        months = len(closes) - 1

                    price_pct = _trend_pct(closes, months)
                    vol_pct = _trend_pct(volumes, months)

                    price_trend, price_keep, price_color = _trend_and_keep(price_pct)
                    vol_trend, vol_keep, vol_color = _trend_and_keep(vol_pct)

                    price_part = "n/a"
                    if price_pct is not None:
                        last_price = closes[-1]
                        prev_price = closes[-1 - months]
                        price_part = f"{price_color}{price_trend} {price_pct:+.1f}% ({prev_price} -> {last_price} {ratingSymbol}){Colors.CRESET}"

                    vol_part = "n/a"
                    if vol_pct is not None:
                        last_vol = volumes[-1]
                        prev_vol = volumes[-1 - months]
                        vol_part = f"{vol_color}{vol_trend} {vol_pct:+.1f}% ({_formatNumberWithSuffix(prev_vol)} -> {_formatNumberWithSuffix(last_vol)} {ratingSymbol}){Colors.CRESET}"

                    flag = "🟡 REVIEW"
                    flag_color = Colors.CYELLOW
                    if price_keep == "KEEP" and vol_keep == "KEEP":
                        flag = "🟢 KEEP"
                        flag_color = Colors.CGREEN
                    if price_keep == "DROP" or vol_keep == "DROP":
                        flag = "🔴 DROP"
                        flag_color = Colors.CRED

                    # store in crypto set
                    cryptoNewer.rating = (
                        f"{flag_color}{flag}{Colors.CRESET} | "
                        f"Price {months}M: {price_part} | "
                        f"Vol {months}M: {vol_part}"
                    )

                # show growth string
                print(cryptoNewer.rating)

            showValue("∑ Cryptos",setNewer.cryptoCount,setOlder.cryptoCount,days,headerTitle=" ",integerValues=True)
            showValue("∑ BTC all",setNewer.totalBTC.total,setOlder.totalBTC.total,days)
            n=setNewer.totalBTC.total-setNewer.totalBTC.deposit
            o=setOlder.totalBTC.total-setOlder.totalBTC.deposit
            showValue("∑ BTC -Depo",n,o,days)

            showValue("∑ USDC all",setNewer.totalUSDC.total,setOlder.totalUSDC.total,days)
            n=setNewer.totalUSDC.total-setNewer.totalUSDC.deposit
            o=setOlder.totalUSDC.total-setOlder.totalUSDC.deposit
            showValue("∑ USDC -Depo",n,o,days)

            if any(c.getConvertedTotalByName("USDT") is not None
                   and c.getConvertedTotalByName("USDT").total is not None
                   for s in (setNewer, setOlder) for c in s.allCryptos.values()):
                showValue("∑ USDT all",setNewer.totalUSDT.total,setOlder.totalUSDT.total,days)
                n=setNewer.totalUSDT.total-setNewer.totalUSDT.deposit
                o=setOlder.totalUSDT.total-setOlder.totalUSDT.deposit
                showValue("∑ USDT -Depo",n,o,days)

        # differenc growth between last and first
        # printSection(f"Last to first... {last.time} to {first.time}")
        # showDiff(last,first)

        # differenc growth between last and before
        printSection(f"Last to before... {last.time} to {before.time}")
        showDiff(last,before)

    def fromJSON(self,jsonContent):
        entry:dict
        for entry in jsonContent["binanceDataSet"]:
            newCryptoSet=CryptoSet(setWalletClient=self.walletClient)
            newCryptoSet.fromJSON(entry)
            self.cryptoSetList.append(newCryptoSet)

        print("Found %d datasets" % (len(self.cryptoSetList)))

    def toJSON(self) -> dict:
        jsonList:list=[]
        entry:CryptoSet

        for entry in self.cryptoSetList:
            jsonList.append(entry.toJSON())

        jsonDict = {
            "version": CURRENT_DATABASE_VERSION,
            "binanceDataSet": jsonList
        }

        return jsonDict

    def loadData(self):
        print("Loading data...")
        jsonContent:dict=dict()
        if Files.databaseExists():
            databasePath = Path(Files.getDatabaseFilenameWithPath())
            original = databasePath.read_bytes()
            jsonContent = json.loads(original)
            logging.debug(jsonContent)

            if int(jsonContent.get("version", 1)) < CURRENT_DATABASE_VERSION:
                date = datetime.now().strftime("%Y%m%d")
                backupStem = f"{databasePath.stem}.pre-migration-v{CURRENT_DATABASE_VERSION}-{date}"
                counter = 1
                while True:
                    suffix = "" if counter == 1 else f"-{counter}"
                    backupPath = databasePath.with_name(f"{backupStem}{suffix}{databasePath.suffix}")
                    try:
                        with backupPath.open("xb") as backup:
                            backup.write(original)
                        break
                    except FileExistsError:
                        counter += 1
                print(f"Database backup before migration: {backupPath.name}")

            self.fromJSON(migrateDatabase(jsonContent, self.spotClient))

    def saveData(self):
        print("Saving data...")
        # print JSON for database
        jsonContent=self.toJSON()

        with open(Files.getDatabaseFilenameWithPath(), "w", encoding="utf8") as outfile:
            json.dump(jsonContent, outfile, indent=4, sort_keys=False)
            outfile.close()
