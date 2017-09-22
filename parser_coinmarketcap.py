import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:45.0) Gecko/20100101 Firefox/45.0'
}

def get_last_price_usd(token_name):
    return get_last_ticker(token_name)['price_usd']

def get_last_price_btc(token_name):
    return get_last_ticker(token_name)['price_btc']

def get_last_ticker(token_name):
    url = 'https://api.coinmarketcap.com/v1/ticker/' + token_name
    r = requests.get(url, headers=headers).json()
    # r == list is ok, dict is an error
    if type(r) is dict:
        raise Exception('%s %s' % (token_name, r['error']))
    return r[0]