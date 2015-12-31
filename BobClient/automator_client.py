'''
Created on Dec 31, 2015

@author: bob
'''

import os
import urllib3
import json
import hashlib
import time
import socket
import collections
import re
import subprocess

try:
    from httplib import HTTPException
except:
    from http.client import HTTPException

try:
    import urllib2
except ImportError:
    import urllib.request as urllib2

class NotFoundHandler(object):

    '''
    Handler for UI Object Not Found exception.
    It's a replacement of audiostub watcher on device side.
    '''

    def __init__(self):
        self.__handlers = collections.defaultdict(
            lambda: {'on': True, 'handlers': []})

    def __get__(self, instance, type):
        return self.__handlers[instance.adb.device_serial()]

class AutomatorClient(object):
    
    """start and quit rpc server on device.
    """
    handlers = NotFoundHandler()  # handler UI Not Found exception
    device_port = 9081

    def __init__(self, serial=None, local_port=None,
                 adb_server_host=None, adb_server_port=None):
        self.adb = Adb(serial=serial, adb_server_host=adb_server_host,
                       adb_server_port=adb_server_port)
        self.app = None #Android RPC app instance. Can start/stop etc by this instance.
        if local_port:
            self.local_port = local_port
        else:
            try:  # first we will try to use the local port already adb forward
                for s, lp, rp in self.adb.forward_list():
                    if s == self.adb.device_serial() and \
                       rp == 'tcp:%d' % self.device_port:
                        self.local_port = int(lp[4:])
                        break
                else:
                    self.local_port = next_local_port()
            except:
                self.local_port = next_local_port()

    def download(self, filename, url):
        with open(filename, 'wb') as file:
            res = None
            try:
                res = urllib2.urlopen(url)
                file.write(res.read())
            finally:
                if res is not None:
                    res.close()

    @property
    def jsonrpc(self):
        return self.jsonrpc_wrap(
            timeout=int(os.environ.get("jsonrpc_timeout", 90)))

    def jsonrpc_wrap(self, timeout):
        server = self
        ERROR_CODE_BASE = -32000

        def _JsonRPCMethod(url, method, timeout, restart=True):
            _method_obj = JsonRPCMethod(url, method, timeout)

            def wrapper(*args, **kwargs):
                URLError = urllib3.exceptions.HTTPError if os.name == "nt" \
                    else urllib2.URLError
                try:
                    return _method_obj(*args, **kwargs)
                except (URLError, socket.error, HTTPException) as e:
                    if restart:
                        server.stop()
                        server.start(timeout=30)
                        return _JsonRPCMethod(
                            url, method, timeout, False)(*args, **kwargs)
                    else:
                        raise
                except JsonRPCError as e:
                    if e.code >= ERROR_CODE_BASE - 1:
                        server.stop()
                        server.start()
                        return _method_obj(*args, **kwargs)
                    elif e.code == ERROR_CODE_BASE - 2 and self.handlers['on']:
                        # Not Found
                        try:
                            self.handlers['on'] = False
                            # any handler returns True
                            # will break the left handlers
                            any(handler(self.handlers.get('device', None))
                                for handler in self.handlers['handlers'])
                        finally:
                            self.handlers['on'] = True
                        return _method_obj(*args, **kwargs)
                    raise
            return wrapper

        return JsonRPCClient(self.rpc_uri,
                             timeout=timeout,
                             method_class=_JsonRPCMethod)

    def __jsonrpc(self):
        return JsonRPCClient(self.rpc_uri,
                             timeout=int(os.environ.get("JSONRPC_TIMEOUT", 90)))

    def start(self, timeout=5):
        self.app.startservice()
        self.adb.forward(self.local_port, self.device_port)

        while not self.alive and timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
        if not self.alive:
            raise IOError("RPC server not started!")

    def ping(self):
        try:
            return self.__jsonrpc().ping()
        except:
            return None

    @property
    def alive(self):
        '''Check if the rpc server is alive.'''
        return self.ping() == "pong"

    def stop(self):
        '''Stop the rpc server.'''
        res = None
        try:
            res = urllib2.urlopen(self.stop_uri)
        except:
            pass
        finally:
            if res is not None:
                res.close()
        try:
            self.app.startservice("stop")
            self.app.forcestop()
        except:
            pass

    @property
    def stop_uri(self):
        return "http://localhost:%d/stop" % self.local_port

    @property
    def rpc_uri(self):
        return "http://localhost:%d/jsonrpc/0" % self.local_port

def next_local_port():
    def is_port_listening(port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        return result == 0

    global _init_local_port
    _init_local_port = (_init_local_port + 1
                        if _init_local_port < 32764
                        else 9080)
    while is_port_listening(_init_local_port):
        _init_local_port += 1
    return _init_local_port

class Adb(object):

    def __init__(self, serial=None, adb_server_host=None, adb_server_port=None):
        self.__adb_cmd = None
        self.default_serial = serial if serial \
            else os.environ.get("ANDROID_SERIAL", None)
        self.adb_server_host = adb_server_host
        self.adb_server_port = adb_server_port

    def adb(self):
        if self.__adb_cmd is None:
            if "ANDROID_HOME" in os.environ:
                filename = "adb.exe" if os.name == 'nt' else "adb"
                adb_cmd = os.path.join(os.environ["ANDROID_HOME"],
                                       "platform-tools", filename)
                if not os.path.exists(adb_cmd):
                    raise EnvironmentError(
                        "Adb not found in $ANDROID_HOME path: %s."
                        % os.environ["ANDROID_HOME"])
            else:
                import distutils
                if "spawn" not in dir(distutils):
                    import distutils.spawn
                adb_cmd = distutils.spawn.find_executable("adb")
                if adb_cmd:
                    adb_cmd = os.path.realpath(adb_cmd)
                else:
                    raise EnvironmentError("$ANDROID_HOME environment not set.")
            self.__adb_cmd = adb_cmd
        return self.__adb_cmd

    def cmd(self, *args):
        '''adb command, add -s serial by default.
            return the subprocess.Popen object.
        '''
        serial = self.device_serial()
        if serial.find(" ") > 0:
            # TODO how to include special chars on command line
            serial = "'%s'" % serial
        cmd_line = ["-s", serial] + list(args)
        if self.adb_server_port:  # add -P argument
            cmd_line = ["-P", str(self.adb_server_port)] + cmd_line
        if self.adb_server_host:  # add -H argument
            cmd_line = ["-H", self.adb_server_host] + cmd_line
        return self.raw_cmd(*cmd_line)

    def raw_cmd(self, *args):
        '''adb command. return the subprocess.Popen object.'''
        cmd_line = [self.adb()] + list(args)
        if os.name != "nt":
            cmd_line = [" ".join(cmd_line)]
        return subprocess.Popen(cmd_line, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    def device_serial(self):
        devices = self.devices()
        if not devices:
            raise EnvironmentError("Device not attached.")

        if self.default_serial:
            if self.default_serial not in devices:
                raise EnvironmentError("Device %s not connected!"
                                       % self.default_serial)
        elif len(devices) == 1:
            self.default_serial = list(devices.keys())[0]
        else:
            raise EnvironmentError("Multiple devices attached" +
                                   " but default android serial not set.")
        return self.default_serial

    def devices(self):
        '''
        get a dict of attached devices.
        key is the device serial, value is device name.
        '''
        out = self.raw_cmd("devices").communicate()[0].decode("utf-8")
        match = "List of devices attached"
        index = out.find(match)
        if index < 0:
            raise EnvironmentError("adb is not working.")
        return dict([s.split("\t")
                     for s in out[index + len(match):].strip().splitlines()
                     if s.strip()])

    def forward(self, local_port, device_port):
        '''adb port forward. return 0 if success, else non-zero.'''
        return self.cmd("forward",
                        "tcp:%d" % local_port,
                        "tcp:%d" % device_port).wait()

    def forward_list(self):
        '''adb forward --list'''
        version = self.version()
        if int(version[1]) <= 1 \
           and int(version[2]) <= 0 \
           and int(version[3]) < 31:
            raise EnvironmentError("Low adb version.")
        lines = self.raw_cmd("forward", "--list").communicate()[0]\
            .decode("utf-8").strip().splitlines()
        return [line.strip().split() for line in lines]

    def forward_remove(self, local_port):
        ''' adb forward remove <local> '''
        return self.cmd("forward", "--remove", str(local_port))

    def version(self):
        '''adb version'''
        m = re.search(r"(\d+)\.(\d+)\.(\d+)",
                      self.raw_cmd("version").communicate()[0].decode("utf-8"))
        return [m.group(i) for i in range(4)]
class JsonRPCError(Exception):

    def __init__(self, code, message):
        self.code = int(code)
        self.message = message

    def __str__(self):
        return "JsonRPC Error code: %d, Message: %s" % (self.code, self.message)

class JsonRPCMethod(object):

    if os.name == 'nt':
        try:
            pool = urllib3.PoolManager()
        except:
            pass

    def __init__(self, url, method, timeout=30):
        self.url, self.method, self.timeout = url, method, timeout

    def __call__(self, *args, **kwargs):
        if args and kwargs:
            raise SyntaxError("Could not accept both *args and **kwargs as JSONRPC parameters.")
        data = {"jsonrpc": "2.0", "method": self.method, "id": self.id()}
        if args:
            data["params"] = args
        elif kwargs:
            data["params"] = kwargs
        jsonresult = {"result": ""}
        if os.name == "nt":
            res = self.pool.urlopen("POST",
                                    self.url,
                                    headers={"Content-Type": "application/json"},
                                    body=json.dumps(data).encode("utf-8"),
                                    timeout=self.timeout)
            jsonresult = json.loads(res.data.decode("utf-8"))
        else:
            result = None
            try:
                req = urllib2.Request(self.url,
                                      json.dumps(data).encode("utf-8"),
                                      {"Content-type": "application/json"})
                result = urllib2.urlopen(req, timeout=self.timeout)
                jsonresult = json.loads(result.read().decode("utf-8"))
            finally:
                if result is not None:
                    result.close()
        if "error" in jsonresult and jsonresult["error"]:
            raise JsonRPCError(
                jsonresult["error"]["code"],
                "%s: %s" % (jsonresult["error"]["data"]["exceptionTypeName"], jsonresult["error"]["message"])
            )
        return jsonresult["result"]

    def id(self):
        m = hashlib.md5()
        m.update(("%s at %f" % (self.method, time.time())).encode("utf-8"))
        return m.hexdigest()

class JsonRPCClient(object):

    def __init__(self, url, timeout=30, method_class=JsonRPCMethod):
        self.url = url
        self.timeout = timeout
        self.method_class = method_class

    def __getattr__(self, method):
        return self.method_class(self.url, method, timeout=self.timeout)