# converts a given value and currency to other currencies
# given via command line parameters
# License: MIT
# Author: mhl5k

import logging
import argparse

from binance.spot import Spot as SpotClient
from binance.lib.utils import config_logging

from mhl5k.settings import Settings
from mhl5k.files import Files


VERSION = "0.3"


# Functions and constants
# ------------------------

APIURL = "https://api.binance.com"


# Main start up
if __name__ == "__main__":
    print(f"Binance Convert {VERSION}")

    # parse command line
    parser = argparse.ArgumentParser(description='Converts a given value and currency to other currencies')
    parser.add_argument('-f', '--fromCurrency', type=str, help='Currency to convert from', required=True)
    parser.add_argument('-v', '--value', type=float, help='Value to convert', required=True)
    parser.add_argument('-t', '--toCurrency', type=str,help='Currency to convert to, can be multiple', required=True,default=[""],nargs='+')
    parser.add_argument('-d', '--dontKeep', action='store_true', help='Do not keep a portion for from currency', default=False)

    args = parser.parse_args()

    # check account, save data, analyze difference/growth
    try:
        # settings
        settings = Settings()

        # logging
        logging.basicConfig(filename=Files.getLoggingFilenameWithPath(extension="Convert"), level=logging.DEBUG, filemode="w")
        config_logging(logging, logging.DEBUG)

        # Binance Data Set
        spotClient = SpotClient(settings.current["apiKey"], settings.current["apiSecret"])

        # convert
        # amount is # of currencies to convert + keep a portion for the original currency
        number_portion = len(args.toCurrency)
        number_portion = number_portion + (0 if args.dontKeep else 1)
        amount = args.value / number_portion
        # cut amount at 8 decimal places
        amount = round(amount, 8)
        print(f"Converting {args.value} {args.fromCurrency} to {args.toCurrency} each {amount}")
        for eachTo in args.toCurrency:
            print(f"Converting {amount} {args.fromCurrency} to {eachTo}")
            quote = spotClient.send_quote_request(args.fromCurrency,eachTo,fromAmount=amount,walletType="SPOT_EARN")
            print(f"Request: {quote}")
            if "quoteId" in quote:
                # {'ratio': '55.0539', 'inverseRatio': '0.018164', 'validTimestamp': 1774010843257, 'toAmount': '1.98194159', 'fromAmount': '0.036'}
                accepted = spotClient.accept_quote(quote["quoteId"])
                print(f"Accepted: {accepted}")
            else:
                print(f"Error, quote ID not found: {quote}")

    except Exception as E:
        print("Error: %s" % E)
        exit(1)

    # exit
    exit(0)
