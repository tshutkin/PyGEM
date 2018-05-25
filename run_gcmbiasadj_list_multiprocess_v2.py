r"""
preprocessing_gcmbiascorrections.py outputs the adjustment parameters for temperature and precipitation as well as the
mean monthly lapse rates derived via comparisons with the calibration climate dataset.  These will be used to correct 
the GCM climate data for future simulations.

How to run file?
  - In command line:
      change directory to folder with script
      python run_gcmbiascorrections_list_multiprocess.py C:\Users\David\Dave_Rounce\HiMAT\Climate_data\cmip5\gcm_rcpXX_f
      ilenames.txt
  - In spyder:
      %run run_gcmbiascorrections_list_multiprocess.py C:\Users\David\Dave_Rounce\HiMAT\Climate_data\cmip5\gcm_rcpXX_fil
      enames.txt

Adjustment Options:
  Option 1 (default) - adjust the temperature such that the positive degree days [degC*day] is equal, then adjust the
             precipitation such that the accumulation is equal.  Use these adjustments at the initial condition, then 
             optimize them such that the mass balance between the reference and GCM is equal.  This ensures that mass 
             changes are due to the GCM itself and not the bias adjustments.
  Option 2 - adjust mean monthly temperature and incorporate interannual variability and
             adjust mean monthly precipitation [Huss and Hock, 2015]
             (cumulative positive degree days [degC*day] is closer than Options 3 & 4, mean temp similar)
  Option 3 - adjust so the mean temperature is the same for both datasets
             (cumulative positive degree days [degC*day] can be significantly different, mean temp similar)
  Option 4 - adjust the mean monthly temperature to be the same for both datasets
             (cumulative positive degree days [degC*day] is closer than Option 1, mean temp similar)

Why use Option 1 instead of Huss and Hock [2015]?
      The model estimates mass balance.  In an ideal setting, the MB for each GCM over the calibration period would be
      equal.  Option 1 ensures that this is the case, which ensures that any mass changes in the future are strictly due
      to the GCM and not a result of run-away effects due to the bias adjustments.
      Huss and Hock [2015] on the other hand make the mean temperature fairly consistent while trying to capture the 
      interannual variability, but the changes to melt and accumulation could still theoretically be non-negligible.
"""

import pandas as pd
import numpy as np
import os
import argparse
import inspect
#import subprocess as sp
import multiprocessing
from scipy.optimize import minimize
import time
import matplotlib.pyplot as plt
from time import strftime

import pygem_input as input
import pygemfxns_modelsetup as modelsetup
import pygemfxns_climate as climate
import pygemfxns_massbalance as massbalance

#%% ===== SCRIPT SPECIFIC INPUT DATA ===== 
# Glacier selection
rgi_regionsO1 = [15]
rgi_glac_number = 'all'
#rgi_glac_number = ['03473', '03733']
#rgi_glac_number = ['06881']
#rgi_glac_number = ['00001', '00002', '00003', '00004', '00005', '00006', '00007', '00008', '03473', '03733']

# Required input
option_bias_adjustment = 1
gcm_endyear = 2015
output_filepath = input.main_directory + '/../Climate_data/cmip5/bias_adjusted_1995_2100/'
#output_filepath = input.main_directory + '/../Climate_data/cmip5/biasadj_comparison/'
gcm_filepath_var_prefix = input.main_directory + '/../Climate_data/cmip5/'
gcm_filepath_var_ending = '_r1i1p1_monNG/'
gcm_filepath_fx_prefix = input.main_directory + '/../Climate_data/cmip5/'
gcm_filepath_fx_ending = '_r0i0p0_fx/'
gcm_temp_fn_prefix = 'tas_mon_'
gcm_prec_fn_prefix = 'pr_mon_'
gcm_var_ending = '_r1i1p1_native.nc'
gcm_elev_fn_prefix  = 'orog_fx_'
gcm_fx_ending  = '_r0i0p0.nc'
gcm_startyear = 2000
gcm_spinupyears = 5
massbal_idx_start = 0  # 2000
massbal_idx_end = 16   # 2015
gcm_temp_varname = 'tas'
gcm_prec_varname = 'pr'
gcm_elev_varname = 'orog'
gcm_lat_varname = 'lat'
gcm_lon_varname = 'lon'
# Reference data
ref_name = 'ERA-Interim'
filepath_ref = input.main_directory + '/../Climate_data/ERA_Interim/' 
filename_ref_temp = input.gcmtemp_filedict[rgi_regionsO1[0]]
filename_ref_prec = input.gcmprec_filedict[rgi_regionsO1[0]]
filename_ref_elev = input.gcmelev_filedict[rgi_regionsO1[0]]
filename_ref_lr = input.gcmlapserate_filedict[rgi_regionsO1[0]]
# Calibrated model parameters
filepath_modelparams = input.main_directory + '/../Calibration_datasets/'
filename_modelparams = 'calibration_R15_20180403_Opt02solutionspaceexpanding_wnnbrs_20180523.csv'
modelparams_colnames = ['lrgcm', 'lrglac', 'precfactor', 'precgrad', 'ddfsnow', 'ddfice', 'tempsnow', 'tempchange']

#%% FUNCTIONS
def getparser():
    parser = argparse.ArgumentParser(description="run gcm bias corrections from gcm list in parallel")
    # add arguments
    parser.add_argument('gcm_file', action='store', type=str, default='gcm_rcpXX_filenames.txt', 
                        help='text file full of commands to run')
    parser.add_argument('-num_simultaneous_processes', action='store', type=int, default=5, 
                        help='number of simultaneous processes (cores) to use')
    parser.add_argument('-option_parallels', action='store', type=int, default=1,
                        help='Switch to use or not use paralles (1 - use parallels, 0 - do not)')
    parser.add_argument('--n_glaciers', action='store', type=int, default=500,
                        help='number of glaciers to split into each group for parallel processing')
    return parser


def main(list_packed_vars):
    # Unpack variables
    chunk = list_packed_vars[0]
    main_glac_rgi_all = list_packed_vars[1]
    chunk_size = list_packed_vars[2]
    gcm_name = list_packed_vars[3]
    
    time_start = time.time()
    parser = getparser()
    args = parser.parse_args()
    rcp_scenario = os.path.basename(args.gcm_file).split('_')[1]

    # ===== LOAD OTHER GLACIER DATA ===== 
    main_glac_rgi = main_glac_rgi_all.iloc[chunk:chunk + chunk_size, :]
    # Glacier hypsometry [km**2], total area
    main_glac_hyps = modelsetup.import_Husstable(main_glac_rgi, rgi_regionsO1, input.hyps_filepath, 
                                                 input.hyps_filedict, input.hyps_colsdrop)
    # Ice thickness [m], average
    main_glac_icethickness = modelsetup.import_Husstable(main_glac_rgi, rgi_regionsO1, input.thickness_filepath, 
                                                         input.thickness_filedict, input.thickness_colsdrop)
    # Width [km], average
    main_glac_width = modelsetup.import_Husstable(main_glac_rgi, rgi_regionsO1, input.width_filepath, 
                                                  input.width_filedict, input.width_colsdrop)
    elev_bins = main_glac_hyps.columns.values.astype(int)
    # Model parameters
    main_glac_modelparams_all = pd.read_csv(filepath_modelparams + filename_modelparams, index_col=0)
    main_glac_modelparams = main_glac_modelparams_all.loc[main_glac_rgi['O1Index'].values, :] 
    # Select dates including future projections
    dates_table, start_date, end_date = modelsetup.datesmodelrun(startyear=gcm_startyear, endyear=gcm_endyear, 
                                                                 spinupyears=gcm_spinupyears)
    
    # ===== LOAD CLIMATE DATA =====
    # Import air temperature, precipitation, lapse rates, and elevation from pre-processed csv files for a given region
    #  This saves time as opposed to running the nearest neighbor for the reference data as well
    ref_temp_all = np.genfromtxt(filepath_ref + filename_ref_temp, delimiter=',')
    ref_prec_all = np.genfromtxt(filepath_ref + filename_ref_prec, delimiter=',')
    ref_elev_all = np.genfromtxt(filepath_ref + filename_ref_elev, delimiter=',')
    ref_lr_all = np.genfromtxt(filepath_ref + filename_ref_lr, delimiter=',')
    # Select the climate data for the glaciers included in the study
    ref_temp = ref_temp_all[main_glac_rgi['O1Index'].values]
    ref_prec = ref_prec_all[main_glac_rgi['O1Index'].values]
    ref_elev = ref_elev_all[main_glac_rgi['O1Index'].values]
    ref_lr = ref_lr_all[main_glac_rgi['O1Index'].values]
    # Monthly lapse rate
    ref_lr_monthly_avg = (ref_lr.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
                          .reshape(12,-1).transpose())
    # Days per month
    daysinmonth = dates_table['daysinmonth'].values[0:ref_temp.shape[1]]
    dates_table_subset = dates_table.iloc[0:ref_temp.shape[1],:]
    
    # LOAD GCM DATA
    gcm_filepath_var = gcm_filepath_var_prefix + rcp_scenario + gcm_filepath_var_ending
    gcm_filepath_fx = gcm_filepath_fx_prefix + rcp_scenario + gcm_filepath_fx_ending
    gcm_temp_fn = gcm_temp_fn_prefix + gcm_name + '_' + rcp_scenario + gcm_var_ending
    gcm_prec_fn = gcm_prec_fn_prefix + gcm_name + '_' + rcp_scenario + gcm_var_ending
    gcm_elev_fn = gcm_elev_fn_prefix + gcm_name + '_' + rcp_scenario + gcm_fx_ending
    gcm_temp, gcm_dates = climate.importGCMvarnearestneighbor_xarray(
            gcm_temp_fn, gcm_temp_varname, main_glac_rgi, dates_table, start_date, end_date, 
            filepath=gcm_filepath_var, gcm_lon_varname=gcm_lon_varname, gcm_lat_varname=gcm_lat_varname)
    gcm_prec, gcm_dates = climate.importGCMvarnearestneighbor_xarray(
            gcm_prec_fn, gcm_prec_varname, main_glac_rgi, dates_table, start_date, end_date, 
            filepath=gcm_filepath_var, gcm_lon_varname=gcm_lon_varname, gcm_lat_varname=gcm_lat_varname)
    gcm_elev = climate.importGCMfxnearestneighbor_xarray(
            gcm_elev_fn, gcm_elev_varname, main_glac_rgi, filepath=gcm_filepath_fx, 
            gcm_lon_varname=gcm_lon_varname, gcm_lat_varname=gcm_lat_varname)    
    # Monthly lapse rate
    gcm_lr = np.tile(ref_lr_monthly_avg, int(gcm_temp.shape[1]/12))
    # GCM subset to agree with reference time period to calculate bias corrections
    gcm_temp_subset = gcm_temp[:,0:ref_temp.shape[1]]
    gcm_prec_subset = gcm_prec[:,0:ref_temp.shape[1]]
    gcm_lr_subset = gcm_lr[:,0:ref_temp.shape[1]]

    # ===== BIAS CORRECTIONS =====
    # OPTION 1: Adjust temp and prec such that ref and GCM mass balances over calibration period are equal
    if option_bias_adjustment == 1:
        # Bias adjustment parameters
        main_glac_bias_adj_colnames = ['RGIId', 'ref', 'GCM', 'rcp_scenario', 'temp_adj', 'prec_adj', 'ref_mb_mwea', 
                                       'ref_vol_change_perc', 'gcm_mb_mwea', 'gcm_vol_change_perc', 'lrgcm', 'lrglac', 
                                       'precfactor', 'precgrad', 'ddfsnow', 'ddfice', 'tempsnow', 'tempchange']
        main_glac_bias_adj = pd.DataFrame(np.zeros((main_glac_rgi.shape[0],len(main_glac_bias_adj_colnames))), 
                                          columns=main_glac_bias_adj_colnames)
        main_glac_bias_adj['RGIId'] = main_glac_rgi['RGIId'].values
        main_glac_bias_adj['ref'] = ref_name
        main_glac_bias_adj['GCM'] = gcm_name
        main_glac_bias_adj['rcp_scenario'] = rcp_scenario
        main_glac_bias_adj[input.modelparams_colnames] = main_glac_modelparams[input.modelparams_colnames].values

        # BIAS ADJUSTMENT CALCULATIONS
        for glac in range(main_glac_rgi.shape[0]): 
            if glac%200 == 0:
                print(gcm_name,':', main_glac_rgi.loc[main_glac_rgi.index.values[glac],'RGIId'])    
            glacier_rgi_table = main_glac_rgi.iloc[glac, :]
            glacier_area_t0 = main_glac_hyps.iloc[glac,:].values.astype(float)
            icethickness_t0 = main_glac_icethickness.iloc[glac,:].values.astype(float)
            width_t0 = main_glac_width.iloc[glac,:].values.astype(float)
            modelparameters = main_glac_modelparams.loc[main_glac_modelparams.index.values[glac],modelparams_colnames]
            glac_idx_t0 = glacier_area_t0.nonzero()[0]
            
            if icethickness_t0.max() > 0:  
                surfacetype, firnline_idx = massbalance.surfacetypebinsinitial(glacier_area_t0, glacier_rgi_table, 
                                                                               elev_bins)
                surfacetype_ddf_dict = massbalance.surfacetypeDDFdict(modelparameters, option_DDF_firn=0)
                #  option_DDF_firn=0 uses DDF_snow in accumulation area because not account for snow vs. firn here
                surfacetype_ddf = np.zeros(glacier_area_t0.shape)
                for surfacetype_idx in surfacetype_ddf_dict: 
                    surfacetype_ddf[surfacetype == surfacetype_idx] = surfacetype_ddf_dict[surfacetype_idx]
                # Reference data
                glacier_ref_temp = ref_temp[glac,:]
                glacier_ref_prec = ref_prec[glac,:]
                glacier_ref_elev = ref_elev[glac]
                glacier_ref_lrgcm = ref_lr[glac,:]
                glacier_ref_lrglac = ref_lr[glac,:]
                # GCM data
                glacier_gcm_temp = gcm_temp_subset[glac,:]
                glacier_gcm_prec = gcm_prec_subset[glac,:]
                glacier_gcm_elev = gcm_elev[glac]
                glacier_gcm_lrgcm = gcm_lr_subset[glac,:]
                glacier_gcm_lrglac = gcm_lr_subset[glac,:]
                
                # AIR TEMPERATURE: Downscale the gcm temperature [deg C] to each bin
                if input.option_temp2bins == 1:
                    #  T_bin = T_gcm + lr_gcm * (z_ref - z_gcm) + lr_glac * (z_bin - z_ref) + tempchange
                    glac_bin_temp_ref = (
                            glacier_ref_temp + glacier_ref_lrgcm * 
                            (glacier_rgi_table.loc[input.option_elev_ref_downscale] - glacier_ref_elev) + 
                            glacier_ref_lrglac * (elev_bins - 
                            glacier_rgi_table.loc[input.option_elev_ref_downscale])[:,np.newaxis] 
                            + modelparameters['tempchange'])
                    glac_bin_temp_gcm = (
                            glacier_gcm_temp + glacier_gcm_lrgcm * 
                            (glacier_rgi_table.loc[input.option_elev_ref_downscale] - glacier_gcm_elev) + 
                            glacier_gcm_lrglac * (elev_bins - 
                            glacier_rgi_table.loc[input.option_elev_ref_downscale])[:,np.newaxis] 
                            + modelparameters['tempchange'])
                # remove off-glacier values
                glac_bin_temp_ref[glacier_area_t0==0,:] = 0
                glac_bin_temp_gcm[glacier_area_t0==0,:] = 0
                # TEMPERATURE BIAS CORRECTIONS
                # Energy available for melt [degC day]    
                melt_energy_available_ref = glac_bin_temp_ref * daysinmonth
                melt_energy_available_ref[melt_energy_available_ref < 0] = 0
                # Melt [mwe for each month]
                melt_ref = melt_energy_available_ref * surfacetype_ddf[:,np.newaxis]
                # Melt volume total [mwe * km2]
                melt_vol_ref = (melt_ref * glacier_area_t0[:,np.newaxis]).sum()
                # Optimize bias adjustment such that PDD are equal                
                def objective(bias_adj_glac):
                    glac_bin_temp_gcm_adj = glac_bin_temp_gcm + bias_adj_glac
                    melt_energy_available_gcm = glac_bin_temp_gcm_adj * daysinmonth
                    melt_energy_available_gcm[melt_energy_available_gcm < 0] = 0
                    melt_gcm = melt_energy_available_gcm * surfacetype_ddf[:,np.newaxis]
                    melt_vol_gcm = (melt_gcm * glacier_area_t0[:,np.newaxis]).sum()
                    return abs(melt_vol_ref - melt_vol_gcm)
                # - initial guess
                bias_adj_init = 0      
                # - run optimization
                bias_adj_temp_opt = minimize(objective, bias_adj_init, method='SLSQP', tol=1e-5)
                bias_adj_temp_init = bias_adj_temp_opt.x
                glac_bin_temp_gcm_adj = glac_bin_temp_gcm + bias_adj_temp_init
                # PRECIPITATION/ACCUMULATION: Downscale the precipitation (liquid and solid) to each bin
                glac_bin_acc_ref = np.zeros(glac_bin_temp_ref.shape)
                glac_bin_acc_gcm = np.zeros(glac_bin_temp_ref.shape)
                glac_bin_prec_ref = np.zeros(glac_bin_temp_ref.shape)
                glac_bin_prec_gcm = np.zeros(glac_bin_temp_ref.shape)
                if input.option_prec2bins == 1:
                    # Precipitation using precipitation factor and precipitation gradient
                    #  P_bin = P_gcm * prec_factor * (1 + prec_grad * (z_bin - z_ref))
                    glac_bin_precsnow_ref = (glacier_ref_prec * modelparameters['precfactor'] * 
                                             (1 + modelparameters['precgrad'] * (elev_bins - 
                                             glacier_rgi_table.loc[input.option_elev_ref_downscale]))[:,np.newaxis])
                    glac_bin_precsnow_gcm = (glacier_gcm_prec * modelparameters['precfactor'] * 
                                             (1 + modelparameters['precgrad'] * (elev_bins - 
                                             glacier_rgi_table.loc[input.option_elev_ref_downscale]))[:,np.newaxis])
                # Option to adjust prec of uppermost 25% of glacier for wind erosion and reduced moisture content
                if input.option_preclimit == 1:
                    # If elevation range > 1000 m, apply corrections to uppermost 25% of glacier (Huss and Hock, 2015)
                    if elev_bins[glac_idx_t0[-1]] - elev_bins[glac_idx_t0[0]] > 1000:
                        # Indices of upper 25%
                        glac_idx_upper25 = glac_idx_t0[(glac_idx_t0 - glac_idx_t0[0] + 1) / glac_idx_t0.shape[0] * 100 > 75]   
                        # Exponential decay according to elevation difference from the 75% elevation
                        #  prec_upper25 = prec * exp(-(elev_i - elev_75%)/(elev_max- - elev_75%))
                        glac_bin_precsnow_ref[glac_idx_upper25,:] = (
                                glac_bin_precsnow_ref[glac_idx_upper25[0],:] * np.exp(-1*(elev_bins[glac_idx_upper25] - 
                                elev_bins[glac_idx_upper25[0]]) / (elev_bins[glac_idx_upper25[-1]] - 
                                elev_bins[glac_idx_upper25[0]]))[:,np.newaxis])
                        glac_bin_precsnow_gcm[glac_idx_upper25,:] = (
                                glac_bin_precsnow_gcm[glac_idx_upper25[0],:] * np.exp(-1*(elev_bins[glac_idx_upper25] - 
                                elev_bins[glac_idx_upper25[0]]) / (elev_bins[glac_idx_upper25[-1]] - 
                                elev_bins[glac_idx_upper25[0]]))[:,np.newaxis])
                        # Precipitation cannot be less than 87.5% of the maximum accumulation elsewhere on the glacier
                        for month in range(glac_bin_precsnow_ref.shape[1]):
                            glac_bin_precsnow_ref[glac_idx_upper25[(glac_bin_precsnow_ref[glac_idx_upper25,month] < 0.875 * 
                            glac_bin_precsnow_ref[glac_idx_t0,month].max()) & 
                            (glac_bin_precsnow_ref[glac_idx_upper25,month] != 0)], month] = (
                                                                0.875 * glac_bin_precsnow_ref[glac_idx_t0,month].max())
                            glac_bin_precsnow_gcm[glac_idx_upper25[(glac_bin_precsnow_gcm[glac_idx_upper25,month] < 0.875 * 
                            glac_bin_precsnow_gcm[glac_idx_t0,month].max()) & 
                            (glac_bin_precsnow_gcm[glac_idx_upper25,month] != 0)], month] = (
                                                                0.875 * glac_bin_precsnow_gcm[glac_idx_t0,month].max())
                # Separate total precipitation into liquid (glac_bin_prec) and solid (glac_bin_acc)
                if input.option_accumulation == 1:
                    # if temperature above threshold, then rain
                    glac_bin_prec_ref[glac_bin_temp_ref > modelparameters['tempsnow']] = (
                        glac_bin_precsnow_ref[glac_bin_temp_ref > modelparameters['tempsnow']])
                    glac_bin_prec_gcm[glac_bin_temp_gcm_adj > modelparameters['tempsnow']] = (
                        glac_bin_precsnow_gcm[glac_bin_temp_gcm_adj > modelparameters['tempsnow']])
                    # if temperature below threshold, then snow
                    glac_bin_acc_ref[glac_bin_temp_ref <= modelparameters['tempsnow']] = (
                        glac_bin_precsnow_ref[glac_bin_temp_ref <= modelparameters['tempsnow']])
                    glac_bin_acc_gcm[glac_bin_temp_gcm_adj <= modelparameters['tempsnow']] = (
                        glac_bin_precsnow_gcm[glac_bin_temp_gcm_adj <= modelparameters['tempsnow']])
                elif input.option_accumulation == 2:
                    # If temperature between min/max, then mix of snow/rain using linear relationship between min/max
                    glac_bin_prec_ref = (
                            (1/2 + (glac_bin_temp_ref - modelparameters['tempsnow']) / 2) * glac_bin_precsnow_ref)
                    glac_bin_prec_gcm = (
                            (1/2 + (glac_bin_temp_gcm_adj - modelparameters['tempsnow']) / 2) * glac_bin_precsnow_gcm)
                    glac_bin_acc_ref = glac_bin_precsnow_ref - glac_bin_prec_ref
                    glac_bin_acc_gcm = glac_bin_precsnow_gcm - glac_bin_prec_gcm
                    # If temperature above maximum threshold, then all rain
                    glac_bin_prec_ref[glac_bin_temp_ref > modelparameters['tempsnow'] + 1] = (
                        glac_bin_precsnow_ref[glac_bin_temp_ref > modelparameters['tempsnow'] + 1])
                    glac_bin_prec_gcm[glac_bin_temp_gcm_adj > modelparameters['tempsnow'] + 1] = (
                        glac_bin_precsnow_gcm[glac_bin_temp_gcm_adj > modelparameters['tempsnow'] + 1])
                    glac_bin_acc_ref[glac_bin_temp_ref > modelparameters['tempsnow'] + 1] = 0
                    glac_bin_acc_gcm[glac_bin_temp_gcm_adj > modelparameters['tempsnow'] + 1] = 0
                    # If temperature below minimum threshold, then all snow
                    glac_bin_acc_ref[glac_bin_temp_ref <= modelparameters['tempsnow'] - 1] = (
                            glac_bin_precsnow_ref[glac_bin_temp_ref <= modelparameters['tempsnow'] - 1])
                    glac_bin_acc_gcm[glac_bin_temp_gcm_adj <= modelparameters['tempsnow'] - 1] = (
                            glac_bin_precsnow_gcm[glac_bin_temp_gcm_adj <= modelparameters['tempsnow'] - 1])
                    glac_bin_prec_ref[glac_bin_temp_ref <= modelparameters['tempsnow'] - 1] = 0
                    glac_bin_prec_gcm[glac_bin_temp_gcm_adj <= modelparameters['tempsnow'] - 1] = 0
                # remove off-glacier values
                glac_bin_acc_ref[glacier_area_t0==0,:] = 0
                glac_bin_acc_gcm[glacier_area_t0==0,:] = 0
                glac_bin_prec_ref[glacier_area_t0==0,:] = 0
                glac_bin_prec_gcm[glacier_area_t0==0,:] = 0
                # account for hypsometry
                glac_bin_acc_ref_warea = glac_bin_acc_ref * glacier_area_t0[:,np.newaxis]
                glac_bin_acc_gcm_warea = glac_bin_acc_gcm * glacier_area_t0[:,np.newaxis]
                # precipitation bias adjustment
                bias_adj_prec_init = glac_bin_acc_ref_warea.sum() / glac_bin_acc_gcm_warea.sum()
    
                # BIAS ADJUSTMENT PARAMETER OPTIMIZATION such that mass balance between two datasets are equal 
                bias_adj_params = np.zeros((2))
                bias_adj_params[0] = bias_adj_temp_init
                bias_adj_params[1] = bias_adj_prec_init        
                
                def objective_2(bias_adj_params):
                    # Reference data
                    # Mass balance
                    (glac_bin_temp, glac_bin_prec, glac_bin_acc, glac_bin_refreeze, glac_bin_snowpack, glac_bin_melt, 
                     glac_bin_frontalablation, glac_bin_massbalclim, glac_bin_massbalclim_annual, glac_bin_area_annual, 
                     glac_bin_icethickness_annual, glac_bin_width_annual, glac_bin_surfacetype_annual, 
                     glac_wide_massbaltotal, glac_wide_runoff, glac_wide_snowline, glac_wide_snowpack, 
                     glac_wide_area_annual, glac_wide_volume_annual, glac_wide_ELA_annual) = (
                        massbalance.runmassbalance(modelparameters, glacier_rgi_table, glacier_area_t0, icethickness_t0, 
                                                   width_t0, elev_bins, glacier_ref_temp, glacier_ref_prec, 
                                                   glacier_ref_elev, glacier_ref_lrgcm, glacier_ref_lrglac, 
                                                   dates_table_subset, option_calibration=1))
                    # Annual glacier-wide mass balance [m w.e.]
                    glac_wide_massbaltotal_annual_ref = np.sum(glac_wide_massbaltotal.reshape(-1,12), axis=1)
                    # Average annual glacier-wide mass balance [m w.e.a.]
                    mb_mwea_ref = glac_wide_massbaltotal_annual_ref.mean()
                    
                    # GCM data
                    # Bias corrections
                    glacier_gcm_temp_adj = glacier_gcm_temp + bias_adj_params[0]
                    glacier_gcm_prec_adj = glacier_gcm_prec * bias_adj_params[1]
                    
                    # Mass balance
                    (glac_bin_temp, glac_bin_prec, glac_bin_acc, glac_bin_refreeze, glac_bin_snowpack, glac_bin_melt, 
                     glac_bin_frontalablation, glac_bin_massbalclim, glac_bin_massbalclim_annual, glac_bin_area_annual, 
                     glac_bin_icethickness_annual, glac_bin_width_annual, glac_bin_surfacetype_annual, 
                     glac_wide_massbaltotal, glac_wide_runoff, glac_wide_snowline, glac_wide_snowpack, 
                     glac_wide_area_annual, glac_wide_volume_annual, glac_wide_ELA_annual) = (
                        massbalance.runmassbalance(modelparameters, glacier_rgi_table, glacier_area_t0, icethickness_t0, 
                                                   width_t0, elev_bins, glacier_gcm_temp_adj, glacier_gcm_prec_adj, 
                                                   glacier_gcm_elev, glacier_gcm_lrgcm, glacier_gcm_lrglac, 
                                                   dates_table_subset, option_calibration=1))
                    # Annual glacier-wide mass balance [m w.e.]
                    glac_wide_massbaltotal_annual_gcm = np.sum(glac_wide_massbaltotal.reshape(-1,12), axis=1)
                    # Average annual glacier-wide mass balance [m w.e.a.]
                    mb_mwea_gcm = glac_wide_massbaltotal_annual_gcm.mean()
                    return abs(mb_mwea_ref - mb_mwea_gcm)
                # CONSTRAINTS
                #  everything goes on one side of the equation compared to zero
                def constraint_temp_prec(bias_adj_params):
                    return -1 * (bias_adj_params[0] * (bias_adj_params[1] - 1))
                    #  To avoid increases/decreases in temp compensating for increases/decreases in prec, respectively,
                    #  ensure that if temp increases, then prec decreases, and vice versa.  This works because
                    #  (prec_adj - 1) is positive or negative for increases or decrease, respectively, so multiplying 
                    #  this by temp_adj gives a positive or negative value.  We want it to always be negative, but since 
                    #  inequality constraint is for >= 0, we multiply it by -1.
                # Define constraint type for each function
                con_temp_prec = {'type':'ineq', 'fun':constraint_temp_prec}
                #  inequalities are non-negative, i.e., >= 0
                # Select constraints used to optimize precfactor
                cons = [con_temp_prec]
                # INITIAL GUESS
                bias_adj_params_init = bias_adj_params          
                # Run the optimization
                bias_adj_params_opt_raw = minimize(objective_2, bias_adj_params_init, method='SLSQP', constraints=cons,
                                                   tol=1e-3)
                # Record the optimized parameters
                bias_adj_params_opt = bias_adj_params_opt_raw.x
                main_glac_bias_adj.loc[glac, ['temp_adj', 'prec_adj']] = bias_adj_params_opt 
            
                # Compute mass balances to have output data
                # Reference data
                (glac_bin_temp, glac_bin_prec, glac_bin_acc, glac_bin_refreeze, glac_bin_snowpack, glac_bin_melt, 
                 glac_bin_frontalablation, glac_bin_massbalclim, glac_bin_massbalclim_annual, glac_bin_area_annual, 
                 glac_bin_icethickness_annual, glac_bin_width_annual, glac_bin_surfacetype_annual, 
                 glac_wide_massbaltotal, glac_wide_runoff, glac_wide_snowline, glac_wide_snowpack, 
                 glac_wide_area_annual, glac_wide_volume_annual, glac_wide_ELA_annual) = (
                    massbalance.runmassbalance(modelparameters, glacier_rgi_table, glacier_area_t0, icethickness_t0, 
                                               width_t0, elev_bins, glacier_ref_temp, glacier_ref_prec, 
                                               glacier_ref_elev, glacier_ref_lrgcm, glacier_ref_lrglac, 
                                               dates_table_subset, option_calibration=1))
                # Annual glacier-wide mass balance [m w.e.]
                glac_wide_massbaltotal_annual_ref = np.sum(glac_wide_massbaltotal.reshape(-1,12), axis=1)
                # Average annual glacier-wide mass balance [m w.e.a.]
                mb_mwea_ref = glac_wide_massbaltotal_annual_ref.mean()
                #  units: m w.e. based on initial area
                # Volume change [%]
                if icethickness_t0.max() > 0:
                    glac_vol_change_perc_ref = (mb_mwea_ref / 1000 * glac_wide_area_annual[0] * 
                                                glac_wide_massbaltotal_annual_ref.shape[0] / glac_wide_volume_annual[0] 
                                                * 100)
                # Record reference results
                main_glac_bias_adj.loc[glac, ['ref_mb_mwea', 'ref_vol_change_perc']] = (
                        [mb_mwea_ref, glac_vol_change_perc_ref])
                
                # Climate data
                # Bias corrections
                glacier_gcm_temp_adj = glacier_gcm_temp + bias_adj_params_opt[0]
                glacier_gcm_prec_adj = glacier_gcm_prec * bias_adj_params_opt[1]
                (glac_bin_temp, glac_bin_prec, glac_bin_acc, glac_bin_refreeze, glac_bin_snowpack, glac_bin_melt, 
                 glac_bin_frontalablation, glac_bin_massbalclim, glac_bin_massbalclim_annual, glac_bin_area_annual, 
                 glac_bin_icethickness_annual, glac_bin_width_annual, glac_bin_surfacetype_annual, 
                 glac_wide_massbaltotal, glac_wide_runoff, glac_wide_snowline, glac_wide_snowpack, 
                 glac_wide_area_annual, glac_wide_volume_annual, glac_wide_ELA_annual) = (
                    massbalance.runmassbalance(modelparameters, glacier_rgi_table, glacier_area_t0, icethickness_t0, 
                                               width_t0, elev_bins, glacier_gcm_temp_adj, glacier_gcm_prec_adj, 
                                               glacier_gcm_elev, glacier_gcm_lrgcm, glacier_gcm_lrglac, 
                                               dates_table_subset, option_calibration=1))
                # Annual glacier-wide mass balance [m w.e.]
                glac_wide_massbaltotal_annual_gcm = np.sum(glac_wide_massbaltotal.reshape(-1,12), axis=1)
                # Average annual glacier-wide mass balance [m w.e.a.]
                mb_mwea_gcm = glac_wide_massbaltotal_annual_gcm.mean()
                #  units: m w.e. based on initial area
                # Volume change [%]
                if icethickness_t0.max() > 0:
                    glac_vol_change_perc_gcm = (mb_mwea_gcm / 1000 * glac_wide_area_annual[0] * 
                                                glac_wide_massbaltotal_annual_gcm.shape[0] / glac_wide_volume_annual[0] 
                                                * 100) 
                # Record GCM results
                main_glac_bias_adj.loc[glac, ['gcm_mb_mwea', 'gcm_vol_change_perc']] = (
                        [mb_mwea_gcm, glac_vol_change_perc_gcm])
#                print(mb_mwea_ref, glac_vol_change_perc_ref)
#                print(mb_mwea_gcm, glac_vol_change_perc_gcm)
                
        # EXPORT THE ADJUSTMENT VARIABLES (greatly reduces space)
        # Set up directory to store climate data
        if os.path.exists(output_filepath) == False:
            os.makedirs(output_filepath)
        # Temperature and precipitation parameters
        output_biasadjparams_fn = (gcm_name + '_' + rcp_scenario + '_biasadj_opt1_' + 
                                   str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '_' + 
                                   str(strftime("%Y%m%d")) + '_' + str(chunk) + '.csv')
        main_glac_bias_adj.to_csv(output_filepath + output_biasadjparams_fn)
        # Lapse rate parameters (same for all GCMs - only need to export once)
        output_filename_lr = ('biasadj_mon_lravg_' + str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) +
                              '_' + str(chunk) + '.csv')
        if os.path.exists(output_filepath + output_filename_lr) == False:
            np.savetxt(output_filepath + output_filename_lr, ref_lr_monthly_avg, delimiter=",")
        

    # Export variables as global to view in variable explorer
    if (args.option_parallels == 0) or (main_glac_rgi_all.shape[0] < 2 * args.num_simultaneous_processes):
        global main_vars
        main_vars = inspect.currentframe().f_locals

    print('\nProcessing time of', gcm_name, 'for', chunk,':',time.time()-time_start, 's')

#%% PARALLEL PROCESSING
if __name__ == '__main__':
    time_start = time.time()
    parser = getparser()
    args = parser.parse_args()
    
    # Select glaciers and define chunks
    main_glac_rgi_all = modelsetup.selectglaciersrgitable(rgi_regionsO1=rgi_regionsO1, rgi_regionsO2 = 'all', 
                                                          rgi_glac_number=rgi_glac_number)
    chunk_size = int(np.ceil(main_glac_rgi_all.shape[0] / args.num_simultaneous_processes))
    
    # Read GCM names from command file
    with open(args.gcm_file, 'r') as gcm_fn:
        gcm_list = gcm_fn.read().splitlines()
        rcp_scenario = os.path.basename(args.gcm_file).split('_')[1]
        print('Found %d gcms to process'%(len(gcm_list)))
        
    # Loop through all GCMs
    for gcm_name in gcm_list:
        print('Processing:', gcm_name)
        # Pack variables for multiprocessing
        list_packed_vars = [] 
        for chunk in range(0, main_glac_rgi_all.shape[0], chunk_size):
            list_packed_vars.append([chunk, main_glac_rgi_all, chunk_size, gcm_name])
        
        # Parallel processing
        if (args.option_parallels != 0) and (main_glac_rgi_all.shape[0] >= 2 * args.num_simultaneous_processes):
            with multiprocessing.Pool(args.num_simultaneous_processes) as p:
                p.map(main,list_packed_vars)
        
        # No parallel processing
        else:
            # Loop through the chunks and export bias adjustments
            for n in range(len(list_packed_vars)):
                main(list_packed_vars[n])                                
         
        # Combine output into single package and 
        if option_bias_adjustment == 1:
            output_biasadj_prefix = (gcm_name + '_' + rcp_scenario + '_biasadj_opt1_' + 
                                     str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '_')
            output_lr_prefix = 'biasadj_mon_lravg_'
        biasadj_list = []
        lr_list = []
        for i in os.listdir(output_filepath):
            # Append bias adjustment results
            if i.startswith(output_biasadj_prefix) == True:
                biasadj_list.append(i)
                if len(biasadj_list) == 1:
                    biasadj_all = pd.read_csv(output_filepath + i, index_col=0)
                else:
                    biasadj_2join = pd.read_csv(output_filepath + i, index_col=0)
                    biasadj_all = biasadj_all.append(biasadj_2join, ignore_index=True)
                # Remove file after its been merged
                os.remove(output_filepath + i)
            # Append lapse rates
            if i.startswith(output_lr_prefix) == True:
                lr_list.append(i)
                if len(lr_list) == 1:
                    lr_all = np.genfromtxt(output_filepath + i, delimiter=',')
                else:
                    lr_2join = np.genfromtxt(output_filepath + i, delimiter=',')
                    if lr_2join.shape[0] == lr_all.shape[1]:
                        lr_2join.shape = (1,lr_all.shape[1])
                    lr_all = np.concatenate((lr_all, lr_2join), axis=0)
                # Remove file after its been merged
                os.remove(output_filepath + i)
        # Export joined files
        # Bias adjustment parameters
        biasadj_all_fn = (gcm_name + '_' + rcp_scenario + '_biasadj_opt1_' + str(gcm_startyear - gcm_spinupyears) + 
                          '_' + str(gcm_endyear) + '_' + str(strftime("%Y%m%d")) + '.csv')
        biasadj_all.to_csv(output_filepath + biasadj_all_fn)
        # Lapse rate parameters (same for all GCMs - only need to export once)
        lr_all_fn = ('biasadj_mon_lravg_' + str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + 
                     '_' + str(strftime("%Y%m%d")) +'.csv')
        if os.path.exists(output_filepath + lr_all_fn) == False:
            np.savetxt(output_filepath + lr_all_fn, lr_all, delimiter=",")
            
                
#    # Place local variables in variable explorer
#    main_vars_list = list(main_vars.keys())
#    gcm_name = main_vars['gcm_name']
#    rcp_scenario = main_vars['rcp_scenario']
#    main_glac_rgi = main_vars['main_glac_rgi']
#    main_glac_hyps = main_vars['main_glac_hyps']
#    main_glac_icethickness = main_vars['main_glac_icethickness']
#    main_glac_width = main_vars['main_glac_width']
#    elev_bins = main_vars['elev_bins']
#    main_glac_bias_adj = main_vars['main_glac_bias_adj']
#    dates_table = main_vars['dates_table']
#    glacier_ref_temp = main_vars['glacier_ref_temp']
#    glacier_ref_prec = main_vars['glacier_ref_prec']
#    glacier_gcm_temp_adj = main_vars['glacier_gcm_temp_adj']
#    glacier_gcm_prec_adj = main_vars['glacier_gcm_prec_adj']
#    bias_adj_temp_init = main_vars['bias_adj_temp_init']
#    
#    # Plot reference vs. GCM temperature and precipitation
#    dates = dates_table['date']
#    plt.plot(dates, glacier_ref_temp, label='ref temp')
#    plt.plot(dates, glacier_gcm_temp_adj, label='gcm_temp')
#    plt.ylabel('Temperature [degC]')
#    plt.legend()
#    plt.show()
#    
#    plt.plot(dates, glacier_ref_prec, label='ref prec')
#    plt.plot(dates, glacier_gcm_prec_adj, label='gcm_prec')
#    plt.ylabel('Precipitation [m]')
#    plt.legend()
#    plt.show()
    
    
            
    print('Total processing time:', time.time()-time_start, 's')      

#%% ===== OTHER OPTIONS (OLD SCRIPTS) =====
#    elif option_bias_adjustment == 2:
#        # Huss and Hock (2015)
#        # TEMPERATURE BIAS CORRECTIONS
#        # Calculate monthly mean temperature
#        ref_temp_monthly_avg = (ref_temp.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
#                                .reshape(12,-1).transpose())
#        gcm_temp_monthly_avg = (gcm_temp_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
#                                .reshape(12,-1).transpose())
#        gcm_temp_monthly_adj = ref_temp_monthly_avg - gcm_temp_monthly_avg
#        # Monthly temperature bias adjusted according to monthly average
#        t_mt = gcm_temp + np.tile(gcm_temp_monthly_adj, int(gcm_temp.shape[1]/12))
#        # Mean monthly temperature bias adjusted according to monthly average
#        t_m25avg = np.tile(gcm_temp_monthly_avg + gcm_temp_monthly_adj, int(gcm_temp.shape[1]/12))
#        # Calculate monthly standard deviation of temperature
#        ref_temp_monthly_std = (ref_temp.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).std(1)
#                                .reshape(12,-1).transpose())
#        gcm_temp_monthly_std = (gcm_temp_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).std(1)
#                                .reshape(12,-1).transpose())
#        variability_monthly_std = ref_temp_monthly_std / gcm_temp_monthly_std
#        # Bias adjusted temperature accounting for monthly mean and variability
#        gcm_temp_bias_adj = t_m25avg + (t_mt - t_m25avg) * np.tile(variability_monthly_std, int(gcm_temp.shape[1]/12))
#        # PRECIPITATION BIAS CORRECTIONS
#        # Calculate monthly mean precipitation
#        ref_prec_monthly_avg = (ref_prec.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
#                                .reshape(12,-1).transpose())
#        gcm_prec_monthly_avg = (gcm_prec_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
#                                .reshape(12,-1).transpose())
#        bias_adj_prec = ref_prec_monthly_avg / gcm_prec_monthly_avg
#        # Bias adjusted precipitation accounting for differences in monthly mean
#        gcm_prec_bias_adj = gcm_prec * np.tile(bias_adj_prec, int(gcm_temp.shape[1]/12))
#        
#        # MASS BALANCES FOR DATA COMPARISON
#        main_glac_wide_volume_loss_perc = np.zeros(main_glac_rgi.shape[0])
#        for glac in range(main_glac_rgi.shape[0]):
##        for glac in [0]:
#            # Glacier data
#            modelparameters = main_glac_modelparams[glac,:]
#            glacier_rgi_table = main_glac_rgi.loc[glac, :]
#            glacier_gcm_elev = ref_elev[glac]
#            glacier_gcm_prec = ref_prec[glac,:]
#            glacier_gcm_temp = ref_temp[glac,:]
#            glacier_gcm_lrgcm = ref_lr[glac,:]
#            glacier_gcm_lrglac = glacier_gcm_lrgcm.copy()
#            glacier_area_t0 = main_glac_hyps.iloc[glac,:].values.astype(float)   
#            # Inclusion of ice thickness and width, i.e., loading values may be only required for Huss mass redistribution!
#            icethickness_t0 = main_glac_icethickness.iloc[glac,:].values.astype(float)
#            width_t0 = main_glac_width.iloc[glac,:].values.astype(float)
#            
#            # Mass balance for reference data
#            (glac_bin_temp, glac_bin_prec, glac_bin_acc, glac_bin_refreeze, glac_bin_snowpack, glac_bin_melt, 
#             glac_bin_frontalablation, glac_bin_massbalclim, glac_bin_massbalclim_annual, glac_bin_area_annual, 
#             glac_bin_icethickness_annual, glac_bin_width_annual, glac_bin_surfacetype_annual, 
#             glac_wide_massbaltotal, glac_wide_runoff, glac_wide_snowline, glac_wide_snowpack, 
#             glac_wide_area_annual, glac_wide_volume_annual, glac_wide_ELA_annual) = (
#                massbalance.runmassbalance(modelparameters, glacier_rgi_table, glacier_area_t0, icethickness_t0, 
#                                           width_t0, elev_bins, glacier_gcm_temp, glacier_gcm_prec, 
#                                           glacier_gcm_elev, glacier_gcm_lrgcm, glacier_gcm_lrglac, 
#                                           dates_table_subset, option_calibration=1))
#            # Total volume loss
#            glac_wide_massbaltotal_annual_ref = np.sum(glac_wide_massbaltotal.reshape(-1,12), axis=1)
#            glac_wide_volume_loss_total_ref = (
#                    np.cumsum(glac_wide_area_annual[glac_wide_massbaltotal_annual_ref.shape] * 
#                              glac_wide_massbaltotal_annual_ref / 1000)[-1])
#            
#            # Mass balance for GCM data
#            glacier_gcm_temp = gcm_temp_bias_adj[glac,0:ref_temp.shape[1]]
#            glacier_gcm_prec = gcm_prec_bias_adj[glac,0:ref_temp.shape[1]]
#            (glac_bin_temp, glac_bin_prec, glac_bin_acc, glac_bin_refreeze, glac_bin_snowpack, glac_bin_melt, 
#             glac_bin_frontalablation, glac_bin_massbalclim, glac_bin_massbalclim_annual, glac_bin_area_annual, 
#             glac_bin_icethickness_annual, glac_bin_width_annual, glac_bin_surfacetype_annual, 
#             glac_wide_massbaltotal, glac_wide_runoff, glac_wide_snowline, glac_wide_snowpack, 
#             glac_wide_area_annual, glac_wide_volume_annual, glac_wide_ELA_annual) = (
#                massbalance.runmassbalance(modelparameters, glacier_rgi_table, glacier_area_t0, icethickness_t0, 
#                                           width_t0, elev_bins, glacier_gcm_temp, glacier_gcm_prec, 
#                                           glacier_gcm_elev, glacier_gcm_lrgcm, glacier_gcm_lrglac, 
#                                           dates_table_subset, option_calibration=1))
#            # Total volume loss
#            glac_wide_massbaltotal_annual_gcm = np.sum(glac_wide_massbaltotal.reshape(-1,12), axis=1)
#            glac_wide_volume_loss_total_gcm = (
#                    np.cumsum(glac_wide_area_annual[glac_wide_massbaltotal_annual_gcm.shape] * 
#                              glac_wide_massbaltotal_annual_gcm / 1000)[-1])
#            
##        # PRINTING BIAS ADJUSTMENT OPTION 2
##        # Temperature parameters
##        output_tempvar = (gcm_name + '_' + rcp_scenario + '_biasadjparams_hh2015_mon_tempvar_' + 
##                          str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '.csv')
##        output_tempavg = (gcm_name + '_' + rcp_scenario + '_biasadjparams_hh2015_mon_tempavg_' + 
##                          str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '.csv')
##        output_tempadj = (gcm_name + '_' + rcp_scenario + '_biasadjparams_hh2015_mon_tempadj_' + 
##                          str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '.csv')
##        np.savetxt(output_filepath + output_tempvar, variability_monthly_std, delimiter=",") 
##        np.savetxt(output_filepath + output_tempavg, gcm_temp_monthly_avg, delimiter=",") 
##        np.savetxt(output_filepath + output_tempadj, gcm_temp_monthly_adj, delimiter=",")
##        # Precipitation parameters
##        output_precadj = (gcm_name + '_' + rcp_scenario + '_biasadjparams_hh2015_mon_precadj_' + 
##                          str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '.csv')
##        np.savetxt(output_filepath + output_precadj, bias_adj_prec, delimiter=",")  
##        # Reference elevation (same for all GCMs - only need to export once; needed because bias correcting to the 
##        #  reference, which has a specific elevation)
###        np.savetxt(output_filepath)
##        # Lapse rate - monthly average (same for all GCMs - only need to export once)
##        output_filename_lr = ('biasadj_mon_lravg_' + str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) +
##                              '.csv')
##        if os.path.exists(output_filepath + output_filename_lr) == False:
##            np.savetxt(output_filepath + output_filename_lr, ref_lr_monthly_avg, delimiter=",")
        

# OLD TEMP BIAS CORRECTIONS
##    elif option_bias_adjustment == 3:
##        # Reference - GCM difference
##        bias_adj_temp= (ref_temp - gcm_temp_subset).mean(axis=1)
##        # Bias adjusted temperature accounting for mean of entire time period
###        gcm_temp_bias_adj = gcm_temp + bias_adj_temp[:,np.newaxis]
##    elif option_bias_adjustment == 4:
##        # Calculate monthly mean temperature
##        ref_temp_monthly_avg = (ref_temp.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
##                                .reshape(12,-1).transpose())
##        gcm_temp_monthly_avg = (gcm_temp_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
##                                .reshape(12,-1).transpose())
##        bias_adj_temp = ref_temp_monthly_avg - gcm_temp_monthly_avg
##        # Bias adjusted temperature accounting for monthly mean
###        gcm_temp_bias_adj = gcm_temp + np.tile(bias_adj_temp, int(gcm_temp.shape[1]/12))
#    if option_bias_adjustment == 1:
#        # Remove negative values for positive degree day calculation
#        ref_temp_pos = ref_temp.copy()
#        ref_temp_pos[ref_temp_pos < 0] = 0
#        # Select days per month
#        daysinmonth = dates_table['daysinmonth'].values[0:ref_temp.shape[1]]
#        # Cumulative positive degree days [degC*day] for reference period
#        ref_PDD = (ref_temp_pos * daysinmonth).sum(1)
#        # Optimize bias adjustment such that PDD are equal
#        bias_adj_temp = np.zeros(ref_temp.shape[0])
#        for glac in range(ref_temp.shape[0]):
#            ref_PDD_glac = ref_PDD[glac]
#            gcm_temp_glac = gcm_temp_subset[glac,:]
#            def objective(bias_adj_glac):
#                gcm_temp_glac_adj = gcm_temp_glac + bias_adj_glac
#                gcm_temp_glac_adj[gcm_temp_glac_adj < 0] = 0
#                gcm_PDD_glac = (gcm_temp_glac_adj * daysinmonth).sum()
#                return abs(ref_PDD_glac - gcm_PDD_glac)
#            # - initial guess
#            bias_adj_init = 0      
#            # - run optimization
#            bias_adj_temp_opt = minimize(objective, bias_adj_init, method='SLSQP', tol=1e-5)
#            bias_adj_temp[glac] = bias_adj_temp_opt.x
##        gcm_temp_bias_adj = gcm_temp + bias_adj_temp[:,np.newaxis]
# OLD PREC BIAS CORRECTIONS
#if option_bias_adjustment == 1:
#        # Temperature consistent with precipitation elevation
#        #  T = T_gcm + lr_gcm * (z_ref - z_gcm) + tempchange + bias_adjustment
#        ref_temp4prec = ((ref_temp_raw + ref_lr*(glac_elev4prec - ref_elev)[:,np.newaxis]) + (modelparameters[:,7] + 
#                         bias_adj_temp)[:,np.newaxis])
#        gcm_temp4prec = ((gcm_temp_raw + gcm_lr*(glac_elev4prec - gcm_elev)[:,np.newaxis]) + (modelparameters[:,7] + 
#                         bias_adj_temp)[:,np.newaxis])[:,0:ref_temp.shape[1]]
#        # Snow accumulation should be consistent for reference and gcm datasets
#        if input.option_accumulation == 1:
#            # Single snow temperature threshold
#            ref_snow = np.zeros(ref_temp.shape)
#            gcm_snow = np.zeros(ref_temp.shape)
#            for glac in range(main_glac_rgi.shape[0]):
#                ref_snow[glac, ref_temp4prec[glac,:] < modelparameters[glac,6]] = (
#                        ref_prec[glac, ref_temp4prec[glac,:] < modelparameters[glac,6]])
#                gcm_snow[glac, gcm_temp4prec[glac,:] < modelparameters[glac,6]] = (
#                        gcm_prec_subset[glac, gcm_temp4prec[glac,:] < modelparameters[glac,6]])
#        elif input.option_accumulation == 2:
#            # Linear snow threshold +/- 1 degree
#            # If temperature between min/max, then mix of snow/rain using linear relationship between min/max
#            ref_snow = (1/2 + (ref_temp4prec - modelparameters[:,6][:,np.newaxis]) / 2) * ref_prec
#            gcm_snow = (1/2 + (gcm_temp4prec - modelparameters[:,6][:,np.newaxis]) / 2) * gcm_prec_subset
#            # If temperature above or below the max or min, then all rain or snow, respectively. 
#            for glac in range(main_glac_rgi.shape[0]):
#                ref_snow[glac, ref_temp4prec[glac,:] > modelparameters[glac,6] + 1] = 0 
#                ref_snow[glac, ref_temp4prec[glac,:] < modelparameters[glac,6] - 1] = (
#                        ref_prec[glac, ref_temp4prec[glac,:] < modelparameters[glac,6] - 1])
#                gcm_snow[glac, gcm_temp4prec[glac,:] > modelparameters[glac,6] + 1] = 0
#                gcm_snow[glac, gcm_temp4prec[glac,:] < modelparameters[glac,6] - 1] = (
#                        gcm_prec_subset[glac, gcm_temp4prec[glac,:] < modelparameters[glac,6] - 1])
#        # precipitation bias adjustment
#        bias_adj_prec = ref_snow.sum(1) / gcm_snow.sum(1)
##        gcm_prec_bias_adj = gcm_prec * bias_adj_prec[:,np.newaxis]
#    else:
#        # Calculate monthly mean precipitation
#        ref_prec_monthly_avg = (ref_prec.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
#                                .reshape(12,-1).transpose())
#        gcm_prec_monthly_avg = (gcm_prec_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1)
#                                .reshape(12,-1).transpose())
#        bias_adj_prec = ref_prec_monthly_avg / gcm_prec_monthly_avg
#        # Bias adjusted precipitation accounting for differences in monthly mean
##        gcm_prec_bias_adj = gcm_prec * np.tile(bias_adj_prec, int(gcm_temp.shape[1]/12))
      