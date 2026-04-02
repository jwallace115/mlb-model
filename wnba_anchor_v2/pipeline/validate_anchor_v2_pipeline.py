#!/usr/bin/env python3
import os
for f in ['wnba_anchor_v2/models/ridge_anchor_v2_wnba.pkl']: print(f'[{"PASS" if os.path.exists(f) else "FAIL"}] {f}')