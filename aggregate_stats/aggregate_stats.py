import pandas as pd

class calculate_annual_stats():
    def __init__(self, StreamflowClimateStatistics):
        self.s = StreamflowClimateStatistics
        self.vol_mk_stats = {}
        self.runoff_timing_mk_stats = {}
        self.vol_figs = {}
        self.runoff_timing_figs = {}
        self.site_meta_data = {}
    
    def calc_stats_headwater(self, 
        site,
        start_date='1928-10-01', 
        end_date='2023-10-01', 
        month_intervals={'01-01':'12-31', '01-01':'03-31', '04-01':'06-30', '07-01':'9-30', '10-01':'12-31'},
        headwater_metadata_df=pd.read_excel('headwater_sites.xlsx')
    ):
        # self.s.calc_max(calc_from_rolling_median=False, window_size=7)
        self.s.calc_annual_runoff_threshold_day(0.5, alpha=.05)
        
        for k,v in month_intervals.items():
            try:
                self.s.calc_runoff_bw_days(begin_month_day=k, end_month_day=v, alpha=0.05)
                # self.vol_figs[f'{k}_to_{v}'] = streamflow_stat_plots.Plot_Runoff_Volume_Between_2Days(s)
                self.vol_mk_stats[f'{k}_to_{v}'] = self.s.volume_bw_days_mann_kendall_test
            except Exception(e):
                print('Issue occurred calculating volume stats or creating figures.')
                print(e)
                pass
        try:
            self.vol_mk_stats['Total Vol MK Test'] = self.s.total_volume_mann_kendall_test
            
            # self.runoff_timing_mk_stats['Q on date of peak Q date MK Test'] = s.rolling_yr_Qmax_mk_test
            # self.runoff_timing_mk_stats['dayofyear on date of peak Q date MK Test'] = s.rolling_yr_DOYmax_mk_test
            self.runoff_timing_mk_stats['Threshold Vol MK Test'] = s.threshold_vol_mann_kendall_test
            self.runoff_timing_mk_stats['Threshold Vol DOY MK Test'] = s.threshold_vol_dates_mann_kendall_test
            
            self.site_meta_data['lat'] = headwater_metadata_df[headwater_metadata_df.index==site].iat[0,1]
            self.site_meta_data['long'] = headwater_metadata_df[headwater_metadata_df.index==site].iat[0,2]
            self.site_meta_data['name'] = headwater_metadata_df[headwater_metadata_df.index==site].iat[0,0]
            self.site_meta_data['site'] = site
        except Exception as e:
            print('Error occurred calculating mann-kendall on total volume, runoff timing and volume, or adding site meta data')
            print(e)
            pass
            # print(e.message)
            # print(e.args)

class aggregate_stats():
    
    def __init__(self, annual_stats_objs):
        self.annual_stats_objs = annual_stats_objs
        self.aggregate_peakrunoffQ = {}
        self.aggregate_peakrunoffDOY = {}
        self.aggregate_thresholdVol = {}
        self.aggregate_thresholdDOY = {}
        self.aggregate_vols = {}

        self.aggregate_peakrunoffQ_dfs = {}
        self.aggregate_peakrunoffDOY_dfs = {}
        self.aggregate_vols_dfs = {}
        self.figs = {}
        self.aggregate_meta_data = {}

    def _aggregate_stats(self):

        # for key in self.annual_stats_objs.get(.vol_mk_stats.keys():
        #     print(key)

        self.aggregate_vols = {'01-01_to_03-31':{}, '04-01_to_06-30':{}, '07-01_to_9-30':{}, '10-01_to_12-31':{}, 'Total Vol MK Test':{}}
        
        for site, stats_object in self.annual_stats_objs.items():
            # print(stats_object.site_meta_data)
            self.aggregate_meta_data[site] = stats_object.site_meta_data
            
            # self.PeakRunoffQ = self.annual_stats.runoff_timing_mk_stats.get()
            # self.PeakRunoffQ = self.annual_stats.runoff_timing_mk_stats.get()
            self.aggregate_thresholdVol[site] = stats_object.runoff_timing_mk_stats.get('Threshold Vol DOY MK Test')
            self.aggregate_thresholdDOY[site] = stats_object.runoff_timing_mk_stats.get('Threshold Vol MK Test')            

            for date_range, vol_stats in stats_object.vol_mk_stats.items():
                self.aggregate_vols.get(date_range)[site]=vol_stats
    
    def _convert_dicts_to_dfs(self):
        
        #Convert dicts to dfs
        # for site, stats_object in self.annual_stats_objs.items():
        self.aggregate_thresholdVol_df = pd.DataFrame(self.aggregate_thresholdVol).T.rename(columns={0:"Trend", 1:"h", 2:"p", 3:'z', 4:'Tau', 5:'s', 6:'var_s', 7:'slope', 8:'intercept'})
        self.aggregate_thresholdDOY_df = pd.DataFrame(self.aggregate_thresholdDOY).T.rename(columns={0:"Trend", 1:"h", 2:"p", 3:'z', 4:'Tau', 5:'s', 6:'var_s', 7:'slope', 8:'intercept'})
  
        for date_range in self.aggregate_vols.keys():
            self.aggregate_vols_dfs[date_range] = pd.DataFrame(self.aggregate_vols.get(date_range)).T.rename(columns={0:"Trend", 1:"h", 2:"p", 3:'z', 4:'Tau', 5:'s', 6:'var_s', 7:'slope', 8:'intercept'})