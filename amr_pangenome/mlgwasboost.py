#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 15 16:12:32 2020

@author: jhyun95

"""

import time
import collections, re
import numpy as np
import pandas as pd
import scipy.stats
import sklearn.base, sklearn.svm, sklearn.ensemble
import sklearn.metrics, sklearn.model_selection
import xgboost as xgb

import amr_pangenome.mlgwas


def grid_search_xgb_rse(df_features, df_labels, df_aro, drug, 
    parameter_sweep={'n_estimators':[25,50,100,200,400],
                     'colsample_by_tree': [1.0,0.75,0.5,0.25],
                     'max_depth':[3,5,7]},
    fixed_parameters={'learning_rate':0.1, 'min_split_loss':0,
                      'min_child_weight':1, 'subsample':0.8,
                      'scale_pos_weight':1, 'reg_lambda':0,
                      'reg_alpha':1, 'objective':'binary:logistic'},
    seed=1, n_jobs=1):
    ''' 
    Grid search for XGB-RSE, based on grid_search_xvm_rse.
    '''
    
    report_values = []
    param_columns = list(parameter_sweep.keys())
    columns = param_columns + ['GWAS score', 'GWAS ranks', 'MCC avg', 'MCC 5CV', 'GWAS time', '5CV time']
    round3 = lambda x: round(x,3)
    mcc_scorer = sklearn.metrics.make_scorer(sklearn.metrics.matthews_corrcoef)
    for variable_parameters in sklearn.model_selection.ParameterGrid(parameter_sweep):
        print variable_parameters
        xgb_params = dict(fixed_parameters)
        xgb_params.update(variable_parameters)
        xgb_params['seed'] = seed
        xgb_params['n_jobs'] = n_jobs
        
        ''' Train XGB on full data for weights -> ranks -> GWAS score '''
        print '\tTraining full (GWAS)...',
        t = time.time()
        df_weights, xgb_clf, X, y = gwas_xgb_rse(df_features, df_labels, 
            null_shuffle=False, xgb_kwargs=xgb_params, return_matrices=True)
        aro_hit_count = df_aro[pd.notnull(df_aro.loc[:,drug])].shape[0]
        if aro_hit_count == 0: # no reference hits, cannot score based on GWAS
            gwas_score = np.nan; gwas_ranks = [np.nan]
        else: # reference hits available
            df_eval = amr_pangenome.mlgwas.evaluate_gwas(df_weights, df_aro, drug, signed_weights=False)
            gwas_score, gwas_ranks = amr_pangenome.mlgwas.score_ranking(df_eval, signed_weights=False)
        time_gwas = time.time() - t
        print round3(time_gwas)
        
        ''' Evaluate prediction performance with 5-fold CV '''
        print '\tTraining 5CV (MCC)...',
        t = time.time()
        mcc_scores = sklearn.model_selection.cross_val_score(
            xgb_clf, X=X, y=y, scoring=mcc_scorer, cv=5)
        mcc_avg = np.mean(mcc_scores)
        time_5cv = time.time() - t
        print round3(time_5cv) 

        ''' Report scores '''
        print '\tSelected features:', df_weights.shape[0]
        print '\tGWAS Score:', round3(gwas_score), '\t', map(round3, gwas_ranks)
        print '\tPred Score:', round3(mcc_avg), '\t', map(round3, mcc_scores)
        param_set = list(map(lambda x: variable_parameters[x], param_columns))
        report_values.append(param_set + [gwas_score, gwas_ranks, 
            mcc_avg, mcc_scores, time_gwas, time_5cv])
        
    df_report = pd.DataFrame(columns=columns, data=report_values)
    return df_report


def gwas_xgb_rse(df_features, df_labels, null_shuffle, xgb_kwargs={
    'n_estimators':100, 'learning_rate':0.1, 'min_split_loss':0, 
    'max_depth':5, 'min_child_weight':1, 'colsample_by_tree':0.5, 
    'subsample':0.8, 'scale_pos_weight':1, 'reg_lambda':0, 'reg_alpha':1 , 
    'seed':1, 'objective':'binary:logistic', 'n_jobs':1}, 
    return_matrices=False):
    '''
    Runs a random subspace ensemble with XGBoost random forest classifier.
    Parameters and outputs are modeled after gwas_rse().
    '''
    
    X, y = amr_pangenome.mlgwas.setup_Xy(df_features, df_labels, null_shuffle)
    xgb_clf = xgb.XGBClassifier(**xgb_kwargs)
    xgb_clf.fit(X,y,verbose=True)
    weights = xgb_clf.feature_importances_
    df_weights = pd.DataFrame(data=weights, index=df_features.index, columns=['XGB'])
    df_weights = df_weights[df_weights.XGB != 0.0]
    if return_matrices:
        return df_weights, xgb_clf, X, y
    else:
        return df_weights, xgb_clf