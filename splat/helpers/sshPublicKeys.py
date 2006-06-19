# sshPublicKeys.py vi:ts=4:sw=4:expandtab:
#
# LDAP SSH Public Key Helper.
# Authors:
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

import sys, os, logging

import splat
from splat import plugin

logger = logging.getLogger(splat.LOG_NAME)

# Sub-process result codes
SSH_ERR_NONE = 0
SSH_ERR_MISC = 1
SSH_ERR_PRIVSEP = 2
SSH_ERR_MKDIR = 3
SSH_ERR_WRITE = 4

class WriterContext(object):
    """ Option Context """
    def __init__(self):
        self.minuid = None
        self.mingid = None
        self.home = None
        self.splitHome = None
        self.command = None

class Writer(plugin.Helper):
    # Required Attributes
    attributes = ('sshPublicKey', 'homeDirectory', 'gidNumber', 'uidNumber')

    def parseOptions(self, options):
        context = WriterContext()

        for key in options.keys():
            if (key == 'home'):
                context.home = os.path.abspath(options[key])
                splitHome = context.home.split('/')
                if (splitHome[0] != ''):
                    raise plugin.SplatPluginError, "Relative paths for the home option are not permitted"
                context.splitHome = splitHome
                continue
            if (key == 'minuid'):
                context.minuid = int(options[key])
                continue
            if (key == 'mingid'):
                context.mingid = int(options[key])
                continue
            if (key == 'command'):
                context.command = options[key]
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key

        return context

    def work(self, context, ldapEntry):
        attributes = ldapEntry.attributes

        # Test for required attributes
        if (not attributes.has_key('sshPublicKey') or not attributes.has_key('homeDirectory')):
            return
        if (not attributes.has_key('uidNumber') or not attributes.has_key('gidNumber')):
            return

        home = attributes.get("homeDirectory")[0]
        uid = int(attributes.get("uidNumber")[0])
        gid = int(attributes.get("gidNumber")[0])
        keys = attributes.get("sshPublicKey")

        # Validate the home directory
        if (context.home != None):
            givenPath = os.path.abspath(home).split('/')
            if (len(givenPath) < len(context.splitHome)):
                raise plugin.SplatPluginError, "LDAP Server returned home directory (%s) located outside of %s for entry '%s'" % (home, context.home, ldapEntry.dn)

            for i in range(0, len(context.splitHome)):
                if (context.splitHome[i] != givenPath[i]):
                    raise plugin.SplatPluginError, "LDAP Server returned home directory (%s) located outside of %s for entry '%s'" % (home, context.home, ldapEntry.dn)

        # Validate the UID
        if (context.minuid != None):
            if (context.minuid > uid):
                raise plugin.SplatPluginError, "LDAP Server returned uid %d less than specified minimum uid of %d for entry '%s'" % (uid, context.minuid, ldapEntry.dn)
        # Validate the GID
        if (context.mingid != None):
            if (context.mingid > gid):
                raise plugin.SplatPluginError, "LDAP Server returned gid %d less than specified minimum gid of %d for entry '%s'" % (gid, context.mingid, ldapEntry.dn)


        tmpfilename = "%s/.ssh/authorized_keys.tmp" % home
        filename = "%s/.ssh/authorized_keys" % home
        logger.info("Writing key to %s" % filename)

        # Make sure the home directory exists
        if (not os.path.isdir(home)):
            try:
                os.makedirs(home)
                os.chown(home, uid, gid)
            except OSError, e:
                raise plugin.SplatPluginError, "Failed to create home directory, %s" % e

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
                os._exit(SSH_ERR_PRIVSEP)

            # Adopt a strict umask
            os.umask(077)

            try:
                # Make sure the directory exists
                dir = os.path.split(tmpfilename)[0]
                if not os.path.exists(dir): os.makedirs(dir)
            except OSError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(SSH_ERR_MKDIR)

            try:
                f = open(tmpfilename, "w+")
                for key in keys:
                    if (context.command == None):
                        contents = "%s\n" % key
                    else:
                        contents = "command=\"%s\" %s\n" % (context.command, key)

                    f.write(contents)
                f.close()
            except IOError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(SSH_ERR_WRITE)

            # Move key to ~/authorized_keys
            try:
                os.rename(tmpfilename, filename)
            except OSError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(SSH_ERR_WRITE)

            os._exit(SSH_ERR_NONE)
        else:
            while (1):
                try:
                    result = os.waitpid(pid, 0)
                except OSError, e:
                    import errno
                    if (e.errno == errno.EINTR):
                        continue
                    raise
                break

            status = os.WEXITSTATUS(result[1])

        # Handle the error conditions
        if (status == SSH_ERR_NONE):
            outf.close()
            inf.close()
            return
        else:
            errstr = inf.readline()
            outf.close()
            inf.close()

        if (status == SSH_ERR_PRIVSEP):
            raise plugin.SplatPluginError, "Failed to drop privileges, %s" % errstr

        if (status == SSH_ERR_MKDIR):
            raise plugin.SplatPluginError, "Failed to create SSH directory '%s', %s" % errstr

        if (status == SSH_ERR_WRITE):
            raise plugin.SplatPluginError, "Failed to write SSH key, %s" % errstr
