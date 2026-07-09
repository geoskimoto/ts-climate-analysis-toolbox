import pandas as pd
import datetime
import matplotlib.pyplot as plt
import plotly.graph_objects as go

class MatplotlibPlotUtils:
    def __init__(self, GeneralStatistics, **kwargs):
        self._GeneralStatistics = GeneralStatistics
        self._colors = ['crimson', 'springgreen', 'dodgerblue', 'purple', 'green', 'deeppink', "lawngreen", "coral", "lime", "navy", "goldenrod", 'crimson', 'springgreen', 'dodgerblue', 'purple', 'green', 'deeppink', "lawngreen", "coral", "lime", "navy", "goldenrod"]
        self._name_of_date_column = GeneralStatistics.data_loader._name_of_date_column
        self._name_of_Q_column = GeneralStatistics.data_loader._name_of_Q_column
        
    def _plot_individual_years(self, ax, series_alpha, kwargs):
#         print(grouped_water_years)
        if kwargs.get('water_year_on', True):
            for year in self._GeneralStatistics._df['Water Year'].unique():
                year_df = self._GeneralStatistics._grouped_water_years.get_group(year) 
                ax.plot(year_df['month-day'], year_df[self._name_of_Q_column], label=f'{year}', alpha=series_alpha)
        else:
            for year in self._GeneralStatistics._df['Calendar Year'].unique():
#                 year_df = self._GeneralStatistics._df[self._GeneralStatistics._df['Calendar Year']==year]
                year_df = self._GeneralStatistics._grouped_calendar_years.get_group(year) 
                ax.plot(year_df['month-day'], year_df[self._name_of_Q_column], label=f'{year}', alpha=series_alpha)

    def _plot_central_tendency_stats(self, ax, plot_stats):
        if plot_stats:
            self._GeneralStatistics._mean.plot(ax=ax, label="Mean", linestyle=':', color='black', linewidth=1, zorder=3)
            self._GeneralStatistics._median.plot(ax=ax, label="Median", linestyle='--', color='black', linewidth=1, zorder=3)

    def _plot_highlighted_years(self, ax, highlight_years, **kwargs):
        if isinstance(kwargs.get('highlight_years'), list):
            for year in highlight_years:
    #             if kwargs.get('water_year_on', True):
                year_df = self._GeneralStatistics._grouped_water_years.get_group(year)
    #             else:
    #                 year_df = self._GeneralStatistics._df[self._GeneralStatistics._df['Calendar Year']==year]

                ax.plot(year_df['month-day'], year_df[self._name_of_Q_column], label=f'{year}', color='red', linewidth=1.5, alpha=1)
        else:
            pass
    def _plot_spread(self, **kwargs):
        
        if kwargs.get('spread_on', True):            
            spread_zorder = kwargs.get('spread_zorder', 1)
            spread_alpha = kwargs.get('spread_alpha', 0.15)
            spread_color = kwargs.get('spread_color', 'yellow')
            
            if kwargs.get('spread_type', 'quartiles'):
                lower_bound = self._GeneralStatistics._lower_bound_percentile25
                upper_bound = self._GeneralStatistics._upper_bound_percentile75
            elif kwargs.get('spread_type', 'std'):
                lower_bound = self._GeneralStatistics._lower_bound_st_dev
                upper_bound = self._GeneralStatistics._upper_bound_st_dev

            plt.fill_between(
                list(range(0, len(pd.DataFrame(self._GeneralStatistics._mean).iloc[:, 0]))),
                pd.DataFrame(self._GeneralStatistics._mean).iloc[:, 0].astype(float),
                pd.DataFrame(lower_bound).iloc[:, 0].astype(float),                
        #                 pd.DataFrame(self._GeneralStatistics._lower_bound_st_dev).iloc[:, 0].astype(float),
                where=(pd.DataFrame(self._GeneralStatistics._mean).iloc[:, 0].astype(float) > pd.DataFrame(self._GeneralStatistics._lower_bound_percentile25).iloc[:, 0].astype(float)),
                interpolate=True, color=spread_color, alpha=spread_alpha, zorder=spread_zorder, label="q25-q75")

            plt.fill_between(
                list(range(0, len(pd.DataFrame(self._GeneralStatistics._mean).iloc[:, 0]))),
                pd.DataFrame(self._GeneralStatistics._mean).iloc[:, 0].astype(float),
                pd.DataFrame(upper_bound).iloc[:, 0].astype(float),
        #                 pd.DataFrame(self._GeneralStatistics._upper_bound_st_dev).iloc[:, 0].astype(float),                
                where=(pd.DataFrame(self._GeneralStatistics._mean).iloc[:, 0].astype(float) < pd.DataFrame(self._GeneralStatistics._upper_bound_percentile75).iloc[:, 0].astype(float)),
                interpolate=True, color=spread_color, alpha=spread_alpha, zorder=spread_zorder)
        else:
            pass
    # def _plot_grouped_by_decade(self, ax, kwargs):
    #     for i, decade in enumerate(self._GeneralStatistics._unique_decades):
    #         years_in_decade = [year for year in self._GeneralStatistics._unique_years if decade <= year < decade + 10]
    #         mean_values = self._GeneralStatistics._pivot_table[years_in_decade].mean(axis=1)
    #         std_dev_values = self._GeneralStatistics._pivot_table[years_in_decade].std(axis=1)
    #         ax.plot(self._GeneralStatistics._pivot_table.index, mean_values, label=f'Decade {decade}s', color=self._colors[i])
    #         ax.fill_between(self._GeneralStatistics._pivot_table.index, mean_values - std_dev_values, mean_values + std_dev_values, alpha=0.2, color=self._colors[i])
    

    def _customize_plot(self, ax, kwargs):
        if kwargs.get('water_year_on', True):
            self._forced_x_labels = kwargs.get('forced_x_labels', ['10-01', '11-01', '12-01', '01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01', '09-01'])
            self._forced_x_positions = kwargs.get('forced_x_positions', [1, 31, 62, 93, 121, 152, 182, 213, 243, 273, 303, 335]),
        else:
            self._forced_x_labels = kwargs.get('forced_x_labels', ['01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01', '09-01', '10-01', '11-01', '12-01'])       
            self._forced_x_positions = kwargs.get('forced_x_positions', [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 336]),

        if self._forced_x_positions is not None and self._forced_x_labels is not None:
#             print(self._forced_x_positions[0])
#             print(self._forced_x_labels)
            ax.set_xticks(self._forced_x_positions[0])
            ax.set_xticklabels(self._forced_x_labels, rotation=45)
            xlim_min = self._forced_x_positions[0][0]
            xlim_max = self._forced_x_positions[0][-1]
            ax.set_xlim([xlim_min, xlim_max])
            ax.set_ylim([kwargs.get('y_lower_lim', self._GeneralStatistics._df[self._GeneralStatistics.data_loader._name_of_Q_column].min()), kwargs.get('y_upper_lim', self._GeneralStatistics._df[self._GeneralStatistics.data_loader._name_of_Q_column].max())])

        plt.grid(color='green', linestyle=":", linewidth=0.5)
        plt.xlabel('Month-Day')
        plt.ylabel(kwargs.get('ylabel', "Discharge (cfs)"))
        plt.title(kwargs.get('title'))

        if kwargs.get('legend_mode') == "partial":
#             labels = ['Mean', 'Median', 'q25-q75'] + kwargs.get('highlight_years', [])
            plt.legend(loc=kwargs.get('legend_pos', 'upper right'), ncol=kwargs.get('legend_ncol', 1), labels=['Mean', 'Median'] + kwargs.get('highlight_years', []))
        else:
            plt.legend(loc=kwargs.get('legend_pos'), ncol=kwargs.get('legend_ncol'))#, labels=labels)


import plotly.express as px
import datetime
import pandas as pd

class PlotlyPlotUtils:
    def __init__(self, GeneralStatistics):
        self._GeneralStatistics = GeneralStatistics
        self._colors = px.colors.qualitative.Plotly #['crimson', 'springgreen', 'dodgerblue', 'purple', 'green', 'deeppink', "lawngreen", "coral", "lime", "navy", "goldenrod", 'crimson', 'springgreen', 'dodgerblue', 'purple', 'green', 'deeppink', "lawngreen", "coral", "lime", "navy", "goldenrod"]

    def _plot_central_tendency_stats(self, fig, plot_stats):
        if plot_stats:
            fig.add_trace(go.Scatter(x=self._GeneralStatistics._df.index, y=self._GeneralStatistics._mean,
                                     mode='lines', name="Mean", line=dict(color='black', dash='dash')))
            fig.add_trace(go.Scatter(x=self._GeneralStatistics._df.index, y=self._GeneralStatistics._median,
                                     mode='lines', name="Median", line=dict(color='black', dash='dot')))
 
    def _plot_highlighted_years(self, fig, highlight_years):
        try:
            for i, year in enumerate(highlight_years):
                fig.add_trace(go.Scatter(x=self._GeneralStatistics._df.index, y=self._GeneralStatistics._pivot_table[year],
                                        mode='lines', name=str(year), line=dict(color=self._colors[i], width=2.5), opacity=1, hoverinfo='text'))
        except Exception as E:
            print(E)
            pass
    def _plot_quartile_shading(self, fig, quartile_shading, quartile_shading_alpha, kwargs):
        if quartile_shading:
            for i, row in self._GeneralStatistics._pivot_table.iterrows():
                fig.add_trace(go.Scatter(x=row.index, y=row,
                                         fill='tonexty',
                                         fillcolor='yellow',
                                         line=dict(color='rgba(255,255,255,0)'),
                                         name="q25-q75", opacity=quartile_shading_alpha))

    # def _plot_grouped_by_decade(self, fig, kwargs):
    #     for decade in self._GeneralStatistics._unique_decades:
    #         years_in_decade = [year for year in self._GeneralStatistics._unique_years if decade <= year < decade + 10]
    #         mean_values = self._GeneralStatistics._pivot_table[years_in_decade].mean(axis=1)
    #         std_dev_values = self._GeneralStatistics._pivot_table[years_in_decade].std(axis=1)
    #         fig.add_trace(go.Scatter(x=self._GeneralStatistics._pivot_table.index, y=mean_values,
    #                                  mode='lines', name=f'Decade {decade}s', line=dict(color=self._colors[i])))
    #         fig.add_trace(go.Scatter(x=self._GeneralStatistics._pivot_table.index, y=mean_values + std_dev_values,
    #                                  fill='tonexty',
    #                                  fillcolor=self._colors[i],
    #                                  line=dict(color='rgba(255,255,255,0)'),
    #                                  name="Decade std dev", opacity=0.2))
    def _plot_vline(self, fig):
        # current_monthday = datetime.datetime.now().strftime('%m%d')
        print(datetime.datetime.now().strftime('%j'))
#         print(f'{current_monthday[:2]}-{current_monthday[2:]}')
#         fig.add_vline(x=f'{current_monthday[:1]}-{current_monthday[2:]}', line_dash='dash', line_color='red')#, annotated_text='Current Date')
        fig.add_vline(x=datetime.datetime.now().strftime('%j'), line_dash='dash', line_color='red')#, annotated_text='Current Date')

    def _plot_individual_years(self, fig, series_alpha, kwargs):
        try:
            for year in self._GeneralStatistics._df['Water Year'].unique():
                fig.add_trace(go.Scatter(x=self._GeneralStatistics._pivot_table.reset_index().index, 
                                        y=self._GeneralStatistics._pivot_table[int(year)],
                                        mode='lines', name=str(year), opacity=series_alpha, showlegend=False, hoverinfo='none'))
        except Exception as E:
            print(E)
            pass
             
    def _customize_plot(self, fig, kwargs):
        fig.update_layout(xaxis=dict(
            tickvals=kwargs.get('forced_x_positions', [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 336]),
            ticktext=kwargs.get('forced_x_labels', ['01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01', '09-01', '10-01', '11-01', '12-01']),
            tickangle=45),
            yaxis=dict(range=[kwargs.get('y_lower_lim', self._GeneralStatistics._df[self._GeneralStatistics.data_loader._name_of_Q_column].min()),
                                kwargs.get('y_upper_lim', self._GeneralStatistics._df[self._GeneralStatistics.data_loader._name_of_Q_column].max())]),
            title=kwargs.get('title', ''),
            legend=dict(x=0, y=1),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
              )

        


