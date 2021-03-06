'''
    License: GPLv3.
    Adrin Jalali.
    Jan 2014, Saarbruecken, Germany.

miscellaneous functions used mostly in the data loading/preprocessing
phase.
'''

import csv;
import sys;
import os;
import numpy as np;
import graph_tool as gt;
from graph_tool import draw;
from graph_tool import spectral;
from graph_tool import stats;
from sklearn import svm;
from sklearn import cross_validation as cv;
from sklearn.metrics import roc_auc_score;
from sklearn.grid_search import GridSearchCV
import sklearn.ensemble
import sklearn.tree
from collections import defaultdict
import time
from joblib import Parallel, delayed, logger
import pickle


from constants import *;
from rat import *

def read_csv(file_name, skip_header, delimiter = '\t'):
    data = csv.reader(open(file_name, 'r'), delimiter=delimiter);
    if (skip_header): next(data);
    table = [row for row in data];
    return table;

def get_column(table, col):
    res = list();
    for i in range(len(table)):
        res.append(table[i][col]);
    return res;

def dump_list(data, file_name):
    file = open(file_name, 'w');
    for item in data:
        print>>file, item;
    file.close();

def extract(d, keys):
    return dict((k, d[k]) for k in keys if k in d);

def print_stats(mine):
    print("MIC", mine.mic())
    print("MAS", mine.mas())
    print("MEV", mine.mev())
    print("MCN (eps=0)", mine.mcn(0))
    print("MCN (eps=1-MIC)", mine.mcn_general())
                        
def reload_rat():
    with open("./rat.py") as f:
        code = compile(f.read(), "rat.py", 'exec')
        exec(code)

def print_scores(prefix, scores):
    if isinstance(scores, dict):
        for key in sorted(scores.keys()):
            value = scores[key]
            if (prefix != ''):
                print_scores("%s (%s)" %(prefix, str(key)), value)
            else:
                print(key)
                print_scores("\t", value)
    else:
        print("%s: %.3lg +/- %.3lg" % (prefix, np.mean(scores), 2 * np.std(scores)))
        
def print_log(all_scores, rat_scores = dict()):
    print('=========')
    print_scores('', all_scores)
    print_scores('', rat_scores)

def dump_scores(file_name, scores):
    import pickle
    pickle.dump(scores, open(file_name, "wb"))

def _fit_and_score(estimator, X, y, scorer, train, test, verbose, parameters,
                   fit_params, max_learner_count, return_train_score=False,
                   return_parameters=False):
    if verbose > 1:
        if parameters is None:
            msg = "no parameters to be set"
        else:
            msg = '%s' % (', '.join('%s=%s' % (k, v)
                                    for k, v in parameters.items()))
        print("[CV] %s %s" % (msg, (64 - len(msg)) * '.'))

    # Adjust lenght of sample weights
    n_samples = len(X)
    fit_params = fit_params if fit_params is not None else {}
    fit_params = dict([(k, np.asarray(v)[train]
                        if hasattr(v, '__len__') and len(v) == n_samples else v)
                       for k, v in fit_params.items()])

    if parameters is not None:
        estimator.set_params(**parameters)

    X_train, y_train = sklearn.cross_validation._safe_split(
        estimator, X, y, train)
    X_test, y_test = sklearn.cross_validation._safe_split(
        estimator, X, y, test, train)
    result = list()
    from_scratch = True
    for i in range(max_learner_count):
        start_time = time.time()

        estimator.fit(X_train, y_train, from_scratch = from_scratch)
        test_score = sklearn.cross_validation._score(
            estimator, X_test, y_test, scorer)
        if return_train_score:
            train_score = _score(estimator, X_train, y_train, scorer)
        ret = [train_score] if return_train_score else []

        scoring_time = time.time() - start_time

        ret.extend([test_score, len(X_test), scoring_time])
        if return_parameters:
            ret.append(parameters)
        result.append(ret)
        from_scratch = False


        if verbose > 2:
            msg += ", score=%f" % test_score
        if verbose > 1:
            end_msg = "%s -%s" % (msg, logger.short_format_time(scoring_time))
            print("[CV] %s %s" % ((64 - len(end_msg)) * '.', end_msg))

    return result
        
def rat_cross_val_score(estimator, X, y=None, scoring=None, cv=None, n_jobs=1,
                    verbose=0, fit_params=None, score_func=None,
                    pre_dispatch='2*n_jobs', max_learner_count = 2):
    X, y = sklearn.utils.check_arrays(X, y, sparse_format='csr', allow_lists=True)
    cv = sklearn.cross_validation._check_cv(cv,
                                            X, y,
                                            classifier=sklearn.base.is_classifier(estimator))
    scorer = sklearn.cross_validation.check_scoring(
        estimator, score_func=score_func, scoring=scoring)
    # We clone the estimator to make sure that all the folds are
    # independent, and that it is pickle-able.

    jobs = list(dict())

    fit_params = fit_params if fit_params is not None else {}
    parallel = Parallel(n_jobs=n_jobs, verbose=verbose,
                        pre_dispatch=pre_dispatch)

    fit_params['from_scratch'] = True
    collected_scores = dict()
    scorer = sklearn.metrics.scorer.get_scorer(scoring)
    scorer = sklearn.metrics.scorer.get_scorer(scoring)
    scores = parallel(
        delayed(_fit_and_score)(
            estimator,
            X, y, scorer,
            train, test,
            verbose, None, fit_params,
            max_learner_count = max_learner_count)
        for train, test in cv)

    return (scores)

