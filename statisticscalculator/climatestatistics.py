import scipy.integrate as integrate
# from scipy.stats import kendalltau
from statsmodels.tsa.seasonal import STL
# from pymannkendall import seasonal_test
from pymannkendall import original_test
from statisticscalculator.generalstatistics import GeneralStatistics
import pandas as pd
from functools import reduce

class Streamflow(GeneralStatistics):
    def __init__(self, Dataloader):
        super().__init__(Dataloader)
        self.data_loader=Dataloader
        
    def calc_annual_runoff_threshold_day(self, percent=0.5, alpha=0.10):

        '''Calculates the total volume and then returns date when specified percent of that total volume is reached.'''

        self._percent = percent
        yearly_volume_dfs = {}
        yearly_volume_statistics = {}
        for wy in self._df['Water Year'].unique():           
            volume_df = pd.DataFrame()
            volume_df['values'] = self._df[self._df['Water Year']==wy][self.data_loader._name_of_Q_column]
            volume_df['WY_Date'] = self._df[self._df['Water Year']==wy]['WY_Date']
            volume_df['daily_volume_ksfd'] = volume_df['values'] * 86.4 #(86400s/day to convert to daily volume and then divide by 1000 to get ksfd) 
            volume_df['cumsum_volume_ksfd'] = volume_df['daily_volume_ksfd'].cumsum()
            volume_df['daily_volume_maf'] = volume_df['values'] / 43560 #1cfs=1.983471acft; which is the same as 1af=43,560ft^3.  See google keep notes for extra info on how to convert.
            volume_df['cumsum_volume_maf'] = volume_df['daily_volume_maf'].cumsum()            
#             print(volume_df)                  
            total_volume = volume_df['daily_volume_maf'].sum()
            wy_dates = self._df[self._df['Water Year']==wy]['WY_Date']
            volume_point_date = wy_dates[volume_df['cumsum_volume_maf']>= percent * total_volume].iloc[0]

            wy_doy = self._df[self._df['Water Year']==wy]['dayofyear']
            volume_point_doy = wy_doy[volume_df['cumsum_volume_maf']>= percent * total_volume].iloc[0]

#             tau, p_value = kendalltau(volume_df['WY_Date'], volume_df['values'])
#             df_for_mk_test = volume_df[['WY_Date']] #, 'values']]
#             df_for_mk_test['WY_Date'].astype(int) #need convert date to integer for test to work.
#             smk = seasonal_test(df_for_mk_test, alpha=0.05, period=12)
            yearly_volume_dfs[wy] = volume_df
            yearly_volume_statistics[wy] = {'total_volume': total_volume, 
                                            f'{percent*100}%_volume': total_volume * percent, 
                                            f'{percent*100}%_volume_point_date': volume_point_date,
                                            # f'{percent*100}%_volume_point_dayofyear': volume_point_doy
                                            }

        self.threshold_vol_stats = pd.DataFrame(yearly_volume_statistics).T
        self.threshold_vol_stats[f'{percent*100}%_volume_point_day_of_yr'] = \
            self.threshold_vol_stats[f'{percent*100}%_volume_point_date'].apply(lambda x: x.strftime('%m-%d'))
            # self.threshold_vol_stats[f'{percent*100}%_volume_point_date'] = pd.to_datetime(self.threshold_vol_stats[f'{percent*100}%_volume_point_date']).dt.strftime('%m-%d')     
        self.threshold_vol_stats['50%_volume_point_month_day'] = pd.to_datetime(self.threshold_vol_stats[f'{percent*100}%_volume_point_date']).dt.strftime('%b %d')     
        # self.threshold_vol_stats = yearly_volume_dfs

        self.threshold_vol_mann_kendall_test = original_test(self.threshold_vol_stats[f'{percent*100}%_volume'], alpha=alpha)
        self.threshold_vol_dates_mann_kendall_test = original_test(self.threshold_vol_stats[f'{percent*100}%_volume_point_date'].apply(lambda dt: dt.timetuple().tm_yday), alpha=alpha)        
        self.total_volume_mann_kendall_test = original_test(self.threshold_vol_stats['total_volume'])


    def calc_runoff_bw_days(self, begin_month_day='09-25', end_month_day='09-28', alpha=0.10):

        '''Calculates the runoff between two dates for every year in the data set.  Intended to be used to calculate the summertime (or whatever period) volumes of a stream 
        which then trend in volume can be determined for that period.'''

        self.begin_month_day = begin_month_day
        self.end_month_day = end_month_day
        volume_dfs = {}
        volume_bw_days_dict = {}
        for wy in self._df['Water Year'].unique():           
            #filter df by wy and month_day range:
            filtered_vol_df = self._df[self._df['Water Year']==wy]
            # print(wy)
            # print(filtered_vol_df.head(2))
            filtered_vol_df = filtered_vol_df[filtered_vol_df['month-day'].between(begin_month_day, end_month_day)][['month-day', self.data_loader._name_of_Q_column]].set_index('month-day')

            #convert cfs to a daily value (ft^3/d)...actually maf would be better:
            # 1 Cubic Feet Per Second to Million Acre-feet Per Year = 0.0007 https://www.kylesconverter.com/flow/cubic-feet-per-second-to-million-acre--feet-per-year
            filtered_vol_df['daily_volume_ksfd'] = filtered_vol_df[self.data_loader._name_of_Q_column] * 86.4 #(86400s/day to convert to daily volume and then divide by 1000 to get ksfd) 
            filtered_vol_df['cumsum_volume_ksfd'] = filtered_vol_df['daily_volume_ksfd'].cumsum()
            filtered_vol_df['daily_volume_maf'] = filtered_vol_df[self.data_loader._name_of_Q_column] / 43560 #1cfs=1.983471acft; which is the same as 1af=43,560ft^3.  See google keep notes for extra info on how to convert.
            filtered_vol_df['cumsum_volume_maf'] = filtered_vol_df['daily_volume_maf'].cumsum()
#             print(volume_df)                  
            # volume_bw_days = filtered_vol_df['daily_volume_ksfd'].sum()
            volume_bw_days = filtered_vol_df['daily_volume_maf'].sum()

            # wy_dates = self._df[self._df['Water Year']==wy]['WY_Date']

            volume_dfs[wy] = filtered_vol_df
            volume_bw_days_dict[wy] = volume_bw_days
        
        self.volume_dfs = volume_dfs
        # print(volume_bw_days_dict)
        data = {'Year': list(volume_bw_days_dict.keys()), f'{self.data_loader._name_of_Q_column}':list(volume_bw_days_dict.values())}
        volume_bw_days_df = pd.DataFrame(data)
        volume_bw_days_df.set_index('Year', inplace=True)
        self.volume_bw_days_df=volume_bw_days_df

        self.volume_bw_days_mann_kendall_test = original_test(self.volume_bw_days_df[self.data_loader._name_of_Q_column], alpha=alpha)

    def calc_max(self, calc_from_rolling_median=False, window_size=5,  alpha=0.10, ignore_winter_months=False):
        
        '''Calculates date when peak discharge occurs for each year.'''
        
        max_dfs = []
        for wy in self._df['Water Year'].unique():
            filtered_df = self._df[self._df['Water Year']==wy]

            # if mean:
            rolling_mean_df = pd.DataFrame({'Date': filtered_df['Date'],
                            'month-day': filtered_df['month-day'],
                            'dayofyear': filtered_df['dayofyear'], 
                            'WY_Date': filtered_df['WY_Date'], 
                            'Water Year': filtered_df['Water Year'], 
                            'Calendar Year': filtered_df['Calendar Year'],
                            f'{self.data_loader._name_of_Q_column}': filtered_df[self.data_loader._name_of_Q_column], 
                            'rolling mean max': filtered_df[self.data_loader._name_of_Q_column].rolling(window=window_size).mean()})

            if ignore_winter_months == False:
                wy_max = rolling_mean_df[rolling_mean_df['rolling mean max'] == rolling_mean_df['rolling mean max'].max()]
            else:
                rolling_mean_df = rolling_mean_df[(rolling_mean_df['month-day']>='02-01') & (rolling_mean_df['month-day']>='07-01')]
                wy_max = rolling_mean_df[rolling_mean_df['rolling mean max'] == rolling_mean_df['rolling mean max'].max()]
                wy_max = wy_max[wy_max['month-day']]
            
            max_dfs.append(wy_max)

        self.rolling_yr_maxs = pd.concat(max_dfs, ignore_index=True)
        self.rolling_yr_Qmax_mk_test = original_test(self.rolling_yr_maxs[self.data_loader._name_of_Q_column],  alpha=alpha)
        self.rolling_yr_DOYmax_mk_test = original_test(self.rolling_yr_maxs['dayofyear'],  alpha=alpha)

    def _STL(self):
        self.stl = STL(self.volume_df[['WY_Date', 'values']], seasonal=13)
        self.stl_result = self.stl.fit()
        self.trend = self.stl.trend
        


class Snow(GeneralStatistics):
    def __init__(self, Dataloader):
        super().__init__(Dataloader)
        self.data_loader=Dataloader

    def calc_accumulation_bw_days(self, begin_month_day='10-01', parameter='WTEQ', end_month_day='06-01', alpha=0.10):

        '''Calculates the accumulation (e.g. SWE, Precip) between two dates for every year in the data set.  Trend can then be determined with resulting data.'''

        self.begin_month_day = begin_month_day
        self.end_month_day = end_month_day
        volume_dfs = {}
        volume_bw_days_dict = {}
        for wy in self._df['Water Year'].unique():           
            #filter df by wy and month_day range:
            filtered_accum_df = self._df[self._df['Water Year']==wy]
            # print(wy)
            # print(filtered_vol_df.head(2))
            filtered_accum_df = filtered_accum_df[filtered_accum_df['month-day'].between(begin_month_day, end_month_day)][['month-day', self.data_loader._name_of_Q_column]].set_index('month-day')

            #convert cfs to a daily volume (ft^3/d), which is ksfd
            #to get ksfd multiply by 86400s/day and then divide by 1000, 
            # then divide by 43,560ft^3 to get af (1af=43,560ft^3), 
            # and lastly by 1000000 to get maf
            filtered_accum_df[f'{parameter}_accum'] = filtered_accum_df[self.data_loader._name_of_Q_column] * 86.4 /43560/1000000
            filtered_accum_df['cumsum'] = filtered_accum_df[f'{parameter}_accum'].cumsum()
#             print(volume_df)                  
            volume_bw_days = filtered_accum_df[f'{parameter}_accum'].sum()
            # wy_dates = self._df[self._df['Water Year']==wy]['WY_Date']

            volume_dfs[wy] = filtered_accum_df
            volume_bw_days_dict[wy] = volume_bw_days
        
        self.volume_dfs = volume_dfs
        # print(volume_bw_days_dict)
        data = {'Year': list(volume_bw_days_dict.keys()), f'{self.data_loader._name_of_Q_column}':list(volume_bw_days_dict.values())}
        volume_bw_days_df = pd.DataFrame(data)
        volume_bw_days_df.set_index('Year', inplace=True)
        self.volume_bw_days_df=volume_bw_days_df

        self.volume_bw_days_mann_kendall_test = original_test(self.volume_bw_days_df[self.data_loader._name_of_Q_column], alpha=alpha) 

    def calc_max(self, calc_from_rolling_median=False, window_size=1,  alpha=0.10):
        
        '''Calculates date when peak discharge occurs for each year.  Can calculate from rolling median by setting calc_from_rolling_median=True and setting
        the window_size to the number of days you'd like to be included in the mean calculation.'''
        max_dfs = []
        for wy in self._df['Water Year'].unique():
            filtered_df = self._df[self._df['Water Year']==wy]
            self._filtered_df = filtered_df
            # if mean:
            rolling_mean_df = pd.DataFrame({'Date': filtered_df['Date'],
                            'month-day': filtered_df['month-day'],
                            'dayofyear': filtered_df['dayofyear'], 
                            'WY_Date': filtered_df['WY_Date'], 
                            'Water Year': filtered_df['Water Year'], 
                            'Calendar Year': filtered_df['Calendar Year'],
                            f'{self.data_loader._name_of_Q_column}': filtered_df[self.data_loader._name_of_Q_column], 
                            'rolling mean max': filtered_df[self.data_loader._name_of_Q_column].rolling(window=window_size).mean()})
            wy_max = rolling_mean_df[rolling_mean_df['rolling mean max'] == rolling_mean_df['rolling mean max'].max()]
            
        # max_dfs = []
        # for wy in s._df['Water Year'].unique():
        #     filtered_df = s._df[s._df['Water Year']==wy]
        #     rolling_mean_df = pd.DataFrame({'Date': filtered_df['Date'],
        #                     'month-day': filtered_df['month-day'],
        #                     'dayofyear': filtered_df['dayofyear'],
        #                     'WY_Date': filtered_df['WY_Date'], 
        #                     'Water Year': filtered_df['Water Year'], 
        #                     'Calendar Year': filtered_df['Calendar Year'],
        #                     'WTEQ': filtered_df['WTEQ'], 
        #                     'rolling mean max': filtered_df['WTEQ'].rolling(window=1).mean()})

        #     wy_max = rolling_mean_df[rolling_mean_df['rolling mean max'] == rolling_mean_df['rolling mean max'].max()]

            max_dfs.append(wy_max)

        self.rolling_yr_maxs = pd.concat(max_dfs, ignore_index=True)
        self.rolling_yr_Qmax_mk_test = original_test(self.rolling_yr_maxs[self.data_loader._name_of_Q_column],  alpha=alpha)
        self.rolling_yr_DOYmax_mk_test = original_test(self.rolling_yr_maxs['dayofyear'],  alpha=alpha)