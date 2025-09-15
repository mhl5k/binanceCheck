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


VERSION = "0.43"

# Functions and constants
# ------------------------

APIURL = "https://api.binance.com"


# Main start up
if __name__ == "__main__":
    print(f"Binance Check {VERSION}")

    # parse command line
    parser = argparse.ArgumentParser(description='Check binance account, gathers data and compare values between dates.')
    parser.add_argument('-o', '--setolder', type=str, help='Date of older dataset, YYYY-MM-DD | YYYY-MM | YYYY')
    parser.add_argument('-n', '--setnewer', type=str, help='Date of newer dataset, YYYY-MM-DD | YYYY-MM | YYYY')
    parser.add_argument('-g', '--no-gather', action='store_true', help='Do not gather new dataset')

    args = parser.parse_args()

    setOlderDate = args.setolder if args.setolder else "before"
    setNewerDate = args.setnewer if args.setnewer else "latest"

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
        binanceAccountDataSet.analyzeGrowthAndShow(setOlderDate, setNewerDate)

    except Exception as E:
        print("Error: %s" % E)
        exit(1)

    # exit
    exit(0)
