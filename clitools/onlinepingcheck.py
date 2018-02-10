# -*- coding: utf-8 -*-

"""Test internet connectivity."""

# supports python27+ with IPy
# starting with python3.4 no additional dependencies

from __future__ import print_function
from __future__ import absolute_import

from itertools import chain
import platform
from random import randint
import sys
import subprocess  # nosec

if sys.version_info < (3, 4):
    import IPy

    def new_ip(address):
        """Construct new IP address from string."""
        return IPy.IP(address)

    def is_global(ip_address):
        """Test if IP is in a public range."""
        return ip_address.iptype() == 'PUBLIC'

else:
    # pylint: disable=import-error
    import ipaddress

    def new_ip(address):
        """Construct new IP address from string."""
        return ipaddress.IPv4Address(address)

    def is_global(ip_address):
        """Test if IP is in a public range."""
        return ip_address.is_global


def random_ip():
    """Make a random IP string and return it."""
    return new_ip("%i.%i.%i.%i" % (randint(1, 254),  # nosec
                                   randint(1, 254),  # nosec
                                   randint(1, 254),  # nosec
                                   randint(1, 254)))  # nosec


def random_public_ip():
    """Make a random public IP and return it."""
    anip = random_ip()
    while not is_global(anip):
        anip = random_ip()
    return anip


def rand_ips(max_num=None):
    """
    Generate random IP addresses.

    :param max_num: generate this many IPs and not more
    """
    count = 0
    while max_num is None or count < max_num:
        if max_num is not None:
            count += 1
        yield random_ip()


def can_ping_host(host, num_tries=1):
    """
    Test if the given host can be pinged at least once out of num_tries.

    :param host: the host to ping
    :param num_tries: number of retries
    """
    if platform.system() == "Darwin":
        args = ['ping', '-n', '-c', '1', '-t', '1', "%s" % host]
    else:
        args = ['ping', '-n', '-c', '1', '-W', '1', "%s" % host]
    can_ping = False
    for _ in range(0, num_tries):
        # print(" ".join(args))
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec
        res = proc.wait()
        if res == 0:
            can_ping = True
            break
    return can_ping


def online_check():
    """
    Test if we can reach anything via ping.

    First iterates over some known hosts, then some randomly
    generated IPs and ends with DNS root servers.
    """
    try_first_ips = [
        "216.58.213.238",  # google
        "8.8.8.8",  # google
        "8.8.4.4",  # google
        "46.228.47.115",  # yahoo
        ]
    last_resort_ips = [  # dns root servers
        "198.41.0.4",
        "192.228.79.201",
        "192.33.4.12",
        "128.8.10.90",
        "192.203.230.10",
        "192.5.5.241",
        "192.112.36.4",
        "128.63.2.53",
        "192.36.148.17",
        "192.58.128.30",
        "193.0.14.129",
        "198.32.64.12",
        "202.12.27.33"
    ]

    iplists = []
    iplists.append(try_first_ips)
    iplists.append(rand_ips(max_num=50))
    iplists.append(last_resort_ips)

    return any(can_ping_host(ip) for ip in chain(*iplists))


def main():
    """Run main program."""
    if online_check():
        print("online")
        return 0
    print("offline")
    return 1


if __name__ == '__main__':
    sys.exit(main())
