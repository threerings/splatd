# daemon.py vi:ts=4:sw=4:expandtab:
#
# LIDS Daemon Support.
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

import lids
from lids import plugin

from twisted.internet import reactor, task

import ldap, logging

class Context(object):
    # LIDS Daemon Context
    def __init__(self, ldapConnection):
        """
        Initialize a LIDS Daemon context
        @param ldapConnection: A connected instance of ldaputils.Connection
        """
        self.svc = {}
        self.tasks = {}
        self.l = ldapConnection

    def addHelper(self, name, controller):
        """
        Add a helper controller to the daemon context
        @param name: Unique caller-assigned name. Helpers with non-unique names will overwrite previous additions.
        @param controller: HelperController
        """
        self.svc[name] = controller

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

        ctrl = self.svc[name]
        logger = logging.getLogger(lids.LOG_NAME)

        # XXX TODO LDAP scope && group filter support
        try:
            entries = self.l.search(ctrl.searchBase, ldap.SCOPE_SUBTREE, ctrl.searchFilter, ctrl.searchAttr)
        except ldap.LDAPError, e:
            logger.error("LDAP Search error for helper %s: %s" % (name, e))
            return

        for entry in entries:
            try:
                ctrl.work(entry)
            except lids.LIDSError, e:
                logger.error("Helper invocation for '%s' failed with error: %s" % (name, e))
                continue

    def start(self, once = False):
        """
        Add the daemon context to the twisted runloop
        """
        for name, ctrl in self.svc.items():
            t = task.LoopingCall(self._invokeHelper, name)
            t.start(ctrl.interval)
            self.tasks[name] = t

    def run(self):
        """
        Run the associated helper tasks once
        """
        for name, ctrl in self.svc.items():
                self._invokeHelper(name)
