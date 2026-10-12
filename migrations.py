"""Ordered database migrations. Legacy compatibility belongs only here."""

from copy import deepcopy
from datetime import datetime, timezone
import math

from crypto import Crypto, PriceConversion, PriceUnavailableError
from cryptoset import CryptoSet


CURRENT_DATABASE_VERSION = 8


class Migration2V8:
    targetVersion = 8
    minSourceVersion = 1

    def __init__(self, spotClient):
        self.spotClient = spotClient
        self.prices = {}

    @staticmethod
    def normalizeCrypto(entry):
        # V8 has explicit fields; translate V1-V7 before using the normal loader.
        normalized = Crypto(entry['asset'], None).toJSON()
        normalized.update({key: entry[key] for key in normalized if key in entry})
        normalized['earnFlexible'] = entry.get('earnFlexible', entry.get('savingsWalletFlexible', '0.00000000'))
        normalized['earnLocked'] = entry.get('earnLocked', entry.get('earnStaking', '0.00000000'))
        conversions = {}
        for converted in entry.get('convertedTotal', []):
            conversions.setdefault(converted['name'], converted)
        if 'BTC' not in conversions and 'totalBTCValue' in entry:
            conversions['BTC'] = {'name': 'BTC', 'total': entry['totalBTCValue'], 'deposit': '0.00000000'}
        normalized['convertedTotal'] = list(conversions.values())
        crypto = Crypto(entry['asset'], None)
        crypto.fromJSON(normalized)
        if crypto.getConvertedTotalByName('USDC') is None:
            unavailable = False
            for field in ('USDCValue', 'currentUSDCValue', 'dailyCloseUSDC'):
                price = entry.get(field)
                if price is not None and float(price) > 0:
                    crypto.updateTotalIn('USDC', unitPrice=float(price))
                    break
                if price is not None and float(price) == -1:
                    unavailable = True
            if unavailable and crypto.getConvertedTotalByName('USDC') is None:
                converted = Crypto.ConvertedTotal('USDC')
                converted.set(None, None)
                crypto.allTotals.append(converted)
        return crypto.toJSON()

    @staticmethod
    def needsRefresh(crypto, currency):
        converted = crypto.getConvertedTotalByName(currency)
        if converted is None:
            return True
        if converted.total is None:
            return False
        amount = crypto.getTotal()
        total = converted.total
        precision = .000000005
        if not math.isfinite(total) or total < 0:
            return True
        if amount == 0:
            return total > precision
        if total == 0:
            btc = crypto.getConvertedTotalByName('BTC')
            return amount > precision and (btc is None or btc.total is None or btc.total > precision)
        price = total / amount
        if crypto.name == currency and not math.isclose(total, amount, rel_tol=0, abs_tol=2 * precision):
            return True
        deposit = converted.deposit
        if deposit is None or not math.isfinite(deposit) or deposit < 0:
            return True
        expected = crypto.paymentDeposit * price
        tolerance = precision * (1 + abs(crypto.paymentDeposit / amount)) * (1 + abs(price))
        return not math.isclose(deposit, expected, rel_tol=0, abs_tol=tolerance)

    def getPrice(self, asset, currency, day):
        key = (asset, currency, day)
        if key not in self.prices:
            try:
                self.prices[key] = PriceConversion.getPriceForCrypto(
                    asset, 1.0, currency, day=day, spotClient=self.spotClient
                )
            except PriceUnavailableError:
                self.prices[key] = None
        return self.prices[key]

    def migrate(self, content):
        # Work on fresh objects; exceptions leave the caller's data untouched.
        sets = []
        pending = []
        today = datetime.now(timezone.utc).date()
        for entry in content['binanceDataSet']:
            dataset = CryptoSet(None)
            normalized = dataset.toJSON()
            normalized.update({key: entry[key] for key in ('uuid', 'timestamp', 'time') if key in entry})
            normalized['crypto'] = [self.normalizeCrypto(c) for c in entry['crypto']]
            for currency in ('BTC', 'USDC', 'USDT'):
                if currency in entry.get('totals', {}):
                    normalized['totals'][currency] = entry['totals'][currency]
            if 'totalBTC' in entry and 'BTC' not in entry.get('totals', {}):
                normalized['totals']['BTC']['total'] = entry['totalBTC']
            dataset.fromJSON(normalized)
            sets.append(dataset)
            day = datetime.fromtimestamp(dataset.timestamp, timezone.utc).date()
            for crypto in dataset.allCryptos.values():
                converted = crypto.getConvertedTotalByName('USDC')
                if converted is not None and not self.needsRefresh(crypto, 'USDC') and (
                        converted.total is not None or not self.needsRefresh(crypto, 'USDT')):
                    continue
                if day > today:
                    raise ValueError(f'Cannot migrate future snapshot on {day}')
                pending.append((crypto, day))

        if pending:
            print(f'Migration2V8: {len(pending)} positions to check')
        for crypto, day in pending:
            for currency in ('USDC', 'USDT'):
                converted = crypto.getConvertedTotalByName(currency)
                if converted is not None and not self.needsRefresh(crypto, currency):
                    if converted.total is not None:
                        break
                    continue
                # Transient API/network errors propagate: no completed migration.
                price = self.getPrice(crypto.name, currency, day)
                if price is not None:
                    crypto.updateTotalIn(currency, unitPrice=price)
                    break
                if converted is None:
                    converted = Crypto.ConvertedTotal(currency)
                    crypto.allTotals.append(converted)
                converted.set(None, None)

        for dataset in sets:
            for currency in ('USDC', 'USDT'):
                total = CryptoSet.CryptoSetTotal(currency)
                for crypto in dataset.allCryptos.values():
                    converted = crypto.getConvertedTotalByName(currency)
                    if converted is not None and converted.total is not None:
                        total.total += converted.total
                        total.deposit += converted.deposit or 0.0
                if currency == 'USDC':
                    dataset.totalUSDC = total
                else:
                    dataset.totalUSDT = total
        return {'version': self.targetVersion, 'binanceDataSet': [s.toJSON() for s in sets]}


# The first step handles all existing legacy versions. Add Migration2V9 here
# when V9 exists; an input at V7 will then run V8 first, followed by V9.
MIGRATIONS = {8: Migration2V8}


def migrateDatabase(content, spotClient):
    version = int(content.get('version', 1))
    if version > CURRENT_DATABASE_VERSION:
        raise ValueError(f'Database V{version} is newer than supported V{CURRENT_DATABASE_VERSION}')
    if version == CURRENT_DATABASE_VERSION:
        return content
    result = deepcopy(content)
    for target, migration in sorted(MIGRATIONS.items()):
        if version < target <= CURRENT_DATABASE_VERSION:
            minimum = getattr(migration, 'minSourceVersion', target - 1)
            if version < minimum:
                raise ValueError(f'Missing migration step before V{target}: database is V{version}')
            result = migration(spotClient).migrate(result)
            if result['version'] != target:
                raise ValueError(f'Migration2V{target} did not produce V{target}')
            version = target
    if version != CURRENT_DATABASE_VERSION:
        raise ValueError(f'No migration path from V{version} to V{CURRENT_DATABASE_VERSION}')
    return result
