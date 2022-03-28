# class to handle Colors for printing
# License: MIT
# Author: mhl5k

__version__ = "0.11"

from turtle import color


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

# Test function for module  
def _test():
    # tests
    assert Colors.getColorByGLTZero(-0.1) == Colors.CRED
    assert Colors.getColorByGLTZero(0.1) == Colors.CGREEN
    assert Colors.getColorByGLTZero(0) == Colors.CRESET
    
    # end
    print(__file__+" "+__version__+": All module tests did run fine.")

# when file ist started directlx
if __name__ == '__main__':
    _test()