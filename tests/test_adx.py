import unittest
import numpy as np
import pandas as pd
from analysis import directional_indicators,wilder_average,di_buy_signals

class ADXTests(unittest.TestCase):
    def test_wilder_seed_and_recursion(self):
        result=wilder_average(pd.Series([1.,2.,3.,4.,5.]),3)
        self.assertTrue(result.iloc[:2].isna().all())
        np.testing.assert_allclose(result.iloc[2:],[2,8/3,31/9])
    def test_monotonic_and_adxr_lag(self):
        for sign in [1,-1]:
            close=pd.Series(100+sign*np.arange(80))
            result=directional_indicators(pd.DataFrame({'High':close+1,'Low':close-1,'Close':close}))
            self.assertTrue(result.ADX.iloc[:26].isna().all())
            np.testing.assert_allclose(result.ADX.iloc[26:],100)
            self.assertTrue(result.ADXR.iloc[:40].isna().all())
            np.testing.assert_allclose(result.ADXR.iloc[40:],100)
            inactive='MinusDI' if sign==1 else 'PlusDI'
            self.assertTrue((result[inactive].iloc[13:]==0).all())
    def test_flat_no_infinity(self):
        frame=pd.DataFrame({'High':[10.]*60,'Low':[10.]*60,'Close':[10.]*60})
        result=directional_indicators(frame)
        self.assertTrue((result.iloc[-1]==0).all())
    def test_equal_direction_moves_have_no_dm(self):
        result=directional_indicators(pd.DataFrame({'High':np.arange(60)+100,'Low':100-np.arange(60),'Close':[100]*60}))
        self.assertEqual(result.PlusDI.iloc[-1],0)
        self.assertEqual(result.MinusDI.iloc[-1],0)

    def test_buy_cross_warmup_equality_and_repeated_crosses(self):
        plus = pd.Series([np.nan, 25, 26, 20, 21, 22, 19, 23, np.nan, 30])
        minus = pd.Series([20.] * len(plus))
        self.assertEqual(di_buy_signals(plus, minus).tolist(),
                         [False, False, False, False, True, False, False, True, False, False])
