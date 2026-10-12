# binanceCheck

## bugs, issues, open requests
* liquid earning removed (API has been removed)
* recurring buy not visible in FIAT deposit (no API endpoint yet)

## used for
checks your binance account with the given API key.

* binanceCheck: It collects all currencies you have in wallet, earn flexibel and staking,
and your amounts in the wallet used for spot orders. It shows the growth across datasets.

Use this code as starting point to gather information from Binance.
Due to missing APIs to access all Binance products, you may see wrong
values in your assets, because they cannot be gathered.

It saves all data in a json file, so it can be used to visualize it 
with other analyzing tools.

It shows the growth of your currencies, for example
when you are using Binance Earn or trading them.

When calculating the BTC total price, the pair price of
Crypto/BTC or BTC/crypto is checked. Whenever there is no BTC
pair available, Crypto/USDC or USDC/crypto pair is checked first,
and then USDC/BTC is used.

## API requirements
The program requires an Binance API key and API secret.
The binance API must enable the "Read" functionality only.

## Database migrations

Loading an older database runs the ordered migrations in `migrations.py`
before loading the current format. `Migration2V8` normalizes legacy fields,
repairs conversions, fills historical USDC values with USDT as fallback,
and recalculates the corresponding dataset totals. Confirmed missing prices
are stored as `null`. Temporary API failures abort the run without saving.
Before migration, an exact copy is created next to the database and its name
is printed, for example `database.pre-migration-v8-20261012.json`. Existing
backups are preserved by adding a numbered suffix to the next backup.

A V8 database is loaded without legacy checks or historical price requests.
For V9, add `Migration2V9` to `MIGRATIONS` and update
`CURRENT_DATABASE_VERSION`. A V7 database will run V8, then V9; each step
works with the preceding format. Migration results are saved by the regular
save step; `--no-save` keeps the original file unchanged.

## If you find it useful...
DOGE: D9p216o9FmYwJXr6PHoDFGM2jgKgVCGrbE

## the end
