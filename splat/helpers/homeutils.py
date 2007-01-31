# homeutils.py vi:ts=4:sw=4:expandtab:
#
# Support functions for plugins that deal with user home directories.
# Authors:
#       Nick Barkas <snb@threerings.net>
#
# Copyright (c) 2007 Three Rings Design, Inc.
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
import shutil
import errno
import re
import splat
from splat import plugin
    
def requiredAttributes():
    """
    LDAP attributes needed by any home directory related helper. 
    
    @returns tuple of required attributes.
    """
    return ('homeDirectory', 'gidNumber', 'uidNumber')

def getLDAPAttributes(ldapEntry, homePath=None, minuid=None, mingid=None):
    """
    Extract home directory, numberic uid, and numeric gid 
    attributes from an LDAP record. Also validates these attributes
    against minuid, mingid, and home, if they are defined.
    
    @param ldapEntry: ldaputils.client.Entry object representing 
        an LDAP record for a user.
    @param homePath: LDAP record's homeDirectory must be located within 
        path given by this string.
    @param minuid: LDAP record's minimum acceptable uidNumber.
    @param mingid: LDAP record's minimum acceptable gidNumber.
    @returns tuple containing the first homeDirectory, uidNumber, 
        and gidNumber attributes in ldapEntry.
    """
    attributes = ldapEntry.attributes

    # Test for required attributes
    if (not (attributes.has_key('homeDirectory') and attributes.has_key('uidNumber') and attributes.has_key('gidNumber'))):
        raise plugin.SplatPluginError, "Required attributes homeDirectory, uidNumber, and gidNumber not all specified for dn %s." % ldapEntry.dn

    home = attributes.get("homeDirectory")[0]
    uid = int(attributes.get("uidNumber")[0])
    gid = int(attributes.get("gidNumber")[0])

    # Validate the home directory
    if (homePath != None):
        # Path the user's home directory must be within.
        splitHomePath = homePath.split('/')
        # User's actual home directory.
        splitHome = home.split('/')
        for i in range(0, len(splitHomePath)):
            if (splitHomePath[i] != splitHome[i]):
                raise plugin.SplatPluginError, "LDAP Server returned home directory %s located outside of %s for dn %s" % (home, homePath, ldapEntry.dn)

    # Validate the UID
    if (minuid != None):
        if (minuid > uid):
            raise plugin.SplatPluginError, "LDAP Server returned uid %d less than specified minimum uid of %d for dn %s" % (uid, minuid, ldapEntry.dn)

    # Validate the GID
    if (mingid != None):
        if (mingid > gid):
            raise plugin.SplatPluginError, "LDAP Server returned gid %d less than specified minimum gid of %d for entry '%s'" % (gid, mingid, ldapEntry.dn)

    return (home, uid, gid)

def makeHomeDir(home, uid, gid, skeldir=None, postcreate=None):
    """
    Create a home directory.
    
    @param home: Path of home directory to create.
    @param uid: Numeric user ID of home directory owner.
    @param gid: Numerid group ID of home directory owner.
    @param skeldir: Optional skeletal home directory to copy files 
        from. Files with names such as dot.foo will be copied to 
        the user's home directory as .foo.
    @param postcreate: Optional script to run after a home directory
        has been created. The script will be given the user's uid, 
        gid, and home directory as arguments.
    """
    # Create the home directory, unless it already exists
    if (not os.path.isdir(home)):
        try:
            os.makedirs(home)
            os.chown(home, uid, gid)
        except OSError, e:
            raise plugin.SplatPluginError, "Failed to create home directory, %s" % e
    # If it does already exist, do nothing at all and we are done
    else:
        return

    # Copy files from skeletal directories to user's home directory if we
    # are using a skeldir          
    if (skeldir != None):
        _copySkelDir(skeldir, home, uid, gid)

    # Fork and run post create script if it was defined
    if (postcreate != None):
        pipe = os.pipe()
        inf = os.fdopen(pipe[0], 'r')

        pid = os.fork()
        if (pid == 0):
            try:
                os.execl(postcreate, postcreate, str(uid), str(gid), home)
            except OSError, e:
                raise plugin.SplatPluginError, "Failed to execute post-creation script %s [Errno %d] %s." % (postcreate, e.errno, e.strerror)

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

        # Check if child process exited happily.
        if (status == 0):
            inf.close()
            return
        else:
            errstr = inf.readline()
            inf.close()
            raise plugin.SplatPluginError, "Post creation script %s %d %d %s exited abnormally: %s" % (postcreate, uid, gid, home, errstr)


def _copySkelDir(srcDir, destDir, uid, gid):
    """
    Recursively copy a directory tree, preserving permission modes and 
    access times, but changing ownership of files to uid:gid. Also, 
    renames files/directories named dot.foo to .foo.

    @param srcDir: Skeletel dir to copy from. E.g. '/usr/share/skel'
    @param destDir: Destionation home directory.
    @param uid: Numeric UID of user whose home directory is destDir.
    @param gid: Numeric GID of user whose home directory is destDir.
    """
    # Regular expression matching files named dot.foo
    pattern = re.compile('^dot\.')
    for srcFile in os.listdir(srcDir):
        destFile = pattern.sub('.', srcFile)
        # Not portable: hardcoded / as path delimeter
        srcPath = srcDir + '/' + srcFile
        destPath = destDir + '/' + destFile

        # Go deeper if we are copying a sub directory
        if (os.path.isdir(srcPath)):
            try:
                os.makedirs(destPath)
                shutil.copystat(srcPath, destPath)
            except OSError, e:
                raise plugin.SplatPluginError, "Failed to create destination directory: %s" % destPath
                continue

            _copySkelDir(srcPath, destPath, uid, gid)

        # Copy regular files
        else:
            try:
                shutil.copy2(srcPath, destPath)
            except IOError, e: 
                raise plugin.SplatPluginError, "Failed to copy %s to %s: %s" % (srcPath, destPath, e)
                continue

        # Change ownership of files/directories after copied
        try:
            os.chown(destPath, uid, gid)
        except OSError, e:
            raise plugin.SplatPluginError, "Failed to change ownership of %s to %d:%d" % (destPath, uid, gid)
            continue
