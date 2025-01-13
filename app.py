import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import requests
import io
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page config
st.set_page_config(page_title="OSM Strategy Scanner", layout="wide")

def fetch_nifty500_symbols():
    """Fetch Nifty 500 symbols from NSE"""
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            symbols = [f"{symbol}.NS" for symbol in df['Symbol'].tolist()]
            return symbols
        else:
            # Fallback to top 20 stocks if unable to fetch
            return [
                'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS',
                'ICICIBANK.NS', 'BHARTIARTL.NS', 'SBIN.NS', 'HDFC.NS', 'KOTAKBANK.NS',
                'BAJFINANCE.NS', 'WIPRO.NS', 'HCLTECH.NS', 'ASIANPAINT.NS', 'ITC.NS',
                'AXISBANK.NS', 'MARUTI.NS', 'ULTRACEMCO.NS', 'SUNPHARMA.NS', 'TITAN.NS'
            ]
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return None

def fetch_stock_data(symbol):
    """Fetch stock data using yfinance"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        stock = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if not stock.empty:
            return stock
        return None
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {e}")
        return None

def analyze_stock(stock_data, symbol):
    """Analyze a single stock based on OSM criteria"""
    if stock_data is None or stock_data.empty:
        return None
        
    try:
        current_price = stock_data['Close'][-1]
        year_high = stock_data['High'].max()
        
        # Calculate returns
        six_months_ago = len(stock_data) - int(len(stock_data)/2)
        year_ago = 0
        
        six_month_price = stock_data['Close'][six_months_ago]
        year_ago_price = stock_data['Close'][year_ago]
        
        six_month_return = ((current_price - six_month_price) / six_month_price) * 100
        year_return = ((current_price - year_ago_price) / year_ago_price) * 100
        distance_from_high = ((year_high - current_price) / year_high) * 100
        
        return {
            'Symbol': symbol.replace('.NS', ''),
            'Current Price': current_price,
            '52W High': year_high,
            '1Y Return': year_return,
            '6M Return': six_month_return,
            'Distance from High': distance_from_high
        }
    except Exception as e:
        st.error(f"Error analyzing {symbol}: {e}")
        return None

def plot_returns_comparison(selected_stocks):
    """Create a bar plot comparing 1Y and 6M returns"""
    fig = go.Figure(data=[
        go.Bar(name='1Y Return', x=selected_stocks['Symbol'], y=selected_stocks['1Y Return']),
        go.Bar(name='6M Return', x=selected_stocks['Symbol'], y=selected_stocks['6M Return'])
    ])
    
    fig.update_layout(
        title='Returns Comparison',
        barmode='group',
        xaxis_title='Stocks',
        yaxis_title='Return %'
    )
    
    return fig

def main():
    st.title("🚀 OSM (One Stock Millionaire) Strategy Scanner")
    
    # Strategy description
    with st.expander("View Strategy Rules", expanded=True):
        st.write("""
        ### Strategy Rules:
        - **Universe:** Nifty 500 stocks
        - **Entry Conditions:**
            - Stocks near 52-week high
            - 1-year return > 6-month return
            - 6-month return > 50% (must be positive)
        - **Hold Period:** 3 months
        - **Stop Loss:** 15% from entry price
        - **Position Sizing:**
            - 1st stock: 40% of capital
            - 2nd stock: 30% of capital
            - 3rd stock: 30% of capital
        """)

    # Add a progress bar for scanning
    progress_bar = st.progress(0)
    
    # Fetch and process data
    if st.button("Scan for Stocks", type="primary"):
        symbols = fetch_nifty500_symbols()
        
        if symbols:
            all_stocks_data = []
            total_symbols = len(symbols)
            
            # Create a status message
            status_text = st.empty()
            
            for i, symbol in enumerate(symbols):
                # Update progress
                progress = (i + 1) / total_symbols
                progress_bar.progress(progress)
                status_text.text(f"Analyzing {symbol}... ({i+1}/{total_symbols})")
                
                # Fetch and analyze stock
                stock_data = fetch_stock_data(symbol)
                if stock_data is not None:
                    analysis = analyze_stock(stock_data, symbol)
                    if analysis:
                        all_stocks_data.append(analysis)
                
                # Add a small delay to avoid API rate limits
                time.sleep(0.5)
            
            # Convert to DataFrame and apply strategy filters
            if all_stocks_data:
                df = pd.DataFrame(all_stocks_data)
                
                # Apply OSM strategy criteria
                selected_stocks = df[
                    (df['6M Return'] > 50) &
                    (df['1Y Return'] > df['6M Return']) &
                    (df['Distance from High'] < 5)
                ].sort_values('Distance from High').head(3)
                
                # Add allocation and stop loss
                if not selected_stocks.empty:
                    selected_stocks['Allocation %'] = [40 if i == 0 else 30 for i in range(len(selected_stocks))]
                    selected_stocks['Stop Loss'] = selected_stocks['Current Price'] * 0.85
                    
                    # Display results
                    st.subheader("Selected Stocks")
                    st.dataframe(
                        selected_stocks.style.format({
                            'Current Price': '₹{:.2f}',
                            '52W High': '₹{:.2f}',
                            '1Y Return': '{:.2f}%',
                            '6M Return': '{:.2f}%',
                            'Distance from High': '{:.2f}%',
                            'Allocation %': '{:.0f}%',
                            'Stop Loss': '₹{:.2f}'
                        }),
                        use_container_width=True
                    )
                    
                    # Plot returns comparison
                    st.plotly_chart(plot_returns_comparison(selected_stocks), use_container_width=True)
                    
                    # Export option
                    csv = selected_stocks.to_csv(index=False)
                    st.download_button(
                        label="Download Results",
                        data=csv,
                        file_name="osm_strategy_results.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No stocks matched the strategy criteria.")
            else:
                st.error("No valid stock data found.")
        
        # Clear progress bar and status
        progress_bar.empty()
        
    # Disclaimer
    st.caption("""
    **Disclaimer:** This tool is for educational purposes only. 
    Always conduct your own research and consider consulting with a financial advisor before making investment decisions.
    Past performance is not indicative of future results.
    """)

if __name__ == "__main__":
    main()
