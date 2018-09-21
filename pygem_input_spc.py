"""List of model inputs required to run PyGEM"""

# Built-in libraries
import os
from time import strftime
# External libraries
import pandas as pd
import pickle


def get_shean_glacier_nos(region_no, number_glaciers=0, option_random=0):
    """
    Generate list of glaciers that have calibration data and select number of glaciers to include.
    
    The list is currently sorted in terms of area such that the largest glaciers are modeled first.
    
    Parameters
    ----------
    region_no : int
        region number (Shean data available for regions 13, 14, and 15)
    number_glaciers : int
        number of glaciers to include in model run (default = 0)
    option_random : int
        option to select glaciers randomly for model run (default = 0, not random)
    
    Returns
    -------
    num : list of strings
        list of rgi glacier numbers
    """
    # safety, convert input to int
    region_no = int(region_no)
    # get shean's data, convert to dataframe, get
    # glacier numbers
    csv_path = '../DEMs/Shean_2018_0806/hma_mb_20180803_1229.csv'
    ds_all = pd.read_csv(csv_path)
    ds_reg = ds_all[(ds_all['RGIId'] > region_no) & (ds_all['RGIId'] < region_no + 1)].copy()
    if option_random == 1:
        ds_reg = ds_reg.sample(n=number_glaciers)
        ds_reg.reset_index(drop=True, inplace=True)
    else:
        ds_reg = ds_reg.sort_values('area_m2', ascending=False)
        ds_reg.reset_index(drop=True, inplace=True)
    rgi = ds_reg['RGIId']
    # get only glacier numbers, convert to string
    num = rgi % 1
    num = num.round(5)
    num = num.astype(str)
    # slice string to remove decimal
    num = [n[2:] for n in num]
    # make sure there are 5 digits
    for i in range(len(num)):
        while len(num[i]) < 5:
            num[i] += '0'
    if number_glaciers > 0:
        num = num[0:number_glaciers]
    return num

#%% MODEL PARAMETERS THAT ARE FREQUENTLY ADJUSTED DURING DEVELOPMENT
# ===== MCMC and ensemble selections ========
# Number of chains (min 1, max 3)
n_chains = 3
# number of MCMC samples to use
mcmc_sample_no = 100
mcmc_burn_no = 0
ensemble_no = mcmc_sample_no - mcmc_burn_no
#mcmc_step = 'am'
mcmc_step = None
thin_interval = 1

# ===== GLACIER SELECTION =====
# Region number 1st order (RGI V6.0) - HMA is 13, 14, 15
rgi_regionsO1 = [15]
#rgi_regionsO1 = [7]
#rgi_glac_number = ['00030']
# 2nd order region numbers (RGI V6.0)
rgi_regionsO2 = 'all'
# RGI glacier number (RGI V6.0)
#rgi_glac_number = 'all'
#rgi_glac_number = ['05152', '02793', '02790', '05153', '02827', '02828', '05141', '02842', '04148', '02847', '02826', 
#                   '02699', '02792', '02909', '06976', '04811', '07146', '03475', '06985', '03473']
#rgi_glac_number = ['05152', '03473']
#rgi_glac_number = ['03473']
if 'rgi_glac_number' not in locals():
    rgi_glac_number = get_shean_glacier_nos(rgi_regionsO1[0], 48, option_random=1)
#    with open('rgi_glac_number.pkl', 'wb') as f:
#        pickle.dump(rgi_glac_number, f)

# Reference climate dataset
ref_gcm_name = 'ERA-Interim' # used as default for argument parsers

# First year of model run
startyear = 2000
#  water year example: 2000 would start on October 1999, since October 1999 - September 2000 is the water year 2000
#  calendar year example: 2000 would start on January 2000
# Last year of model run
endyear = 2018
# Spin up time [years]
spinupyears = 0

# Synthetic simulation options
#  synthetic simulations refer to climate data that is created (ex. repeat 1990-2000 for the next 100 years) 
option_synthetic_sim = 0
synthetic_startyear = 1990
synthetic_endyear = 2000
synthetic_spinupyears = 0

# Remove NaN values (glaciers without calibration data)
option_removeNaNcal = 1
#  Option 0 (default) - do not remove these glaciers
#  Option 1 - remove glaciers without cal data
# Model setup directory
main_directory = os.getcwd()
modelsetup_dir = main_directory + '/../PyGEM_cal_setup/'

#%% ===== CALIBRATION OPTIONS =====
option_calibration = 2
#  Option 1 - calibration using minimization (returns single parameter set)
#  Option 2 - calibration using MCMC method (returns many parameter sets)


# MCMC export configuration
mcmc_output_fp = main_directory + '/../MCMC_data/'
mcmc_output_netcdf_fp = mcmc_output_fp + 'netcdf/'
mcmc_output_csv_fp = mcmc_output_fp + 'csv/'
mcmc_output_figs_fp = mcmc_output_fp + 'figures/'
mcmc_output_filename = ('parameter_sets_' + str(len(rgi_glac_number)) + 'glaciers_' + str(mcmc_sample_no) + 'samples_' 
                        + str(ensemble_no) + 'ensembles_' + str(strftime("%Y%m%d")) + '.nc')
mcmc_output_csv_fn = ('parameter_stats_' + str(len(rgi_glac_number)) + 'glaciers_' + str(n_chains) + 'chains_' + 
                      str(mcmc_sample_no) + 'iter_' + str(mcmc_burn_no) + 'burn_' + str(strftime("%Y%m%d")) + '.csv')
# MCMC distribution parameters
mcmc_distribution_type = 'truncnormal'
precfactor_mu = 0
precfactor_sigma = 1
precfactor_boundlow = -2
precfactor_boundhigh = 2
precfactor_start = precfactor_mu
tempchange_mu = 0
tempchange_sigma = 4
tempchange_boundlow = -10
tempchange_boundhigh = 10
tempchange_start = tempchange_mu
ddfsnow_mu = 0.0041
ddfsnow_sigma = 0.0015
ddfsnow_boundlow = ddfsnow_mu - 1.96 * ddfsnow_sigma 
ddfsnow_boundhigh = ddfsnow_mu + 1.96 * ddfsnow_sigma
ddfsnow_start=ddfsnow_mu

#%% MODEL PARAMETERS 
# Option to import calibration parameters for each glacier
option_import_modelparams = 0
#  Option 1 (default) - csv of glacier parameters
#  Option 0 - use the parameters set by the input
precfactor = 1
#  range 0.5 - 2
# Precipitation gradient on glacier [% m-1]
precgrad = 0.0001
#  range 0.0001 - 0.0010
# Degree-day factor of snow [m w.e. d-1 degC-1]
ddfsnow = 0.0041
#  range 2.6 - 5.1 * 10^-3
# Temperature adjustment [deg C]
tempchange = 0
#  range -10 to 10
# Lapse rate from gcm to glacier [K m-1]
lrgcm = -0.0065
# Lapse rate on glacier for bins [K m-1]
lrglac = -0.0065
#  k_p in Radic et al. (2013)
#  c_prec in Huss and Hock (2015)
# Degree-day factor of ice [m w.e. d-1 degC-1]
ddfice = 0.0041 / 0.7
#  note: '**' means to the power, so 10**-3 is 0.001
# Ratio degree-day factor snow snow to ice
ddfsnow_iceratio = 0.7
# Temperature threshold for snow [deg C]
tempsnow = 1.0
#   Huss and Hock (2015) T_snow = 1.5 deg C with +/- 1 deg C for ratios
#  facilitates calibration similar to Huss and Hock (2015)
# Frontal ablation  dictating rate [yr-1]
frontalablation_k = 2

# Calving option
option_frontalablation_k = 1
#  Option 1 (default) - use values as Huss and Hock (2015)
#  Option 2 - calibrate each glacier independently, use transfer functions for uncalibrated glaciers
# Calving parameter dictionary
#  according to Supplementary Table 3 in Huss and Hock (2015)
frontalablation_k0dict = {
            1:  3.4,
            2:  0,
            3:  0.2,
            4:  0.2,
            5:  0.5,
            6:  0.3,
            7:  0.5,
            8:  0,
            9:  0.2,
            10: 0,
            11: 0,
            12: 0,
            13: 0,
            14: 0,
            15: 0,
            16: 0,
            17: 6,
            18: 0,
            19: 1}

# Model parameters filepath, filename, and column names
modelparams_filepath = main_directory + '/../Calibration_datasets/'
#modelparams_filename = 'calparams_R15_20180306_nearest.csv'
#modelparams_filename = 'calparams_R15_20180305_fillnanavg.csv'
#modelparams_filename = 'calparams_R15_20180403_nearest.csv'
modelparams_filename = 'calparams_R15_20180403_nnbridx.csv'
#modelparams_filename = 'calparams_R14_20180313_fillnanavg.csv'
modelparams_colnames = ['lrgcm', 'lrglac', 'precfactor', 'precgrad', 'ddfsnow', 'ddfice', 'tempsnow', 'tempchange']

#%% CLIMATE DATA
# ERA-INTERIM (Reference data)
# Variable names
eraint_varnames = ['temperature', 'precipitation', 'geopotential', 'temperature_pressurelevels']
#  Note: do not change variable names as these are set to run with the download_erainterim_data.py script.
#        If option 2 is being used to calculate the lapse rates, then the pressure level data is unnecessary.
# Dates
eraint_start_date = '19790101'
eraint_end_date = '20180501'
# Resolution
grid_res = '0.5/0.5'
# Bounding box (N/W/S/E)
bounding_box = '90/0/-90/360'
# Lapse rate option
option_lr_method = 1
#  Option 0 - lapse rates are constant defined by input
#  Option 1 (default) - lapse rates derived from gcm pressure level temperature data (varies spatially and temporally)
#  Option 2 - lapse rates derived from surrounding pixels (varies spatially and temporally)
#    Note: Be careful with option 2 as the ocean vs land/glacier temperatures can causeƒ unrealistic inversions
# Filepath
eraint_fp = main_directory + '/../Climate_data/ERA_Interim/download/'
# Filenames
eraint_temp_fn = 'ERAInterim_Temp2m_DailyMeanMonthly_' + eraint_start_date + '_' + eraint_end_date + '.nc'
eraint_prec_fn = 'ERAInterim_TotalPrec_DailyMeanMonthly_' + eraint_start_date + '_' + eraint_end_date + '.nc'
eraint_elev_fn = 'ERAInterim_geopotential.nc'
eraint_pressureleveltemp_fn = 'ERAInterim_pressureleveltemp_' + eraint_start_date + '_' + eraint_end_date + '.nc'
eraint_lr_fn = ('ERAInterim_lapserates_' + eraint_start_date + '_' + eraint_end_date + '_opt' + str(option_lr_method) + 
                '_world.nc')

# CMIP5 (GCM data)
cmip5_fp_var_prefix = main_directory + '/../Climate_data/cmip5/'
cmip5_fp_var_ending = '_r1i1p1_monNG/'
cmip5_fp_fx_prefix = main_directory + '/../Climate_data/cmip5/'
cmip5_fp_fx_ending = '_r0i0p0_fx/'
cmip5_fp_lr = main_directory + '/../Climate_data/cmip5/bias_adjusted_1995_2100/2018_0524/'
cmip5_lr_fn = 'biasadj_mon_lravg_1995_2015_R15.csv'

#%% GLACIER DATA (RGI, ICE THICKNESS, ETC.)
# ===== RGI DATA =====
# Glacier selection option
option_glacier_selection = 1
#  Option 1 (default) - enter numbers associated with RGI V6.0
#  Option 2 - glaciers/regions selected via shapefile
#  Option 3 - glaciers/regions selected via new table (other inventory)
# Filepath for RGI files
rgi_filepath = main_directory + '/../RGI/rgi60/00_rgi60_attribs/'
# Column names
rgi_lat_colname = 'CenLat'
rgi_lon_colname = 'CenLon'
elev_colname = 'elev'
indexname = 'GlacNo'
rgi_O1Id_colname = 'glacno'
rgi_glacno_float_colname = 'RGIId_float'
# Column names from table to drop
rgi_cols_drop = ['GLIMSId','BgnDate','EndDate','Status','Connect','Linkages','Name']
# Dictionary of hypsometry filenames
rgi_dict = {
            1:  '01_rgi60_Alaska.csv',
            3:  '03_rgi60_ArcticCanadaNorth.csv',
            4:  '04_rgi60_ArcticCanadaSouth.csv',
            6:  '06_rgi60_Iceland.csv',
            7:  '07_rgi60_Svalbard.csv',
            8:  '08_rgi60_Scandinavia.csv',
            9:  '09_rgi60_RussianArctic.csv',
            13: '13_rgi60_CentralAsia.csv',
            14: '14_rgi60_SouthAsiaWest.csv',
            15: '15_rgi60_SouthAsiaEast.csv'}

# ===== ADDITIONAL DATA (hypsometry, ice thickness, width) =====
# Option to shift all elevation bins by 20 m
#  (required for Matthias' ice thickness and area since they are 20 m off, see email from May 24 2018)
option_shift_elevbins_20m = 1
# Elevation band height [m]
binsize = 10
# Filepath for the hypsometry files
hyps_filepath = main_directory + '/../IceThickness_Huss/bands_10m_DRR/'
# Dictionary of hypsometry filenames 
# (Files from Matthias Huss should be manually pre-processed to be 'RGI-ID', 'Cont_range', and bins starting at 5)
hyps_filedict = {
                1:  'area_01_Huss_Alaska_10m.csv',
                3:  'area_RGI03_10.csv',
                4:  'area_RGI04_10.csv',
                6:  'area_RGI06_10.csv',
                7:  'area_RGI07_10.csv',
                8:  'area_RGI08_10.csv',
                9:  'area_RGI09_10.csv',
                13: 'area_13_Huss_CentralAsia_10m.csv',
                14: 'area_14_Huss_SouthAsiaWest_10m.csv',
                15: 'area_15_Huss_SouthAsiaEast_10m.csv'}
# Extra columns in hypsometry data that will be dropped
hyps_colsdrop = ['RGI-ID','Cont_range']
# Filepath for the ice thickness files
thickness_filepath = main_directory + '/../IceThickness_Huss/bands_10m_DRR/'
# Dictionary of thickness filenames
thickness_filedict = {
                1:  'thickness_01_Huss_Alaska_10m.csv',
                3:  'thickness_RGI03_10.csv',
                4:  'thickness_RGI04_10.csv',
                6:  'thickness_RGI06_10.csv',
                7:  'thickness_RGI07_10.csv',
                8:  'thickness_RGI08_10.csv',
                9:  'thickness_RGI09_10.csv',
                13: 'thickness_13_Huss_CentralAsia_10m.csv',
                14: 'thickness_14_Huss_SouthAsiaWest_10m.csv',
                15: 'thickness_15_Huss_SouthAsiaEast_10m.csv'}
# Extra columns in ice thickness data that will be dropped
thickness_colsdrop = ['RGI-ID','Cont_range']
# Filepath for the width files
width_filepath = main_directory + '/../IceThickness_Huss/bands_10m_DRR/'
# Dictionary of thickness filenames
width_filedict = {
                1:  'width_01_Huss_Alaska_10m.csv',
                3:  'width_RGI03_10.csv',
                4:  'width_RGI04_10.csv',
                6:  'width_RGI06_10.csv',
                7:  'width_RGI07_10.csv',
                8:  'width_RGI08_10.csv',
                9:  'width_RGI09_10.csv',
                13: 'width_13_Huss_CentralAsia_10m.csv',
                14: 'width_14_Huss_SouthAsiaWest_10m.csv',
                15: 'width_15_Huss_SouthAsiaEast_10m.csv'}
# Extra columns in ice thickness data that will be dropped
width_colsdrop = ['RGI-ID','Cont_range']

#%% MODEL TIME FRAME DATA
# Note: models are required to have complete data for each year such that refreezing, scaling, etc. are consistent for
#       all time periods.
# Leap year option
option_leapyear = 1
#  Option 1 (default) - leap year days are included, i.e., every 4th year Feb 29th is included in the model, so
#                       days_in_month = 29 for these years.
#  Option 0 - exclude leap years, i.e., February always has 28 days
# Water year option
option_wateryear = 3
#  Option 1 (default) - water year (ex. 2000: Oct 1 1999 - Sept 1 2000)
#  Option 2 - calendar year
#  Option 3 - define start/end months and days (BE CAREFUL WHEN CUSTOMIZING USING OPTION 3 - DOUBLE CHECK YOUR DATES)
# User specified start/end dates
#  note: start and end dates must refer to whole years 
startmonthday = '06-01'
endmonthday = '05-31'
# Water year starting month
wateryear_month_start = 10
# First month of winter
winter_month_start = 10
#  for HMA, winter is considered  October 1 - April 30
# First month of summer
summer_month_start = 5
#  for HMA, summer is considered May 1 - September 30
# Option to use dates based on first of each month or those associated with the climate data
option_dates = 1
#  Option 1 (default) - use dates associated with the dates_table that user generates (first of each month)
#  Option 2 - use dates associated with the climate data (problem here is that this may differ between products)
# Model timestep
timestep = 'monthly'
#  enter 'monthly' or 'daily'
#  water year example: 2000 would end on September 2000
#  calendar year example: 2000 would end on December 2000

# Seasonal dictionaries for WGMS data that is not provided
lat_threshold = 75
# Winter (start/end) and Summer (start/end)
monthdict = {'northernmost': [9, 5, 6, 8],
             'north': [10, 4, 5, 9],
             'south': [4, 9, 10, 3],
             'southernmost': [3, 10, 11, 2]}

# Latitude threshold
# 01 - Alaska - < 75
# 02 - W Can - < 75
# 03 - N Can - > 74
# 04 - S Can - < 74
# 05 - Greenland - 60 - 80
# 06 - Iceland - < 75
# 07 - Svalbard - 70 - 80
# 08 - Scandinavia - < 70
# 09 - Russia - 72 - 82
# 10 - N Asia - 46 - 77


#%% CALIBRATION DATA (05/30/2018)
#  for each mass balance dataset, store the parameters here and add to the class

# ===== SHEAN GEODETIC =====
shean_fp = main_directory + '/../DEMs/Shean_2018_0806/'
shean_fn = 'hma_mb_20180803_1229.csv'
#shean_fn = 'hma_mb_20180803_1229_all_filled.csv'
shean_rgi_glacno_cn = 'RGIId'
shean_mb_cn = 'mb_mwea'
shean_mb_err_cn = 'mb_mwea_sigma'
shean_time1_cn = 't1'
shean_time2_cn = 't2'
shean_area_cn = 'area_m2'
#shean_vol_cn = 'mb_m3wea'
#shean_vol_err_cn = 'mb_m3wea_sigma'

# ===== BRUN GEODETIC =====
brun_fp = main_directory + '/../DEMs/'
brun_fn = 'Brun_Nature2017_MB_glacier-wide.csv'
brun_rgi_glacno_cn = 'GLA_ID'
brun_mb_cn = 'MB [m w.a a-1]'
brun_mb_err_cn = 'err. on MB [m w.e a-1]'
# NEED TO FINISH SETTING UP BRUN WITH CLASS_MBDATA

# ===== MAUER GEODETIC =====
mauer_fp = main_directory + '/../DEMs/'
mauer_fn = 'RupperMauer_GeodeticMassBalance_Himalayas_2000_2016.csv'
mauer_rgi_glacno_cn = 'id'
mauer_mb_cn = 'geoMassBal'
mauer_mb_err_cn = 'geoMassBalSig'
mauer_time1_cn = 'Year1'
mauer_time2_cn = 'Year2'
# NEED TO FINISH SETTING UP MAUER WITH CLASS_MBDATA

# ===== WGMS =====
wgms_datasets = ['wgms_d', 'wgms_ee']
#wgms_datasets = ['wgms_d']
wgms_fp = main_directory + '/../WGMS/DOI-WGMS-FoG-2018-06/'
wgms_rgi_glacno_cn = 'glacno'
wgms_obs_type_cn = 'obs_type'
# WGMS lookup tables information
wgms_lookup_fn = 'WGMS-FoG-2018-06-AA-GLACIER-ID-LUT.csv'
rgilookup_fullfn = main_directory + '/../RGI/rgi60/00_rgi60_links/00_rgi60_links.csv'
rgiv6_fn_prefix = main_directory + '/../RGI/rgi60/00_rgi60_attribs/' + '*'
rgiv5_fn_prefix = main_directory + '/../RGI/00_rgi50_attribs/' + '*'

# WGMS (d) geodetic mass balance information
wgms_d_fn = 'WGMS-FoG-2018-06-D-CHANGE.csv'
wgms_d_fn_preprocessed = 'wgms_d_rgiv6_preprocessed.csv'
wgms_d_thickness_chg_cn = 'THICKNESS_CHG'
wgms_d_thickness_chg_err_cn = 'THICKNESS_CHG_UNC'
wgms_d_volume_chg_cn = 'VOLUME_CHANGE'
wgms_d_volume_chg_err_cn = 'VOLUME_CHANGE_UNC'
wgms_d_z1_cn = 'LOWER_BOUND'
wgms_d_z2_cn = 'UPPER_BOUND'

# WGMS (e/ee) glaciological mass balance information
wgms_e_fn = 'WGMS-FoG-2018-06-E-MASS-BALANCE-OVERVIEW.csv'
wgms_ee_fn = 'WGMS-FoG-2018-06-EE-MASS-BALANCE.csv'
wgms_ee_fn_preprocessed = 'wgms_ee_rgiv6_preprocessed.csv' 
wgms_ee_mb_cn = 'BALANCE'
wgms_ee_mb_err_cn = 'BALANCE_UNC'
wgms_ee_t1_cn = 'YEAR'
wgms_ee_z1_cn = 'LOWER_BOUND'
wgms_ee_z2_cn = 'UPPER_BOUND'
wgms_ee_period_cn = 'period'

# ===== COGLEY DATA =====
cogley_fp = main_directory + '/../Calibration_datasets/'
cogley_fn_preprocessed = 'Cogley_Arctic_processed_wInfo.csv'
cogley_rgi_glacno_cn = 'glacno'
cogley_mass_chg_cn = 'geo_mass_kgm2a'
cogley_mass_chg_err_cn = 'geo_mass_unc'
cogley_z1_cn = 'Zmin'
cogley_z2_cn = 'Zmax'
cogley_obs_type_cn = 'obs_type'

# ===== REGIONAL DATA =====
# Regional data refers to all measurements that have lumped multiple glaciers together
#  - a dictionary linking the regions to RGIIds is required
mb_group_fp = main_directory + '/../Calibration_datasets/'
mb_group_dict_fn = 'mb_group_dict.csv'
mb_group_data_fn = 'mb_group_data.csv'
mb_group_t1_cn = 'begin_period'
mb_group_t2_cn = 'end_period'


# Minimization details
method_opt = 'SLSQP'
ftol_opt = 1e-2

# Limit potential mass balance for future simulations option
option_mb_envelope = 1

# Mass change tolerance [%] - required for calibration
masschange_tolerance = 0.1

# Mass balance uncertainty [mwea]
massbal_uncertainty_mwea = 0.1
# Z-score tolerance
#  all refers to tolerance if multiple calibration points
#  single refers to tolerance if only a single calibration point since we want this to be more exact
zscore_tolerance_all = 1
zscore_tolerance_single = 0.1

# Calibration output filename prefix (grid search)
calibrationnetcdf_filenameprefix = 'calibration_gridsearchcoarse_R'

#%% TRANSFER FUNCTIONS
# Slope of line of best fit for parameter vs. median elevation
#  These are derived from run_preprocessing.py option_parameter_relationships
#  If the relationship is not significant, then set the slope to 0
tempchange_lobf_property_cn = 'Zmed'
tempchange_lobf_slope = 0.0028212
precfactor_lobf_property_cn = 'Zmed'
precfactor_lobf_slope = -0.004693
ddfsnow_lobf_property_cn = 'Zmed'
ddfsnow_lobf_slope = 1.112333e-06
precgrad_lobf_property_cn = 'Zmed'
precgrad_lobf_slope = 0


#%% BIAS ADJUSTMENT OPTIONS (required for future simulations)
option_bias_adjustment = 1
#  Option 0 - ignore bias adjustments
#  Option 1 - bias adjustments using new technique 
#  Option 2 - bias adjustments using Huss and Hock [2015] methods
#  Option 3 - bias adjustments using monthly temp and prec
biasadj_data_filepath = main_directory + '/../Climate_data/cmip5/R15_rcp26_1995_2100/'
biasadj_params_filepath = main_directory + '/../Climate_data/cmip5/bias_adjusted_1995_2100/'
biasadj_fn_lr = 'biasadj_mon_lravg_1995_2100.csv'
biasadj_fn_ending = '_biasadj_opt1_1995_2100.csv'

#%% Mass balance model options
# Initial surface type options
option_surfacetype_initial = 1
#  Option 1 (default) - use median elevation to classify snow/firn above the median and ice below.
#   > Sakai et al. (2015) found that the decadal ELAs are consistent with the median elevation of nine glaciers in High
#     Mountain Asia, and Nuimura et al. (2015) also found that the snow line altitude of glaciers in China corresponded
#     well with the median elevation.  Therefore, the use of the median elevation for defining the initial surface type
#     appears to be a fairly reasonable assumption in High Mountain Asia.
#  Option 2 (Need to code) - use mean elevation instead
#  Option 3 (Need to code) - specify an AAR ratio and apply this to estimate initial conditions
# Firn surface type option
option_surfacetype_firn = 1
#  Option 1 (default) - firn is included
#  Option 0 - firn is not included
# Debris surface type option
option_surfacetype_debris = 0
#  Option 0 (default) - debris cover is not included
#  Option 1 - debris cover is included
#   > Load in Batu's debris maps and specify for each glacier
#   > Determine how DDF_debris will be included

# DDF firn
option_DDF_firn = 1
#  Option 1 (default) - DDF_firn is average of DDF_ice and DDF_snow (Huss and Hock, 2015)
#  Option 0 - DDF_firn equal to DDF_snow (m w.e. d-1 degC-1)
# DDF debris
ddfdebris = ddfice
# Reference elevation options for downscaling climate variables
option_elev_ref_downscale = 'Zmed'
#  Option 1 (default) - 'Zmed', median glacier elevation
#  Option 2 - 'Zmax', maximum glacier elevation
#  Option 3 - 'Zmin', minimum glacier elevation (terminus)
# Downscale temperature to bins options
option_temp2bins = 1
#  Option 1 (default) - lr_gcm and lr_glac to adjust temperature from gcm to the glacier bins
# Adjust temperatures based on changes in surface elevation option
option_adjusttemp_surfelev = 1
#  Option 1 (default) - yes, adjust temperature
#  Option 0 - do not adjust temperature
# Downscale precipitation to bins options
option_prec2bins = 1
#  Option 1 (default) - prec_factor and prec_grad to adjust precipitation from gcm to the glacier bins
# Accumulation erosion
option_preclimit = 1
#  Option 1 (default) - limit the uppermost 25% using an expontial fxn
# Accumulation options
option_accumulation = 2
#  Option 1 (default) - Single threshold (<= snow, > rain)
#  Option 2 - single threshold +/- 1 deg uses linear interpolation

# Surface type options
option_surfacetype = 1
#  How is surface type considered, annually?
# Surface ablation options
option_surfaceablation = 1
#  Option 1 (default) - DDF for snow, ice, and debris
# Refreezing model options
option_refreezing = 2
#  Option 1 (default) - heat conduction approach (Huss and Hock, 2015)
#  Option 2 - annual air temperature appraoch (Woodward et al., 1997)
# Refreeze depth [m]
refreeze_depth = 10
# Refreeze month
refreeze_month = 10
#  required for air temperature approach to set when the refreeze is included
# Melt model options
option_melt_model = 1
#  Option 1 (default) DDF
# Mass redistribution / Glacier geometry change options
option_massredistribution = 1
#  Option 1 (default) - Mass redistribution based on Huss and Hock (2015), i.e., volume gain/loss redistributed over the
#                       glacier using empirical normalized ice thickness change curves
# Cross-sectional glacier shape options
option_glaciershape = 1
#  Option 1(default) - parabolic (used by Huss and Hock, 2015)
#  Option 2 - rectangular, i.e., glacier lowering but area and width does not change
#  Option 3 - triangular
# Glacier width option
option_glaciershape_width = 1
#  Option 0 (default) - do not include
#  Option 1 - include
# Advancing glacier ice thickness change threshold
icethickness_advancethreshold = 5
#  Huss and Hock (2015) use a threshold of 5 m
# Percentage of glacier considered to be terminus
terminus_percentage = 20
#  Huss and Hock (2015) use 20% to calculate new area and ice thickness

#%% OUTPUT OPTIONS
# Output filepath
output_filepath = main_directory + '/../Output/'
# Netcdf filename prefix
netcdf_fn_prefix = 'PyGEM_R'
# Netcdf output package number
output_package = 2
    # Option 0 - no netcdf package
    # Option 1 - "raw package" [preferred units: m w.e.]
    #             monthly variables for each bin (temp, prec, acc, refreeze, snowpack, melt, frontalablation,
    #                                             massbal_clim)
    #             annual variables for each bin (area, icethickness, surfacetype)
    # Option 2 - "Glaciologist Package" output [units: m w.e. unless otherwise specified]:
    #             monthly glacier-wide variables (prec, acc, refreeze, melt, frontalablation, massbal_total, runoff, 
    #                                             snowline)
    #             annual glacier-wide variables (area, volume, ELA)


#%% WARNING MESSAGE OPTION
option_warningmessages = 1
#  Warning messages are a good check to make sure that the script is running properly, and small nuances due to
#  differences in input data (e.g., units associated with GCM air temperature data are correct)
#  Option 1 (default) - print warning messages within script that are meant to assist user
#                       currently these messages are only included in a few scripts (e.g., climate data)
#  Option 0 - do not print warning messages within script

#%% MODEL PROPERTIES 
# Density of ice [kg m-3]
density_ice = 900
# Density of water [kg m-3]
density_water = 1000
# Area of ocean [km2]
area_ocean = 362.5 * 10**6
# Heat capacity of ice [J K-1 kg-1]
ch_ice = 1.89 * 10**6
# Thermal conductivity of ice [W K-1 m-1]
k_ice = 2.33
# Model tolerance (used to remove low values caused by rounding errors)
tolerance = 1e-12
# Gravity [m s-2]
gravity = 9.81
# Standard pressure [Pa]
pressure_std = 101325
# Standard temperature [K]
temp_std = 288.15
# Universal gas constant [J mol-1 K-1]
R_gas = 8.3144598
# Molar mass of Earth's air [kg mol-1]
molarmass_air = 0.0289644
# Bulk flow parameter for frontal ablation (m^-0.5)
af = 0.7