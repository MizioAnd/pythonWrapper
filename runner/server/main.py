# -*- coding: utf-8 -*-
"""
@since 09/04/2015
"""
import SocketServer
from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
from argparse import ArgumentParser
import signal
import logging
import psutil
import subprocess
import datetime
import threading
import os
import time
import shutil
import zmq

__author__ = 'sposs'


def get_dummy():
    """
    Only needed because of the ping
    :return: True
    """
    return True


class ThreadedSJONRPCServer(SocketServer.ThreadingMixIn, SimpleJSONRPCServer):
    def __init__(self, *args, **kwargs):
        SimpleJSONRPCServer.__init__(self, *args, **kwargs)


class Monitor(threading.Thread):
    """
    This thing takes care of monitoring
    """
    def __init__(self, process):
        threading.Thread.__init__(self)
        self.running = True
        self.process = process
        self.peak = 0
        self.avg = 0
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind("tcp://*:47802")

    def stop(self):
        self.running = False
        
    def run(self):
        meas = 0
        vals = 0
        while self.running:
            if len(self.process.memory_info_ex()) > 1:
                mem = self.process.memory_info_ex()[1]
            else:
                mem = 0
            for child in self.process.children():
                if len(child.memory_info_ex()) > 1:
                    mem += child.memory_info_ex()[1]
            if mem > self.peak:
                self.peak = mem
            meas += 1
            self.socket.send_string("memory %s" % mem)
            vals += mem
            time.sleep(1)
        self.avg = float(vals)/meas

    def get_stats(self):
        return {"peak": self.peak, "avg": self.avg}


class Runner(object):
    def __init__(self, host, port, repo_path):
        super(Runner, self).__init__()
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.addHandler(logging.StreamHandler())
        self.log.setLevel(logging.INFO)
        self._server = None
        self.port = port
        self.host = host
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        self.path_to_svn_repo = repo_path
        self.process = None

    def stop(self, signum, frame):
        self.finalize()
        exit(0)

    def finalize(self):
        pass

    def execute(self, pdict=None, rmdir=False):
        """
        Main element: executes the code
        :return:
        """
        if pdict is None:
            raise ValueError("pdict MUST be set")
        for item in ["nicenessVal", "cpuRangeVal", "outputDir"]:
            if item not in pdict:
                raise ValueError("Missing %s in pdict" % item)

        curdir = os.getcwd()
        os.chdir(self.path_to_svn_repo)
        # Start by svn upping
        subprocess.check_call(["svn", "up"])
        os.chdir(curdir)
        if os.path.isdir(pdict["outputDir"]) and rmdir:
                shutil.rmtree(pdict["outputDir"])
        os.makedirs(pdict["outputDir"])
        os.chdir(pdict["outputDir"])
        # now execute matlabscript
        now = datetime.datetime.utcnow()

        self.process = psutil.Popen(["matlabscript2014", "-n", str(pdict["nicenessVal"]), "-c",
                                    str(pdict["cpuRangeVal"]), "LinTimelyOscSolCurrent"], stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
        mon = Monitor(self.process)
        mon.start()
        (stdout, stderr) = self.process.communicate()
        mon.stop()
        mon.join()
        result = {}
        result.update(mon.get_stats())
        delta = datetime.datetime.utcnow() - now
        result["Wallclock"] = str(delta)
        result["StdOut"] = stdout
        result["StdErr"] = stderr
        os.chdir(curdir)
        return result

    def kill(self):
        """
        Kill the program
        :return: None
        """
        self.log.info("Killing program")
        for child in self.process.children():
            child.kill()
        self.process.kill()

    def run(self):
        self.log.info("Serving on %s:%s" % (self.host, self.port))
        self._server = ThreadedSJONRPCServer((self.host, self.port))
        self._server.register_function(self.execute)
        self._server.register_function(self.kill)
        self._server.register_function(get_dummy, "ping")
        self._server.register_introspection_functions()
        self._server.serve_forever()


def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", help="Server port", dest="port", required=True, type=int)
    parser.add_argument("--host", help="Host to use", dest="host", required=True)
    parser.add_argument("--repo-path", help="Path to SVN repo on this host", dest="repopath", required=True)
    options = parser.parse_args(args)
    r = Runner(options.host, options.port, options.repopath)
    r.run()


if __name__ == "__main__":
    main(["--host", "localhost", "-p", "5555"])
