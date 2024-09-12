# gets all values from Binance and puts it into an DB
# to be used by excel or whatever
# License: MIT
# Author: mhl5k

import logging
import argparse
from binance.lib.utils import config_logging
from dataset import BinanceDataSet
from mhl5k.settings import Settings
from mhl5k.files import Files


VERSION = "0.40"

# Functions and constants
# ------------------------

APIURL = "https://api.binance.com"


# Main start up
if __name__ == "__main__":

    # parse command line
    parser = argparse.ArgumentParser(description='Check binance account, gathers data and compare values between dates.')
    parser.add_argument('-1', '--set1', type=str, help='Date of dataset 1')
    parser.add_argument('-2', '--set2', type=str, help='Date of dataset 2')
    parser.add_argument('-g', '--no-gather', action='store_true', help='Do not gather new dataset')

    args = parser.parse_args()

    set1Date = args.set1 if args.set1 else "before"
    set2Date = args.set2 if args.set2 else "latest"

    # check account, save data, analyze difference/growth
    try:
        # Logging
        settings = Settings()
        logging.basicConfig(filename=Files.getLoggingFilenameWithPath(extension="Check"), level=logging.DEBUG, filemode="w")
        config_logging(logging, logging.DEBUG)

        # Binance Data Set
        binanceAccountDataSet = BinanceDataSet(settings)
        binanceAccountDataSet.loadData()
        if args.no_gather == False:
            binanceAccountDataSet.gatherNewDataSet()
        binanceAccountDataSet.saveData()
        print("Done")

        # analyze datasets
        binanceAccountDataSet.analyzeGrowthAndShow(set1Date, set2Date)

    except Exception as E:
        print("Error: %s" % E)
        exit(1)

    # exit
    exit(0)
