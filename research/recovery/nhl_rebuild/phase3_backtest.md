======================================================================
PHASE 3: HONEST BACKTEST
======================================================================

OOS games with market: 1312
Validation drift (Model A): +0.0186
Validation drift (Model B): -0.1706
Validation drift (Model C): -0.0437

--- BETTING SIMULATION (flat -110, $100 units) ---

  Model A_cal:
    edge>=0.0: 1266 bets  W=713  L=553  win%=56.3%  ROI=+5.3%  P&L=$+6741
    edge>=0.3:  654 bets  W=358  L=296  win%=54.7%  ROI=+0.8%  P&L=$+523
    edge>=0.5:  358 bets  W=203  L=155  win%=56.7%  ROI=+3.8%  P&L=$+1358
    edge>=0.8:  114 bets  W=67  L=47  win%=58.8%  ROI=+6.6%  P&L=$+753
    edge>=1.0:   30 bets  W=19  L=11  win%=63.3%  ROI=+12.2%  P&L=$+365

  Model B_cal:
    edge>=0.0: 1266 bets  W=680  L=586  win%=53.7%  ROI=+2.9%  P&L=$+3673
    edge>=0.3:  324 bets  W=174  L=150  win%=53.7%  ROI=+2.8%  P&L=$+915
    edge>=0.5:   80 bets  W=44  L=36  win%=55.0%  ROI=+4.8%  P&L=$+383
    edge>=0.8:   16 bets  W=7  L=9  win%=43.8%  ROI=-19.3%  P&L=$-310
    edge>=1.0:    1 bets  W=0  L=1  win%=0.0%  ROI=-100.0%  P&L=$-100

  Model C_cal:
    edge>=0.0: 1266 bets  W=700  L=566  win%=55.3%  ROI=+3.9%  P&L=$+4966
    edge>=0.3:  530 bets  W=295  L=235  win%=55.7%  ROI=+3.1%  P&L=$+1631
    edge>=0.5:  235 bets  W=128  L=107  win%=54.5%  ROI=-0.1%  P&L=$-19
    edge>=0.8:   54 bets  W=34  L=20  win%=63.0%  ROI=+13.3%  P&L=$+717
    edge>=1.0:   10 bets  W=4  L=6  win%=40.0%  ROI=-34.6%  P&L=$-346

--- MONTHLY BREAKDOWN (Model C calibrated, edge>=0.5) ---
  2024-10:  26 bets  win%=57.7%
  2024-11:  29 bets  win%=51.7%
  2024-12:  35 bets  win%=57.1%
  2025-01:  51 bets  win%=52.9%
  2025-02:  32 bets  win%=46.9%
  2025-03:  39 bets  win%=59.0%
  2025-04:  23 bets  win%=56.5%