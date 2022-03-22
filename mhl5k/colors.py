# class to handle Binance crypto values
# License: MIT
# Author: mhl5k
# 

class Colors:
    CGREEN="\033[92m"
    CRED="\033[91m"
    CRESET="\033[0m"

    # get red, green or white whether lower, greater, equal to zero
    def getColorByGLTZero(value:float) -> str:
        color=Colors.CRESET
        if value<0: color=Colors.CRED
        if value>0: color=Colors.CGREEN
        return color
