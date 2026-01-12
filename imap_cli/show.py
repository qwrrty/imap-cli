# -*- coding: utf-8 -*-


"""Functions searching in IMAP account"""


import codecs
import email
import logging
import re
import sys

from email import header

import docopt

import imap_cli
from imap_cli import config
from imap_cli import const
from imap_cli import fetch


log = logging.getLogger('imap-cli-list')
usage = """Usage: imap-cli-mm [options] <search-cmd>...

Options:
    -m, --mailbox=<mailbox>     Search the specified mailbox (default: INBOX)
    -c, --config-file=<FILE>    Configuration file (`~/.config/imap-cli` by
                                default)
    -f, --format=<FMT>          Output format
    -l, --limit=<limit>         Limit number of mail displayed
    -v, --verbose               Generate verbose messages
    -h, --help                  Show help options.
    --version                   Print program version.

The "search-cmd" arguments specify an IMAP search string, as follows:

      ALL            All messages in the mailbox; the default initial
                     key for ANDing.

      ANSWERED       Messages with the \\Answered flag set.

      BCC <string>   Messages that contain the specified string in the
                     envelope structure's BCC field.

      BEFORE <date>  Messages whose internal date is earlier than the
                     specified date.

      BODY <string>  Messages that contain the specified string in the
                     body of the message.

      CC <string>    Messages that contain the specified string in the
                     envelope structure's CC field.

      DELETED        Messages with the \\Deleted flag set.

      DRAFT          Messages with the \\Draft flag set.

      FLAGGED        Messages with the \\Flagged flag set.

      FROM <string>  Messages that contain the specified string in the
                     envelope structure's FROM field.

      HEADER <field-name> <string>
                     Messages that have a header with the specified
                     field-name (as defined in [RFC-822]) and that
                     contains the specified string in the [RFC-822]
                     field-body.

      KEYWORD <flag> Messages with the specified keyword set.

      LARGER <n>     Messages with an RFC822.SIZE larger than the
                     specified number of octets.

      NEW            Messages that have the \\Recent flag set but not the
                     \\Seen flag.  This is functionally equivalent to
                     "(RECENT UNSEEN)".

      NOT <search-key>
                     Messages that do not match the specified search
                     key.

      OLD            Messages that do not have the \\Recent flag set.
                     This is functionally equivalent to "NOT RECENT" (as
                     opposed to "NOT NEW").

      ON <date>      Messages whose internal date is within the
                     specified date.

      OR <search-key1> <search-key2>
                     Messages that match either search key.

      RECENT         Messages that have the \\Recent flag set.

      SEEN           Messages that have the \\Seen flag set.

      SENTBEFORE <date>
                     Messages whose [RFC-822] Date: header is earlier
                     than the specified date.

      SENTON <date>  Messages whose [RFC-822] Date: header is within the
                     specified date.

      SENTSINCE <date>
                     Messages whose [RFC-822] Date: header is within or
                     later than the specified date.

      SINCE <date>   Messages whose internal date is within or later
                     than the specified date.

      SMALLER <n>    Messages with an RFC822.SIZE smaller than the
                     specified number of octets.

      SUBJECT <string>
                     Messages that contain the specified string in the
                     envelope structure's SUBJECT field.

      TEXT <string>  Messages that contain the specified string in the
                     header or body of the message.

      TO <string>    Messages that contain the specified string in the
                     envelope structure's TO field.

      UID <message set>
                     Messages with unique identifiers corresponding to
                     the specified unique identifier set.

      UNANSWERED     Messages that do not have the \\Answered flag set.

      UNDELETED      Messages that do not have the \\Deleted flag set.

      UNDRAFT        Messages that do not have the \\Draft flag set.

      UNFLAGGED      Messages that do not have the \\Flagged flag set.

      UNKEYWORD <flag>
                     Messages that do not have the specified keyword
                     set.

      UNSEEN         Messages that do not have the \\Seen flag set.

----
imap-cli-mm 0.7
Copyright (C) 2026 Tim Pierce
MIT License
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
"""


FLAGS_RE = r'.*FLAGS \((?P<flags>[^\)]*)\)'
MAIL_ID_RE = r'^(?P<mail_id>\d+) \('
UID_RE = r'.*UID (?P<uid>[^ ]*)'


def fetch_mails_info(imap_account, mail_set=None, decode=True, limit=None):
    """Retrieve information for every mail in mail_set

    Returns a dictionary with metadata about each email, with
    keys flags, id, uid, from, to, date, subject

    .. versionadded:: 0.2

    :param imap_account: imaplib.IMAP4 or imaplib.IMAP4_SSL instance
    :param mail_set: List of mail UID
    :param decode: Wether we must or mustn't decode mails informations
    :param limit: Return only last mails
    :return: email metadata
    :rtype: dict
    """
    flags_re = re.compile(FLAGS_RE)
    mail_id_re = re.compile(MAIL_ID_RE)
    uid_re = re.compile(UID_RE)

    if mail_set is None:
        mail_set = fetch_uids(imap_account, limit=limit)
    elif isinstance(mail_set, str):
        mail_set = mail_set.split()

    mails_data = fetch.fetch(imap_account, mail_set,
                             ['BODY.PEEK[HEADER]', 'FLAGS', 'UID'])
    if mails_data is None:
        return

    for mail_data in mails_data:
        flags_match = flags_re.match(mail_data[0])
        mail_id_match = mail_id_re.match(mail_data[0])
        uid_match = uid_re.match(mail_data[0])
        if mail_id_match is None or flags_match is None or uid_match is None:
            continue

        flags = flags_match.groupdict().get('flags').split()
        mail_id = mail_id_match.groupdict().get('mail_id').split()[0]
        mail_uid = uid_match.groupdict().get('uid').split()[0]

        # Some IMAP servers return the mail data preceded with ">From "
        # which screws up email.message_from_string parsing.
        mailtext = mail_data[1][1:] if mail_data[1].startswith(">From ") else mail_data[1]

        mail = email.message_from_string(mailtext)
        if decode is True:
            for header_name, header_value in mail.items():
                header_new_value = []
                for value, encoding in header.decode_header(header_value):
                    if value is None:
                        continue
                    try:
                        decoded_value = codecs.decode(value,
                                                      encoding or 'utf-8',
                                                      'ignore')
                    except TypeError:
                        log.debug("Can't decode {} with {} encoding".format(
                            value, encoding))
                        decoded_value = value
                    header_new_value.append(decoded_value)
                mail.replace_header(header_name, ' '.join(header_new_value))

        yield dict([
            ('flags', flags),
            ('id', mail_id),
            ('uid', mail_uid),
            ('from', mail['from']),
            ('to', mail['to']),
            ('date', mail['date']),
            ('subject', mail.get('subject', '')),
        ])


def fetch_uids(imap_account, charset=None, limit=None, search_criterion=None):
    """Retrieve information for every mail search_criterion.

    .. versionadded:: 0.3

    :param imap_account: imaplib.IMAP4 or imaplib.IMAP4_SSL instance
    :param charset: Desired charset for IMAP response
    :param limit: Return only last mails
    :param search_criterion: List of criteria for IMAP Search
    """
    request_search_criterion = search_criterion
    if search_criterion is None:
        request_search_criterion = 'ALL'
    elif isinstance(search_criterion, list):
        request_search_criterion = ' '.join(search_criterion)

    if imap_account.state != 'SELECTED':
        log.warning('No directory specified, selecting {}'.format(
            const.DEFAULT_DIRECTORY))
        imap_cli.change_dir(imap_account, const.DEFAULT_DIRECTORY)

    status, data_bytes = imap_account.uid(
        'SEARCH',
        charset,
        request_search_criterion)
    data = [data_bytes[0].decode('utf-8')]
    if status == const.STATUS_OK:
        return data[0].split() if limit is None else data[0].split()[-limit:]


def main():
    args = docopt.docopt('\n'.join(usage.split('\n')), version=const.VERSION)
    logging.basicConfig(
        level=logging.DEBUG if args['--verbose'] else logging.INFO,
        stream=sys.stdout,
    )

    connect_conf = config.new_context_from_file(args['--config-file'],
                                                section='imap')
    if connect_conf is None:
        return 1
    display_conf = config.new_context_from_file(args['--config-file'],
                                                section='display')
    if args['--format']:
        display_conf['format_list'] = args['--format']
    if args['--limit']:
        try:
            limit = int(args['--limit'])
            if limit < 1:
                raise ValueError
        except ValueError:
            log.error('Invalid argument limit : {}'.format(args['--limit']))
            return 1
    else:
        limit = None

    try:
        imap_account = imap_cli.connect(**connect_conf)
        imap_cli.change_dir(
            imap_account,
            directory=args['--mailbox'] or const.DEFAULT_DIRECTORY)
        mail_set = fetch_uids(imap_account,
                              search_criterion=args['<search-cmd>'])
        if len(mail_set) == 0:
            log.error('No mail found')
            return 0
        for mail_info in fetch_mails_info(imap_account,
                                          limit=limit, mail_set=mail_set):
            sys.stdout.write(
                display_conf['format_list'].format(**mail_info))
            sys.stdout.write('\n')

        imap_cli.disconnect(imap_account)
    except KeyboardInterrupt:
        log.info('Interrupt by user, exiting')

    return 0


if __name__ == '__main__':
    sys.exit(main())
