# -*- coding: utf-8 -*-
"""
@since 09/04/2015
"""
import logging
import socket
import threading
from jsonrpclib import Server
import subprocess
import os
import datetime
import zmq
import time

__author__ = 'sposs'


class Monitoring(threading.Thread):
    """
    This is a monitoring thread, tells the Memory used
    """
    def __init__(self, host):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.addHandler(logging.StreamHandler())
        self.log.setLevel(logging.INFO)
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.SUB)
        self.message = u"memory"
        self.socket.setsockopt_string(zmq.SUBSCRIBE, self.message)
        self.socket.connect("tcp://%s:47802" % host)
        time.sleep(0.5)
        self.running = True
        self.poll = zmq.Poller()
        self.poll.register(self.socket, zmq.POLLIN)

    def run(self):
        while self.running:
            socks = self.poll.poll(1000)
            if self.socket in socks:
                message = self.socket.recv_string()
                if not message:
                    continue
                message = message.replace(self.message, "")
                self.log.info("\rMemory: %s" % float(message.strip())/1024**3)

    def stop(self):
        self.running = False


class Client(object):
    def __init__(self, host, port):
        super(Client, self).__init__()
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.addHandler(logging.StreamHandler())
        self.log.setLevel(logging.INFO)
        self.url = "http://%s:%s" % (host, port)
        self.log.info("Connecting to %s" % self.url)
        self._server = Server(self.url)
        try:
            self._server.ping()
        except:
            raise EnvironmentError("Server unavailable")
        self._pdict = {}
        self.message = ""
        self.monitor = Monitoring(host)
        self.monitor.start()

    def commit(self, path, message):
        """
        Commit before running
        :param path: path to svn repository
        :param message: a commit message
        :return:
        """
        curdir = os.getcwd()
        self.message = message
        os.chdir(path)
        subprocess.check_call(["svn", "up"])
        subprocess.check_call(["svn", "commit", "-m", message])
        os.chdir(curdir)

    def set_parameters(self, pdict):
        """
        Run parameters
        :param pdict:
        :return:
        """
        self._pdict = pdict

    def execute(self, cleanup=True):
        """
        Execute the bugger
        :return:
        """
        res = None
        try:
            res = self._server.execute(self._pdict, cleanup)
        except KeyboardInterrupt:
            self.monitor.stop()
            server2 = Server(self.url)
            server2.kill()
        except socket.error:
            self.log.error("Server was interrupted")
            exit(1)
        finally:
            self.monitor.stop()
        if res is None:
            raise ValueError("Run failed")
        resstr = "%s\t%s\t %s\t %s\t %s\t %s\t %s" % (str(datetime.datetime.utcnow()), self.message, 
                                                      self._pdict["cpuRangeVal"], self._pdict["outputDir"],
                                                      res["Wallclock"], res["peak"]/1024.**3, res["avg"]/1024**3)
        self.log.info("date \t\t\t message \t\t cpu \t outputdir \t time \t peak_mem \t avg_mem")
        self.log.info(resstr)
        with open(os.path.expanduser("~/result.dat"), "a") as out:
            out.write(resstr+"\n")


if __name__ == "__main__":
    c = Client("th1.mpq.univ-paris-diderot.fr", 47801)
    c.set_parameters({"nicenessVal": 0, "cpuRangeVal": "0-2", "outputDir": "some_other_dir"})
    c.commit("/Users/mizio/Documents/MizioSpatafora/stefMount/Documents/current", "Another test message")
    c.execute()
