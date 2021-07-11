#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Dirty wrapper around rdiff-backup.

rdiff-backup-wrapper simplifies the automated use of rdiff-wrapper:
* store configuration for multiple runs
* purge old backups
* logging / plays nice with cron

Example config file:

[common]
sets = localbackup
logfile = local_path, optional
logcount = int, optional
# synclogs means that all logfiles created will be rsynced to the specified
# path at the end of the run
synclogs = rsync_path, optional

[set_localbackup]
name = , required
source = , required
destination = , required
pingcheck = hostname_or_ip, optional
dircheck = local_path, optional

"""

import os
import sys
from ConfigParser import SafeConfigParser
from optparse import OptionParser
import logging


author = """Paul Kremer, 2007"""
license = 'MIT'
__configObject = None  # holder for a Config object


def get_config(configfile=None):
    """Return an instance of ConfigParser."""
    global __configObject
    from os import path
    if __configObject is None:
        if configfile is not None:
            cfgfile = configfile
        else:
            cfgfile = path.join(get_app_home_path(), 'config.ini')
        __configObject = SafeConfigParser()
        __configObject.read(cfgfile)
    return __configObject


def is_mac_osx():
    """Determine if we're running on macOS."""
    import re
    import platform
    darwin = re.compile('Darwin')
    if darwin.match(platform.system()):
        return True
    else:
        return False


def get_app_home_path():
    """Return the application's config directory."""
    from os import environ, path, mkdir
    home = environ['HOME']
    if is_mac_osx():
        homepath = path.join(home, 'Library', 'Application Support', 'rdiff-backup-wrapper')
    else:
        homepath = path.join(home, '.rdiff-backup-wrapper')
    if not path.exists(homepath):
        mkdir(homepath)
    return homepath


def get_app_log_path():
    """Return the application log directory."""
    from os import environ, path, mkdir
    if is_mac_osx():
        home = environ['HOME']
        logpath = path.join(home, 'Library', 'Logs', 'rdiff-backup-wrapper')
    else:
        logpath = path.join(get_app_home_path(), 'log')
    if not path.exists(logpath):
        mkdir(logpath)
    return logpath


def run_proc(args=None, quiet=False):
    """Run specified external command."""
    import subprocess  # noqa: S404
    if args is None:
        raise NameError('args must be set to run a program!')
    logging.debug('executing %s', ' '.join(args))
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    res = proc.wait()
    if not res == 0 and quiet is False:
        logging.error('error while executing %s', ' '.join(args))
        logging.error('Non-zero exit code: %s', res)
        logging.error('STDOUT is:')
        for line in proc.stdout.readlines():
            logging.error(line.rstrip('\n'))
        logging.error('STDERR is:')
        for line in proc.stderr.readlines():
            logging.error(line.rstrip('\n'))
    else:
        if not quiet:
            for line in proc.stdout.readlines():
                logging.info(line.rstrip('\n'))
    if res == 0:
        return True
    else:
        return False


def get_common_config_values(cfg):
    """Return config values from the common section."""
    from string import strip

    common_options = {'sets': None}
    required_common_options = {'sets': None}
    # make sure required options are set by simply trying to get() them:
    for c in required_common_options:
        cfg.get('common', c)

    sets_str = cfg.get('common', 'sets')
    setnames = map(strip, sets_str.split(','), ' ')
    common_options['sets'] = setnames
    return common_options


def get_set_config_values(cfg, setname, common_options):
    """Return config values for the given set."""
    import re
    set_options = {'name': None, 'source': None, 'destination': None}
    # make sure required options are set by simply trying to get() them:
    for c in set_options:
        set_options[c] = cfg.get(setname, c, False, common_options)
    # now fetch all given options:
    excludeoptionmatch = re.compile('^--exclude.*')
    for c in cfg.options(setname):
        set_options[c] = cfg.get(setname, c, False, common_options)
        set_options[c] = set_options[c].split(os.linesep)  # multi-line options

        # remove double slashes from filenames:
        if excludeoptionmatch.match(c):
            for i in range(len(set_options[c])):
                set_options[c][i] = os.path.expanduser(set_options[c][i])
                while not set_options[c][i].find(os.sep + os.sep) == -1:
                    set_options[c][i] = set_options[c][i].replace(os.sep + os.sep, os.sep)
        if len(set_options[c]) == 1:
            set_options[c] = set_options[c][0]
        elif len(set_options[c]) == 0:
            set_options[c] = ''

    set_options['source'] = os.path.expanduser(set_options['source'])
    set_options['destination'] = os.path.expanduser(set_options['destination'])
    return set_options


def ping_host(host):
    """Determine if host is pingable."""
    args = ['ping', '-c', '1', host]
    res = run_proc(args, True)
    # print "Ping host %s returned:" % host
    # print res
    return res


def do_backup_with_options(copt, dopt):
    """Perform backup given options."""
    import re
    from types import ListType
    m = re.compile(r'^\-\-.*')
    additional_run_options = ['--remove-older-than']
    additional_run = []
    forbidden_options = ['-r', '--restore-as-of']
    cmdlineoptions = []
    for k in dopt:
        if m.match(k):  # it's a command line option for rdiff-backup!
            if k in additional_run_options:
                additional_run = [k, dopt[k]]
            elif k in forbidden_options:
                pass
            else:
                if type(dopt[k]) is ListType:
                    # print "FOUND LIST"
                    for val in dopt[k]:
                        cmdlineoptions.append(k)
                        cmdlineoptions.append(val)
                else:
                    cmdlineoptions.append(k)
                    if len(dopt[k]) > 0:  # some command line arguments are switches and take no value!
                        cmdlineoptions.append(dopt[k])
    cmdlineoptions.append(dopt['source'])
    cmdlineoptions.append(dopt['destination'])
    cmdlineoptions.insert(0, 'rdiff-backup')
    logging.info('%s ---> %s', dopt['source'], dopt['destination'])
    # do run!
    backupRunResult = run_proc(cmdlineoptions)
    # if successfull:
    if backupRunResult is True:
        if len(additional_run) > 0:
            additional_run.append(dopt['destination'])
            additional_run.insert(0, 'rdiff-backup')
            logging.info('Cleanup: %s', ' '.join(additional_run))
            backupRunResult = run_proc(additional_run)
    return backupRunResult


def pass_ping_check(setoptions):
    """Based on options, pass or don't pass the ping check."""
    if ('pingcheck' in setoptions and ping_host(setoptions['pingcheck'])) or ('pingcheck' not in setoptions):
        return True
    else:
        logging.warn("could not ping host '%s'" % setoptions['pingcheck'])
        return False


def pass_dir_check(setoptions):
    """Based on options, pass or don't pass the dir check."""
    if ('dircheck' in setoptions and os.path.exists((setoptions['dircheck']))) or ('dircheck' not in setoptions):
        return True
    else:
        logging.warn("error: directory '%s' does not exist" % setoptions['dircheck'])
        return False


def setup_logging(verbosity=1, logfile='main.log', logcount=62):
    """Configure python logging."""
    from logging import handlers
    if logfile is None:
        logfile = 'main.log'
    if logcount is None:
        logcount = 62
    # set up logging
    logging.basicConfig(level=logging.DEBUG, filename=os.devnull, filemode='w')

    # define a Handler which writes messages to sys.stderr
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    if verbosity == 0:
        # simply no logging to console whatsoever ;-)
        pass
    elif verbosity == 2:
        console.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(console)
    else:  # normal : 1
        console.setLevel(logging.ERROR)
        logging.getLogger().addHandler(console)

    if logfile == os.devnull:
        fileH = logging.FileHandler(os.devnull)
    else:
        fileH = handlers.RotatingFileHandler(os.path.join(get_app_log_path(), logfile), backupCount=logcount)
        fileH.doRollover()  # rotate logfiles straight off!

    fileH.setLevel(logging.INFO)
    formatterFile = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    fileH.setFormatter(formatterFile)
    logging.getLogger().addHandler(fileH)


def version_check():
    """Fail if python version is too old."""
    import platform
    (major, minor, dummypatchlevel) = platform.python_version_tuple()
    major = int(major)
    minor = int(minor)
    if (major <= 2 and minor < 4):
        print('this script requires Python version 2.4 or newer. Sorry!')  # noqa: T001
        sys.exit(256)


def main():
    """Run main program."""
    version_check()
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='configfile', help='alternative config file', default='')
    parser.add_option('-v', '--verbose', dest='verbose', help='be verbose', action='store_true', default=False)
    parser.add_option('-q', '--quiet', dest='quiet', help='be quiet', action='store_true', default=False)
    (options, dummyargs) = parser.parse_args()

    verbosity = 1  # normal
    if options.quiet is True:
        verbosity = 0
    if options.verbose is True:
        verbosity = 2

    if len(options.configfile) > 0:
        cfg = get_config(options.configfile)
    else:
        cfg = get_config()

    thelogfile = None
    if cfg.has_option('common', 'logfile'):
        thelogfile = cfg.get('common', 'logfile')

    if cfg.has_option('common', 'logcount'):
        logcount = cfg.getint('common', 'logcount')
    else:
        logcount = None

    setup_logging(verbosity=verbosity, logfile=thelogfile, logcount=logcount)

    logging.debug('starting')

    ended_with_success = True
    common_options = get_common_config_values(cfg)
    for backup_set in common_options['sets']:
        logging.info('===START==================[ %s ]===========================', backup_set)
        setoptions = get_set_config_values(cfg, 'set_' + backup_set, common_options)
        if pass_ping_check(setoptions) and pass_dir_check(setoptions):
            result = do_backup_with_options(common_options, setoptions)
            if result is False:
                logging.error("error in backup backup_set '%s'" % backup_set)
                ended_with_success = False
        logging.info('===END==================[ %s ]===========================', backup_set)
    # done with backups, now sync the logs to the optional destination:
    logging.info('ended with success == %s' % ended_with_success)

    # TODO: currently we sync ALL available logs in logPath, but maybe they should be specific to the config file used?
    if cfg.has_option('common', 'synclogs'):
        destination = cfg.get('common', 'synclogs')
        destination = os.path.expanduser(destination)
        src = get_app_log_path()
        if not src.endswith(os.sep):
            src += os.sep
        if not destination.endswith(os.sep):
            destination += os.sep
        run_proc(['rsync', '-aupz', src, destination])

    if ended_with_success is False:
        sys.exit(256)


if __name__ == '__main__':
    main()
