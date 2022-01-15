#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Script to enable or disable gitlab shared runners and pause/un-pause private runners.

Unfortunately, the Gitlab API to query quota usage for minutes is unavailable in the free tier.
This means that there is no easy way to automatically determine *when* to disable the shared runners.

Logic is tuned for the following use case:

You host a private gitlab-runner setup but only for when you run out of minutes in the free tier.
When running out of free minutes, enable the private runner, otherwise disable it and ensure the
free tier shared runners are active.
So basically this is a cost saving script.

Relevant doc links:

https://git.bct-technology.com/help/api/groups.md
https://docs.gitlab.com/ee/api/runners.html#list-groups-runners
https://about.gitlab.com/pricing/faq-consumption-cicd/
"""

import sys
import gitlab

import click


def group_projects_shared_runners(gl, grp, enabled=False):
    """Enable or disable shared runners in a private group and all projects."""
    if enabled:
        grp.shared_runners_setting = 'enabled'
    else:
        grp.shared_runners_setting = 'disabled_and_unoverridable'
    grp.save()
    for prj in grp.projects.list(as_list=False):  # use generator due to pagination
        thisprj = gl.projects.get(prj.id, lazy=False)
        if thisprj.shared_runners_enabled != enabled:
            click.echo('{0}/{1}: {2} -> {3}'.format(grp.name, thisprj.name, thisprj.shared_runners_enabled, enabled))
            thisprj.shared_runners_enabled = enabled
            thisprj.save()
        else:
            click.echo('{0}/{1}: {2}'.format(grp.name, thisprj.name, thisprj.shared_runners_enabled))


@click.command()
@click.option('--enable/--disable', default=True)
@click.option('--gitlab-token', envvar='GITLAB_TOKEN', type=click.STRING, required=True)
@click.option('--gitlab-url', envvar='GITLAB_URL', default='https://gitlab.com', type=click.STRING, required=True)
@click.option('--private_group_name', default=None, type=click.STRING, required=True)
def main(enable, gitlab_token, gitlab_url, private_group_name):
    """Enable or disable GitLab shared runners."""
    gl = gitlab.Gitlab(gitlab_url, private_token=gitlab_token)

    my_private_group = None
    for _grp in gl.groups.list():
        if _grp.name == private_group_name:
            my_private_group = _grp
    if my_private_group is None:
        raise Exception('{0} not found'.format(private_group_name))

    mygrp = gl.groups.get(my_private_group.id)
    # click.echo(mygrp.name)
    group_projects_shared_runners(gl, mygrp, enabled=enable)

    runners = mygrp.runners.list()
    for runner in runners:
        therunner = gl.runners.get(runner.id)
        for _grp in therunner.groups:
            if _grp['id'] == my_private_group.id:
                if therunner.active is not (not enable):
                    click.echo('runner: {0}/{1}: {2} -> {3}'.format(
                        _grp['name'],
                        therunner.description,
                        therunner.active,
                        not enable
                    ))
                    therunner.active = not enable
                    therunner.save()
                else:
                    click.echo('runner: {0}/{1}: {2}'.format(
                        _grp['name'],
                        therunner.description,
                        therunner.active
                    ))
    return 0


if __name__ == '__main__':
    sys.exit(main())
