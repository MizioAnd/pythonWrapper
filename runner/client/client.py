# -*- coding: utf-8 -*-
"""
@since 09/04/2015
"""
import logging
from jsonrpclib import Server
import subprocess
import os
import datetime

__author__ = 'sposs'


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
        #try:
        res = self._server.execute(self._pdict, cleanup)
        #except KeyboardInterrupt:
        #   server2 = Server(self.url)
        #   server2.kill()
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
