# binanceCheck
## used for
checks your binance account with the given API key.

* binanceCheck: It collects all currencies you have in savings (flexibel),
liquid swap and your amounts in the wallet used for spot orders. It shows the growth across datasets.
* binanceTradeTimeProgress: Checks all trading pairs, rates and prints 5m, 1h, 1d growth. 
You can specify parts of trading pairs as parameter e.g. BTC, ETH, ETHBTC, etc.

Use this code as starting point to gather information from Binance.
Due to missing APIs to access all Binance products, you may see wrong
values in your assets, because they cannot be gathered.

It saves all data in a json file, so it can be used to visualize it 
with other analyzing tools.

It shows the growth of your currencies, for example
when you are using Binance Earn or Trading them.

When calculating the BTC total price, the pair price of
Crypto/BTC or BTC/crypto is checked. Whenever there is no BTC
pair available, Crypto/USDT or USDT/crypto pair is checked first,
and then USDT/BTC is used.

## open requests, issues
* cannot show locked savings yet (could not find any API yet)
* cannot show locked stakings yet (could not find any API yet)

## API requirements
The program requires an Binance API key and API secret.
The binance API must enable the "Read" functionality only.

## If you find it useful...
... in any way, you can send me a coffee.
* https://www.buymeacoffee.com/mhl5k

or
* RVN:  REUCghmYBrmzq2VhTkkXcEr4HZjHinZuWM
* DOGE: DHuDg2CNALDrYnAK4FYiodYN1tioSVbk6R

## the end
