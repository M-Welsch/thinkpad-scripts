#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright © 2014-2015 Martin Ueding <dev@martin-ueding.de>
# Licensed under The GNU Public License Version 2 (or later)

import argparse
import logging
import sys

import tps
import tps.config
import tps.hooks
import tps.input
import tps.screen
import tps.unity
import tps.vkeyboard

logger = logging.getLogger(__name__)


def main():
    '''
    Entry point for ``thinkpad-rotate``.
    '''
    options = _parse_args()

    config = tps.config.get_config()

    if options.via_hook:
        xrandr_bug_fail_early(config)

    try:
        new_direction = new_rotation(
            tps.screen.get_rotation(config['screen']['internal']),
            options.direction, config)
    except tps.UnknownDirectionException:
        logger.error('Direction cannot be understood.')
        sys.exit(1)
    except tps.screen.ScreenNotFoundException as e:
        logger.error('Unable to determine rotation of "{}": {}'.format(
            config['screen']['internal'], e))
        sys.exit(1)

    rotate_to(new_direction, config)


def rotate_to(direction, config):
    '''
    Performs all steps needed for a screen rotation.
    '''
    tps.hooks.prerotate(direction, config)

    tps.screen.rotate(config['screen']['internal'], direction)
    tps.input.map_rotate_all_input_devices(config['screen']['internal'],
                                           direction)

    if config['rotate'].getboolean('subpixels'):
        if config['rotate'].getboolean('subpixels_with_external') \
           or not tps.screen.get_externals(config['screen']['internal']):
            tps.screen.set_subpixel_order(direction)

    if config['unity'].getboolean('toggle_launcher'):
        tps.unity.set_launcher(not direction.physically_closed)

    tps.vkeyboard.toggle(config['vkeyboard']['program'],
                         direction.physically_closed)

    try:
        trackpoint_xinput_id = tps.input.get_xinput_id('TrackPoint')
        tps.input.set_xinput_state(
            trackpoint_xinput_id,
            not direction.physically_closed,
        )
    except tps.input.InputDeviceNotFoundException as e:
        logger.info('TrackPoint was not found, could not be (de)activated.')
        logger.debug('Exception was: “%s”', str(e))

    try:
        touchpad_xinput_id = tps.input.get_xinput_id('TouchPad')
        tps.input.set_xinput_state(
            touchpad_xinput_id,
            not direction.physically_closed,
        )
    except tps.input.InputDeviceNotFoundException as e:
        logger.info('TouchPad was not found, could not be (de)activated.')
        logger.debug('Exception was: “%s”', str(e))

    if config['rotate'].getboolean('xrandr_bug_workaround') and can_use_chvt():
        toggle_virtual_terminal()

    tps.hooks.postrotate(direction, config)


def new_rotation(current, desired_str, config):
    '''
    Determines the new rotation based on desired and current one.
    '''
    if desired_str is None:
        if not current.physically_closed:
            new = tps.translate_direction(config['rotate']['default_rotation'])
            logger.info('Using default, setting to {}'.format(new))
        else:
            new = tps.NORMAL
            logger.info('Using default, setting to {}'.format(new))
    else:
        desired = tps.translate_direction(desired_str)
        if desired == current:
            new = tps.NORMAL
            logger.info('You try to rotate into the direction it is, '
                        'reverting to normal.')
        else:
            new = desired
            logger.info('User chose to set to {}'.format(new))
    return new


def can_use_chvt():
    '''
    Checks whether ``chvt`` can be called with ``sudo`` without a password.

    :rtype: bool
    '''
    command = ['sudo', '-n', 'chvt']
    returncode = tps.call(command, logger)

    return returncode == 0


def toggle_virtual_terminal():
    '''
    XRandr has a `bug in Ubuntu`__, maybe even in other distributions. In
    Ubuntu 15.04 a workaround is to change the virtual terminal to a different
    one and back to the seventh, the graphical one. This can be automated using
    the ``chvt`` command which requires superuser privileges. An entry in the
    sudo file can let the normal user execute this program.

    __ https://bugs.launchpad.net/ubuntu/+source/x11-xserver-utils/+bug/1451798
    '''
    assert can_use_chvt()
    tps.check_call(['sudo', '-n', 'chvt', '6'], logger)
    tps.check_call(['sudo', '-n', 'chvt', '7'], logger)


def has_external_screens(config):
    '''
    Checks whether any external screens are attached.
    '''
    externals = tps.screen.get_externals(config['screen']['internal'])
    return len(externals) > 0


def xrandr_bug_fail_early(config):
    '''
    Quits the program if xrandr bug cannot be coped with.

    Abort the program if no external screen is attached and ``chvt`` workaround
    does not work. In case the workaround is not enabled in the configuration,
    this program does nothing.
    '''
    # Do nothing if workaround is not requested.
    if not config['rotate'].getboolean('xrandr_bug_workaround'):
        return

    # Do nothing if ``chvt`` can be called.
    if not can_use_chvt():
        return

    # Do nothing if an external screen is attached. The bug does not appear
    # then.
    if has_external_screens(config):
        return

    logger.warning('Aborting since there are no external screens attached '
                   'and XRandr bug workaround is enabled.')
    sys.exit(1)


def _parse_args():
    """
    Parses the command line arguments.

    If the logging module is imported, set the level according to the number of
    ``-v`` given on the command line.

    :return: Namespace with arguments.
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("direction", nargs='?', help="Positional arguments.")
    parser.add_argument("-v", dest='verbose', action="count",
                        help='Enable verbose output. Can be supplied multiple '
                             'times for even more verbosity.')
    parser.add_argument('--via-hook', action='store_true')

    options = parser.parse_args()

    tps.config.set_up_logging(options.verbose)

    return options


if __name__ == "__main__":
    main()
