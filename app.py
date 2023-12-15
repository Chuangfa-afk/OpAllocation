import yfinance as yf
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from flask import Flask, request, render_template

### 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

app = Flask(__name__)

def get_risk_free_rate():
    treasury_symbol = '^IRX'
    try:
        treasury_bill = yf.Ticker(treasury_symbol)
        hist = treasury_bill.history(period="1d")
        latest_rate = hist['Close'].iloc[-1] / 100
        return latest_rate
    except Exception as e:
        print(f"Error fetching risk-free rate: {e}")
        return None

def get_historical_data(stocks, start='2010-01-01', end=None):
    if end is None:
        end = pd.to_datetime('today').strftime('%Y-%m-%d')

    successful_downloads = {}
    failed_tickers = []

    for stock in stocks:
        try:
            data = yf.download(stock, start=start, end=end, progress=False)
            successful_downloads[stock] = data['Adj Close']
        except Exception as e:
            print(f"Failed to download data for {stock}: {e}")
            failed_tickers.append(stock)

    return successful_downloads, failed_tickers

def calculate_portfolio_stats(weights, mean_returns, cov_matrix, risk_free_rate):
    portfolio_return = np.sum(mean_returns * weights) * 252
    portfolio_std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
    sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_std_dev
    return portfolio_return, portfolio_std_dev, sharpe_ratio

def maximize_sharpe_ratio(mean_returns, cov_matrix, risk_free_rate):
    num_assets = len(mean_returns)
    args = (mean_returns, cov_matrix, risk_free_rate)
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = tuple((0, 1) for asset in range(num_assets))
    initial_guess = num_assets * [1. / num_assets,]
    opt_results = minimize(lambda w: -calculate_portfolio_stats(w, *args)[2], 
                           initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
    return opt_results.x

def optimal_portfolio(stocks_data):
    if not isinstance(stocks_data, dict):
        raise ValueError("stocks_data must be a dictionary of DataFrames.")

    data = pd.concat(stocks_data.values(), axis=1)
    data.columns = stocks_data.keys()

    mean_returns = data.pct_change().mean()
    cov_matrix = data.pct_change().cov()
    risk_free_rate = get_risk_free_rate()

    max_sharpe_weights = maximize_sharpe_ratio(mean_returns, cov_matrix, risk_free_rate)
    expected_return, expected_volatility, expected_sharpe = calculate_portfolio_stats(max_sharpe_weights, mean_returns, cov_matrix, risk_free_rate)

    return max_sharpe_weights, expected_return, expected_volatility, expected_sharpe

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    errors = None
    if request.method == 'POST':
        stocks = [stock.strip() for stock in request.form['stocks'].split(',')]
        try:
            successful_downloads, failed_tickers = get_historical_data(stocks)
            if failed_tickers:
                errors = f"Failed to download data for the following ticker(s): {', '.join(failed_tickers)}"
            if successful_downloads:
                opt_weights, exp_return, exp_volatility, exp_sharpe = optimal_portfolio(successful_downloads)
                results = {
                    'weights': {stock: weight for stock, weight in zip(successful_downloads.keys(), opt_weights)},
                    'exp_return': exp_return,
                    'exp_volatility': exp_volatility,
                    'exp_sharpe': exp_sharpe
                }
        except Exception as e:
            errors = str(e)
    return render_template('index.html', results=results, errors=errors)

if __name__ == '__main__':
    app.run(debug=True)
