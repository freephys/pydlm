"""
===============================================================================

The code for all hidden method for the class dlm

===============================================================================

This piece of code include all the hidden methods and members of the class dlm.
It provides the basic modeling, filtering, forecasting and smoothing of a dlm.

"""
from copy import deepcopy
from numpy import matrix
from pydlm.base.kalmanFilter import kalmanFilter
from pydlm.modeler.builder import builder

# this class defines the basic functionalities for dlm, which is not supposed
# to be used by the user. Most functionality in the main dlm will be
# constructed by using the hidden functions in this class


class _dlm:
    """ _dlm includes all hidden functions that used by the class dlm. These hidden
    methods provide the basic modeling, filtering, forecasting and smoothing of
    dlm.

    Attributes:
        data: the observed time series data
        n: the length of the time series data
        result: the inner class that records the filtered and smoothed results
        builder: the @builder that is used for providing the modeling
        functionality. For details please refer to @builder
        Filter: the filter used for filtering time series data using the model.
                For details please refer to @kalmanFilter
        initialized: indicates whether the dynamic linear model has been
                     initialized
        options: model options, including initial guess of the observational
                 variance.
                 More is going to be added (plot options and shrinkage options)
        time: the time label, used for plotting


    Methods:
        _initialize: initialize the dlm (builder and kalmanFilter)
        _forwardFilter: run forward filter for a specific start and end date
        _backwardSmoother: run backward smooth for a specific start and end
                           date
        _predict: predict the latent state and observation for a given period
                          of time
        _resetModelStatus: reset the model status to its prior status
        _setModelStatus: set the model status to a specific date
        _defaultOptions: a class to store and set default options
        _result: a class to store the results
        _copy: copy the result from the model to the _result class
        _reverseCopy: copy the result from the _result class to the model
        _checkFeatureSize: check whether the features's n matches the data's n
    """
    # define the basic members
    # initialize the result
    def __init__(self, data):

        self.data = list(data)
        self.n = len(data)
        self.result = None
        self.builder = builder()
        self.Filter = None
        self.initialized = False
        self.options = self._defaultOptions()
        self.time = None
        self._printInfo = True

    # an inner class to store all options
    class _defaultOptions:
        """ All plotting and fitting options

        """
        def __init__(self):
            self.noise = 1.0
            self.stable = True

            self.plotOriginalData = True
            self.plotFilteredData = True
            self.plotSmoothedData = True
            self.plotPredictedData = True
            self.showDataPoint = True
            self.showFittedPoint = False
            self.showConfidenceInterval = True
            self.dataColor = 'black'
            self.filteredColor = 'blue'
            self.predictedColor = 'green'
            self.smoothedColor = 'red'
            self.separatePlot = True
            self.confidence = 0.95
            self.intervalType = 'ribbon'

    # an inner class to store all results
    class _result:
        """ Class to store the results

        """
        # class level (static) variables to record all names
        records = ['filteredObs', 'predictedObs', 'smoothedObs',
                   'filteredObsVar',
                   'predictedObsVar', 'smoothedObsVar', 'noiseVar',
                   'df',
                   'filteredState', 'predictedState', 'smoothedState',
                   'filteredCov', 'predictedCov', 'smoothedCov']

        # quantites to record the result
        def __init__(self, n):

            # initialize all records to be [None] * n
            for variable in self.records:
                setattr(self, variable, [None] * n)

            # record the dates that have been filtered
            self.filteredSteps = [0, -1]
            # record the dates that have been smoothed
            self.smoothedSteps = [0, -1]
            # record the last used filterType
            self.filteredType = None
            # record the current prediction status in the form of
            # [start date, current date, [predictedObs1, predictedObs2,...]]
            self.predictStatus = None

        # extend the current record by n blocks
        def _appendResult(self, n):
            for variable in self.records:
                getattr(self, variable).extend([None] * n)

        # pop out a specific date
        def _popout(self, date):
            for variable in self.records:
                getattr(self, variable).pop(date)

    # initialize the builder
    def _initialize(self):
        """ Initialize the model: initialize builder and filter.

        """
        self.builder.initialize(noise=self.options.noise)
        # if self.options.shrink == 'auto':
        #    self.Filter = kalmanFilter(discount = self.builder.discount,
        #                           shrink = 1 - min(self.builder.discount),
        #                           shrinkageMatrix = self.builder.sysVarPrior)
        # else:
        self.Filter = kalmanFilter(discount=self.builder.discount)
        self.result = self._result(self.n)
        self.initialized = True

    # use the forward filter to filter the data
    # start: the place where the filter started
    # end: the place where the filter ended
    # save: the index for dates where the filtered results should be saved,
    #       could be 'all' or 'end'
    # isForget: indicate where the filter should use the previous state as
    #         prior or just use the prior information from builder
    def _forwardFilter(self,
                       start=0,
                       end=None,
                       save='all',
                       ForgetPrevious=False,
                       renew=False):
        """ Running forwardFilter for the data for a given start and end date

        Args:
            start: the start date
            end: the end date (default to the last day of the chain)
            save: indicate the dates of which the result needs to be saved for.
                  'all' stands for (start, end), otherwise an integer between
                  start and end.
            ForgetPrevious: indicate whether the fitering should start from
                            the prior status or the previous date that has
                            been filtered.
                            (used for rolling window filtering, see @dlm)
            renew: if true, filter will refit certain days when the
                   chain gets
                   too long to add numerical stability, the length of the chain
                   is determined by the information carried on. For example,
                   when discount = 0.9, any days that are 65 days ago together
                   only carry information 1%, so we ignore
                   these days and refit the model to aid stability.
        """
        # the default value for end
        if end is None:
            end = self.n - 1

        # to see if the ff need to run or not
        if start > end:
            return None

        # also we need to make we save consectively
#        if save == 'all' and start > self.result.filteredSteps[1] + 1:
#            raise NameError('The data before start date has yet to be
#                            filtered!')

        # for rolling window run, we need to make sure the saved
        #  date is consecutive
#        if save != 'all' and end > self.result.filteredSteps[1] + 1:
#            raise NameError('The previous date needs to be filtered'
#                           + ' for rolling window!')

        # first we need to initialize the model to the correct status
        # if the start point is 0 or we want to forget the previous result
        if start == 0 or ForgetPrevious:
            self._resetModelStatus()

        # otherwise we use the result on the previous day as the prior
        else:
            if start > self.result.filteredSteps[1] + 1:
                raise NameError('The data before start date has' +
                                ' yet to be filtered! Otherwise set' +
                                ' ForgetPrevious to be True. Check the' +
                                ' <filteredSteps> in <result> object.')
            self._setModelStatus(date=start - 1)

        # we run the forward filter sequentially
        lastRenewPoint = start  # record the last renew point
        for step in range(start, end + 1):

            # first check whether we need to update evaluation or not
            if len(self.builder.dynamicComponents) > 0 or \
               len(self.builder.automaticComponents) > 0:
                self.builder.updateEvaluation(step)

            # check if rewnew is needed
            if renew and step - lastRenewPoint > self.builder.renewTerm \
               and self.builder.renewTerm > 0.0:
                # we renew the state of the day
                self._resetModelStatus()
                for innerStep in range(step - int(self.builder.renewTerm),
                                       step):
                    self.Filter.forwardFilter(self.builder.model,
                                              self.data[innerStep])
                lastRenewPoint = step

            # then we use the updated model to filter the state
            self.Filter.forwardFilter(self.builder.model, self.data[step])

            # extract the result and record
            if save == 'all' or save == step:
                self._copy(model=self.builder.model,
                           result=self.result,
                           step=step,
                           filterType='forwardFilter')

#        self.result.filteredSteps = (0, end)

    # use the backward smooth to smooth the state
    # start: the last date of the backward filtering chain
    # days: number of days to go back from start
    def _backwardSmoother(self, start=None, days=None, ignoreFuture=False):
        """ Backward smooth over filtered results for a specific start
            and number of days

        Args:
            start: the start date
            days: number of days to be smoothed starting from start towards
                  zero
            ignoreFuture: indicate whether the smoothed should start as if the
                          future data was not observed or using the future data
                          as the initial smoothing status.
        """
        # the default start date is the most recent date
        if start is None:
            start = self.n - 1

        # the default backward days number is the total length
        if days is None:
            end = 0
        else:
            end = max(start - days + 1, 0)

        # the forwardFilter has to be run before the smoother
        if self.result.filteredSteps[1] < start:
            raise NameError('The last day has to be filtered before smoothing! \
            check the <filteredSteps> in <result> object.')

        # and we record the most recent day which does not need to be smooth
        if start == self.n - 1 or ignoreFuture is True:
            self.result.smoothedState[start] = self.result.filteredState[start]
            self.result.smoothedObs[start] = self.result.filteredObs[start]
            self.result.smoothedCov[start] = self.result.filteredCov[start]
            self.result.smoothedObsVar[start] \
                = self.result.filteredObsVar[start]
            self.builder.model.noiseVar = self.result.noiseVar[start]
            start -= 1
        else:
            self.builder.model.noiseVar = self.result.noiseVar[self.n - 1]

        # empty smoothing chain, return None
        if start < end:
            return None

        # insert the previous smoothed dates
        self.builder.model.state = self.result.smoothedState[start + 1]
        self.builder.model.sysVar = self.result.smoothedCov[start + 1]

        # we smooth the result sequantially from start - 1 to end
        dates = list(range(end, start + 1))
        dates.reverse()
        for day in dates:
            # we first update the model to be correct status before smooth
            self.builder.model.prediction.state \
                = self.result.predictedState[day + 1]
            self.builder.model.prediction.sysVar \
                = self.result.predictedCov[day + 1]

            if len(self.builder.dynamicComponents) > 0 or \
               len(self.builder.automaticComponents) > 0:
                self.builder.updateEvaluation(day)

            # then we use the backward filter to filter the result
            self.Filter.backwardSmoother(
                model=self.builder.model,
                rawState=self.result.filteredState[day],
                rawSysVar=self.result.filteredCov[day])

            # extract the result
            self._copy(model=self.builder.model,
                       result=self.result,
                       step=day,
                       filterType='backwardSmoother')

#        self.result.smoothedSteps = (end, start)

    # Forecast the result based on filtered chains
    def _predictInSample(self, date, days=1):
        """ Predict the model's status based on the model of a specific day

        Args:
            date: the date the prediction is based on
            day: number of days forward that need to be predicted.

        Returns:
            A tuple. (Predicted observation, variance of the predicted
            observation)

        """

        if date + days > self.n - 1:
            raise NameError('The range is out of sample.')

        predictedObs = [None] * days
        predictedObsVar = [None] * days
        # reset the date to the date we are interested in
        self._setModelStatus(date=date)
        self.builder.model.prediction.step = 0
        for i in range(1, days):
            # update the evaluation vector
            if len(self.builder.dynamicComponents) > 0 or \
               len(self.builder.automaticComponents) > 0:
                self.builder.updateEvaluation(date + i)

            self.Filter.predict(self.builder.model)
            predictedObs[i - 1] = self.builder.model.prediction.obs
            predictedObsVar[i - 1] = self.builder.model.prediction.obsVar

        return (predictedObs, predictedObsVar)

    # feature set contains all the features for prediction.
    # It is a dictionary with key equals to the name of the component and
    # the value as the new feature (a list). The function
    # will first use the features provided in this feature dict, if not
    # found, it will fetch the default feature from the component. If
    # it could not find feature for some component, it returns an error
    def _oneDayAheadPredict(self, date, featureDict=None):
        if date > self.n - 1:
            raise NameError('The date is beyond the data range.')

        self._setModelStatus(date=date)
        self._constructEvaluationForPrediction(featureDict=featureDict,
                                               date=date + 1)
        self.builder.model.prediction.step = 0
        self.Filter.predict(self.builder.model)
        predictedObs = self.builder.model.prediction.obs
        predictedObsVar = self.builder.model.prediction.obsVar
        self.result.predictStatus = [date, date + 1, [predictedObs]]
        return (predictedObs, predictedObsVar)

    def _continuePredict(self, featureDict=None):
        if self.result.predictStatus is None:
            raise NameError('_continoousPredict can only be used after ' +
                            '_oneDayAheadPredict')
        currentDate = self.result.predictStatus[1]

        # need to take care of the automaticComponents, especially the
        # auto regressive component.
        for name in self.builder.automaticComponents:
            comp = self.builder.automaticComponents[name]
            if comp.componentType != 'autoReg':
                continue

            if len(self.result.predictStatus[2]) >= comp.d:
                feature = self.result.predictStatus[2][-comp.d:]
            else:
                extra = comp.d - len(self.predictStatus[2])
                feature = self.data[(currentDate - extra + 1):
                                    (currentDate + 1)] + self.result.predictStatus[2]
            if featureDict is None:
                featureDict = {}

            featureDict[name] = feature

        self._constructEvaluationForPrediction(featureDict=featureDict,
                                               date=currentDate + 1)
        self.Filter.predict(self.builder.model)
        predictedObs = self.builder.model.prediction.obs
        predictedObsVar = self.builder.model.prediction.obsVar
        self.result.predictStatus[1] += 1
        self.result.predictStatus[2].append(predictedObs)
        return (predictedObs, predictedObsVar)

    def _constructEvaluationForPrediction(self,
                                          featureDict=None,
                                          date=None):

        if featureDict is None and date is None:
            raise NameError('FeatureDict and date cannot be None ' +
                            'at the same time.')

        # find the correct evaluation vector
        if featureDict is None:
            self.builder.updateEvaluation(date)
        else:
            for i in self.builder.dynamicComponents:
                if i in featureDict:
                    self.builder.model.evaluation[
                        0, self.builder.componentIndex[i][0]:
                        (self.builder.componentIndex[i][1] + 1)] = featureDict[i]
                else:
                    if date is None:
                        raise NameError('Both date and featureDict are ' +
                                        'not provided for component ' +
                                        i)
                    comp = self.builder.dynamicComponents[i]
                    comp.updateEvaluation(date)
                    self.builder.model.evaluation[
                        0, self.builder.componentIndex[i][0]:
                        (self.builder.componentIndex[i][1] + 1)] = comp.evaluation

            for i in self.builder.automaticComponents:
                if i in featureDict:
                    self.builder.model.evaluation[
                        0, self.builder.componentIndex[i][0]:
                        (self.builder.componentIndex[i][1] + 1)] = featureDict[i]
                else:
                    if date is None:
                        raise NameError('Both date and featureDict are ' +
                                        'not provided for component ' +
                                        i)
                    comp = self.builder.automaticComponents[i]
                    comp.updateEvaluation(date)
                    self.builder.model.evaluation[
                        0, self.builder.componentIndex[i][0]:
                        (self.builder.componentIndex[i][1] + 1)] = comp.evaluation
        self.builder.model.evaluation = matrix(self.builder.model.evaluation)
# =======================================================================

    # to set model to a specific date
    def _setModelStatus(self, date=0):
        """ Set the model status to a specific date (the date mush have been filtered)

        """
        if date < self.result.filteredSteps[0] or \
           date > self.result.filteredSteps[1]:
            raise NameError('The date has yet to be filtered yet. ' +
                            'Check the <filteredSteps> in <result> object.')

        self._reverseCopy(model=self.builder.model,
                          result=self.result,
                          step=date)
        if len(self.builder.dynamicComponents) > 0 or \
           len(self.builder.automaticComponents) > 0:
            self.builder.updateEvaluation(date)

    # reset model to initial status
    def _resetModelStatus(self):
        """ Reset the model to the prior status

        """
        self.builder.model.state = self.builder.statePrior
        self.builder.model.sysVar = self.builder.sysVarPrior
        self.builder.model.noiseVar = self.builder.noiseVar
        self.builder.model.df = 1
        self.builder.model.initializeObservation()

    # a function used to copy result from the model to the result
    def _copy(self, model, result, step, filterType):
        """ Copy result from the model to _result class

        """

        if filterType == 'forwardFilter':
            result.filteredObs[step] = model.obs
            result.predictedObs[step] = model.prediction.obs
            result.filteredObsVar[step] = model.obsVar
            result.predictedObsVar[step] = model.prediction.obsVar
            result.filteredState[step] = model.state
            result.predictedState[step] = model.prediction.state
            result.filteredCov[step] = model.sysVar
            result.predictedCov[step] = model.prediction.sysVar
            result.noiseVar[step] = model.noiseVar
            result.df[step] = model.df

        elif filterType == 'backwardSmoother':
            result.smoothedState[step] = model.state
            result.smoothedObs[step] = model.obs
            result.smoothedCov[step] = model.sysVar
            result.smoothedObsVar[step] = model.obsVar

    def _reverseCopy(self, model, result, step):
        """ Copy result from _result class to the model

        """

        model.obs = result.filteredObs[step]
        model.prediction.obs = result.predictedObs[step]
        model.obsVar = result.filteredObsVar[step]
        model.prediction.obsVar = result.predictedObsVar[step]
        model.state = result.filteredState[step]
        model.prediction.state = result.predictedState[step]
        model.sysVar = result.filteredCov[step]
        model.prediction.sysVar = result.predictedCov[step]
        model.noiseVar = result.noiseVar[step]
        model.df = result.df[step]

    # check if the data size matches the dynamic features
    def _checkFeatureSize(self):
        """ Check features's n matches the data's n

        """
        if len(self.builder.dynamicComponents) > 0:
            for name in self.builder.dynamicComponents:
                if self.builder.dynamicComponents[name].n != self.n:
                    raise NameError('The data size of dlm and '
                                    + name + ' does not match')

    def _1DmatrixToArray(self, arrayOf1dMatrix):
        return [item.tolist()[0][0] for item in arrayOf1dMatrix]

    # function to turn off printing system info
    def _printSystemInfo(self, yes):
        if yes:
            self._printInfo = True
            self.builder._printInfo = True
        else:
            self._printInfo = False
            self.builder._printInfo = False

    def _clean(self):
        self.result.predictStatus = None