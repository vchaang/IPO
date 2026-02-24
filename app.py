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
    .pos-return { color: #5C946E !important; }
    .neg-return { color: #C96464 !important; }
    h1, h2, h3 { font-weight: 400 !important; letter-spacing: -0.5px; }
</style>
""", unsafe_allow_html=True)

# --- CACHED DATA FETCHING ---
# The @st.cache_data decorator saves the result for 1 hour (3600 seconds).
# This prevents Yahoo from blocking the app due to too many requests!
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    
    # 1. Fetch History (Our primary source of truth)
    hist_max = stock.history(period="max")
    if hist_max.empty:
        return False, f"No trading data found for {ticker}.", None, None, None, None
        
    ipo_date = hist_max.index.min().date()
    
    # 2. Fetch Info (Silently catch rate limits)
    try:
        stock_info = stock.info or {}
    except:
        stock_info = {}
        
    # 3. Fetch Fast Info for backup Market Cap
    try:
        fast_mcap = stock.fast_info.get('marketCap', 0)
    except:
        fast_mcap = 0
        
    return True, "Success", hist_max, stock_info, ipo_date, fast_mcap

@st.cache_data(ttl=86400, show_spinner=False) # Cache funds for 24 hours
def fetch_funds(ticker):
    try:
        return yf.Ticker(ticker).mutualfund_holders
    except:
        return None

# --- METRICS CALCULATOR ---
def calculate_metrics(hist_max):
    current_year = datetime.now().year
    if hist_max is None or hist_max.empty:
        return 0, 0, "N/A", "N/A"
        
    current_price = hist_max['Close'].iloc[-1]
    prev_close = hist_max['Close'].iloc[-2] if len(hist_max) > 1 else current_price
    
    # YTD
    ytd_data = hist_max[hist_max.index.year == current_year]
    if not ytd_data.empty:
        first_ytd = ytd_data['Close'].iloc[0]
        ytd_val = ((current_price - first_ytd) / first_ytd) * 100
        ytd_return = f"{ytd_val:+.2f}%"
    else:
        ytd_return = "N/A"
        
    # 1-Year
    one_year_ago = pd.Timestamp.now(tz=hist_max.index.tz) - pd.Timedelta(days=365)
    past_data = hist_max[hist_max.index <= one_year_ago]
    
    if not past_data.empty:
        first_1y = past_data['Close'].iloc[-1]
        one_yr_val = ((current_price - first_1y) / first_1y) * 100
        one_yr_return = f"{one_yr_val:+.2f}%" if len(hist_max) >= 250 else f"{one_yr_val:+.2f}% (Since IPO)"
    else:
        first_ipo = hist_max['Close'].iloc[0]
        one_yr_val = ((current_price - first_ipo) / first_ipo) * 100
        one_yr_return = f"{one_yr_val:+.2f}% (Since IPO)"

    return current_price, prev_close, ytd_return, one_yr_return

# --- UI LAYOUT ---
st.title("Post-IPO Catalyst & Flow Tracker")
st.markdown("<p style='color: #888; font-size: 16px; font-weight: 300;'>Predictive Index Inclusion & IPO Lock-up Mapping</p>", unsafe_allow_html=True)
st.write("")

# Inputs
col_search, col_override = st.columns([2, 1])
with col_search:
    ticker_input = st.text_input("Enter Ticker (e.g. EIKN, ARM, AAPL)", "")
with col_override:
    sector_override = st.selectbox(
        "Sector (Use if Auto-Detect fails)", 
        ["Auto-Detect", "Healthcare / Biotech", "Technology / Growth", "Other"]
    )

if ticker_input:
    ticker = ticker_input.upper().strip()
    with st.spinner(f"Pulling optimized market data for {ticker}..."):
        
        # Call our new, super-fast cached functions!
        success, msg, hist_max, stock_info, ipo_date, fast_mcap = fetch_stock_data(ticker)
        
        if not success:
            st.error(msg)
        else:
            # Profile Data
            sector = stock_info.get('sector', 'Unknown')
            industry = stock_info.get('industry', 'Unknown')
            
            display_sector = sector
            if sector == 'Unknown' and sector_override != "Auto-Detect":
                display_sector = f"Manual: {sector_override}"
            
            mcap = stock_info.get('marketCap', fast_mcap)
            mcap_str = f"${mcap / 1e9:.2f}B" if mcap else "Unknown"
            
            days_public = (datetime.now().date() - ipo_date).days
            is_mature = days_public > 365
            status_badge = "Mature Company" if is_mature else "Recent IPO"

            st.write("---")
            
            # Top Row: Info & Prices
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader(f"{ticker} Profile")
                st.caption(stock_info.get('shortName', 'Company Name'))
                st.markdown(f"**Status:** {status_badge}")
                st.markdown(f"**Sector:** {display_sector}")
                st.markdown(f"**Industry:** {industry}")
                st.markdown(f"**Est. Market Cap:** {mcap_str}")
                
            with col2:
                st.subheader("Price & Performance")
                cp, pc, ytd, oyr = calculate_metrics(hist_max)
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Current Price", f"${cp:.2f}" if cp else "N/A", f"{cp - pc:+.2f}" if cp and pc else None)
                m2.metric("Previous Close", f"${pc:.2f}" if pc else "N/A")
                m3.metric("YTD Return", ytd)
                m4.metric("1-Year Return", oyr)

            st.write("---")

            # Middle Row: Deadlines
            st.subheader("Mechanical & Regulatory Deadlines")
            st.write("")
            
            deadlines = {
                "IPO Pricing / First Trade": ipo_date,
                "Quiet Period (T+25)": ipo_date + timedelta(days=25),
                "Lock-Up Expiry (T+180)": ipo_date + timedelta(days=180)
            }
            
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
                st.markdown(f"<p style='color: #888; font-size: 14px;'>{ticker} has been public for >1 year. Mechanical lock-ups are irrelevant. The funds listed below control the daily passive flows.</p>", unsafe_allow_html=True)
                
                # Fetch cached funds
                funds = fetch_funds(ticker)
                
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
                ipo_month = ipo_date.month
                
                if ipo_month <= 4: 
                    inclusions.append({"Index": "Russell 2000/3000", "Target": "Late June", "Prob": "High", "Rationale": "Eligible for the June Reconstitution."})
                elif ipo_month <= 10: 
                    inclusions.append({"Index": "Russell 2000/3000", "Target": "Dec 11", "Prob": "High", "Rationale": "Eligible for the December Semi-Annual Reconstitution."})
                
                inclusions.append({"Index": "CRSP US Total Market (VTI)", "Target": "Next Quarterly Rebalance", "Prob": "High", "Rationale": "Quarterly rebalance inclusion."})
                inclusions.append({"Index": "MSCI USA IMI", "Target": "Next Index Review", "Prob": "High" if mcap >= 1e9 else "Medium", "Rationale": "Quarterly/Semi-Annual reviews based on liquidity/cap."})
                inclusions.append({"Index": "S&P Composite 1500", "Target": f"After {(ipo_date + timedelta(days=365)).strftime('%b %Y')}", "Prob": "Low", "Rationale": "Requires 12 months seasoning + GAAP profitability."})
                
                is_biotech = False
                is_tech = False
                
                if sector_override == "Healthcare / Biotech":
                    is_biotech = True
                elif sector_override == "Technology / Growth":
                    is_tech = True
                elif sector_override == "Auto-Detect":
                    is_biotech = sector == 'Healthcare' or 'Biotech' in industry or 'Pharmaceutical' in industry
                    is_tech = sector in ['Technology', 'Communication Services', 'Consumer Discretionary']

                if is_biotech:
                    inclusions.append({"Index": "S&P Biotech (XBI)", "Target": "Next Quarterly Rebalance", "Prob": "High", "Rationale": "Requires 1-2 months seasoning."})
                    inclusions.append({"Index": "Nasdaq Biotech (NBI)", "Target": "December (Annual)", "Prob": "High", "Rationale": "Annual December reconstitution."})
                elif is_tech or (not is_biotech and sector_override == "Auto-Detect"):
                    inclusions.append({"Index": "Nasdaq 100 (QQQ)", "Target": "Standard or Fast Entry (15 Days)", "Prob": "Varies", "Rationale": "Standard requires 3mo seasoning. Mega-caps fast-track in 15 days."})

                st.table(pd.DataFrame(inclusions))
