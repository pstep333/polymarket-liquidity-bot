import pandas as pd
from py_clob_client.client import ClobClient
from variables import chain_id, host, key, funder


def get_markets(client):
    resp = client.get_markets()
    pages = []
    pages.append(resp['data'])

    flag = True
    while flag:
        resp = client.get_markets(next_cursor=resp['next_cursor'])
        pages.append(resp['data'])
        if resp['next_cursor'] == 'LTE=':
            flag = False

    open_markets = []
    for page in pages:
        for market in page:
            if (market['active'] == True) & (market['closed'] == False):
                open_markets.append(market)

    questions = []
    condition_ids = []
    question_ids = []
    first_tokens = []
    first_outcomes = []
    first_prices = []
    second_tokens = []
    second_outcomes = []
    second_prices = []

    for market in open_markets:
        questions.append(market['question'])
        condition_ids.append(market['condition_id'])
        question_ids.append(market['question_id'])
        first_tokens.append(market['tokens'][0]['token_id'])
        first_outcomes.append(market['tokens'][0]['outcome'])
        first_prices.append(market['tokens'][0]['price'])
        second_tokens.append(market['tokens'][1]['token_id'])
        second_outcomes.append(market['tokens'][1]['outcome'])
        second_prices.append(market['tokens'][1]['price'])

    dict = {'question': questions,
            'condition_id': condition_ids, 
            'question_id': question_ids, 
            'first_token_id': first_tokens,
            'first_outcome': first_outcomes,
            'first_price': first_prices,
            'second_token_id': second_tokens,
            'second_outcome': second_outcomes,
            'second_price': second_prices}

    return pd.DataFrame(dict)


def main():
    client = ClobClient(host=host, key=key, chain_id=chain_id, signature_type=1, funder=funder)
    client.set_api_creds(client.create_or_derive_api_creds())
    df = get_markets(client)

    # use to get ids of desired markets
    for i, row in df.iterrows():
        if ('cowboy' in row['question'].lower()) & ('' in row['question'].lower()):
            print(row['question'])
            print(row['first_price'])
            print(row['condition_id'])


if __name__ == '__main__':
    main()
