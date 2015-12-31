'''
Created on Dec 31, 2015

@author: bob
'''

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
from android.adb import Adb

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

class AutoStub(object):
    
    """start and quit rpc server on device.
    """
    handlers = NotFoundHandler()  # handler UI Not Found exception
    device_port = 9083
    local_port = 0

    def __init__(self, adb = None, serial=None, local_port=None,
                 adb_server_host=None, adb_server_port=None):
        self.adb = adb if adb else Adb(serial=serial, adb_server_host=adb_server_host,
                       adb_server_port=adb_server_port)
        self.serial = self.adb.device_serial()
        self.local_port = local_port if local_port else self.get_local_port()
        #self.app = AudioStubApp(serial)

    def get_local_port(self):
        def is_port_listening(port):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = s.connect_ex(('127.0.0.1', port))
            s.close()
            return result == 0

        try:  # first we will try to use the local port already adb forward
            for s, lp, rp in self.adb.forward_list():
                if s == self.adb.device_serial() and \
                   rp == 'tcp:%d' % self.device_port:
                    return int(lp[4:])
                    break

            init_local_port = 9080
            while is_port_listening(init_local_port):
                if init_local_port >= 32764:
                    raise Exception("Can't find free local port to forward!!")
                init_local_port += 1
            return init_local_port
        except:
            raise Exception("Can't find port to bind")

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