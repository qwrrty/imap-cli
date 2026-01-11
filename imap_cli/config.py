# -*- coding: utf-8 -*-


"""Configurator"""


import codecs
import configparser
import getpass
import itertools
import logging
import os

from imap_cli import const


app_name = os.path.splitext(os.path.basename(__file__))[0]
DEFAULT_CONFIG = {
    'hostname': 'imap.example.org',
    'username': 'username',
    'password': 'secret',
    'ssl': True,

    'limit': 10,
    'format_list': ''.join([
        '\n',
        'ID:         {uid}\n',
        'Flags:      {flags}\n',
        'From:       {from}\n',
        'To:         {to}\n',
        'Date:       {date}\n',
        'Subject:    {subject}',
    ]),
    'format_thread': '{uid} {subject} <<< FROM {from}',
    'format_status': ''.join([
        '{directory:>20} : ',
        '{count:>5} Mails - ',
        '{unseen:>5} Unseen - ',
        '{recent:>5} Recent']),

    'delete_method': 'MOVE_TO_TRASH',
    'trash_directory': 'Trash',
}
log = logging.getLogger(app_name)


def new_context(config=None):
    """Read configuration from *config* dict.

    .. versionadded:: 0.1

    :param config: Dict containing custom configuration

    Example:

    >>> from imap_cli import config
    >>> config.new_context({'hostname': 'another.imap-server.org',
                            'password': 'another.secret'})
    {'username': 'username', 'hostname': 'another.imap-server.org',
     'limit': 10, 'password': 'another.secret'}
    """
    if config is None:
        log.debug('Loading default configuration')
        config = DEFAULT_CONFIG
    else:
        log.debug('Loading custom configuration')

    return dict(
        (key, value)
        for key, value in itertools.chain(DEFAULT_CONFIG.items(),
                                          config.items())
    )


def new_context_from_file(config_filename=None, encoding='utf-8',
                          section=None):
    """Open and read *config_filename* and parse configuration from it.

    .. versionadded:: 0.1

    :param config_filename: Configuration filename
    :param encoding: Encoding of configuration file
    :param section: Import only a specific section of configuration file

    Example:

    >>> from imap_cli import config
    >>> config_file = 'config-example.ini'
    >>> config.new_context_from_file(config_file, section='imap')
    {'hostname': 'imap.example.org', 'password': 'secret', 'ssl': True,
     'username': 'username'}
    """
    if config_filename is None:
        config_filename = const.DEFAULT_CONFIG_FILE
    config_filename = os.path.abspath(
        os.path.expanduser(os.path.expandvars(config_filename)))
    if not os.path.isfile(config_filename):
        log.error('Configuration file \'{}\' not found.'.format(
            config_filename))
        return None
    log.debug('Reading configuration file \'{}\''.format(config_filename))

    config_reader = configparser.RawConfigParser()
    with codecs.open(config_filename, 'r', encoding) as config_file:
        config_reader.read_file(config_file)

    config = {}
    if section is None or section == 'imap':
        # Account
        config['username'] = config_reader.get('imap', 'username')

        config['sasl_auth'] = (
            config_reader.get('imap', 'sasl_auth')
            if config_reader.has_option('imap', 'sasl_auth')
            else None
        )

        if config['sasl_auth']:
            config['sasl_ir'] = (
                const.SASL_XOAUTH2_IR.format(config['username'],
                                             config_reader
                                             .get('imap',
                                                  'bearer_access_token'))
                if config['sasl_auth'] == 'XOAUTH2' and
                config_reader.has_option('imap', 'bearer_access_token')
                else config_reader.get('imap', 'sasl_ir')
            )
        else:
            try:
                config['password'] = config_reader.get('imap', 'password')
            except configparser.NoOptionError:
                config['password'] = getpass.getpass()

        config['hostname'] = config_reader.get('imap', 'hostname')
        config['ssl'] = config_reader.getboolean('imap', 'ssl')

    if section is None or section == 'display':
        # Display
        if config_reader.has_option('display', 'limit'):
            config['limit'] = config_reader.getint('display', 'limit')

        config['format_list'] = (
            config_reader.get('display', 'format_list')
            if config_reader.has_option('display', 'format_list')
            else 'From: {from:<30} To: {to:<20} Subject: {subject}'
        )

        config['format_status'] = (
            config_reader.get('display', 'format_status')
            if config_reader.has_option('display', 'format_status')
            else DEFAULT_CONFIG['format_status']
        )

        config['format_thread'] = (
            config_reader.get('display', 'format_thread')
            if config_reader.has_option('display', 'format_thread')
            else DEFAULT_CONFIG['format_thread']
        )

    if section is None or section == 'trash':
        # Account
        config['trash_directory'] = config_reader.get('trash',
                                                      'trash_directory')
        config['delete_method'] = config_reader.get('trash', 'delete_method')

    return config
