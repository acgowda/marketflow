# imports
import yfinance as yf
import pandas as pd
import numpy as np
import zipfile
import pickle
from sklearn.preprocessing import StandardScaler

# get most recent list of SP500 tickers
def get_sp500_tickers():
    """
    Returns a data frame of the most recent
    S&P 500 tickers from the Wikipedia page
    on the S&P 500 Index

    Also saves a pickle file of the tickers for future use
    """
    tickers = pd.read_html(
      'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol']

    with open('sp500_tickers','wb') as f:
      pickle.dump(tickers,f)
    return tickers

def remove_inf(df):
    """
    Removes negative and positive infinities from our dataframe
    by replacing them with the minimum and maximum values from the column
    they are located in
    """
    # replace any infinite values with respective
    # max or min value of each column
    for col in df.columns:
        # indices where positive infinities are located
        p_ind = df[df[col]==np.inf].index
        # indices where negative infinities are located
        n_ind = df[df[col]==-np.inf].index
        # replacing the positive and negative infinities
        if len(p_ind) > 0:
          df[col].replace(np.inf,max(df[col].drop(p_ind,axis = 0)))
        if len(n_ind) > 0:
          df[col].replace(-np.inf,min(df[col].drop(n_ind,axis = 0)))
    return df

def create_target(df):
    """
    Used to create the target variable, which indicates
    if a stock will be up or down the next day
    """
    df = df.copy()
    df['close'] = df['close'].pct_change()
    df.dropna(inplace = True) #drop nan
    df['close'] = df['close'].apply(lambda x: 1 if x > 0 else 0)
    df['close'] = df['close'].shift(-1)

    return df

def get_index_data(indices = ["^GSPC","^VIX"],period = '5y'):
    """
    Obtain index data for our training dataset.

    Index data represents all other column-wise data
    that we will use to train our model.

    In this case, we used the following financial indices
    to train our model:
    ['^GSPC','^VIX']
    """

    main_df = pd.DataFrame()
    scaler = StandardScaler()
    for ind in indices:
        # read in a specific indices' historical financial information
        df = yf.Ticker(ind).history(period=period)

        # drop whichever columns work
        try:
          df.drop(['Dividends','Stock Splits','Open','Low','High'],axis = 1,inplace = True)
        except:
          df.drop(['Open','Low','High'],axis = 1,inplace = True)

        # lowercase the columns and label them
        for col in df.columns:
          df.rename(columns = {col:f'{ind}-{col.lower()}'},inplace = True)

        # create moving average columns
        df[f'{ind}-ma5'] = df[f'{ind}-close'].rolling(window=5).mean()
        df[f'{ind}-ma20'] = df[f'{ind}-close'].rolling(window=20).mean()
        df[f'{ind}-ma60'] = df[f'{ind}-close'].rolling(window=60).mean()
        df[f'{ind}-ma200'] = df[f'{ind}-close'].rolling(window=200).mean()

        # normalise values in our indices' dataframe & fill NAs
        cols = list(df.columns)
        i_ind = df.index
        df = pd.DataFrame(scaler.fit_transform(df),index = i_ind)
        df.columns = cols
        df.fillna(method = 'ffill')

        df = remove_inf(df)

        # add this data to our final df
        if main_df.empty:
          main_df = df
        else:
          main_df = pd.concat([main_df,df],axis = 1)
    return main_df

def compile_normalise_data(tickers,indices = ["^GSPC","^VIX"],period = '5y'):
    """
    Compile all of the data
    we will use to train our model
    """
    main_df = pd.DataFrame() # our final dataframe
    count = 0 # keep track of progress
    scaler = StandardScaler() # for scaling our data

    # get extra financial information we want to use
    # in making predictions
    index_df = get_index_data(indices,period)

    for ticker in tickers:
        try:
          # yahoo finance doesn't like '.' full stops, and prefers '-' dashes
          ticker = ticker.replace('.', '-')
          # read in a specific ticker's historical financial information
          df = yf.Ticker(ticker).history(period = period)
          # drop columns we won't be using from that dataframe
          df.drop(['Dividends','Stock Splits'],axis = 1,inplace = True)

          # make column names lower cased, because it's easier to type
          for col in df.columns:
            df.rename(columns = {col:col.lower()},inplace = True)

          # add a few rolling window columns on our closing price
          df['ma5'] = df['close'].rolling(window=5).mean()
          df['ma20'] = df['close'].rolling(window=20).mean()
          df['ma60'] = df['close'].rolling(window=60).mean()
          df['ma200'] = df['close'].rolling(window=200).mean()

          # normalise all columns except for the
          # column containing our closing price
          y = df['close']
          X = df.drop(['close'],axis = 1)
          cols = list(X.columns)
          X = pd.DataFrame(scaler.fit_transform(X),index = y.index)
          df = pd.concat([y,X],axis = 1)
          df.columns = ['close'] + cols

          # fill foward missing values just in case any came up
          df.fillna(method = 'ffill')

          df = remove_inf(df) # remove inf values

          # get day of week; 0 = Monday, ..., so on so forth
          # as a column
          df['day'] = list(pd.Series(df.index).apply(lambda x: str(x.weekday())))

          # get month of year as a column
          df['month'] = list(pd.Series(df.index).apply(lambda x: str(x.month)))

          # convert categorical data to dummy variables
          df = pd.get_dummies(df)

          # merge the extra financial info along the column-axis
          df = pd.concat([df,index_df], axis=1, ignore_index=False)

          # make our target variable
          df = create_target(df)

          # remove NaNs
          df.dropna(inplace = True)

          # add this data to our final df
          if main_df.empty:
            main_df = df
          else:
            main_df = pd.concat([main_df,df],axis = 0)

          # progress counting
          count +=1 # increment for every stock addded
          if count % 50 == 0: # will let us know progress for every 50 stocks added
              print(f'Progress: {count}/{len(tickers)}')
        except:
          continue
    # drop any NaNs
    main_df = main_df.dropna(axis = 0)

    # we know that the ^VIX-volume column is always going to
    # be uninformative
    main_df.drop(['^VIX-volume'],axis = 1,inplace = True)
    # return df
    return main_df

def get_input_data(tickers,indices = ["^GSPC","^VIX"],period = '5y'):
    """
    Gets the data we need for model training or testing;
    Ensures that the dataset has equal number of buy/sell signals
    in it, so that our model training and testing process won't
    be biased

    Indices will default to "^GSPC","^VIX" which
    represent the S&P500 index and VIX index on
    yahoo finance, respectively

    Use these dates to replicate our training set
    start = '2017-01-01'
    end = '2022-05-12'
    """
    df = compile_normalise_data(tickers,indices = ["^GSPC","^VIX"],period = '5y')

    # obtain whichever is lower: the number of buy signals (1)
    # or the number of sell signals (0)
    lower = min(len(df.loc[df['close'] == 1]), len(df.loc[df['close'] == 0]))

    # get dataframes of buys and sells which have the same number
    # of buy and sell signals
    # and combine them into a single dataframe
    buys_df = df.loc[df['close'] == 1].sample(frac=lower/len(df.loc[df['close'] == 1]))
    sells_df = df.loc[df['close'] == 0].sample(frac=lower/len(df.loc[df['close'] == 0]))
    df_new = pd.concat([buys_df,sells_df],axis = 0)

    # shuffle the data
    df_new = df_new.sample(frac = 1)

    return df_new

def get_preds_data(ticker,indices = ["^GSPC","^VIX"],period = '2y'):
    """
    Get data which we will use our model to make predictions on
    """

    df = yf.Ticker(ticker).history(period = period)
    index_df = get_index_data(indices,period)
    scaler = StandardScaler()

    # drop columns we won't be using from that dataframe
    df.drop(['Dividends','Stock Splits'],axis = 1,inplace = True)
    # make column names lower cased, because it's easier to type
    for col in df.columns:
      df.rename(columns = {col:col.lower()},inplace = True)

    # add a few rolling window columns on our closing price
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma200'] = df['close'].rolling(window=200).mean()

    # normalise all columns except for the
    # column containing our closing price
    y = df['close']
    X = df.drop(['close'],axis = 1)
    cols = list(X.columns)
    X = pd.DataFrame(scaler.fit_transform(X),index = y.index)
    df = pd.concat([y,X],axis = 1)
    df.columns = ['close'] + cols

    # fill foward missing values just in case any came up
    df.fillna(method = 'ffill')

    df = remove_inf(df) # remove inf values

    # get day of week; 0 = Monday, ..., so on so forth
    # as a column
    df['day'] = list(pd.Series(df.index).apply(lambda x: str(x.weekday())))

    # get month of year as a column
    df['month'] = list(pd.Series(df.index).apply(lambda x: str(x.month)))

    # convert categorical data to dummy variables
    df = pd.get_dummies(df)

    # merge the extra financial info along the column-axis
    df = pd.concat([df,index_df], axis=1, ignore_index=False)

    df.drop(['^VIX-volume'],axis = 1,inplace = True)
    # print(df['close'].pct_change())
    # prediction_row = df.drop(['close'],axis = 1).iloc[len(df['close'])-1]

    df_new = create_target(df)

    return df_new