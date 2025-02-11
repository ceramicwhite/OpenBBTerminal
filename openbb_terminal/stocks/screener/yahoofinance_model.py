"""Yahoo Finance Model"""
__docformat__ = "numpy"
import configparser
import datetime
import logging
from pathlib import Path
import random

import numpy as np
import pandas as pd
import yfinance as yf
from finvizfinance.screener import ticker
from pandas.plotting import register_matplotlib_converters
from sklearn.preprocessing import MinMaxScaler


from openbb_terminal.decorators import log_start_end

from openbb_terminal.core.config.paths import USER_PRESETS_DIRECTORY
from openbb_terminal.rich_config import console
from openbb_terminal.stocks.screener import finviz_model

logger = logging.getLogger(__name__)

register_matplotlib_converters()

PRESETS_PATH = USER_PRESETS_DIRECTORY / "stocks" / "screener"
PRESETS_PATH_DEFAULT = Path(__file__).parent / "presets"
preset_choices = {
    filepath.name: filepath
    for filepath in PRESETS_PATH.iterdir()
    if filepath.suffix == ".ini"
}
preset_choices.update(
    {
        filepath.name: filepath
        for filepath in PRESETS_PATH_DEFAULT.iterdir()
        if filepath.suffix == ".ini"
    }
)

d_candle_types = {
    "o": "Open",
    "h": "High",
    "l": "Low",
    "c": "Close",
    "a": "Adj Close",
}


@log_start_end(log=logger)
def historical(
    preset_loaded: str = "top_gainers",
    limit: int = 10,
    start_date: str = (
        datetime.datetime.now() - datetime.timedelta(days=6 * 30)
    ).strftime("%Y-%m-%d"),
    type_candle: str = "a",
    normalize: bool = True,
):
    """View historical price of stocks that meet preset

    Parameters
    ----------
    preset_loaded: str
        Preset loaded to filter for tickers
    limit: int
        Number of stocks to display
    start_date: str
        Start date to display historical data, in YYYY-MM-DD format
    type_candle: str
        Type of candle to display
    normalize : bool
        Boolean to normalize all stock prices using MinMax

    Returns
    -------
    pd.DataFrame
        Dataframe of the screener
    list[str]
        List of stocks
    bool
        Whether some random stock selection due to limitations
    """
    screen = ticker.Ticker()
    if preset_loaded in finviz_model.d_signals:
        screen.set_filter(signal=finviz_model.d_signals[preset_loaded])

    else:
        preset_filter = configparser.RawConfigParser()
        preset_filter.optionxform = str  # type: ignore
        preset_filter.read(preset_choices[preset_loaded])

        d_general = preset_filter["General"]
        d_filters = {
            **preset_filter["Descriptive"],
            **preset_filter["Fundamental"],
            **preset_filter["Technical"],
        }

        d_filters = {k: v for k, v in d_filters.items() if v}

        if "Signal" in d_general and d_general["Signal"]:
            screen.set_filter(filters_dict=d_filters, signal=d_general["Signal"])
        else:
            screen.set_filter(filters_dict=d_filters)

    l_stocks = screen.screener_view(verbose=0)
    limit_random_stocks = False

    df_screener = pd.DataFrame()

    if l_stocks:
        if len(l_stocks) > limit:
            random.shuffle(l_stocks)
            l_stocks = sorted(l_stocks[:limit])
            console.print(
                "\nThe limit of stocks to compare with are 10. Hence, 10 random similar stocks will be displayed.",
                f"\nThe selected list will be: {', '.join(l_stocks)}",
            )
            limit_random_stocks = True

        df_screener = yf.download(
            l_stocks, start=start_date, progress=False, threads=False
        )[d_candle_types[type_candle]][l_stocks]
        df_screener = df_screener[l_stocks]

        if np.any(df_screener.isna()):
            nan_tickers = df_screener.columns[df_screener.isna().sum() >= 1].to_list()
            console.print(
                f"NaN values found in: {', '.join(nan_tickers)}.  Replacing with zeros."
            )
            df_screener = df_screener.fillna(0)

        # This puts everything on 0-1 scale for visualizing
        if normalize:
            mm_scale = MinMaxScaler()
            df_screener = pd.DataFrame(
                mm_scale.fit_transform(df_screener),
                columns=df_screener.columns,
                index=df_screener.index,
            )

    return df_screener, l_stocks, limit_random_stocks
