# gets all values from Binance and puts it into an DB
# to be used by excel or whatever
# License: MIT
# Author: mhl5k

import logging
import argparse
from dataset import BinanceDataSet
from mhl5k.settings import Settings
from mhl5k.files import Files


VERSION = "1.2"


# Functions and constants
# ------------------------

APIURL = "https://api.binance.com"


# Main start up
if __name__ == "__main__":
    print(f"Binance Check {VERSION}")

    # parse command line
    parser = argparse.ArgumentParser(description='Check binance account, gathers data and compare values between dates.')
    parser.add_argument('-d', '--days', type=int, help='Nr. of days to go back for comparison', default=0)
    parser.add_argument('-g', '--no-gather', action='store_true', help='Do not gather new dataset', default=False)
    parser.add_argument('-s', '--no-save', action='store_true', help='Do not save gathered dataset', default=False)

    args = parser.parse_args()

    compareNrOfDays = args.days

    # check account, save data, analyze difference/growth
    try:
        # Logging
        settings = Settings()
        logging.basicConfig(filename=Files.getLoggingFilenameWithPath(extension="Check"), level=logging.DEBUG, filemode="w")

        # Binance Data Set
        binanceAccountDataSet = BinanceDataSet(settings)
        binanceAccountDataSet.loadData()

        # only gather new data if not disabled
        if args.no_gather == False:
            # gather new data set
            binanceAccountDataSet.gatherNewDataSet()

        # gather open USDC values for all assets, including the new data set
        binanceAccountDataSet.gatherOpenUSDCValues()
        if args.no_save == False:
            binanceAccountDataSet.saveData()

        # analyze datasets
        binanceAccountDataSet.analyzeGrowthAndShow(compareNrOfDays)

        print("Done")

    except Exception as E:
        print("Error: %s" % E)
        exit(1)

    # exit
    exit(0)
