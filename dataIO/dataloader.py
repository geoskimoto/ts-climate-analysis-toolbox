import pandas as pd
import datetime

class DataLoader:
    def __init__(self, cvs_path_or_df, name_of_date_column, name_of_Q_column):
        self.cvs_path_or_df = cvs_path_or_df
        self._name_of_date_column = name_of_date_column
        self._name_of_Q_column = name_of_Q_column
        self.df = self.load_data()
    
    def load_data(self):
        import pandas as pd
        if isinstance(self.cvs_path_or_df, pd.DataFrame):
            self._df = self.cvs_path_or_df.copy()  # Set the DataFrame directly
            # Convert columns to numeric, handling errors by setting non-numeric values to NaN
            if isinstance(self._df[self._name_of_Q_column].iloc[0], str):
                self._df[self._name_of_Q_column] = pd.to_numeric(self._df[self._name_of_Q_column], errors='coerce')

        elif isinstance(self.cvs_path_or_df, str):
            try:
                print(f"Importing CSV with the file path: {self.csv_path}")
                self._df = pd.read_csv(self.cvs_path_or_df)
                # Convert columns to numeric, handling errors by setting non-numeric values to NaN
                if isinstance(self._df[self._name_of_Q_column][0], str):
                    self._df[self._name_of_Q_column] = pd.to_numeric(self._df[self._name_of_Q_column], errors='coerce')
                # self._df['Year'] = pd.to_numeric(self._df['Year'], errors='coerce')
            except Exception as e:
                print(f"Error reading CSV file: {e}")
                
        else:
            print("Invalid input type. Please provide either a pandas DataFrame or a CSV file path.")
            
