## Introduction ##
Splat is a daemon designed to help keep information in an LDAP directory in sync with information outside of an LDAP directory. This information can be any set of attributes on any object in the LDAP directory.

Splat currently supports the following:

  * Writing SSH public keys
  * Writing .forward files
  * Creating user home directories
  * Archiving and deleting home directories of deleted users
  * OpenNMS user synchronization

## Requirements ##
  * [Python](http://www.python.org) 2.4+
  * [Twisted Networking Framework](http://twistedmatrix.com)
  * [Python LDAP](http://python-ldap.sourceforge.net/)
  * [ZConfig](http://www.zope.org/Members/fdrake/zconfig/)

Additionally, for the OpenNMS plugin you will need
  * [pysqlite2](http://pysqlite.org/)
  * [cElementTree](http://effbot.org/zone/celementtree.htm) (or Python 2.5+, which includes this module)

## Installation ##
Splat uses the standard Python distutils. To install, run setup.py:

```
./setup.py install
```
The splat framework will be installed in the Python site-packages directory. The splatd daemon will be installed in the Python-specified bin directory. An example configuration file, splat.conf, is supplied with the source distribution.

There are also splat packages available for several operating systems. Splat is in the FreeBSD ports collection as net/splatd, in MacPorts as splat, and in Ubuntu as splatd.

## Caveats ##
  * Splat current stores the full search result in memory. This may cause excessive memory consumption with extremely large result sets.
  * Blocking LDAP calls are used. A complex query or overloaded/unreachable LDAP server may cause Splat to block for significant periods of time.
  * TLS/SSL is supported, but StartTLS is not.