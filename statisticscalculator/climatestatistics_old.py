import scipy.integrate as integrate
# from scipy.stats import kendalltau
from statsmodels.tsa.seasonal import STL
# from pymannkendall import seasonal_test
from pymannkendall import original_test
from statisticscalculator.generalstatistics import GeneralStatistics
import pandas as pd

class Streamflow(GeneralStatistics):
    def __init__(self, Dataloader):
        super().__init__(Dataloader)
        self.data_loader=Dataloader
        yearly_volume_dfs = {}
        yearly_volume_statistics = {}
        
        for wy in self._df['Water Year'].unique():           
            volume_df = pd.DataFrame()
            volume_df['values'] = self._df[self._df['Water Year']==wy][self.data_loader._name_of_Q_column]
            volume_df['WY_Date'] = self._df[self._df['Water Year']==wy]['WY_Date']
            volume_df['daily_volume_ft^3/d'] = volume_df['values'] #* 86400 / 43559.9 #convert ft^3 to af.
            volume_df['cumsum_volume ft^3'] = volume_df['daily_volume_ft^3/d'].cumsum()
#             print(volume_df)                  
            total_volume = volume_df['daily_volume_ft^3/d'].sum()
            wy_dates = self._df[self._df['Water Year']==wy]['WY_Date']
            half_volume_point_date = wy_dates[volume_df['cumsum_volume ft^3']>= 0.5 * total_volume].iloc[0]
#             tau, p_value = kendalltau(volume_df['WY_Date'], volume_df['values'])
#             df_for_mk_test = volume_df[['WY_Date']] #, 'values']]
#             df_for_mk_test['WY_Date'].astype(int) #need convert date to integer for test to work.
#             smk = seasonal_test(df_for_mk_test, alpha=0.05, period=12)
            yearly_volume_dfs[wy] = volume_df
            yearly_volume_statistics[wy] = {'total_volume': total_volume, 
                                            'half_volume': total_volume * 0.5, 
                                            'half_volume_point_date': half_volume_point_date,
#                                             'mann-kendall_tau': tau,
#                                             'mann-kendall_p-value': p_value,
#                                             'seasonal-mann-kendall': {
#                                                 'water_year': wy,
#                                                 'trend': smk.trend,
#                                                 'h': smk.h, #True (if trend is present) or False (if the trend is absence)
#                                                 'p_value': smk.p,
#                                                 'z': smk.z, #normalized test stats
#                                                 'tau': smk.Tau,
#                                                 'Mann-Kendall score': smk.s
#                                              }
                                            }

        self.yearly_volume_statistics = pd.DataFrame(yearly_volume_statistics).T
        # self.yearly_volume_statistics['half_volume_point_date'] = self.yearly_volume_statistics['half_volume_point_date']
        self.yearly_volume_statistics['half_volume_point_day_of_yr'] = self.yearly_volume_statistics['half_volume_point_date'].apply(lambda x: x.strftime('%m-%d'))     
        self.yearly_volume_dfs = yearly_volume_dfs
#         def _to_day_of_year(dt):
#             return dt.timetuple().tm_yday
        self.half_volume_day_mann_kendall_test = original_test(self.yearly_volume_statistics['half_volume_point_date'].apply(lambda dt: dt.timetuple().tm_yday), alpha=0.05)
        self.total_volume_mann_kendall_test = original_test(self.yearly_volume_statistics['total_volume'])

    def _STL(self):
        self.stl = STL(self.volume_df[['WY_Date', 'values']], seasonal=13)
        self.stl_result = self.stl.fit()
        self.trend = self.stl.trend
        
            