
import json
from datetime import date
from math import exp

import asyncio
import pandas as pd
import requests
import streamlit as st
from matplotlib import pyplot as plt



def convert_expreturn_to_annualreturn(r):  # in the units of year
    return exp(r)-1


async def get_symbol_estimations(symbol, startdate, enddate, index='^GSPC'):
    url = "https://1phrvfsc16.execute-api.us-east-1.amazonaws.com/default/fininfoestimate"

    payload = json.dumps({
        "symbol": symbol,
        "startdate": startdate,
        "enddate": enddate,
        "index": index
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    return json.loads(response.text)


async def get_symbol_plot_data(symbol, startdate, enddate):
    url = "https://ed0lbq7vph.execute-api.us-east-1.amazonaws.com/default/finportplot"

    payload = json.dumps({
        'startdate': startdate,
        'enddate': enddate,
        'components': {symbol: 1}
    })
    headers = {
        'Content-Type': 'text/plain'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    result = json.loads(response.text)
    data = result['data']
    plot_url = result['plot']['url']
    spreadsheet_url = result['spreadsheet']['url']
    return pd.DataFrame.from_records(data), plot_url, spreadsheet_url


async def get_ma_plots_info(symbol, startdate, enddate, dayswindow, title=None):
    api_url = 'https://vwl0qcnnve.execute-api.us-east-1.amazonaws.com/default/finport-ma-plot'
    payload = json.dumps({
        'symbol': symbol,
        'startdate': startdate,
        'enddate': enddate,
        'dayswindow': dayswindow,
        'title': symbol if title is None else title
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("GET", api_url, headers=headers, data=payload)
    plot_info = json.loads(response.text)
    return plot_info['plot']['url']


# load symbols
allsymbol_info = json.load(open('allsymdf.json', 'r'))
symbols = ['VOO'] + [item['symbol'] for item in allsymbol_info if item['symbol'] != 'VOO']
allsymbol_info = {item['symbol']: item for item in allsymbol_info}


st.sidebar.title('Symbols')
symbol = st.sidebar.selectbox(
    'Choose a symbol',
    symbols
)
i_startdate = st.sidebar.date_input('Start Date', value=date(2021, 1, 6))
i_enddate = st.sidebar.date_input('End Date', value=date.today())

if st.sidebar.button('Compute!'):

    index = '^GSPC'
    startdate = i_startdate.strftime('%Y-%m-%d')
    enddate = i_enddate.strftime('%Y-%m-%d')

    # starting asyncio
    task_estimate_symbols = get_symbol_estimations(symbol, startdate, enddate, index)
    task_values_over_time = get_symbol_plot_data(symbol, startdate, enddate)
    task_maplot = get_ma_plots_info(symbol, startdate, enddate, [50, 200], title=symbol)

    # estimation
    symbol_estimate = asyncio.run(task_estimate_symbols)
    r = symbol_estimate['r']
    sigma = symbol_estimate['vol']
    downside_risk = symbol_estimate['downside_risk']
    upside_risk = symbol_estimate['upside_risk']
    beta = symbol_estimate['beta']

    # making portfolio and time series
    worthdf, stockdividend_ploturl, spreadsheet_url = asyncio.run(task_values_over_time)
    maploturl = asyncio.run(task_maplot)

    # display
    col1, col2 = st.columns((2, 1))

    # plot
    f = plt.figure()
    f.set_figwidth(10)
    f.set_figheight(8)
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value')
    stockline, = plt.plot(worthdf['TimeStamp'], worthdf['stock_value'], label='stock', linewidth=0.75)
    totalline, = plt.plot(worthdf['TimeStamp'], worthdf['value'], label='stock+dividend', linewidth=0.75)
    xticks, _ = plt.xticks(rotation=90)
    step = len(xticks) // 10
    plt.xticks(xticks[::step])
    plt.legend([stockline, totalline], ['stock', 'stock+dividend'])
    col1.pyplot(f)
    col1.image(maploturl)

    # inference
    col2.title('Inference')
    col2.write('yield = {:.4f} (annually {:.2f}%)'.format(r, convert_expreturn_to_annualreturn(r)*100))
    col2.write('volatility = {:.4f}'.format(sigma))
    col2.write('downside risk = {:.4f}'.format(downside_risk))
    col2.write('upside risk = {:.4f}'.format(upside_risk))
    if beta is not None:
        col2.write('beta (w.r.t. {}) = {:.4f}'.format(index, beta))
    col2.write('Name: {}'.format(allsymbol_info[symbol]['description']))
    col2.markdown('Symbol: [{sym:}](https://finance.yahoo.com/quote/{sym:})'.format(sym=symbol))
    col2.markdown('[Download plot (stock+dividend)]({})'.format(stockdividend_ploturl))
    col2.markdown('[Download moving average plot]({})'.format(maploturl))

    # Data display
    st.title('Data')
    st.markdown('[Download Excel]({})'.format(spreadsheet_url))
    st.dataframe(worthdf)
