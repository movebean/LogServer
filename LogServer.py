import sys
import logging

from gevent import socket
from gevent.greenlet import Greenlet
from gevent.hub import getcurrent
from gevent.server import StreamServer
import gevent

__all__ = ['LogServer']

class _Greenlet_stdreplace(Greenlet):
    _fileobj = None

    def switch(self, *args, **kw):
        if self._fileobj is not None:
            self.switch_in()
        Greenlet.switch(self, *args, **kw)

    def switch_in(self):
        self.saved = sys.stdin, sys.stderr, sys.stdout
        sys.stdin = sys.stdout = sys.stderr = self._fileobj

    def switch_out(self):
        sys.stdin, sys.stderr, sys.stdout = self.saved
        self.saved = None

    def run(self):
        try:
            return Greenlet.run(self)
        finally:
            # XXX why is this necessary?
            self.switch_out()

class _fileobject(socket._fileobject):

    def __init__(self, log_server, *args, **kwds):
        socket._fileobject.__init__(self, *args, **kwds)
        self.log_server = log_server

    def write(self, data):
        try:
            self._sock.sendall(data)
        except Exception as e:
            self.log_server.do_close(self._sock)
            if self._sock:
                self._sock.close()
            self.close()
            print type(e), str(e)

    def isatty(self):
        return True

    def flush(self):
        pass

    def readline(self, *a):
        return socket._fileobject.readline(self, *a).replace("\r\n", "\n")

class LogServer(StreamServer):

    def __init__(self, listener, logger, **server_args):
        StreamServer.__init__(self, listener, spawn=_Greenlet_stdreplace.spawn, **server_args)
        self.logger = logger

    def handle(self, socket, address):
        f = getcurrent()._fileobj = _fileobject(self, socket)
        getcurrent().switch_in()
        try:
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
            s_handler = logging.StreamHandler()
            s_handler.setFormatter(formatter)
            self.logger.addHandler(s_handler)
            socket.logger_handler = s_handler
            socket.peer_name = str(socket.getpeername())
        except Exception as e:
            self.logger.info("Get log connection ERROR %s" % str(e))
            return
        finally:
            self.logger.info("Finish accept connection")
        self.logger.info("Get log connection from %s SUCCESS" % str(socket.getpeername()))

    def serve_forever(self, *args, **kwds):
        return gevent.spawn(super(LogServer, self).serve_forever, *args, **kwds)

    def do_close(self, socket, *args):
        if not socket:
            return
        self.logger.removeHandler(socket.logger_handler)
        socket.close()
        self.logger.info("RemoveHandler from peer %s" % socket.peer_name)


if __name__ == '__main__':
  import datetime
  import logging
  import gevent

  def InitLog():
    ' InitLog'
    global _normal

    now = datetime.datetime.now()
    handler = logging.FileHandler("./log/abs_log_{0}.txt".format(now.strftime("%Y%m%d_%H%M%S")))
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    _normal = logging.getLogger('_normal')
    _normal.addHandler(handler)
    _normal.setLevel(logging.DEBUG)


  def Func1():
    i = 0
    while i < 10:
      i += 1
      _normal.info(1)
      gevent.sleep(1)

  work = gevent.spawn(Func1)
  InitLog()
  server = LogServer(('127.0.0.1', 9000), _normal)
  server.serve_forever()
  gevent.wait([work])
