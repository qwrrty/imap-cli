# -*- coding: utf-8 -*-


"""Functions searching in IMAP account"""


import ast
import codecs
import datetime
import email
from email import header
import logging
import re
import sys

import docopt

import imap_cli
from imap_cli import config
from imap_cli import const
from imap_cli import fetch


log = logging.getLogger('imap-cli-list')

FLAGS_RE = r'.*FLAGS \((?P<flags>[^\)]*)\)'
MAIL_ID_RE = r'^(?P<mail_id>\d+) \('
UID_RE = r'.*UID (?P<uid>[^ ]*)'


def escape(word):
    """Escape a word with quotation marks if necessary to preserve spaces.

    :param word: a string containing a word or search term
    :returns: the input word, surrounded by quotation marks if necessary
    :rtype: str
    """

    if any(c.isspace() for c in word):
        return '"{}"'.format(word)
    else:
        return word


def combine_search_criterion(search_criterion, operator='AND'):
    """Return a single IMAP search string combining all criterion given.

    .. versionadded:: 0.4

    :param operator: Possible values are : 'AND', 'OR' and 'NOT'
    """
    if operator not in ['AND', 'OR', 'NOT']:
        operator = 'AND'
        log.warning(''.join([
            'Wrong value for "operator" argument,',
            'taking default value "{}"']).format(operator))

    if operator == 'AND':
        return '({})'.format(' '.join([escape(w) for w in search_criterion]))
    if operator == 'OR':
        return 'OR {}'.format(' '.join([escape(w) for w in search_criterion]))
    if operator == 'NOT':
        return 'NOT {}'.format(' '.join([escape(w) for w in search_criterion]))


def create_search_criterion(address=None, date=None, size=None, subject=None,
                            tags=None, text=None, operator='AND'):
    """Create a list for all search criterion

    Wrapper helping developer to construct a list of search criterion with
    a single method.

    .. versionadded:: 0.2

    """
    search_criterion = []
    if address is not None:
        search_criterion.append(create_search_criterion_by_mail_address(
            address))
    if date is not None:
        search_criterion.append(create_search_criterion_by_date(date))
    if tags is not None:
        search_criterion.append(create_search_criteria_by_tag(tags))
    if text is not None:
        search_criterion.append(create_search_criteria_by_text(text))
    if subject is not None:
        search_criterion.append(create_search_criterion_by_subject(subject))
    if size is not None:
        search_criterion.append(create_search_criterion_by_size(size))

    if len(search_criterion) == 0:
        search_criterion.append('ALL')

    return search_criterion


def create_search_criterion_by_date(datetime, relative=None, sent=False):
    """Return a search criteria by date.

    .. versionadded:: 0.4

    :param relative: Can be one of 'BEFORE', 'SINCE', 'ON'.
    :param sent: Search after "sent" date instead of "received" date.
    """
    if relative not in ['BEFORE', 'ON', 'SINCE']:
        relative = 'SINCE'
    formated_date = datetime.strftime('%d-%h-%Y')
    return '{}{} {}'.format('SENT'
                            if sent is True
                            else '', relative, formated_date)


def create_search_criterion_by_header(header_name, header_value):
    """Return search criteria by header.

    .. versionadded:: 0.4
    """
    return 'HEADER {} {}'.format(header_name, header_value)


def create_search_criterion_by_mail_address(mail_address, header_name='FROM'):
    """Return a search criteria over mail address.

    .. versionadded:: 0.4

    :param header_name: Specify in wich header address must be searched. \
                        Possible values are "FROM", "CC", "BCC" and "TO"
    """
    if header_name not in ['BCC', 'CC', 'FROM', 'TO']:
        header_name = 'FROM'
        log.warning(
            'Wrong "header_name" value, taking default value {}'.format(
                header_name))

    return '{} "{}"'.format(header_name, mail_address)


def create_search_criterion_by_size(size, relative='LARGER'):
    """Return a search criteria by size.

    .. versionadded:: 0.4

    :param relative: Can be one of 'LARGER' or 'SMALLER'
    """
    # TODO(rsoufflet) sannitize "size" arg
    if relative not in ['LARGER', 'SMALLER']:
        relative = 'LARGER'
        log.warning(
            'Wrong "relative" argument, taking default value "{}"'.format(
                relative))
    return '{} "{}"'.format(relative, size)


def create_search_criterion_by_subject(subject):
    """Return search criteria by subject.

    .. versionadded:: 0.4
    """
    return 'SUBJECT "{}"'.format(subject)


def create_search_criteria_by_tag(tags):
    """Return a search criteria for specified tags.

    .. versionadded:: 0.3
    """
    if len(tags) == 0:
        return ''

    criterion = []
    for tag in tags:
        if tag.upper() in const.IMAP_SPECIAL_FLAGS:
            criterion.append(tag.upper())
        else:
            criterion.append('KEYWORD "{}"'.format(tag))
    return '({})'.format(
        ' '.join(criterion)) if len(criterion) > 1 else criterion[0]


def create_search_criteria_by_text(text):
    """Return a search criteria for fulltext.

    .. versionadded: 0.4
    """
    return 'BODY "{}"'.format(text)


def create_search_criterion_by_uid(uid):
    """Return a search criteria for UID.

    .. versionadded: 0.4
    """
    return 'UID {}'.format(uid)


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
                        log.debug('Can\'t decode {} with {} encoding'.format(
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
        request_search_criterion = combine_search_criterion(search_criterion)

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
