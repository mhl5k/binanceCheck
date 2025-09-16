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
when you are using Binance Earn or Trading them.

When calculating the BTC total price, the pair price of
Crypto/BTC or BTC/crypto is checked. Whenever there is no BTC
pair available, Crypto/USDC or USDC/crypto pair is checked first,
and then USDC/BTC is used.

## API requirements
The program requires an Binance API key and API secret.
The binance API must enable the "Read" functionality only.

## If you find it useful...
DOGE: D9p216o9FmYwJXr6PHoDFGM2jgKgVCGrbE

## the end
