# -*- coding: utf-8 -*-

import os
import sys
import signal

from twisted.internet import reactor
from twisted.python import log
from scrapy.crawler import _get_spider_loader
from scrapy.utils.project import get_project_settings
from scrapyd.utils import get_crawl_args
from scrapyd import launcher
from scrapyd import runner
from scrapyd.interfaces import IEnvironment


class Launcher(launcher.Launcher):

    protocol_cls = launcher.ScrapyProcessProtocol

    def _set_timeout(self, process):
        with runner.project_environment(process.project):
            loader = _get_spider_loader(get_project_settings())
            spider = loader.load(process.spider)
            timeout = getattr(spider, 'timeout', None)
            if timeout:
                timeout = int(spider.timeout)
                log.msg('Spider has timeout of {} min'.format(timeout))
                reactor.callLater(
                    timeout * 60, self.terminate_process, process)

    def _spawn_process(self, message, slot):
        msg = message
        project = msg['_project']
        args = [sys.executable, '-m', self.runner, 'crawl']
        args += get_crawl_args(msg)
        e = self.app.getComponent(IEnvironment)
        env = e.get_environment(msg, slot)
        pp = self.protocol_cls(slot, project, msg['_spider'], msg['_job'], env)
        pp.deferred.addBoth(self._process_finished, slot)
        reactor.spawnProcess(pp, sys.executable, args=args, env=env)
        self.processes[slot] = pp
        self._set_timeout(pp)

    def terminate_process(self, process):
        log.msg('Terminating "{}"'.format(process.job))
        process.transport.signalProcess(signal.SIGTERM)
        reactor.callLater(10, self.kill_process, process.pid)

    def kill_process(self, pid):
        log.msg('Kill pid: {}'.format(pid))
        os.kill(pid, signal.SIGKILL)
