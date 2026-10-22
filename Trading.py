import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


def get_stock_data(ticker, period="5y"):
    stock = yf.Ticker(ticker)
    return stock.history(period=period)


def calculate_moving_averages(data):
    data["MA50"] = data["Close"].rolling(window=50).mean()
    data["MA200"] = data["Close"].rolling(window=200).mean()
    return data


def identify_golden_cross(data):
    data["Signal"] = 0
    data["GoldenCross"] = (data["MA50"] > data["MA200"]) & (
        data["MA50"].shift(1) <= data["MA200"].shift(1)
    )
    return data


def implement_strategy(data):
    if data.empty:
        return pd.DataFrame(
            columns=[
                "BuyDate",
                "BuyPrice",
                "SellDate",
                "SellPrice",
                "HoldingDays",
                "ProfitPct",
                "SellReason",
            ]
        )

    positions = []
    data = data.iloc[200:].copy()
    buy_dates = data[data["GoldenCross"]].index.tolist()

    for buy_date in buy_dates:
        buy_price = data.loc[buy_date, "Close"]
        target_price = buy_price * 1.15
        max_sell_date = buy_date + pd.Timedelta(days=60)
        sell_period = data.loc[buy_date:max_sell_date].copy()
        target_reached = sell_period[sell_period["Close"] >= target_price]

        if not target_reached.empty:
            sell_date = target_reached.index[0]
            sell_price = target_reached.loc[sell_date, "Close"]
            sell_reason = "Target reached"
        else:
            sell_date_candidates = sell_period.index.tolist()
            if not sell_date_candidates:
                continue
            sell_date = sell_date_candidates[-1]
            sell_price = data.loc[sell_date, "Close"]
            sell_reason = "Max holding period"

        positions.append(
            {
                "BuyDate": buy_date,
                "BuyPrice": buy_price,
                "SellDate": sell_date,
                "SellPrice": sell_price,
                "HoldingDays": (sell_date - buy_date).days,
                "ProfitPct": (sell_price / buy_price - 1) * 100,
                "SellReason": sell_reason,
            }
        )

    return pd.DataFrame(
        positions,
        columns=[
            "BuyDate",
            "BuyPrice",
            "SellDate",
            "SellPrice",
            "HoldingDays",
            "ProfitPct",
            "SellReason",
        ],
    )


def analyze_results(positions):
    if positions.empty:
        print("No trading signals detected")
        return positions

    total_trades = len(positions)
    winning_trades = positions[positions["ProfitPct"] > 0]
    win_rate = len(winning_trades) / total_trades * 100
    print("\n===== Trading Strategy Results (Golden Cross) =====")
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {len(winning_trades)} ({win_rate:.2f}%)")
    print(f"Losing Trades: {total_trades - len(winning_trades)}")
    print(f"Average Profit: {positions['ProfitPct'].mean():.2f}%")
    return positions


@st.cache_data(ttl=3600)
def load_strategy_results(ticker, period):
    data = get_stock_data(ticker, period)
    if data.empty:
        return data, implement_strategy(data)

    data = calculate_moving_averages(data)
    data = identify_golden_cross(data)
    return data, implement_strategy(data)


def create_price_chart(data, positions):
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=data.index,
            y=data["Close"],
            mode="lines",
            name="Close",
            line={"color": "#2563eb", "width": 2},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data.index,
            y=data["MA50"],
            mode="lines",
            name="50-day MA",
            line={"color": "#f59e0b", "width": 1.5},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data.index,
            y=data["MA200"],
            mode="lines",
            name="200-day MA",
            line={"color": "#8b5cf6", "width": 1.5},
        )
    )

    if not positions.empty:
        figure.add_trace(
            go.Scatter(
                x=positions["BuyDate"],
                y=positions["BuyPrice"],
                mode="markers",
                name="Buy",
                marker={"color": "#16a34a", "size": 10, "symbol": "circle"},
                hovertemplate="Buy<br>%{x|%Y-%m-%d}<br>$%{y:.2f}<extra></extra>",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=positions["SellDate"],
                y=positions["SellPrice"],
                mode="markers",
                name="Sell",
                marker={"color": "#dc2626", "size": 10, "symbol": "circle"},
                hovertemplate="Sell<br>%{x|%Y-%m-%d}<br>$%{y:.2f}<extra></extra>",
            )
        )

    figure.update_layout(
        title="Price and moving averages",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"l": 20, "r": 20, "t": 70, "b": 20},
    )
    return figure


def show_trade_statistics(positions):
    if positions.empty:
        st.info("No trades were generated for this period.")
        return

    winners = positions[positions["ProfitPct"] > 0]
    losers = positions[positions["ProfitPct"] <= 0]
    win_rate = len(winners) / len(positions) * 100
    target_exits = (positions["SellReason"] == "Target reached").sum()
    timed_exits = (positions["SellReason"] == "Max holding period").sum()

    first_row = st.columns(4)
    first_row[0].metric("Total trades", f"{len(positions)}")
    first_row[1].metric("Winning trades", f"{len(winners)}")
    first_row[2].metric("Losing trades", f"{len(losers)}")
    first_row[3].metric("Win rate", f"{win_rate:.1f}%")

    second_row = st.columns(4)
    second_row[0].metric("Average trade return", f"{positions['ProfitPct'].mean():.2f}%")
    average_win = f"{winners['ProfitPct'].mean():.2f}%" if not winners.empty else "—"
    average_loss = f"{losers['ProfitPct'].mean():.2f}%" if not losers.empty else "—"
    second_row[1].metric("Average winning return", average_win)
    second_row[2].metric("Average losing return", average_loss)
    second_row[3].metric("Average holding period", f"{positions['HoldingDays'].mean():.1f} days")

    st.subheader("Exit reasons")
    st.write(
        f"Target reached: **{target_exits}** · "
        f"Maximum holding period: **{timed_exits}**"
    )
    st.caption(
        "Returns are calculated per trade before fees and taxes. "
        "They are not a portfolio-level return."
    )


def show_detailed_trades(positions):
    if positions.empty:
        st.info("No trades were generated for this period.")
        return

    trades = positions.copy()
    trades["BuyDate"] = pd.to_datetime(trades["BuyDate"]).dt.strftime("%Y-%m-%d")
    trades["SellDate"] = pd.to_datetime(trades["SellDate"]).dt.strftime("%Y-%m-%d")
    st.dataframe(
        trades,
        use_container_width=True,
        hide_index=True,
        column_config={
            "BuyDate": "Buy date",
            "BuyPrice": st.column_config.NumberColumn("Buy price", format="$%.2f"),
            "SellDate": "Sell date",
            "SellPrice": st.column_config.NumberColumn("Sell price", format="$%.2f"),
            "HoldingDays": st.column_config.NumberColumn("Holding days", format="%d"),
            "ProfitPct": st.column_config.NumberColumn("Return", format="%.2f%%"),
            "SellReason": "Exit reason",
        },
    )


def run_app():
    st.set_page_config(page_title="Trading Strategy Results", page_icon="📈", layout="wide")
    st.title("Trading Strategy Results")
    st.sidebar.header("Settings")
    ticker = st.sidebar.text_input("Stock ticker", value="MSFT").strip().upper()
    period = st.sidebar.selectbox("History period", ["1y", "2y", "5y", "10y", "max"], index=2)
    page = st.sidebar.radio(
        "View",
        ["Price chart", "Trade statistics", "Detailed trades"],
    )

    if not ticker:
        st.warning("Enter a stock ticker to view results.")
        return

    data, positions = load_strategy_results(ticker, period)
    if data.empty:
        st.error(f"No price data was returned for {ticker}. Check the ticker and try again.")
        return

    st.caption(f"{ticker} · {period} of available price history")
    if page == "Price chart":
        st.plotly_chart(create_price_chart(data, positions), use_container_width=True)
        st.caption("Green dots mark buys; red dots mark sells.")
    elif page == "Trade statistics":
        st.header("Overall trade statistics")
        show_trade_statistics(positions)
    else:
        st.header("Detailed trades")
        show_detailed_trades(positions)


def main():
    _, positions = load_strategy_results("MSFT", "5y")
    analyze_results(positions)
    return positions


if __name__ == "__main__":
    run_app()
