# mailForwardingAddress.py vi:ts=4:sw=4:expandtab:
#
# LDAP mailForwardingAddress Helper.
# Authors:
#       Will Barton <wbb4@opendarwin.org>
#       Landon Fuller <landonf@threerings.net>
#       Kevin Van Vechten <kevin@opendarwin.org>
#
# Copyright (c) 2005, 2006 Three Rings Design, Inc.
# Portions copyright (c) 2005 Apple Computer, Inc.
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

import sys, logging, errno, string
import os, stat, time

import splat
from splat import plugin
import homeutils

logger = logging.getLogger(splat.LOG_NAME)

# Sub-process result codes
HELPER_ERR_NONE = 0
HELPER_ERR_MISC = 1
HELPER_ERR_PRIVSEP = 2
HELPER_ERR_WRITE = 3

class WriterContext(object):
    def __init__(self):
        self.home = None
        self.minuid = None
        self.mingid = None
        self.skeldir = None
        self.postcreate = None
        self.makehome = False

class Writer(plugin.Helper):
    # Required Attributes
    @classmethod
    def attributes(self): 
        return ('mailForwardingAddress',) + homeutils.requiredAttributes()

    @classmethod
    def parseOptions(self, options):
        context = WriterContext()

        for key in options.iterkeys():
            if (key == 'home'):
                context.home = str(options[key])
                if (context.home[0] != '/'):
                    raise plugin.SplatPluginError, "Relative paths for the home option are not permitted"
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
            if (key == 'makehome'):
                context.makehome = self._parseBooleanOption(str(options[key]))
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key

        return context
    
    def work(self, context, ldapEntry, modified):
        # Skip unmodified entries
        if (not modified):
            return

        # Get LDAP attributes, and make sure we have all the ones we need
        attributes = ldapEntry.attributes
        if (not attributes.has_key('mailForwardingAddress')):
            raise plugin.SplatPluginError, "Required attribute mailForwardingAddress not found for dn %s." % ldapEntry.dn
        addresses = attributes.get("mailForwardingAddress")
        (home, uid, gid) = homeutils.getLDAPAttributes(ldapEntry, context.home, context.minuid, context.mingid)

        # If config says to create the home directory and it doesn't exist, do so.
        if (not os.path.isdir(home)):
            if (context.makehome == True):
                homeutils.makeHomeDirectory(home, uid, gid, context.skeldir, context.postcreate)
            else:
                # If we weren't told to make homedir, log a warning and quit
                logger.warning(".forward file not being written because home directory %s does not exist. To have this home directory created automatically by this plugin, set the makehome option to true in your splat configuration file, or use the homeDirectory plugin." % home)
                return

        tmpfilename = "%s/.forward.tmp" % home
        filename = "%s/.forward" % home

        # Make sure the modifyTimestamp entry exists before looking at it
        if (ldapEntry.attributes.has_key('modifyTimestamp')):

            # stat() the file, check if it is outdated
            try:
                fileTime = os.stat(filename)[stat.ST_MTIME]
    
                # If the entry is older than the file, skip it
                # This will occur when someone has been added to a group that 
                # we filter on, but this entry hasn't been changed since the 
                # key was written. Also will happen on first iteration by 
                # daemon, because modifed will always be true then.
                if (ldapEntry.getModTime() < fileTime):
                    logger.debug("Skipping %s, up-to-date" % filename)
                    return
    
            except OSError:
                # File doesn't exist, or some other error.
                # Ignore the exception, it'll be caught again
                # and reported below.
                pass
    
        logger.info("Writing mail address to %s" % filename)

        # Fork and setuid to write the files
        pipe = os.pipe()
        outf = os.fdopen(pipe[1], 'w')
        inf = os.fdopen(pipe[0], 'r')

        pid = os.fork()
        if (pid == 0):
            # Drop privs
            try:
                os.setgid(gid)
                os.setuid(uid)
            except OSError, e:
                print str(e)
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(HELPER_ERR_PRIVSEP)

            # Adopt a strict umask
            os.umask(077)

            try:
                f = open(tmpfilename, "w+")
                for address in addresses:
                    contents = "%s\n" % address
                    f.write(contents)
                f.close()
            except IOError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(HELPER_ERR_WRITE)

            # Move forward to ~/
            try:
                os.rename(tmpfilename, filename)
            except OSError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(HELPER_ERR_WRITE)

            os._exit(HELPER_ERR_NONE)
        else:
            while (1):
                try:
                    result = os.waitpid(pid, 0)
                except OSError, e:
                    if (e.errno == errno.EINTR):
                        continue
                    raise
                break

            status = os.WEXITSTATUS(result[1])

        # Handle the error conditions
        if (status == HELPER_ERR_NONE):
            outf.close()
            inf.close()
            return
        else:
            errstr = inf.readline()
            outf.close()
            inf.close()

        if (status == HELPER_ERR_PRIVSEP):
            raise plugin.SplatPluginError, "Failed to drop privileges, %s" % errstr

        if (status == HELPER_ERR_WRITE):
            raise plugin.SplatPluginError, "Failed to write .forward, %s" % errstr
