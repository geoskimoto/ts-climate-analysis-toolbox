import pandas as pd
import math
# import datetime

# class StatisticsCalculator:
#     def __init__(self, DataLoader):
#         self.data_loader = DataLoader
#         self._df = self.data_loader._df
#         self._df['Date'] = pd.to_datetime(self._df[self.data_loader._name_of_date_column])
#         self._df = self._df[~self._df.duplicated('Date')]
#         self._df['month'] = self._df['Date'].dt.month
#         self._df['Year'] = self._df['Date'].dt.year
#         self._df['month-day'] = self._df['Date'].apply(lambda x: x.strftime('%m-%d'))
#         self._df['Water Year'] = self._df['Date'].dt.year.where(self._df['Date'].dt.month<10, self._df['Date'].dt.year+1)
#         self.stats = self._calculate_statistics()
    
#     def _calculate_statistics(self, **kwargs):

#         self._stats = self._df.groupby("month-day")[self.data_loader._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
#         self._monthly_stats = self._df.groupby("month")[self.data_loader._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
#         self._mean = self._stats.iloc[:, 0]
#         self._median = self._stats.iloc[:, 1]
#         self._st_dev = self._stats.iloc[:, 2]
        
        
# #         minData = [np.nanmin(a) for a in statsData]
# #         maxData = [np.nanmax(a) for a in statsData]
# #         meanData = [np.nanpercentile(a, 50) for a in statsData]
# #         lowestData = [np.nanpercentile(a, 10) for a in statsData]
# #         highestData = [np.nanpercentile(a, 90) for a in statsData]
# #         lowData = [np.nanpercentile(a, 30) for a in statsData]
# #         highData = [np.nanpercentile(a, 70) for a in statsData]
        
        
#         self._percentile25 = self._stats.iloc[:, 3]
#         self._percentile75 = self._stats.iloc[:, 4]
#         self._lower_bound_st_dev = self._mean - self._st_dev
#         self._upper_bound_st_dev = self._mean + self._st_dev
#         self._lower_bound_percentile25 = self._mean - self._percentile25
#         self._upper_bound_percentile75 = self._mean + self._percentile75

#         water_year = kwargs.get('water_year', True)
#         print(f'water_year: {water_year}')
#         year = 'Water Year' if water_year else 'Year'
#         start_year = kwargs.get("start_year", self._df[year].iloc[0])
#         end_year = kwargs.get("end_year", self._df[year].iloc[-1])
#         self._df = self._df[(self._df[year] >= start_year) & (self._df[year] <= end_year)]
#         self._unique_years = self._df[year].unique()
#         self._start_year, self._end_year = self._unique_years[0], self._unique_years[-1]
#         self._num_of_decades = math.ceil((self._end_year - self._start_year) / 10)
#         self._unique_decades = self._df[year].apply(lambda year: (year // 10) * 10).unique()

#         # Convert years in _pivot_table to water years if necessary

#         self._pivot_table = self._df.copy()
#         self._pivot_table['month-day'] = self._pivot_table['Date'].apply(lambda x: x.strftime('%m-%d'))
#         self._pivot_table = self._pivot_table.pivot(index="month-day", columns=year, values=self.data_loader._name_of_Q_column)
        
#         if water_year == True:
#             self._pivot_table = self._pivot_table[self._df['Water Year'].unique()]
#         else:
#             self._pivot_table = self._pivot_table[self._df['Year'].unique()]
            
#         self._pivot_table_monthly = self._df.pivot(columns='month', values=self.data_loader._name_of_Q_column)
#         self._pivot_table_yearly_stats = {year: self._pivot_table.iloc[:, i].describe() for i, year in enumerate(self._pivot_table.columns)}

#         # Call _prepare_data_for_plotting here
#         # self._prepare_data_for_plotting(start_year, end_year, water_year=water_year)

#     ##  KEEP!!!!!!  And fix up. - calculates volume under curve/water supply for the year
#     # def calculate_yearly_volumes(self):
#     #     years = []
#     #     area = []
#     #     for year in self._pivot_table.columns:
#     #         dates = list(range(0, len(self._pivot_table[year].dropna())))
#     #         area.append(trapz(self._pivot_table[year].dropna(), dates))
#     #         years.append(year)

#     #     Area_dict = OrderedDict()
#     #     for key, value in zip(years, area):
#     #         Area_dict[key] = value
#         # return Area_dict

    
           

class GeneralStatistics:
    def __init__(self, DataLoader):
        self.data_loader = DataLoader
        self._df = self.data_loader._df
        self._df['Date'] = pd.to_datetime(self._df[self.data_loader._name_of_date_column])
        self._df = self._df[~self._df.duplicated('Date')]
        #Replace year in regular calendar year with water year.  This is the key line of code/method for plotting WY.
        self._df['WY_Date'] = self._df['Date'].apply(lambda x: x.replace(year=x.year+1) if 10 <= x.month <=12 else x)
        self._df['month'] = self._df['WY_Date'].dt.month
        self._df['Water Year'] = self._df['WY_Date'].dt.year
        self._df['Calendar Year'] = self._df['Date'].dt.year
        self._df['month-day'] = self._df['WY_Date'].apply(lambda x: x.strftime('%m-%d'))
        self._df['dayofyear'] = self._df['WY_Date'].dt.dayofyear
#         self._df['Water Year'] = self._df['Date'].dt.year.where(self._df['Date'].dt.month<10, self._df['Date'].dt.year+1)
        self.stats = self._calculate_statistics()
#         if kwargs.get('water_year_on', True):
        self._grouped_water_years = self._df.groupby('Water Year')
        
#         else:
#         self._grouped_calendar_years = self._df.groupby('Calendar Year')
        #Create new column with water year dates by replacing normal calendar year in dt object with water year 
        
    def _calculate_statistics(self, **kwargs):

        self._stats = self._df.groupby("month-day")[self.data_loader._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
        self._stats.reset_index(inplace=True)
        self._stats['month'] = self._stats['month-day'].str[:2]
#         self._stats['month'] = pd.to_datetime(self._stats['month-day'], format='%m')
        self._stats['month'] = self._stats['month'].fillna('')
        water_year_sort_order = ['10', '11', '12', '01', '02', '03', '04', '05', '06', '07', '08', '09']
        self._stats['water_year_sort'] = self._stats['month'].map({month: i for i, month in enumerate(water_year_sort_order)})
        self._stats = self._stats.sort_values(by='water_year_sort')
        self._stats.reset_index(inplace=True)
        # self._stats.rename({'index':'day_of_year'})
        # self._stats.set_index('day_of_year', inplace=True)
        # self._monthly_stats = self._df.groupby("month")[self.data_loader._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
        self._mean = self._stats.loc[:, 'mean']
        self._median = self._stats.loc[:, 'median']
        self._st_dev = self._stats.loc[:, 'std']
        self._percentile25 = self._stats.loc[:, 'q25']
        self._percentile75 = self._stats.loc[:, 'q75']
        self._lower_bound_st_dev = self._mean - self._st_dev
        self._upper_bound_st_dev = self._mean + self._st_dev
        self._lower_bound_percentile25 = self._mean - self._percentile25
        self._upper_bound_percentile75 = self._mean + self._percentile75
        
        self._pivot_table = self._df.copy()
        self._pivot_table['month-day'] = self._pivot_table['Date'].apply(lambda x: x.strftime('%m-%d'))
        self._pivot_table = self._pivot_table.pivot(index="month-day", columns='Calendar Year', values=self.data_loader._name_of_Q_column)
        
        # if water_year == True:
        # self._pivot_table = self._pivot_table[self._df['Water Year'].unique()]
        # else:
        self._pivot_table = self._pivot_table[self._df['Calendar Year'].unique()]

    

class StatisticsCalculatorPlotly(GeneralStatistics):
    def __init__(self, DataLoader):
        self.data_loader = DataLoader
        self._df = self.data_loader._df
        self._df['Date'] = pd.to_datetime(self._df[self.data_loader._name_of_date_column])
        self._df = self._df[~self._df.duplicated('Date')]
        #Replace year in regular calendar year with water year.  This is the key line of code/method for plotting WY.
        self._df['WY_Date'] = self._df['Date'].apply(lambda x: x.replace(year=x.year+1) if 10 <= x.month <=12 else x)
        self._df['month'] = self._df['WY_Date'].dt.month
        self._df['Water Year'] = self._df['WY_Date'].dt.year
        self._df['Calendar Year'] = self._df['Date'].dt.year
        self._df['month-day'] = self._df['WY_Date'].apply(lambda x: x.strftime('%m-%d'))
#         self._df['Water Year'] = self._df['Date'].dt.year.where(self._df['Date'].dt.month<10, self._df['Date'].dt.year+1)
        self.stats = self._calculate_statistics()
#         if kwargs.get('water_year_on', True):
        self._grouped_water_years = self._df.groupby('Water Year')
        
#         else:
#         self._grouped_calendar_years = self._df.groupby('Calendar Year')
        #Create new column with water year dates by replacing normal calendar year in dt object with water year 
        
    def _calculate_statistics(self, **kwargs):

        self._stats = self._df.groupby("month-day")[self.data_loader._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
        self._stats.reset_index(inplace=True)
        self._stats['month'] = self._stats['month-day'].str[:2]
#         self._stats['month'] = pd.to_datetime(self._stats['month-day'], format='%m')
        self._stats['month'] = self._stats['month'].fillna('')
        water_year_sort_order = ['10', '11', '12', '01', '02', '03', '04', '05', '06', '07', '08', '09']
        self._stats['water_year_sort'] = self._stats['month'].map({month: i for i, month in enumerate(water_year_sort_order)})
        self._stats = self._stats.sort_values(by='water_year_sort')
        self._stats.reset_index(inplace=True)
#         self._monthly_stats = self._df.groupby("month")[self.data_loader._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
        self._mean = self._stats.loc[:, 'mean']
        self._median = self._stats.loc[:, 'median']
        self._st_dev = self._stats.loc[:, 'std']
        self._percentile25 = self._stats.loc[:, 'q25']
        self._percentile75 = self._stats.loc[:, 'q75']
        self._lower_bound_st_dev = self._mean - self._st_dev
        self._upper_bound_st_dev = self._mean + self._st_dev
        self._lower_bound_percentile25 = self._mean - self._percentile25
        self._upper_bound_percentile75 = self._mean + self._percentile75

        self._pivot_table = self._df.copy()
        self._pivot_table['month-day'] = self._pivot_table['Date'].apply(lambda x: x.strftime('%m-%d'))
        self._pivot_table = self._pivot_table.pivot(index="month-day", columns='Calendar Year', values=self.data_loader._name_of_Q_column)
        
        # if water_year == True:
        # self._pivot_table = self._pivot_table[self._df['Water Year'].unique()]
        # else:
        self._pivot_table = self._pivot_table[self._df['Calendar Year'].unique()]
            
        self._pivot_table_monthly = self._df.pivot(columns='month', values=self.data_loader._name_of_Q_column)
        self._pivot_table_yearly_stats = {year: self._pivot_table.iloc[:, i].describe() for i, year in enumerate(self._pivot_table.columns)}