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
        self.helperClass = None
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
                    self.helperClass = obj
                    break

        if (self.helperClass == None):
            raise SplatPluginError, "Helper module %s not found" % module

        # Get the list of required attributes

        self.searchAttr = self.helperClass.attributes()
        # If None, request all user attributes (LDAP_ALL_USER_ATTRIBUTES)
        if (self.searchAttr == None):
            self.searchAttr = ('*', )

        # Always retrieve the modifyTimestamp operational attribute, too.
        self.searchAttr = self.searchAttr + ('modifyTimestamp',)

        self.defaultContext = self.helperClass.parseOptions(helperOptions)

    def addGroup(self, groupFilter, helperOptions = None):
        """
        Add a new group filter.
        @param groupFilter: Instance of ldaputils.client.GroupFilter
        @param helperOptions; Group-specific helper options. Optional.
        """
        if (helperOptions):
            self.groupsCtx[groupFilter] = self.helperClass.parseOptions(helperOptions)
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

        # Save the start time, used to determine the last successful run
        startTime = int(time.time())

        # TODO LDAP scope support
        entries = ldapConnection.search(self.searchBase, ldap.SCOPE_SUBTREE, self.searchFilter, self.searchAttr)

        # Instantiate a plugin instance
        plugin = self.helperClass()

        # Iterate over the results
        for entry in entries:
            context = None
            entryModified = False
            groupModified = False
            # Find the group helper instance, if any
            for group in self.groups:
                if (group.isMember(ldapConnection, entry.dn)):
                    context = self.groupsCtx[group]
                    
                    # Get the modifyTimestamp of this group. If the group has 
                    # been modified, this entry might have just been added to 
                    # the group, in which case we want to treat the entry as 
                    # modified.
                    groupEntry = ldapConnection.search(group.baseDN, group.scope, group.filter, ('modifyTimestamp',))[0]
                    if (groupEntry.attributes.has_key('modifyTimestamp')):
                        groupModTime = groupEntry.getModTime()
                        if groupModTime != None and groupModTime >= self._lastRun:
                            groupModified = True
                    # If no timestamp, assume the group has been modified.
                    else:
                        groupModified = True
                    
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
                entryModTime = entry.getModTime()
                # Go on to next entry if the modifyTimetamp is malformed
                if entryModTime == None:
                    continue

                if (entryModTime >= self._lastRun):
                    entryModified = True

            # If there is no modifyTimestamp, just say entry has been modified
            else:
                entryModified = True

            try:
                plugin.work(context, entry, entryModified or groupModified)
            except splat.SplatError, e:
                failure = True
                logger.error("Helper invocation for '%s' failed with error: %s" % (self.name, e))

        # Let the plugin clean itself up
        try:
            plugin.finish()
        except splat.SplatError, e:
            failure = True
            logger.error("Helper finish invocation for '%s' failed with error: %s" % (self.name, e))

        # If the entire run was successful, update the last-run timestamp.
        #
        # We use the start time, rather than the current time, as modifications
        # may occur between when the run starts, and when the run finishes.
        if (not failure):
            self._lastRun = startTime

class Helper(object):
    """
    Abstract class for Splat helper plugins
    """
    @classmethod
    def attributes(self):
        """
        Return required LDAP attributes. Return None to have
        all available attributes returned.
        """
        raise NotImplementedError, \
                "This method is not implemented in this abstract class"
    
    @classmethod
    def _parseBooleanOption(self, option):
        """
        Case insensitively convert a string option 'true' or 'false' to 
        the appropriate boolean, and throw an exception if the option 
        isn't either of those strings.
        """
        if option.lower() == 'true':
            return True
        elif option.lower() == 'false':
            return False
        else:
            raise SplatPluginError, "Invalid value for option %s specified; must be set to true or false." % option

    @classmethod
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

    def finish(self):
        """
        Called after all data has been passed to the work() method.
        Override this to implement any necessary post-processing; eg,
        flushing modifications to disk, etc.
        """
        pass
