# gets all values from Binance and puts it into an DB 
# to be used by excel or whatever
# License: MIT
# Author: mhl5k

import logging
from binance.lib.utils import config_logging
from mhl5k.binance.dataset import BinanceDataSet
from mhl5k.settings import Settings
from mhl5k.files import Files
from mhl5k.app import App

VERSION = "0.13"

# Functions and constants
# ------------------------

APIURL="https://api.binance.com"

# Main start up
# -------------
App.printName(version=VERSION)

settings=Settings()

config_logging(logging, logging.DEBUG, Files.getLoggingFilenameWithPath())

try:
    # Binance Account Data Set
    binanceAccountDataSet=BinanceDataSet(settings)
    binanceAccountDataSet.loadData()
    binanceAccountDataSet.gatherNewDataSet()
    binanceAccountDataSet.saveData()
    print("Done")

    # analyze datasets
    binanceAccountDataSet.analyzeGrowth()

except Exception as E:
    print("Error: %s" % E)
    exit(1)

# exit
exit(0)
