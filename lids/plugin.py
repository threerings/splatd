# plugin.py vi:ts=4:sw=4:expandtab:
#
# LIDS plugins
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

import lids
from lids import LIDSError

import types

# Exceptions
class LIDSPluginError(LIDSError):
    pass

class HelperController(object):
    def __init__(self, module, interval, searchBase, searchFilter, groupBase, groupFilter, options):
        """
        Initialize LIDS Helper from module 
        @param module: Module containing a single Helper subclass. Any other subclasses of Helper will be ignored.
        @param interval: Run interval in seconds. An interval of '0' will cause the helper to be run only once.
        @param searchBase: LDAP Search base
        @param searchFilter: LDAP Search filter
        @param groupBase: LDAP Group Search filter (may be None)
        @param groupFilter: LDAP Group Search base (may be None)
        @param options: Dictionary of helper-specific options
        """
        self.helper = None
        self.interval = interval
        self.searchFilter = searchFilter
        self.searchBase = searchBase
        self.groupFilter = groupFilter
        self.groupBase = groupBase

        p = __import__(module, globals(), locals(), ['__file__'])
        for attr in dir(p):
            obj = getattr(p, attr)
            if (isinstance(obj, (type, types.ClassType)) and issubclass(obj, Helper)):
                # Skip abstract class
                if (not obj == Helper):
                    self.helper = obj()
                    break

        if (self.helper == None):
            raise LIDSPluginError, "Helper module %s not found" % module

        if (not hasattr(self.helper, "attributes")):
            raise LIDSPluginError, "Helper missing required 'attributes' attribute."

        self.searchAttr = self.helper.attributes

        self.helper.setOptions(options)

    def work(self, ldapEntry):
        """
        Pass LDAP Entry to the controlled worker
        """
        return self.helper.work(ldapEntry)

class Helper(object):
    """
    Abstract class for LIDS helper plugins
    """
    def setOption(self, option, value):
        raise NotImplementedError, \
                "This method is not implemented in this abstract class"

    def work(self, ldapEntry):
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
