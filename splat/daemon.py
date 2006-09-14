# daemon.py vi:ts=4:sw=4:expandtab:
#
# Splat Daemon Support.
# Author:
#       Will Barton <wbb4@opendarwin.org>
#       Landon Fuller <landonf@threerings.net>
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

# This file contains everything necessary to run a Daemon that
# distributes information from LDAP using helper classes based on the
# frequency specification of sections in a lid.conf file.

import splat
from splat import plugin

from twisted.internet import reactor, task, defer

import ldap, logging

class Context(object):
    # Splat Daemon Context
    def __init__(self, ldapConnection):
        """
        Initialize a Splat Daemon context
        @param ldapConnection: A connected instance of ldaputils.client.Connection
        """
        self.svc = {}
        self.tasks = {}
        self.stopping = False
        self.failure = None
        self.ldapConnection = ldapConnection

    def addHelper(self, controller):
        """
        Add a helper controller to the daemon context
        @param controller: HelperController
        """
        self.svc[controller.name] = controller

    def removeHelper(self, name):
        """
        From a helper controller from the daemon context
        @param name: Unique caller-assigned name.
        """
        # Stop the task, if started, and delete the associated entry
        if (self.tasks.has_key(name)):
            self.tasks[name].stop()
            self.tasks.pop(name)

        # Delete the controller entry
        self.svc.pop(name)

    def _invokeHelper(self, name):
        # Has helper been removed?
        if (not self.svc.has_key(name)):
            return

        # Are we shutting down?
        if (self.stopping):
            return

        ctrl = self.svc[name]
        try:
            ctrl.work(self.ldapConnection)
        except Exception, e:
            # Stop the presses
            self._stopAllTasks()
            # Propigate helper errors
            self.failure = e
            self._checkStop()
            return

    def start(self):
        """
        Add the daemon context to the twisted runloop
        @return A deferred whose callback will be invoked with C{self}
        when stop() is called, or whose errback will be invoked if the
        daemon context raises an exception.
        """
        self.deferResult = defer.Deferred()
        self.stopping = False

        for name, ctrl in self.svc.items():
            t = task.LoopingCall(self._invokeHelper, name)
            t.start(ctrl.interval, False)
            self.tasks[name] = t

        # Provide the caller our deferred result
        return self.deferResult

    def _stopAllTasks(self):
        """
        Request that all running tasks stop
        """
        # Loop through all running tasks
        for key in self.tasks.keys():
            task = self.tasks.pop(key)
            task.stop()

    def _checkStop(self):
        # Check if all tasks have completed
        for name,task in self.tasks:
            if (task.running):
                # Task is still running ...
                reactor.callLater(0, self._checkStop)
                return

        # All tasks have been stopped
        if (self.failure):
            self.deferResult.errback(self.failure)
        else:
            self.deferResult.callback(self)

    def stop(self):
        """
        Stop all running tasks.
        """
        # Stop requested. If any tasks are pending,
        # inform them that we're closing up shop.
        if (len(self.tasks) > 0):
            self._stopAllTasks()
            self.stopping = True
            reactor.callLater(0, self._checkStop)
        else:
            # All tasks stopped.
            # report success.
            self.deferResult.callback(self)
