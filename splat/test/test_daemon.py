#!/usr/bin/env python
# test_daemon.py vi:ts=4:sw=4:expandtab:
#
# Scalable Periodic LDAP Attribute Transmogrifier
# Authors:
#       Landon Fuller <landonf@threerings.net>
#       Will Barton <wbb4@opendarwin.org>
#
# Copyright (c) 2005 Three Rings Design, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright owner nor the names of contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

""" Splat Daemon Unit Tests """

from twisted.trial import unittest
from twisted.internet import reactor, defer

from splat import daemon 
from splat import plugin
from splat import ldaputils

import test_plugin
import slapd

# Useful Constants
from splat.test import DATA_DIR

# Faked Exception
class FakeException(Exception):
    pass

# Mock Helper
class MockHelper(plugin.Helper):
    def __init__(self):
        super(plugin.Helper, self).__init__()
        self.done = False
        self.failure = None
        self.exception = False

    def attributes(self):
        return ('uid',)

    def work(self, context, ldapEntry, modified):
        # Blow a gasket if an exception has been provided
        if (self.exception == True):
            self.failure = "Forced exception"
            self.done = True
            raise FakeException, "Forced exception"

        uid = ldapEntry.attributes['uid'][0]
        if(uid != 'john'):
            self.failure = "Incorrect LDAP attribute returned (Wanted: 'john', Got: '%s')" % uid
        self.done = True

    def parseOptions(self, options):
        return None

    def modify(self, ldapEntry, modifyList):
        pass

    def convert(self):
        pass

# Test Cases
class ContextTestCase(unittest.TestCase):
    """ Test Splat Helper """
    def setUp(self):
        self.slapd = slapd.LDAPServer()
        conn = ldaputils.Connection(slapd.SLAPD_URI)
        self.ctx = daemon.Context(conn)
        self.hc = plugin.HelperController('test', 'splat.test.test_daemon', 1, 'ou=People,dc=example,dc=com', '(uid=john)', False, None)

        self.done = False
        self.failure = None

    def tearDown(self):
        self.slapd.stop()

    def succeeded(self):
        self.done = True

    def failed(self, why):
        self.failure = why

    def test_addHelper(self):
        self.ctx.addHelper(self.hc)

    def test_removeHelper(self):
        # Remove an unstarted task
        self.ctx.addHelper(self.hc)
        self.ctx.removeHelper('test')

        # Remove a started task
        self.ctx.addHelper(self.hc)
        self.ctx.start()
        self.ctx.removeHelper('test')

    def _cbDaemonError(self, result):
        self.ctx.stop()
        self.assertNotEqual(result, self.ctx)

    def _ebDaemonError(self, failure):
        failure.trap(FakeException)

    def test_daemonContextErrorHandling(self):
        self.ctx.addHelper(self.hc)
        # Force a run error
        self.hc.helper.exception = True

        d = self.ctx.start()
        d.addCallback(self._cbDaemonError)
        d.addErrback(self._ebDaemonError)

        # Add a timeout
        timeout = reactor.callLater(5, self.failed, "timeout")

        # Wait for the work method to be called, or for a timeout to occur
        while (not self.hc.helper.done or self.failure):
            reactor.iterate(0.1)

        timeout.cancel()

        if (self.failure):
            self.fail(self.failure)

        return d

    def test_start(self):
        self.ctx.addHelper(self.hc)
        d = self.ctx.start()
        d.addCallback(self._cbDaemonResult)

        # Add a timeout
        timeout = reactor.callLater(5, self.failed, "timeout")

        # Wait for the work method to be called, or for a timeout to occur
        while (not self.hc.helper.done or self.failure):
            reactor.iterate(0.1)

        timeout.cancel()

        # Kill the task
        self.ctx.removeHelper('test')
        self.ctx.stop()

        if (self.failure):
            self.fail(self.failure)

        if (self.hc.helper.failure):
            self.fail(self.hc.helper.failure)

        return d

    def _cbDaemonResult(self, result):
        self.assertEquals(result, self.ctx)

    def test_stop(self):
        self.ctx.addHelper(self.hc)
        d = self.ctx.start()

        d.addCallback(self._cbDaemonResult)

        self.ctx.stop()

        return d
