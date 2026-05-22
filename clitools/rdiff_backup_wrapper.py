#!/usr/bin/env python

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

import logging
import os
import re
import sys
from optparse import OptionParser

try:
    from configparser import ConfigParser as SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser

author = """Paul Kremer, 2007"""
license = 'MIT'  # noqa: A001
__config_object__ = None  # holder for a Config object


def get_config(configfile=None):
    """Return an instance of ConfigParser."""
    global __config_object__
    from os import path

    if __config_object__ is None:
        cfgfile = configfile if configfile is not None else path.join(get_app_home_path(), 'config.ini')
        __config_object__ = SafeConfigParser()
        __config_object__.read(cfgfile)
    return __config_object__


def is_mac_osx():
    """Determine if we're running on macOS."""
    import platform
    import re

    darwin = re.compile('Darwin')
    return bool(darwin.match(platform.system()))


def get_app_home_path():
    """Return the application's config directory."""
    from os import environ, mkdir, path

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
    from os import environ, mkdir, path

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
    stdout, stderr = proc.communicate()
    # stdout/stderr are bytes; decode to text
    try:
        stdout_text = stdout.decode('utf-8') if stdout is not None else ''
    except Exception:
        stdout_text = str(stdout)
    try:
        stderr_text = stderr.decode('utf-8') if stderr is not None else ''
    except Exception:
        stderr_text = str(stderr)
    res = proc.returncode
    if res != 0 and quiet is False:
        logging.error('error while executing %s', ' '.join(args))
        logging.error('Non-zero exit code: %s', res)
        logging.error('STDOUT is:')
        for line in stdout_text.splitlines():
            logging.error(line)
        logging.error('STDERR is:')
        for line in stderr_text.splitlines():
            logging.error(line)
    else:
        if not quiet:
            for line in stdout_text.splitlines():
                logging.info(line)
    return res == 0


def get_common_config_values(cfg):
    """Return config values from the common section."""
    # use str.strip to trim whitespace from set names

    common_options = {'sets': []}
    required_common_options = {'sets': None}
    # make sure required options are set by simply trying to get() them:
    for c in required_common_options:
        cfg.get('common', c)

    sets_str = cfg.get('common', 'sets')
    setnames = [s.strip() for s in sets_str.split(',')]
    common_options['sets'] = setnames
    return common_options


def get_set_config_values(cfg, setname, common_options):
    """Return config values for the given set."""
    # annotate as a generic mapping so static type checkers accept varied value types
    set_options: dict = {'name': None, 'source': None, 'destination': None}
    # make sure required options are set by simply trying to get() them:
    for c in set_options:
        set_options[c] = cfg.get(setname, c, False, common_options)
    # now fetch all given options:
    excludeoptionmatch = re.compile('^--exclude.*')
    for c in cfg.options(setname):
        set_options[c] = cfg.get(setname, c, False, common_options)
        # ensure we have a string before splitting (cfg.get may return None/False)
        val = set_options[c]
        val = '' if (val is None or val is False) else str(val)
        set_options[c] = val.split(os.linesep)  # multi-line options

        # remove double slashes from filenames:
        if excludeoptionmatch.match(c):
            for i in range(len(set_options[c])):
                set_options[c][i] = os.path.expanduser(set_options[c][i])
                while set_options[c][i].find(os.sep + os.sep) != -1:
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
                if isinstance(dopt[k], list):
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
    backuprunresult = run_proc(cmdlineoptions)
    # if successful and there are additional run options, do cleanup
    if backuprunresult is True and len(additional_run) > 0:
        additional_run.append(dopt['destination'])
        additional_run.insert(0, 'rdiff-backup')
        logging.info('Cleanup: %s', ' '.join(additional_run))
        backuprunresult = run_proc(additional_run)
    return backuprunresult


def pass_ping_check(setoptions):
    """Based on options, pass or don't pass the ping check."""
    if ('pingcheck' in setoptions and ping_host(setoptions['pingcheck'])) or ('pingcheck' not in setoptions):
        return True
    else:
        logging.warn("could not ping host '%s'" % setoptions['pingcheck'])
        return False


def pass_dir_check(setoptions):
    """Based on options, pass or don't pass the dir check."""
    if ('dircheck' in setoptions and os.path.exists(setoptions['dircheck'])) or ('dircheck' not in setoptions):
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
        fileh = logging.FileHandler(os.devnull)
    else:
        fileh = handlers.RotatingFileHandler(os.path.join(get_app_log_path(), logfile), backupCount=logcount)
        fileh.doRollover()  # rotate logfiles straight off!

    fileh.setLevel(logging.INFO)
    formatterfile = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    fileh.setFormatter(formatterfile)
    logging.getLogger().addHandler(fileh)


def version_check():
    """Fail if python version is too old."""
    import platform

    (major, minor, dummypatchlevel) = platform.python_version_tuple()
    major = int(major)
    minor = int(minor)
    if major <= 2 and minor < 4:
        print('this script requires Python version 2.4 or newer. Sorry!')  # noqa: T201
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

    cfg = get_config(options.configfile) if len(options.configfile) > 0 else get_config()

    thelogfile = ''
    if cfg.has_option('common', 'logfile'):
        thelogfile = cfg.get('common', 'logfile') or ''

    logcount = cfg.getint('common', 'logcount') if cfg.has_option('common', 'logcount') else 0

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
