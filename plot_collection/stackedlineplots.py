# import pandas as pd
# import datetime
from plot_collection.plot_utilities import MatplotlibPlotUtils, PlotlyPlotUtils
from plotly import graph_objects as go
import matplotlib.pyplot as plt

from statisticscalculator.generalstatistics import StatisticsCalculatorPlotly
class StaticPlotter:
    '''
    Keyword Arguments and defaults include:
        plot_central_tendency_stats=True,
        highlight_years=[],
        water_year=True,
        quartile_shading=True,
        quartile_shading_alpha=0.5,
        group_by_decade=False,
        series_alpha=0.3,
        quartile_shading_zorder=1,
        'forced_x_positions'=[1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 336],
        'forced_x_labels'=['01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01', '09-01', '10-01', '11-01', '12-01']
        'y_lower_lim'=0,
        'y_upper_lim'=25,
        'ylabel'='Discharge',
        'title',
        'legend_mode'='partial',
        'legend_pos'='upper right',
        'legend_ncol'=1
    '''
    def __init__(self, GeneralStatistics, **kwargs):
        self._GeneralStatistics = GeneralStatistics
        self._PlotUtils = MatplotlibPlotUtils(GeneralStatistics)
            
        # self._prepare_data_for_plotting(kwargs.get('input_start_year', 2010), kwargs.get('input_end_year', 2020))
    
        fig, ax = plt.subplots(figsize=(9, 7))

        self._PlotUtils._plot_central_tendency_stats(ax, kwargs.get('plot_central_tendency_stats', True))
        self._PlotUtils._plot_highlighted_years(ax, kwargs.get('highlight_years'))
        self._PlotUtils._plot_spread(**kwargs)

        if kwargs.get('group_by_decade', False):
            self._PlotUtils._plot_grouped_by_decade(ax, kwargs)
        else:
            self._PlotUtils._plot_individual_years(ax, kwargs.get('series_alpha', 0.3), kwargs)

        self._PlotUtils._customize_plot(ax, kwargs)
        self.fig = plt
        plt.show()



class DynamicPlotter:
    '''
    Keyword Arguments and defaults include:
        plot_central_tendency_stats=True,
        highlight_years=[],
        water_year=True,
        quartile_shading=True,
        quartile_shading_alpha=0.5,
        group_by_decade=False,
        series_alpha=0.3,
        quartile_shading_zorder=1,
        'forced_x_positions'=[1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 336],
        'forced_x_labels'=['01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01', '09-01', '10-01', '11-01', '12-01']
        'y_lower_lim'=0,
        'y_upper_lim'=25,
        'ylabel'='Discharge',
        'title',
        'legend_mode'='partial',
        'legend_pos'='upper right',
        'legend_ncol'=1
    '''
    # def __init__(self, GeneralStatistics, **kwargs):
    #     self._GeneralStatistics = GeneralStatistics
    #     self._PlotUtils = PlotlyPlotUtils(GeneralStatistics)
    def __init__(self, StatisticsCalculatorPlotly, **kwargs):
        self._GeneralStatistics = StatisticsCalculatorPlotly
        self._PlotUtils = PlotlyPlotUtils(StatisticsCalculatorPlotly)           
        fig = go.Figure()
        
        if kwargs.get('group_by_decade', False):
            self._PlotUtils._plot_grouped_by_decade(fig, kwargs)
        else:
            self._PlotUtils._plot_individual_years(fig, kwargs.get('series_alpha', 1), kwargs)
 
        self._PlotUtils._customize_plot(fig, kwargs)
    
        # self._PlotUtils._plot_central_tendency_stats(fig, kwargs.get('plot_central_tendency_stats', True))
        self._PlotUtils._plot_highlighted_years(fig, kwargs.get('highlight_years'))
        # self._PlotUtils._plot_quartile_shading(fig, kwargs.get('quartile_shading', True), kwargs.get('quartile_shading_alpha', 0.5), kwargs)
        self._PlotUtils._plot_vline(fig)
        self.fig = fig
        fig.show()
#         plotly.offline.plot(fig, filename=f'{}.html')