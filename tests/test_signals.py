import unittest
import numpy as np
import pandas as pd
from analysis import indicators, oscillator_sell_signals
from data import demo_prices


class OscillatorSignalTests(unittest.TestCase):
    def detect(self, macd, histogram):
        return oscillator_sell_signals(pd.Series(macd), pd.Series(histogram)).tolist()

    def test_crossing_emits_once_while_negative(self):
        self.assertEqual(self.detect([-1,.5,1,.8,.7], [-.2,.2,0,-.1,-.2]),
                         [False,False,False,True,False])

    def test_new_histogram_cross_can_trigger_again(self):
        self.assertEqual(self.detect([-1,1,2,2,2,1], [-1,.2,-.1,.1,0,-.1]),
                         [False,False,True,False,False,True])

    def test_nonpositive_macd_resets_regime(self):
        self.assertEqual(self.detect([-1,1,-.1,.5,.8,.7], [-.1,.1,-.2,-.1,.1,-.1]),
                         [False,False,False,False,False,True])
        self.assertEqual(self.detect([-1,1,0], [-.1,.1,-.1]), [False]*3)

    def test_no_inferred_crossing_before_history(self):
        self.assertEqual(self.detect([.1,.2,.3,.2], [.1,.1,.1,-.1]), [False]*4)

    def test_warmup_and_missing_values_do_not_create_signals(self):
        self.assertEqual(self.detect([np.nan,-1,1,2,1], [np.nan,np.nan,np.nan,.1,-.1]),
                         [False,False,False,False,True])
        self.assertEqual(self.detect([-1,1,np.nan,2,1], [-.1,.1,np.nan,.1,-.1]), [False]*5)

    def test_future_data_cannot_change_past_signals(self):
        macd, hist = [-1,1,2,2,-1,1,2], [-1,.1,-.1,-.2,-.2,.1,-.1]
        full = self.detect(macd,hist)
        for end in range(1,len(macd)+1):
            self.assertEqual(self.detect(macd[:end],hist[:end]), full[:end])

    def test_indicator_pipeline_finds_positive_macd_turns(self):
        frame = demo_prices().tail(240).copy()
        frame['Close'] = np.r_[np.linspace(140,80,80), np.linspace(80,160,100), np.linspace(160,100,60)]
        calculated = indicators(frame)
        selected = calculated.loc[calculated.MACD19SellSignal]
        self.assertGreater(len(selected), 0)
        self.assertTrue((selected.MACD > 0).all())
        self.assertTrue((selected.Histogram < 0).all())
        self.assertTrue((calculated.Histogram.shift(1).loc[selected.index] >= 0).all())


if __name__ == '__main__':
    unittest.main()
