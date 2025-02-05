import yfinance as yf

yfinance_tickers = {
    'aex': '^AEX',       # AEX index
    'banks': '^SX7E',    # European banks sector
    'cac': '^FCHI',      # CAC 40
    'dax': '^GDAXI',     # DAX
    'ftse': '^FTSE',     # FTSE 100
    'mib': '^FTSEMIB.MI',# FTSE MIB
    'smi': '^SSMI',      # SMI
    'sx5e': '^STOXX50E',  # Euro STOXX 50
    'es': '^GSPC'
}

stock = yfinance_tickers['ftse']
data = yf.download(stock, period="1d", interval="1m")
print(data.head())
