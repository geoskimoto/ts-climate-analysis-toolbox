from streamflow_climatestatistics import StreamflowClimateStatistics
import pandas as pd
import datetime

class HalfVolumeDays():
    def __init__(self, StreamflowClimateStatistics):
        self.vol_stats = StreamflowClimateStatistics.yearly_volume_statistics

    def plot_half_volume_days(self, site_name):
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
        fig.show()
        self.fig = fig
#         return fig




class TotalYearlyVolumes():
    def __init__(self, StreamflowClimateStatistics):
        self.vol_stats = StreamflowClimateStatistics.yearly_volume_statistics

    def plot_total_yearly_volumes(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.vol_stats.index, y=self.vol_stats['total_volume']))
        self.fig = fig
        fig.show()