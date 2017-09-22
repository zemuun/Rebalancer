#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import json
from bittrex_api import Bittrex
from parser_coinmarketcap import get_last_ticker

# don't count this tokens in total balance
blacklist = 'DMT LLT MOD USDT'

def debug_print(msg):
    print(msg)

# [0] - 'bitcoin'
# [1] - 'BTC'
# [2] - 0.08 // tokens
def read_extern_balances(filename):
    extern_balances = []
    for line in open(filename):
        if (line == '\n'):
            continue
        line = line.split('\n')
        line = line[0]
        line = line.split(' ')
        extern_balances.append(line)
    return extern_balances

# {key} - 'BTC'
# {value} - 10 (%)
def read_target_portfolio(filename):
    target = {}
    for line in open(filename):
        if (line == '\n'):
            continue
        line = line.split()
        key = line[0].upper()
        value = float(line[1])
        target[key] = value
    # hack
    target['USDT'] = float(0)
    return target

# {key} - 'BTC'
# [0] - 1.0 // price in BTC
# [1] - 5000 // price in USD
def get_extern_rates(extern_balances):
    extern_rates = {}
    for item in extern_balances:
        try:
            ticker = get_last_ticker(item[0])
        except Exception, e:
            debug_print(e)
            extern_rates[item[1]] = [0, 0]
            global blacklist
            blacklist += ' %s' % item[1]
            continue
        last_price_btc = float(ticker['price_btc'])
        last_price_usd = float(ticker['price_usd'])
        newrate = [last_price_btc, last_price_usd]
        extern_rates[item[1]] = newrate
    return extern_rates

# [0] - 'BTC'
# [1] - 0.08 // tokens
def get_bittrex_balances(bittrex):
    bittrex_balances = []
    actual = bittrex.get_balances()
    if is_success(actual):
        balances = actual['result']
        for item in balances:
            if (item['Balance'] > 0):
                currency = item['Currency']
                balance = item['Balance']
                bittrex_balances.append([currency, float(balance)])
    return bittrex_balances

# [0] - 'BTC'
# [1] - 1.0 // price in BTC
def get_bittrex_rates(balances):
    rates = {}
    for item in balances:
        xerate = 0.0
        market = 'none'
        currency = item[0]
        balance = item[1]
        if currency == 'BTC':
            xerate = 1.0
        elif currency == 'USDT':
            market = 'USDT-BTC'
        else:
            market = 'BTC-%s' % currency
        ticker = bittrex.get_ticker(market)
        if is_success(ticker):
            xerate = ticker['result']['Last']
            if currency == 'USDT':
                xerate = 1.0 / xerate
        rates[currency] = float(xerate)
    return rates

def is_success(response):
    return response['success'] == True

def get_rebalance_table(bittrex):
    try:
        extern_balances = read_extern_balances('extern_balances.txt')
    except Exception, e:
        debug_print('Failed reading extern_balances.txt (%s)' % e)
        return {}

    target_portfolio = {}
    try:
        target_portfolio = read_target_portfolio('target.txt')
    except Exception, e:
        debug_print('Failed reading target.txt (%s)' % e)
        return {}

    try:
        extern_rates = get_extern_rates(extern_balances)
    except Exception, e:
        debug_print('Coinmarketcap seems to be down. Response failed. Try again later. (%s)' % e)
        return {}

    total_balance_in_btc = 0.0
    try:
        bittrex_balances = get_bittrex_balances(bittrex)
        bittrex_rates = get_bittrex_rates(bittrex_balances)
        for item in bittrex_balances:
            # hack
            if blacklist.find(item[0]) != -1:
                continue
            total_balance_in_btc += item[1] * bittrex_rates[item[0]]
        for item in extern_balances:
            # hack
            if blacklist.find(item[1]) != -1:
                continue
            total_balance_in_btc += float(item[2]) * extern_rates[item[1]][0]
    except Exception, e:
        debug_print('Bittrex seems to be down. Response failed. Try again later.' % e)
        return {}

    rebalancetable_bittrex = {}
    for item in bittrex_balances:
        name = item[0]
        # hack
        if blacklist.find(name) != -1:
            continue
        if name == 'BTC':
            continue
        units = item[1]
        last_price = bittrex_rates[item[0]]
        balance_in_btc = units * last_price
        pct_in_btc = balance_in_btc / total_balance_in_btc * 100
        pct_target = target_portfolio.get(name.upper())
        if pct_target == None:
            debug_print('No target for %s, decided to sell all units' % name)
            pct_target = 0
        units_target = (pct_target - pct_in_btc) / pct_in_btc * units
        btc_target = units_target * last_price
        rebalancetable_bittrex[name] = [btc_target, units_target, last_price]
    rebalancetable_extern = {}

    for item in extern_balances:
        name = item[1]
        # hack
        if blacklist.find(name) != -1:
            continue
        if name == 'BTC':
            continue
        units = float(item[2])
        last_price = extern_rates[item[1]][0]
        balance_in_btc = units * last_price
        pct_in_btc = balance_in_btc / total_balance_in_btc * 100
        pct_target = target_portfolio.get(name.upper())
        if pct_target == None:
            debug_print('No target for %s, decided to sell all units' % name)
            pct_target = 0
        units_target = (pct_target - pct_in_btc) / pct_in_btc * units
        btc_target = units_target * last_price
        rebalancetable_extern[name] = [btc_target, units_target, last_price]

    rebalancetable_newtokens = {}
    for name in target_portfolio:
        # hack
        if blacklist.find(name) != -1:
            continue
        if name == 'BTC':
            continue
        if not name in rebalancetable_bittrex and not name in rebalancetable_extern:
            btc_target = target_portfolio[name] * total_balance_in_btc / 100
            last_price = 0
            units_target = 0
            rebalancetable_newtokens[name] = [btc_target, units_target, last_price]

    rebalancetable = {}
    rebalancetable['bittrex'] = rebalancetable_bittrex
    rebalancetable['ext'] = rebalancetable_extern
    rebalancetable['new'] = rebalancetable_newtokens
    return rebalancetable

def bittrex_cancel_orders(bittrex):
    opened_orders = bittrex.get_open_orders('')
    if opened_orders.get('success') != True:
        return 1
    opened_orders = opened_orders.get('result')
    debug_print('There is %s opened orders, cancelling them all.' % len(opened_orders))
    for order in opened_orders:
        bittrex.cancel(order.get('OrderUuid'))
    return 0

def print_actions_rebalance(bittrex, rebalance_table):
    #[btc_target, units_target, last_price]
    threshold_btc = 0.00050000
    for item in rebalance_table:
        if abs(rebalance_table[item][0]) <= threshold_btc:
            continue
        toBuy = rebalance_table[item][1] >= 0
        action = 'Buy'
        if not toBuy:
            action = 'Sell'
        debug_print('%s the %s for %s BTC (%s units at %s)' %
                    (action, item, rebalance_table[item][0], rebalance_table[item][1], rebalance_table[item][2]))

def bittrex_rebalance(bittrex, rebalance_table):
    #[btc_target, units_target, last_price]
    threshold_btc = 0.00050000
    # first sell
    for item in rebalance_table:
        if abs(rebalance_table[item][0]) <= threshold_btc:
            continue
        toBuy = rebalance_table[item][1] > 0
        if toBuy:
            continue
        market = 'BTC-%s' % item
        units = -rebalance_table[item][1]
        rate = rebalance_table[item][2]
        r = bittrex.sell_limit(market, units, rate)
        if not r.get('success') == True:
            raise Exception('Error placing sell order - %s (%s)' % (r.get('message'), market))
        else:
            debug_print('Sell %s %s at %s. Uuid: %s' % (units, item, rate, r['result'].get('uuid')))

    for item in rebalance_table:
        if abs(rebalance_table[item][0]) <= threshold_btc:
            continue
        toBuy = rebalance_table[item][1] > 0
        if not toBuy:
            continue
        market = 'BTC-%s' % item
        units = rebalance_table[item][1]
        rate = rebalance_table[item][2]
        r = bittrex.buy_limit(market, units, rate)
        if not r.get('success') == True:
            raise Exception('Error placing buy order - %s (%s)' % (r.get('message'), market))
        else:
            debug_print('Bought %s %s at %s. Uuid: %s' % (units, item, rate, r['result'].get('uuid')))

if __name__ == '__main__':
    with open("bittrex_secrets.json") as secrets_file:
        secrets = json.load(secrets_file)
        secrets_file.close()
    bittrex = Bittrex(secrets['key'], secrets['secret'])

    rt = get_rebalance_table(bittrex)
    debug_print('NAME: btc_target units_target last_price')
    debug_print('bittrex:')
    rt_b = rt.get('bittrex')
    rt_e = rt.get('ext')
    rt_n = rt.get('new')
    for item in sorted(rt_b):
        debug_print('%s: %s %s %s' % (item, rt_b[item][0], rt_b[item][1], rt_b[item][2]))
    debug_print('ext:')
    for item in sorted(rt_e):
        debug_print('%s: %s %s %s' % (item, rt_e[item][0], rt_e[item][1], rt_e[item][2]))

    if bittrex_cancel_orders(bittrex) != 0:
        raise Exception('Error cancelling orders. Aborting.')

    #bittrex_rebalance(bittrex, rt_b)
    print_actions_rebalance(bittrex, rt_b)
    print_actions_rebalance(bittrex, rt_e)
    print_actions_rebalance(bittrex, rt_n)