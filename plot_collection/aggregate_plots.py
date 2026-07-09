class aggregate_mann_kendall_plots():
    def __init__(self):
        self.figs = []

    def scatter(self, aggregate_obj_class):
        df = aggregate_obj_class.aggregate_thresholdDOY_df
        # print(df)
        fig = px.scatter(df, 'p', 'Tau', color='Trend',
                 title='Threshold DOY',
                 hover_data={
                     # 'Site Name': df.index, 
                     'Site': df.index, 
                     # 'Trend': df['Trend'],
                 },
                 symbol = df['Trend'],
                 symbol_map={'no trend':'circle-open', 'decreasing': 'triangle-down', 'increasing':'triangle-up'},
                 color_discrete_map={'decreasing':'red', 'increasing':'green', 'no trend': 'blue'}
                )
        self.figs.append(fig)
        fig.show()
        # fig = px.scatter(ThresholdDOY, 'p', 'tau', color='trend',
        #                  title=ThresholdDOY_title,
        #                  hover_data={
        #                      'Site Name': ThresholdDOY['site_name'], 
        #                      'Site': ThresholdDOY['sites'], 'Trend': ThresholdDOY['trend']
        #                  },
        #                  symbol = ThresholdDOY['trend'],
        #                  symbol_map={'no trend':'circle-open', 'decreasing': 'triangle-down', 'increasing':'triangle-up'},
        #                  color_discrete_map={'decreasing':'red', 'increasing':'green', 'no trend': 'blue'}
        #                 )
        # figs.append(fig)
        # fig.show()
        # with open('HeadwaterSites_MK_Results2.html', 'a') as f:
        #     f.write(fig.to_html(full_html=False, include_plotlyjs='cdn', default_width=1200, default_height=400))

        for date_range, df in aggregate_obj_class.aggregate_vols_dfs.items():
            fig = px.scatter(df, 'p', 'Tau', color='Trend',
                             title=date_range,
                             hover_data={
                                 # 'Site Name': df.index, 
                                 'Site': df.index, 
                                 # 'Trend': df['Trend'],
                             },
                             symbol = df['Trend'],
                             symbol_map={'no trend':'circle-open', 'decreasing': 'triangle-down', 'increasing':'triangle-up'},
                             color_discrete_map={'decreasing':'red', 'increasing':'green', 'no trend': 'blue'}
                            )
            self.figs.append(fig)
            fig.show()

    def save_scatter_figs(self, file_name, delete_existing=False):
        
        if delete_existing:
            if os.path.exists(file_name):
                 os.remove(file_name)
            for fig in self.figs:       
                with open(file_name, 'a') as f:
                    f.write(fig.to_html(full_html=False, include_plotlyjs='cdn', default_width=1200, default_height=400))
        else:
            for fig in self.figs:       
                with open(file_name, 'a') as f:
                    f.write(fig.to_html(full_html=False, include_plotlyjs='cdn', default_width=1200, default_height=400))
                