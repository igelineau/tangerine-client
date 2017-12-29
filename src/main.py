from tangerine import InteractiveSecretProvider, DictionaryBasedSecretProvider, TangerineClient
import datetime
import json
import logging

logging.basicConfig(filename='debug.log', level=logging.DEBUG)

with open('config.json', 'r') as json_file:
    credential = json.load(json_file)

    secret_provider = InteractiveSecretProvider()
    secret_provider_json = DictionaryBasedSecretProvider(credential)
    client = TangerineClient(secret_provider_json)


    with client.login():

        accounts = client.list_accounts()  # type: list
        num = 0  # type: int
        print('Please choose an account')
        for acct in accounts:
            num = num + 1
            print("(" + str(num) + ")  " + acct['description'])

        selectedAccountNo = int(input('Please select the account number: '))
        account = accounts[selectedAccountNo - 1]
        accountNumber = account['number']

        start_date = datetime.date(2017, 1, 1)
        end_date = datetime.date(2018, 1, 1)
        for tran in client.list_transactions([accountNumber], start_date, end_date):
            print(tran)


