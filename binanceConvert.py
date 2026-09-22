# converts a given value and currency to other currencies
# given via command line parameters
# License: MIT
# Author: mhl5k

import logging
import argparse

from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import CONVERT_REST_API_PROD_URL
from binance_sdk_convert.convert import Convert

from mhl5k.settings import Settings
from mhl5k.files import Files


VERSION = "0.4"


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

        configuration = ConfigurationRestAPI(
            api_key=settings.current["apiKey"],
            api_secret=settings.current["apiSecret"],
            base_path=CONVERT_REST_API_PROD_URL,
        )

        convertClient = Convert(config_rest_api=configuration)

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

            quote_response = convertClient.rest_api.send_quote_request(
                from_asset=args.fromCurrency,
                to_asset=eachTo,
                from_amount=amount,
                wallet_type="SPOT_EARN",
            )

            quote = quote_response.data()

            print(f"Request: {quote}")
            if quote.quote_id:
                accepted_response = convertClient.rest_api.accept_quote(quote_id=quote.quote_id)
                accepted = accepted_response.data()
                print(f"Accepted: {accepted}")
            else:
                print(f"Error, quote ID not found: {quote}")

    except Exception as E:
        print("Error: %s" % E)
        exit(1)

    # exit
    exit(0)
