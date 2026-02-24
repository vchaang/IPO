import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta, datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Catalyst & Flow Tracker", page_icon="📈", layout="wide")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
<style>
    .metric-card {
        background-color: #1E293B;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #334155;
        text-align: center;
    }
    .metric-label { font-size: 14px; color: #94A3B8; margin-bottom: 5px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #F8FAFC; }
    .pos-return { color: #34D399 !important; }
    .neg-return { color: #F87171 !important; }
</style>
""", unsafe_allow_html=True)

# --- CORE LOGIC ---
class IPOCatalystTracker:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        self.stock_info = {}
        self.ipo_date = None
        self.current_year = datetime.now().year

    def fetch_data(self):
        try:
            self.stock_info = self.stock.info
            hist = self.stock.history(period="max")
            if hist.empty:
                return False, f"No trading data found for {self.ticker}."
            self.ipo_date = hist.index.min().date()
            return True, "Success"
        except Exception as e:
            return False, f"Error: {str(e)}"

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

# --- UI LAYOUT ---
st.title("📈 Post-IPO Catalyst & Flow Tracker")
st.markdown("Predictive Index Inclusion & IPO Lock-up Mapping")

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
            status_badge = "🟢 Mature Company" if is_mature else "🔵 Recent IPO"

            # Top Row: Info & Prices
            col1, col2 = st.columns([1, 1.5])
            
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
                
                m1, m2 = st.columns(2)
                m3, m4 = st.columns(2)
                
                m1.metric("Current Price", f"${cp:.2f}" if cp else "N/A", f"{cp - pc:+.2f}" if cp and pc else None)
                m2.metric("Previous Close", f"${pc:.2f}" if pc else "N/A")
                m3.metric("YTD Return", ytd)
                m4.metric("1-Year Return", oyr)

            st.divider()

            # Middle Row: Deadlines
            st.subheader("🗓️ Mechanical & Regulatory Deadlines")
            deadlines = tracker.get_mechanical_deadlines()
            
            d_cols = st.columns(3)
            for idx, (event, date) in enumerate(deadlines.items()):
                passed = date < datetime.now().date()
                status = "PASSED" if passed else "UPCOMING"
                color = "grey" if passed else "green"
                
                with d_cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{event}</div>
                        <div class="metric-value">{date.strftime('%b %d, %Y')}</div>
                        <div style="color: {color}; font-size: 12px; font-weight: bold; margin-top: 5px;">{status}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()

            # Bottom Row: Index Logic
            if is_mature:
                st.subheader("🏦 Top Passive Institutional Holders")
                st.info(f"💡 {tracker.ticker} has been public for >1 year. Mechanical lock-ups are irrelevant. The funds listed below control the daily passive flows.")
                
                funds = tracker.stock.mutualfund_holders
                if funds is not None and not funds.empty:
                    funds_clean = funds.head(5)[['Holder', 'pctHeld']]
                    funds_clean['pctHeld'] = (funds_clean['pctHeld'] * 100).round(2).astype(str) + '%'
                    funds_clean.columns = ['Fund Name', '% of Float Owned']
                    st.table(funds_clean)
                else:
                    st.warning("Fund data temporarily unavailable.")
            else:
                st.subheader("🎯 Predictive Index Inclusion Targets")
                
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
