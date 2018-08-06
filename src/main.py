from tangerine import InteractiveSecretProvider, DictionaryBasedSecretProvider, TangerineClient
import json
import logging
import pprint

from datetime import datetime, date
from dateutil.relativedelta import *

from http.client import HTTPConnection # py3

pp = pprint.PrettyPrinter(indent=2)

def debug_requests_on():
    '''Switches on logging of the requests module.'''
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def input_choices_menu(title, prompt, options: dict):
    firstPass = True
    selected_num = -1
    while selected_num < 1 or selected_num > len(options):
        if not firstPass:
            print('Invalid choice.  Please select a valid choice.')
            print()

        print(title)
        num = 1
        for descr, obj in options:
            print(' ({})  {}'.format(num, descr))
            num += 1

        selected_str = input(prompt + ':  ')
        selected_num = int(selected_str)
        firstPass = False

    selected_key = options[selected_num-1][1]
    return selected_key


def list_pending_transactions():
    pending_trans = client.list_pending_transactions()

    for trans in pending_trans:

        amount = f"{trans['amount']} $"
        if 'emt' in trans:
            recipient = trans['emt']['recipient_name']
            effective_date = trans['effective_date']
            print(
                f"{effective_date} - email {amount} To {recipient} From {trans['from_account']['product_description']}")
        elif 'mutual_fund' in trans:
            mutual_fund = trans['mutual_fund']
            action = mutual_fund['trade_type']
            fund_name = mutual_fund['portfolio_name']
            action_descr = f'buy for {amount} units of mutual found: {fund_name}'
            print(f"{mutual_fund['effective_date']} - buy for {amount} units of mutual found: {fund_name}")


def account_actions_menu(client, account):
    choices = [
        ('Move money to another account', 1),
        ('Email money', 2),
        ('List pending transactions', 3),
        ('Schedule rent payment', 4)
        ]
    result_num = input_choices_menu(
        'Available actions:',
        'Please select an action',
        choices)

    if result_num == 1:
        move_money(account)
    elif result_num == 2:
        email_money(account)
    elif result_num == 3:
        list_pending_transactions()
    elif result_num == 4:
        schedule_pay_rent_emt(account)


def select_move_money_target(source_account):
    move_money_accounts = client.list_move_money_accounts()
    target_accounts = move_money_accounts['toAccounts']

    selected_account = input_choices_menu(
        'Destination accounts:',
        'Select the target account',
        [(eacct['description'], eacct) for eacct in target_accounts if eacct['number'] != source_account['number']])
    return selected_account


def select_amount():
    amount = float(input('Please write the amount $ to send: '))
    return amount


def select_when():
    isvalidwhen = False
    is_now = False
    scheduleddate = None

    while not isvalidwhen:
        when_raw = input('Type the planned date of the transfer (YYYY-MM-DD).  If now, hit Enter.')
        if when_raw.strip() == "":
            isvalidwhen = True
            is_now = True
        else:
            parsed_date = datetime.strptime(when_raw, '%Y-%m-%d')
            if parsed_date is not None:
                isvalidwhen = True
                is_now = False
                scheduleddate = parsed_date

    return {
        "when": "NOW" if is_now else "LATER",
        "scheduled_date": scheduleddate
    }


def select_recipient(recipients: dict):
    selected_recipient = input_choices_menu(
        'Email recipients:',
        'Select the email recipient',
        [(f"{recip['first_name']} {recip['last_name']} ({recip['email_address']}", recip) for recip in recipients])
    return selected_recipient


def email_money(account):
    recipients = client.list_email_recipients()
    selected_recipient = select_recipient(recipients)
    when_info = select_when()
    amount = select_amount()

    print('summary:')
    print(f'Amount: {amount}')
    print(f'recipient: {selected_recipient["first_name"]} {selected_recipient["last_name"]} ({selected_recipient["email_address"]}')
    print(f'When: {when_info["when"]}, scheduled_date: {when_info["scheduled_date"]}')

    client.email_money(
        account['number'],
        selected_recipient['sequence_number'],
        amount,
        when_info['when'],
        when_info['scheduled_date'])


def schedule_pay_rent_emt(account):
    recipients = client.list_email_recipients()
    recipient = select_recipient(recipients)

    pending_transactions = client.list_pending_transactions()

    last_payment_month = input('Please enter the month of the last payment format: (YYYY-MM)')
    last_payment_date = datetime.strptime(last_payment_month + '-01', '%Y-%m-%d')

    amount = select_amount()

    current_date = date.today()
    # special case, if current date is 1st of the month,
    # assume we want to pay rent for today too ! might want to flexibilise that later...
    if current_date.day != 1:
        current_date = date(current_date.year, current_date.month, 1) + relativedelta(months=+1)

    payment_dates = list()
    while not dates_equal(current_date, last_payment_date):
        if not exists_transaction_with_criteria(pending_transactions, recipient['email_address'], current_date):
            payment_dates.append(current_date)
        else:
            print(f'payment already scheduled for {current_date}, skipping...')

        current_date += relativedelta(months=+1)

    print('Will schedule a payment for the following dates:')
    for pdate in payment_dates:
        print(pdate)

    print()
    response = ''
    while response.lower() != 'y' and response.lower() != 'n':
        print('RECIPIENT: ' + recipient['email_address'])
        response = input('Please confirm you want to schedule payments for these dates (y/n): ')

    if response == 'y':
        for scheduled_date in payment_dates:
            scheduled_date_string = scheduled_date.strftime('%Y-%m-%d')
            client.email_money(account['number'], recipient['sequence_number'], amount, 'LATER', scheduled_date_string)


def dates_equal(date1: date, date2: date):
    return date1.year == date2.year and date1.month == date2.month and date1.day == date2.day


def exists_transaction_with_criteria(transactions, recipient_email, scheduled_date):
    for trans in transactions:

        if 'emt' in trans:
            effdate = datetime.strptime(trans['effective_date'], '%Y-%m-%d').date()
            if recipient_email == trans['emt']['recipient_email'] and dates_equal(scheduled_date, effdate):
                return True

    return False


def move_money(account):
    target_account = select_move_money_target(account)
    amount = select_amount()
    currency = 'CAD'
    when = select_when()

    client.move_money(
        account_id=account['number'],
        from_account=account['display_name'],
        to_account=target_account['display_name'],
        amount=amount,
        currency='CAD',
        when='NOW'
    )

#debug_requests_on()
#logging.basicConfig(filename='debug.log', level=logging.DEBUG)


with open('config.json', 'r') as json_file:
    credential = json.load(json_file)

secret_provider = InteractiveSecretProvider()
secret_provider_json = DictionaryBasedSecretProvider(credential)
client = TangerineClient(secret_provider_json)

with client.login():

    accounts = client.list_accounts()  # type: list
    selected_account = input_choices_menu('Accounts:', 'Please select the account number', [(acct['description'], acct) for acct in accounts])
    account_actions_menu(client, selected_account)

    #
    # print(client.list_move_money_accounts())
    # exit()

    # client.move_money(
    #     account_id = account['number'],
    #     from_account=account['display_name'], to_account= '2067056',
    #     amount= 100,
    #     currency='CAD',
    #     when='NOW'
    # )

    #client.email_money(accountNumber, recipient_sequence_number= 2114528, amount= 10, when= 'LATER', scheduled_date= '2018-02-01')




    # start_date = datetime.date(2017, 1, 1)
    # end_date = datetime.date(2018, 1, 1)
    # for tran in client.list_transactions([accountNumber], start_date, end_date):
    #     print(tran)


