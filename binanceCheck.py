# gets all values from Binance and puts it into an DB
# to be used by excel or whatever
# License: MIT
# Author: mhl5k

import sys
import logging
from datetime import datetime
from binance.lib.utils import config_logging
from mhl5k.binance.dataset import BinanceDataSet
from mhl5k.settings import Settings
from mhl5k.files import Files
from mhl5k.app import App

VERSION = "0.30"

# Functions and constants
# ------------------------

APIURL = "https://api.binance.com"


def dateIsValid(date:str):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        try:
            datetime.strptime(date, '%Y-%m')
        except ValueError:
            try:
                datetime.strptime(date, '%Y')
            except ValueError:
                return False
    return True


# Main start up
if __name__ == "__main__":

    beforeDate = "before"
    lastDate = "latest"

    if len(sys.argv) > 3:
        print("Usage: %s [beforeDate [lastDate]]" % sys.argv[0])
        exit(1)

    # check before
    if len(sys.argv) >= 2:
        beforeDate = sys.argv[1]
        if dateIsValid(beforeDate) == False:
            App.errorExit(2,"Invalid format for beforeDate. Please use YYYY, YYYY-MM, or YYYY-MM-DD format.")

    # check last
    if len(sys.argv) >= 3:
        lastDate = sys.argv[2]
        if dateIsValid(lastDate) == False:
            App.errorExit(3,"Invalid format for lastDate. Please use YYYY, YYYY-MM, or YYYY-MM-DD format.")

    print("Comparing closest dataset of given beforeDate: %s and lastDate: %s" % (beforeDate, lastDate))

    try:
        # Logging
        settings = Settings()
        logging.basicConfig(filename=Files.getLoggingFilenameWithPath(extension="Check"), level=logging.DEBUG, filemode="w")
        config_logging(logging, logging.DEBUG)

        # Binance Data Set
        binanceAccountDataSet = BinanceDataSet(settings)
        binanceAccountDataSet.loadData()
        binanceAccountDataSet.gatherNewDataSet()
        binanceAccountDataSet.saveData()
        print("Done")

        # analyze datasets
        binanceAccountDataSet.analyzeGrowth(beforeDate, lastDate)

    except Exception as E:
        print("Error: %s" % E)
        exit(1)

    # exit
    exit(0)

