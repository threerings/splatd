# plugin.py vi:ts=4:sw=4:expandtab:
#
# Splat plugins
# Authors:
#       Landon Fuller <landonf@opendarwin.org>
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

import splat
from splat import SplatError

import types
import logging
import ldap
import time

# Exceptions
class SplatPluginError(SplatError):
    pass

class HelperController(object):
    def __init__(self, name, module, interval, searchBase, searchFilter, requireGroup, helperOptions):
        """
        Initialize Splat Helper from module 
        @param name: Unique caller-assigned name. Helpers with non-unique names will overwrite previous additions when added to a daemon context.
        @param module: Module containing a single Helper subclass. Any other subclasses of Helper will be ignored.
        @param interval: Run interval in seconds. An interval of '0' will cause the helper to be run only once.
        @param searchBase: LDAP Search base
        @param searchFilter: LDAP Search filter
        @param requireGroup: Require any returned entries to be a member of a group supplied by addGroup().
        @param helperOptions: Dictionary of helper-specific options
        """
        self.helper = None
        self.name = name
        self.interval = interval
        self.searchFilter = searchFilter
        self.searchBase = searchBase
        self.requireGroup = requireGroup
        # Time of last successful run
        self._lastRun = 0

        self.groupsCtx = {}
        self.groups = []

        p = __import__(module, globals(), locals(), ['__file__'])
        for attr in dir(p):
            obj = getattr(p, attr)
            if (isinstance(obj, (type, types.ClassType)) and issubclass(obj, Helper)):
                # Skip abstract class
                if (not obj == Helper):
                    self.helper = obj()
                    self._helperClass = obj
                    break

        if (self.helper == None):
            raise SplatPluginError, "Helper module %s not found" % module

        self.searchAttr = self.helper.attributes() + ('modifyTimestamp',)

        self.defaultContext = self.helper.parseOptions(helperOptions)

    def addGroup(self, groupFilter, helperOptions = None):
        """
        Add a new group filter.
        @param groupFilter: Instance of ldaputils.GroupFilter
        @param helperOptions; Group-specific helper options. Optional.
        """
        if (helperOptions):
            self.groupsCtx[groupFilter] = self.helper.parseOptions(helperOptions)
        else:
            self.groupsCtx[groupFilter] = self.defaultContext 

        # Groups must be tested in the order they are added
        self.groups.append(groupFilter)

    def work(self, ldapConnection):
        """
        Find matching LDAP entries and fire off the helper
        """
        logger = logging.getLogger(splat.LOG_NAME)
        failure = False

        # TODO LDAP scope support
        entries = ldapConnection.search(self.searchBase, ldap.SCOPE_SUBTREE, self.searchFilter, self.searchAttr)

        # Iterate over the results
        for entry in entries:
            context = None
            modified = True
            # Find the group helper instance, if any
            for group in self.groups:
                if (group.isMember(ldapConnection, entry.dn)):
                    context = self.groupsCtx[group]
                    # Break to outer loop
                    break

            if (context == None and self.requireGroup == False):
                context = self.defaultContext
            elif (context == None and self.requireGroup == True):
                # Move on, empty handed
                logger.debug("DN %s matched zero groups and requireGroup is enabled for helper %s" % (entry.dn, self.name))
                continue

            # Check if our entry has been modified
            if (entry.attributes.has_key('modifyTimestamp')):
                # Convert LDAP UTC time to seconds since epoch
                try:
                    entryMod = time.mktime(time.strptime(entry.attributes['modifyTimestamp'][0] + 'UTC', "%Y%m%d%H%M%SZ%Z")) - time.timezone
                except ValueError:
                    logger.error("Entry %s contains invalid modifyTimestamp attribute value '%s'" % (entry.dn, entry.attributes['modifyTimestamp'][0], self.name))
                    continue

                if (entryMod >= self._lastRun):
                    modified = True
                else:
                    modified = False

            try:
                self.helper.work(context, entry, modified)
            except splat.SplatError, e:
                failure = True
                logger.error("Helper invocation for '%s' failed with error: %s" % (self.name, e))

        # If the entire run was successful, update the timestamp
        if (not failure):
            self._lastRun = int(time.time())

class Helper(object):
    """
    Abstract class for Splat helper plugins
    """
    def attributes(self):
        """
        Return required LDAP attributes.
        """
        raise NotImplementedError, \
                "This method is not implemented in this abstract class"
        
    def parseOptions(self, options):
        """
        Parse the supplied options dict and return
        an opaque configuration context.
        """
        raise NotImplementedError, \
                "This method is not implemented in this abstract class"

    def work(self, context, ldapEntry, modified):
        """
        Do something useful with the supplied ldapEntry
        """
        raise NotImplementedError, \
                "This method is not implemented in this abstract class"

    def modify(self, ldapEntry, modifyDict):
        raise NotImplementedError, \
                "This method is not implemented in this abstract class"

    def convert(self):
        pass
