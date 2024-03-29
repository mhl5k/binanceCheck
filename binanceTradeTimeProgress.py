# shows all Binance trading pairs with progress over 5min, 1h, 24h, ... 
# 
# License: MIT
# Author: mhl5k

import sys
import logging
from binance.lib.utils import config_logging
from mhl5k.binance.dataset import BinanceDataSet
from mhl5k.settings import Settings
from mhl5k.files import Files
from mhl5k.app import App

VERSION = "0.12"

# Functions and constants
# ------------------------

APIURL="https://api.binance.com"

# Main start up
# -------------
App.printName(version=VERSION)

# limit to command line parameter
argFilter=""
if len(sys.argv) == 2:
    argFilter=sys.argv[1]

# load settings
settings=Settings()

config_logging(logging, logging.DEBUG, Files.getLoggingFilenameWithPath())

try:
    # Binance Account Data Set
    binanceAccountDataSet=BinanceDataSet(settings)
    binanceAccountDataSet.showTradeTimeProgress(filter=argFilter)

except Exception as E:
    print("Error: %s" % E)
    exit(1)

# exit
exit(0)
