import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import datetime

class Plot_Runoff_Threshold_Days():
    def __init__(self, StreamflowClimateStatistics):
        self.vol_stats = StreamflowClimateStatistics.yearly_volume_statistics

    def plot_runoff_threshold_days(self, site_name):
        def _to_day_of_year(dt):
            return dt.timetuple().tm_yday
        x = self.vol_stats.index
#             x = volume_stats_for_vip_sites[12452500].index
#             volume_stats_for_vip_sites[12452500]['half_volume_point_day_of_yr'] = volume_stats_for_vip_sites[12452500]['half_volume_point_date'].apply(_to_day_of_year)
        self.vol_stats['half_volume_point_day_of_yr'] = self.vol_stats['half_volume_point_date'].apply(_to_day_of_year)
        y = self.vol_stats['half_volume_point_day_of_yr']

        fig = go.Figure()
        labels = self.vol_stats['half_volume']
        fig.add_trace(go.Scatter(x=x, y=y,mode='markers'))#, name=self.vol_stats['half_volume_point_date']))
        fig.update_layout(title=site_name)
        self.half_vol_days_fig = fig
        fig.show()

        

class Plot_Runoff_Volume_Between_Days():
    def __init__(self, StreamflowClimateStatistics):
        self.vol_stats = StreamflowClimateStatistics.yearly_volume_statistics

    def plot_runoff_volume_between_days(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.vol_stats.index, y=self.vol_stats['total_volume'], mode='markers'))
        self.total_yearly_vol_fig = fig
        fig.show()


class Plot_Runoff_Threshold():
    def __init__(self, StreamflowClimateStatistics2):
        self.threshold_vol_stats = StreamflowClimateStatistics2.threshold_vol_stats
        self.percent = StreamflowClimateStatistics2._percent

    def plot_runoff_threshold(self, site_name):
        def _to_day_of_year(dt):
            return dt.timetuple().tm_yday
        
        x = self.threshold_vol_stats.index

        self.threshold_vol_stats[f'{self.percent*100}%_volume_point_day_of_yr'] = self.threshold_vol_stats[f'{self.percent*100}%_volume_point_date'].apply(_to_day_of_year)
        y = self.threshold_vol_stats[f'{self.percent*100}%_volume_point_day_of_yr']

        # y = self.threshold_vol_stats[f'{self.percent*100}%_volume_point_date']

        self.threshold_vol_stats[f'{self.percent*100}%_volume_point_month_day'] = pd.to_datetime(self.threshold_vol_stats[f'{self.percent*100}%_volume_point_date']).dt.strftime('%b %d')
        y = self.threshold_vol_stats[f'{self.percent*100}%_volume_point_month_day']
        
        # month_day_category_ordering = np.array(self.threshold_vol_stats[f'{self.percent*100}%_volume_point_month_day'].to_list())
        # x = self.threshold_vol_stats[f'{self.percent*100}%_volume_point_month_day']
        # print(x)
        plt.scatter(x, y,)# s=self.threshold_vol_stats[f'{self.percent*100}%_volume'], alpha=0.5) # c=colors,
        plt.show()


        # ticktext = self.threshold_vol_stats[f'{self.percent*100}%_volume_point_month_day'][0::5]
        
        # days_of_year_first_of_month = {'Jan 1': 1, 'Feb 1': 32, 'Mar 1': 60, 'Apr 1': 91, 'May 1': 121, 'June 1': 152, 
        # 'July 1': 182, 'Aug 1': 213, 'Sep 1': 244, 'Oct 1': 274, 'Nov 1': 305, 'Dec 1': 335}
        



class Plot_Peak_Runoff():
    def __init__(self, StreamflowClimateStatistics2):
        self.peak_runoff = StreamflowClimateStatistics2.rolling_yr_maxs
  
    def plot_peak_runoff(self, site_name):
        self.peak_runoff['month-day'] = pd.to_datetime(self.peak_runoff['month-day'], errors = 'coerce', format='%m-%d')
        try:
            self.peak_runoff['dayofyear']=self.peak_runoff['month-day'].apply(lambda dt: dt.timetuple().tm_yday)      
        except:  #nas will crash plot, so get remove them if they exist 
            print('Found nans in dayofyear column.  Dropping them and retrying.')
            self.peak_runoff['dayofyear']=self.peak_runoff['month-day'].dropna().apply(lambda dt: dt.timetuple().tm_yday)

        y = self.peak_runoff['dayofyear']
        fig = px.scatter(self.peak_runoff, x='Water Year', y=y, 
        trendline='ols', title=f'Days when Peak Runoff Occurred at {site_name}')
        fig.update_xaxes(title_text='Water Year')
        fig.update_layout(
            yaxis=dict(
                    tickmode='array',
                    tickvals=y,
                    ticktext=self.peak_runoff['month-day'].dt.strftime('%b %d')
                    # tickmode='linear',
                    # tickvals=y,
                    # ticktext=[(datetime.datetime(2024,3,1) + datetime.timedelta(days=i)).strftime('%b %d') for i in range(90)]
            )
        )
        fig.update_yaxes(title_text='Day of Year')
        fig.show()




class Plot_Runoff_Volume_Between_2Days():
    def __init__(self, StreamflowClimateStatistics2):
        self.vol_stats = StreamflowClimateStatistics2.volume_bw_days_df
        self._name_of_Q_column = StreamflowClimateStatistics2.data_loader._name_of_Q_column
        self.begin_month_day = StreamflowClimateStatistics2.begin_month_day
        self.end_month_day = StreamflowClimateStatistics2.end_month_day
    def plot_runoff_volume_between_2days(self, site_name):
        # fig = go.Figure()
        # fig.add_trace(go.Scatter(x=self.vol_stats.index, y=self.vol_stats[self._name_of_Q_column], mode='markers', trendline="ols"))
        # fig.update_layout(
        #     title=f'Total Runoff Volume between {self.begin_month_day} and {self.end_month_day} at {site_name}',
        #     xaxis_title='Year',
        #     yaxis_title='Day of Year'
        # )
        # self.volume_bw_days_fig = fig
        # fig.show()

        fig = px.scatter(self.vol_stats, x=self.vol_stats.index, y=self.vol_stats[self._name_of_Q_column], trendline='ols', title=f'Runoff Volume between {self.begin_month_day} and {self.end_month_day} at {site_name}')
        fig.update_xaxes(title_text='Water Year')
        fig.update_yaxes(title_text=f'Accumulative Volume (ksfd)')        
        fig.show()