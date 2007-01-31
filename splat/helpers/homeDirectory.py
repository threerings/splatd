# homeDirectory.py vi:ts=4:sw=4:expandtab:
#
# LDAP Home Directory Creating Helper.
# Authors:
#       Nick Barkas <snb@threerings.net>
# Based on ssh key helper by:
#       Will Barton <wbb4@opendarwin.org>
#       Landon Fuller <landonf@threerings.net>
#
# Copyright (c) 2006 Three Rings Design, Inc.
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

import os
import splat
from splat import plugin
import homeutils

class WriterContext(object):
    def __init__(self):
        self.home = None
        self.minuid = None
        self.mingid = None
        self.splitHome = None
        self.skeldir = None
        self.postcreate = None

class Writer(plugin.Helper):
    def attributes(self):
        return homeutils.requiredAttributes()
    
    def parseOptions(self, options):
        context = WriterContext()
        
        for key in options.iterkeys():
            if (key == 'home'):
                context.home = str(options[key])
                if (context.home[0] != '/'):
                    raise plugin.SplatPluginError, "Relative paths for the home option are not permitted"
                splitHome = context.home.split('/')
                context.splitHome = splitHome
                continue
            if (key == 'minuid'):
                context.minuid = int(options[key])
                continue
            if (key == 'mingid'):
                context.mingid = int(options[key])
                continue
            if (key == 'skeldir'):
                context.skeldir = os.path.abspath(options[key])
                # Validate skel directory
                if (not os.path.isdir(context.skeldir)):
                    raise plugin.SplatPluginError, "Skeletal home directory %s does not exist or is not a directory" % context.skeldir
                continue
            if (key == 'postcreate'):
                context.postcreate = os.path.abspath(options[key])
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key
            
        return context

    def work(self, context, ldapEntry, modified):
        # Skip unmodified entries
        if (not modified):
            return
        
        # Otherwise create the home directory
        homeutils.makeHomeDir(ldapEntry, context.skeldir, context.postcreate)
