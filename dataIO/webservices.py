# import urllib
import requests
# import json
import pandas as pd
import io
# import datetime
# import re
from functools import reduce


class nrcs_snotel:
    def __init__(self):
        self.df = None
        self.request = None

    def _construct_url(self, begin_date, end_date, station_triplets, elements, central_tendency_type="NONE",
                       duration_type="DAILY", period_ref="END", return_flags="false",
                       return_original_values="false", return_suspect_data="false"):
        server = "https://wcc.sc.egov.usda.gov/awdbRestApi"
        endpoint = "/services/v1/data"
        begin_date = "?beginDate={}".format(begin_date)
        central_tendency_type = "&centralTendencyType={}".format(central_tendency_type)
        duration = "&duration={}".format(duration_type)
        elements = "%2C%20".join(elements)
        elements = "&elements={}".format(elements)
        end_date = "&endDate={}".format(end_date)
        period_ref = "&periodRef={}".format(period_ref)
        return_flags = "&returnFlags={}".format(return_flags)
        return_original_values = "&returnOriginalValues={}".format(return_original_values)
        return_suspect_data = "&returnSuspectData={}".format(return_suspect_data)
        station_triplets = station_triplets.replace(':','%3A')
#         station_triplets = "&stationTriplets={}%3A{}%3A{}".format(station_triplets[0], station_triplets[1], station_triplets[2])
        station_triplets = "&stationTriplets={}".format(station_triplets)    

        url = "{}{}{}{}{}{}{}{}{}{}{}{}".format(
            server, endpoint, begin_date, central_tendency_type, duration, elements, end_date,
             period_ref, return_flags, return_original_values, return_suspect_data, station_triplets
        )

        self.url=url
        return url

    def _parse_response(self, response):
        try:
            response_data = response.json()
            element_dfs = []
            for element_data in response_data[0]['data']:
                values = element_data['values']
                element_code = element_data['stationElement']['elementCode']
                for entry in values:
                    entry[element_code] = entry.pop('value')
                df = pd.DataFrame.from_dict(values)
                element_dfs.append(df)
            merge_dfs = lambda left, right: pd.merge(left, right, on='date')
            merged_df = reduce(merge_dfs, element_dfs)
            merged_df.set_index('date', inplace=True)
            return merged_df
        except (KeyError, IndexError, ValueError, TypeError) as e:
            print(f"Error parsing response: {e}")
            return None

    def get_data(self, begin_date, end_date, station_triplets, elements, **kwargs):
        try:
            url = self._construct_url(begin_date, end_date, station_triplets, elements, **kwargs)
            print(url)
            response = requests.get(url)
            if response.ok:
                self.df = self._parse_response(response)
                self.request = response
                return self.df
            else:
                print(f"Request failed with status code: {response.status_code}")
                return None
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return None


class usgs_streamflow:
    
    def get_data(self,
                file_format='json', 
                sites='09380000', 
                start_date='2010-10-01', 
                end_date='2023-10-01', 
                site_status='all', 
                parameterCd="00060"
                ):
        
        #Test calls here: https://waterservices.usgs.gov/  #your using the Daily Values Service
        server = 'https://waterservices.usgs.gov'
        endpoint = '/nwis/dv'
        file_format = f'/?format={file_format}'
        sites = f'&sites={sites}'
        start_date = f'&startDT={start_date}'
        end_date = f'&endDT={end_date}'
        site_status = f'&siteStatus={site_status}'
        parameterCd = f'&parameterCd={parameterCd}'  # 00060 represents discharge. Can be a ton of different parameters (https://help.waterdata.usgs.gov/codes-and-parameters/parameters).

        url = f'{server}{endpoint}{file_format}{sites}{start_date}{end_date}{site_status}{parameterCd}'
        print(url)
        req = requests.get(url)
            #Correct url for reference:
            #'https://waterservices.usgs.gov/nwis/dv/?format=json&sites=09380000&startDT=1921-10-01&endDT=2023-10-01&siteStatus=all'

        if req.ok:
            df = pd.DataFrame(req.json()['value']['timeSeries'][0]['values'][0]['value'])
            df['dateTime']= pd.to_datetime(df['dateTime']).dt.date
            df.rename(columns={'dateTime':'Date', 'value':'Discharge'}, inplace=True)
            df = df[['Date', 'Discharge']]
#             df.set_index('dateTime', inplace=True)
            self.req = req
            self.df = df
            return df



class usgs_streamflow2:
    #test service and check out other optional parameters not include in this class:
    # https://waterservices.usgs.gov/test-tools/?service=dv&siteType=ST-CA&statTypeCd=all&major-filters=sites&format=json&date-type=type-none&statReportType=daily&statYearType=calendar&missingData=off&siteStatus=all&siteNameMatchOperator=start
    def __init__(self):
        self.df = None
        self.req = None
        
    def _construct_url(
                    self,
                    file_format='json', 
                    sites='09380000', 
                    start_date='2010-10-01', 
                    end_date='2023-10-01', 
                    site_status='all', #options: active, inactive, all
                    parameterCd="00060"
                    ):
        
        #Test calls here: https://waterservices.usgs.gov/  #your using the Daily Values Service
        server = 'https://waterservices.usgs.gov'
        endpoint = '/nwis/dv'
        file_format = f'/?format={file_format}'
        sites = f'&sites={sites}'
        start_date = f'&startDT={start_date}'
        end_date = f'&endDT={end_date}'
        site_status = f'&siteStatus={site_status}'  
        parameterCd = f'&parameterCd={parameterCd}'  # 00060 represents discharge. Can be a ton of different parameters (https://help.waterdata.usgs.gov/codes-and-parameters/parameters).

        url = f'{server}{endpoint}{file_format}{sites}{start_date}{end_date}{site_status}{parameterCd}'
        print(url)
        req = requests.get(url)
            #Correct url for reference:
            #'https://waterservices.usgs.gov/nwis/dv/?format=json&sites=09380000&startDT=1921-10-01&endDT=2023-10-01&siteStatus=all'
        self.req = req
        self.url = url
        
    def _parse_response(self, req):
        try:
            df = pd.DataFrame(req.json()['value']['timeSeries'][0]['values'][0]['value'])
            df['dateTime']= pd.to_datetime(df['dateTime']).dt.date
            df.rename(columns={'dateTime':'Date', 'value':'Discharge'}, inplace=True)
            df = df[['Date', 'Discharge']]
#             df.set_index('dateTime', inplace=True)
            self.req = req
            self.df = df
            return df
        except (KeyError, IndexError, ValueError, TypeError) as e:
            print(f"Error parsing response: {e}")
            return None  
        
    def get_data(
                self,
                file_format='json', 
                sites='09380000', 
                start_date='2010-10-01', 
                end_date='2023-10-01', 
                site_status='all', 
                parameterCd="00060"
                ):
        try:
            url = self._construct_url(
                    file_format, 
                    sites, 
                    start_date, 
                    end_date, 
                    site_status, 
                    parameterCd)
            
            req = requests.get(self.url)
            if req.ok:
                print("request be good")
                self.df = self._parse_response(self.req)
                return self.df
        except requests.RequestException as e:
            print(f'Request failed: {e}')
            return None


def fetch_ca_water_data(start_date, end_date, stations, parameters):
    base_url = 'https://wateroffice.ec.gc.ca/services/daily_data/csv/inline'
    
    # Format station and parameter lists for URL query parameters
    station_params = '&'.join([f'stations[]={station}' for station in stations])
    parameter_params = '&'.join([f'parameters[]={parameter}' for parameter in parameters])
    
    # Construct the complete URL with parameters
    url = f'{base_url}?{station_params}&{parameter_params}&start_date={start_date}&end_date={end_date}'
    
    # Send HTTP GET request to fetch data
    response = requests.get(url)
    
    # Check if request was successful
    if response.status_code == 200:
        # Read CSV data directly from response content
        data = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        return data
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return None


# # Example usage:
# start_date = '2000-01-01'
# end_date = '2009-12-31'
# stations = ['08NB020','08NB014', '08NHX18', '08NB012', '08NH005']
# parameters = ['level', 'flow']

# # Call the function to fetch data
# water_data = fetch_water_data(start_date, end_date, stations, parameters)

# # Display the fetched data (assuming it's a DataFrame)
# if water_data is not None:
#     print(water_data.head())  # Display the first few rows of the fetched data
