'''
Created on Dec 31, 2015

@author: bob
'''
from android import TestDevice

if __name__ == '__main__':
    d = TestDevice()
    print d.autostub.ping()