# class to handle app (main python file) stuff
# License: MIT
# Author: mhl5k

import sys


class App:

    @staticmethod
    def printName(version:str):
        print("%s %s by mhl5k, MIT license" % (sys.argv[0],version))

    @staticmethod
    def errorExit(nr:int,text:str):
        print(text)
        exit(nr)
