import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import timedelta, datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Catalyst & Flow Tracker", layout="wide")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
<style>
    /* Modern, elegant, minimalist styling */
    .metric-card {
        background: rgba(128, 128, 128, 0.05);
        backdrop-filter: blur(10px);
        padding: 24px 16px;
        border-radius: 8px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        text-align: center;
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        border-color: rgba(128, 128, 128, 0.4);
    }
    .metric-label { 
        font-size: 11px; 
        text-transform: uppercase; 
        letter-spacing: 1.5px; 
        color: #888888; 
        margin-bottom: 8px; 
        font-weight: 600;
    }
    .metric-value { 
        font-size: 28px; 
        font-weight: 300; 
        letter-spacing: -0.5px; 
    }
    .pos-return { color: #5C946E !important; } /* Muted sage green */
    .neg-return { color: #C96464 !important; } /* Muted rose red */
    
    /* Clean up default Streamlit elements */
    h1, h2, h3 {
        font-weight: 400 !important;
        letter-spacing: -0.5px;
    }
</style>
""", unsafe_allow_html=True)

# --- CORE LOGIC ---
class IPOCatalystTracker:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        
        # We now let yfinance handle the session mapping natively to avoid the curl_cffi error
        self.stock = yf.Ticker(self.ticker)
        self.stock_info = {}
        self.ipo_date = None
        self.current_year = datetime.now().year

    def fetch_data(self):
        # Added a 3-attempt retry loop just in case Yahoo is being extra stubborn
        for attempt in range(3):
            try:
                # yfinance sometimes returns None instead of a dictionary if data is missing/blocked. 
                # We force it to be an empty dict to prevent AttributeError crashes.
                info = self.stock.info
                self.stock_info = info if info is not None else {}
                
                hist = self.stock.history(period="max")
                if hist.empty:
                    return False, f"No trading data found for {self.ticker}."
                self.ipo_date = hist.index.min().date()
                return True, "Success"
            except Exception as e:
                if "Too Many Requests" in str(e) or "Rate limited" in str(e) or "429" in str(e):
                    if attempt < 2:
                        time.sleep(2) # Backoff before retrying
                        continue
                return False, f"Error: {str(e)}\n\n(Yahoo Finance might be temporarily blocking the server IP. Try again in a few minutes.)"

    def get_metrics(self):
        current_price = self.stock_info.get('currentPrice', self.stock_info.get('regularMarketPrice', 0))
        prev_close = self.stock_info.get('previousClose', 0)
        
        hist_ytd = self.stock.history(period="ytd")
        hist_1y = self.stock.history(period="1y")
        
        ytd_return = one_yr_return = "N/A"
        ytd_val = one_yr_val = 0
        
        if not hist_ytd.empty and current_price:
            first_ytd = hist_ytd['Close'].iloc[0]
            ytd_val = ((current_price - first_ytd) / first_ytd) * 100
            ytd_return = f"{ytd_val:+.2f}%"
            
        if not hist_1y.empty and current_price:
            first_1y = hist_1y['Close'].iloc[0]
            one_yr_val = ((current_price - first_1y) / first_1y) * 100
            if len(hist_1y) >= 250:
                one_yr_return = f"{one_yr_val:+.2f}%"
            else:
                one_yr_return = f"{one_yr_val:+.2f}% (Since IPO)"

        return current_price, prev_close, ytd_return, one_yr_return, ytd_val, one_yr_val

    def get_mechanical_deadlines(self):
        if not self.ipo_date: return {}
        return {
            "IPO Pricing / First Trade": self.ipo_date,
            "Quiet Period (T+25)": self.ipo_date + timedelta(days=25),
            "Lock-Up Expiry (T+180)": self.ipo_date + timedelta(days=180)
        }
        
    def get_funds(self):
        """Safely fetches mutual fund holders to prevent rate-limit crashes."""
        try:
            return self.stock.mutualfund_holders
        except Exception:
            # If Yahoo rate-limits this specific call, fail gracefully
            return None

# --- UI LAYOUT ---
st.title("Post-IPO Catalyst & Flow Tracker")
st.markdown("<p style='color: #888; font-size: 16px; font-weight: 300;'>Predictive Index Inclusion & IPO Lock-up Mapping</p>", unsafe_allow_html=True)
st.write("") # Spacing

ticker_input = st.text_input("Enter Ticker (e.g. EIKN, ARM, AAPL)", "")

if ticker_input:
    with st.spinner(f"Pulling live market data for {ticker_input.upper()}..."):
        tracker = IPOCatalystTracker(ticker_input)
        success, msg = tracker.fetch_data()
        
        if not success:
            st.error(msg)
        else:
            # 1. Profile Data
            sector = tracker.stock_info.get('sector', 'Unknown')
            industry = tracker.stock_info.get('industry', 'Unknown')
            mcap = tracker.stock_info.get('marketCap', 0)
            mcap_str = f"${mcap / 1e9:.2f}B" if mcap else "Unknown"
            
            days_public = (datetime.now().date() - tracker.ipo_date).days
            is_mature = days_public > 365
            status_badge = "Mature Company" if is_mature else "Recent IPO"

            st.write("---")
            
            # Top Row: Info & Prices
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader(f"{tracker.ticker} Profile")
                st.caption(tracker.stock_info.get('shortName', 'Company Name'))
                st.markdown(f"**Status:** {status_badge}")
                st.markdown(f"**Sector:** {sector}")
                st.markdown(f"**Industry:** {industry}")
                st.markdown(f"**Est. Market Cap:** {mcap_str}")
                
            with col2:
                st.subheader("Price & Performance")
                cp, pc, ytd, oyr, ytd_v, oyr_v = tracker.get_metrics()
                
                m1, m2, m3, m4 = st.columns(4)
                
                m1.metric("Current Price", f"${cp:.2f}" if cp else "N/A", f"{cp - pc:+.2f}" if cp and pc else None)
                m2.metric("Previous Close", f"${pc:.2f}" if pc else "N/A")
                m3.metric("YTD Return", ytd)
                m4.metric("1-Year Return", oyr)

            st.write("---")

            # Middle Row: Deadlines
            st.subheader("Mechanical & Regulatory Deadlines")
            st.write("")
            deadlines = tracker.get_mechanical_deadlines()
            
            d_cols = st.columns(3)
            for idx, (event, date) in enumerate(deadlines.items()):
                passed = date < datetime.now().date()
                status = "Passed" if passed else "Upcoming"
                color = "#888888" if passed else "#5C946E"
                
                with d_cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{event}</div>
                        <div class="metric-value">{date.strftime('%b %d, %Y')}</div>
                        <div style="color: {color}; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; margin-top: 12px;">{status}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("---")

            # Bottom Row: Index Logic
            if is_mature:
                st.subheader("Top Passive Institutional Holders")
                st.markdown(f"<p style='color: #888; font-size: 14px;'>{tracker.ticker} has been public for >1 year. Mechanical lock-ups are irrelevant. The funds listed below control the daily passive flows.</p>", unsafe_allow_html=True)
                
                # Use our new safe wrapper function!
                funds = tracker.get_funds()
                
                if funds is not None and not funds.empty:
                    funds_clean = funds.head(5)[['Holder', 'pctHeld']]
                    funds_clean['pctHeld'] = (funds_clean['pctHeld'] * 100).round(2).astype(str) + '%'
                    funds_clean.columns = ['Fund Name', '% of Float Owned']
                    st.table(funds_clean)
                else:
                    st.warning("Fund data temporarily unavailable due to rate limits from data provider.")
            else:
                st.subheader("Predictive Index Inclusion Targets")
                st.write("")
                
                inclusions = []
                ipo_month = tracker.ipo_date.month
                
                # Logic
                if ipo_month <= 4: inclusions.append({"Index": "Russell 2000/3000", "Target": "Late June", "Prob": "High"})
                elif ipo_month <= 10: inclusions.append({"Index": "Russell 2000/3000", "Target": "Dec 11", "Prob": "High"})
                
                inclusions.append({"Index": "CRSP US Total Market (VTI)", "Target": "Next Quarterly Rebalance", "Prob": "High"})
                inclusions.append({"Index": "MSCI USA IMI", "Target": "Next Index Review", "Prob": "High" if mcap >= 1e9 else "Medium"})
                inclusions.append({"Index": "S&P Composite 1500", "Target": f"After {(tracker.ipo_date + timedelta(days=365)).strftime('%b %Y')}", "Prob": "Low"})
                
                if sector == 'Healthcare' or 'Biotech' in industry:
                    inclusions.append({"Index": "S&P Biotech (XBI)", "Target": "Next Quarterly Rebalance", "Prob": "High"})
                    inclusions.append({"Index": "Nasdaq Biotech (NBI)", "Target": "December (Annual)", "Prob": "High"})
                else:
                    inclusions.append({"Index": "Nasdaq 100 (QQQ)", "Target": "Standard or Fast Entry (15 Days)", "Prob": "Varies"})

                df_inc = pd.DataFrame(inclusions)
                st.table(df_inc)
