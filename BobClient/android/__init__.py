from adb import Adb
from autostub import AutoStub
from uiauto import UiAuto

class TestDevice(object):
    def __init__(self, serial = None):
        self.adb = Adb(serial = serial)
        self.autostub = AutoStub(adb = self.adb)
        self.ui = UiAuto(self.adb.device_serial())