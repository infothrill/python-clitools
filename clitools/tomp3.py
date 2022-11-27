# -*- coding: utf-8 -*-

"""Command line script to batch convert audio files to mp3."""

# apt-get install python-tagpy lame

from __future__ import absolute_import, print_function

import os
import subprocess  # noqa: S404
import sys

import click

# def do_single_process(file_list):
#     for file in file_list:
#         convert(file)
#
# def do_multi_process(file_list):
#     pool = None
#     try:
#         logging.debug("Creating the process pool")
#         pool = multiprocessing.Pool(number_of_processes())
#         results = pool.map_async(convert, file_list)
#         #Specify a timeout in order to receive control-c signal
#         result = results.get(0x0FFFFF)
#     except KeyboardInterrupt:
#         logging.error("Control-c pressed, conversion terminated")
#     finally:
#         logging.debug("Ensuring the processes are stopped")
#         if pool:
#             pool.terminate()
#         logging.debug("Processes stopped")
#
# def number_of_processes():
#     if(options.multiprocess):
#         return options.numberofprocesses
#     else:
#         return 1


def get_flac_tags_mutagen(path):
    """
    Return media tags of specified audio file.

    :param path: path
    """
    from mutagen.flac import FLAC
    return dict(FLAC(path).tags)


def convert_wave_to_mp3(path, dest):
    """
    Convert wave file to mp3 using 'lame'.

    :param path: path
    """
    if not dest.endswith('.mp3'):
        raise ValueError('Dest %s must end in .mp3' % dest)
    if os.path.exists(dest):
        click.secho('WARN: "%s" already exists, skipping' % dest, fg='yellow')
        return None
    cmd = ['lame', '-S', '--silent', '-b', '320', path, dest]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        click.secho('Error: non-zero exit code: %i' % proc.returncode, fg='red')
        if stdout:
            click.echo(stdout)
        if stderr:
            click.echo(stderr)
    return proc.returncode


def convert_flac_to_mp3(path, dest):
    r"""
    Convert given flac file to mp3.

    flac -c -d "$a" | lame --add-id3v2 --pad-id3v2-size 256 --ignore-tag-errors \
        --ta "$ARTIST" --tt "$TITLE" --tl "$ALBUM"  --tg "${GENRE:-12}" \
        --tn "${TRACKNUMBER:-0}" --ty "$DATE" - "$OUTF"

    Please note that the lame replaygain implementation writes a header with loudness
    information that is pretty much unsupported elsewhere. Since this process is
    non-destructive, we add the data anyway.
    """
    if not path.endswith('.flac'):
        raise ValueError('Source path %s must end in .flac' % path)
    if not dest.endswith('.mp3'):
        raise ValueError('Destination path %s must end in .mp3' % dest)
    if os.path.exists(dest):
        click.secho('WARN: "%s" already exists, skipping' % dest, fg='yellow')
        return
    tags = get_flac_tags_mutagen(path)
    # print tags
    lamecmd = ['lame', '-b', '320', '--replaygain-accurate', '--add-id3v2',
               '--pad-id3v2-size', '256', '--ignore-tag-errors']
    lametags = {
        'artist': 'ta',
        'title': 'tt',
        'album': 'tl',
        'genre': 'tg',
        'tracknumber': 'tn',
        'date': 'ty',
    }
    lametagopts = []
    for lametag in lametags:
        if lametag in tags:
            lametagopts.append('--%s' % lametags[lametag])
            lametagopts.append(tags[lametag][-1])
    lamecmd.extend(lametagopts)
    lamecmd.append('-')  # stdin
    lamecmd.append(dest)
    flaccmd = ['flac', '--stdout', '--silent', '--decode', path]
    # print(" ".join(flaccmd) + " | " +" ".join(lamecmd))
    # click.echo(path) #, dest)
    lame = subprocess.Popen(  # noqa: S603
        lamecmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    flac = subprocess.Popen(flaccmd, stdout=lame.stdin)   # noqa: S603
    out, err = lame.communicate()
    if flac.wait() != 0:
        click.secho('ERROR in flac process', fg='red')
        # print out, err
    if lame.returncode != 0:
        click.secho('Error in lame process: %r' % out + err, fg='red')


def rreplace(s, old, new, occurrence):
    """
    Rreplace.

    :param s: string
    :param old: string
    :param new: string
    :param occurrence: int
    """
    return new.join(s.rsplit(old, occurrence))


def resample_mp3(inpath, outpath, bitrate='128'):
    """
    Resample input file with given bitrate to target basedir.

    lame --mp3input -b 128 input.mp3 output.mp3
    """
    if not outpath.endswith('.mp3'):
        raise ValueError('Dest %s must end in .mp3' % outpath)
    if os.path.exists(outpath):
        click.secho('WARN: %s already exists, skipping' % outpath, fg='yellow')
        return None
    # cmd = ["ffmpeg", "-i", inpath, "-ab",  "%sk" % bitrate, outpath]
    # lame is slower !? (90sec ffmpeg, 100sec lame)
    # lame preserves tags!
    cmd = ['lame', '--mp3input', '-b', bitrate, inpath, outpath]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        click.secho('Error: non-zero exit code: %i' % proc.returncode, fg='red')
        if stdout:
            click.secho(stdout, fg='red')
        if stderr:
            click.secho(stderr, fg='red')
    return proc.returncode


def convert(path, destdir, verbose=False, dry_run=False):
    """
    Convert the given file and put converted file to destdir.

    :param path:
    :param destdir:
    :param verbose:
    :param dry_run:
    """
    strategies = {
        '.wav': convert_wave_to_mp3,
        '.aiff': convert_wave_to_mp3,
        '.flac': convert_flac_to_mp3,
        '.mp3': resample_mp3
    }
    ext = None
    for ext_ in strategies:
        if path.endswith(ext_):
            ext = ext_
            break

    if ext is None:
        if verbose:
            click.secho('Skipping "%s"' % path, fg='blue')
    else:
        src_fname = os.path.basename(path)
        dst_fname = rreplace(src_fname, ext, '.mp3', 1)
        dst_path = os.path.join(destdir, dst_fname)
        click.secho('Converting "%s"' % path)
        if not dry_run:
            if not os.path.exists(destdir):
                os.makedirs(destdir, 0o755)
            strategies[ext](path, dst_path)


def newdir(source_parent, target_parent, path):
    """
    Compute destination path.

    :param source_parent:
    :param target_parent:
    :param path:
    """
    if target_parent is None:
        return os.path.dirname(path)

    x = os.path.relpath(path, source_parent)
    y = os.path.join(target_parent, x)
    return os.path.dirname(y)


def filenames(path):
    """
    Generate filenames recursively from path.

    :param path: path
    """
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for relpath in sorted(files):
                yield os.path.join(root, relpath)
    elif os.path.isfile(path):
        yield path
    else:
        raise ValueError('Invalid argument %r' % path)


@click.command()
@click.argument('paths', type=click.Path(exists=True, file_okay=False), nargs=-1)
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.option('-d', '--dry-run', is_flag=True, default=False)
@click.option('-t', '--target', type=click.Path(exists=False, file_okay=False))
def main(paths, target, verbose, dry_run):
    """
    Run command line interface.

    :param paths:
    :param target:
    :param verbose:
    :param dry_run:
    """
    if target is not None:
        target = os.path.expanduser(target)
    if not paths:
        click.echo('Nothing to do, no paths specified.')
        return 0
    for start_path in (os.path.expanduser(p) for p in paths):
        if verbose:
            click.secho('Traversing "%s":' % start_path, fg='blue')
        for path in filenames(start_path):
            destdir = newdir(start_path, target, path)
            convert(path, destdir, verbose, dry_run)
    return 0


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    sys.exit(main())
