## Main table

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 4 | 1 | 45,000 | 492 | 1.28 | 25.35 | 0.0017 |
| 1 | S2 think and vote (k = 5) | 15 | 0 | 227,300 | 20,967 | 10.66 | 215.41 | 0.0300 |
| 1 | S3 tools | 19 | 0 | 83,550 | 4,630 | 6.05 | 119.19 | 0.0148 |
| 2 | S1 direct | 5 | 1 | 45,000 | 527 | 1.29 | 29.97 | 0.0015 |
| 2 | S2 think and vote (k = 5) | 16 | 0 | 227,300 | 20,926 | 11.09 | 216.89 | 0.0297 |
| 2 | S3 tools | 19 | 0 | 81,121 | 4,689 | 5.27 | 102.63 | 0.0110 |

## Per question (run 1)

| Question | S1 | S2 | S3 | S3 rounds | S3 tool calls |
|---|:---:|:---:|:---:|---:|---:|
| Q-01 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-02 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-03 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-04 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-05 | ✗ | ✗ | ✓ | 4 | 7 |
| Q-06 | ✓ | ✓ | ✓ | 3 | 4 |
| Q-07 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-08 | ✗ | ✗ | ✓ | 3 | 6 |
| Q-09 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-10 | ✓ | ✓ | ✓ | 3 | 3 |
| Q-11 | ✗ | ✓ | ✓ | 4 | 10 |
| Q-12 | ✗ | ✗ | ✓ | 4 | 7 |
| Q-13 | ✓ | ✓ | ✓ | 3 | 9 |
| Q-14 | ✗ | ✗ | ✗ | 4 | 7 |
| Q-15 | ✗ | ✓ | ✓ | 3 | 5 |
| Q-16 | ✓ | ✓ | ✓ | 4 | 5 |
| Q-17 | ✗ (unanswered) | ✓ | ✓ | 4 | 8 |
| Q-18 | ✗ | ✓ | ✓ | 3 | 3 |
| Q-19 | ✗ | ✓ | ✓ | 5 | 7 |
| Q-20 | ✗ | ✗ | ✓ | 4 | 10 |

## Per question (run 2)

| Question | S1 | S2 | S3 | S3 rounds | S3 tool calls |
|---|:---:|:---:|:---:|---:|---:|
| Q-01 | ✓ | ✓ | ✓ | 4 | 7 |
| Q-02 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-03 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-04 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-05 | ✗ | ✗ | ✓ | 3 | 5 |
| Q-06 | ✓ | ✓ | ✓ | 3 | 4 |
| Q-07 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-08 | ✗ | ✗ | ✓ | 3 | 6 |
| Q-09 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-10 | ✓ | ✓ | ✓ | 3 | 3 |
| Q-11 | ✗ | ✓ | ✓ | 4 | 10 |
| Q-12 | ✗ | ✗ | ✓ | 4 | 7 |
| Q-13 | ✗ (unanswered) | ✓ | ✓ | 3 | 9 |
| Q-14 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-15 | ✗ | ✓ | ✗ | 4 | 7 |
| Q-16 | ✓ | ✓ | ✓ | 3 | 4 |
| Q-17 | ✗ | ✓ | ✓ | 4 | 8 |
| Q-18 | ✓ | ✓ | ✓ | 3 | 3 |
| Q-19 | ✗ | ✓ | ✓ | 4 | 7 |
| Q-20 | ✗ | ✗ | ✓ | 4 | 10 |

## Wrong answers, run 1

- run 1 s1 Q-01: got ['Ossbridge', 5.69] want (Ossbridge, 4.6)
- run 1 s1 Q-02: got ['Tarnvale', 0.435] want (Harrowfield, 1.69)
- run 1 s1 Q-03: got ['Lindenmoor', 0.168] want (Lindenmoor, 5.3)
- run 1 s1 Q-04: got ['Ashgrove', 5.279] want (Millbrook, 2.59)
- run 1 s1 Q-05: got ['Coldharbour', 1181.653] want (Coldharbour, 14235)
- run 1 s1 Q-07: got ['Coldharbour', 16.59] want (Coldharbour, 18.5)
- run 1 s1 Q-08: got ['Brightwater', 72.403] want (Brightwater, 72.46)
- run 1 s1 Q-09: got ['Brightwater', 9.858] want (Millbrook, 0.6)
- run 1 s1 Q-11: got ['Millbrook', 54.804] want (Redfen, 56.1)
- run 1 s1 Q-12: got ['Harrowfield', 98.061] want (Tarnvale, 64.4)
- run 1 s1 Q-14: got ['Tarnvale', 0.042] want (Ashgrove, 4.9)
- run 1 s1 Q-15: got ['Kelmarsh', 16.034] want (Redfen, 17.61)
- run 1 s1 Q-17: got None want (Harrowfield, 884)
- run 1 s1 Q-18: got ['no', 40016.0] want (yes, 40013)
- run 1 s1 Q-19: got ['Lindenmoor', 0.026] want (Lindenmoor, 0.035)
- run 1 s1 Q-20: got ['Ossbridge', 55643.504] want (Ashgrove, 2993)
- run 1 s2 Q-05: got ['Coldharbour', 14258.0] want (Coldharbour, 14235) — {'coldharbour | 14258.0': 1, 'coldharbour | 14230.0': 1, 'coldharbour | 14277.0': 1, 'coldharbour | 14346.0': 1, 'coldharbour | 14219.0': 1}
- run 1 s2 Q-08: got ['Brightwater', 72.08] want (Brightwater, 72.46) — {'brightwater | 72.08': 1, 'brightwater | 71.96': 1, 'brightwater | 71.86': 1, 'brightwater | 71.66': 1, 'brightwater | 72.46': 1}
- run 1 s2 Q-12: got ['Tarnvale', 0.1] want (Tarnvale, 64.4) — {'tarnvale | 0.1': 2, 'tarnvale | 63.8': 1, 'tarnvale | 64.3': 1, 'tarnvale | 64.0': 1}
- run 1 s2 Q-14: got ['Ashgrove', 4.7] want (Ashgrove, 4.9) — {'ashgrove | 4.8': 1, 'ashgrove | 4.9': 1, 'ashgrove | 0.0': 1, 'ashgrove | 4.7': 2}
- run 1 s2 Q-20: got ['Ashgrove', 2998.0] want (Ashgrove, 2993) — {'ashgrove | 2998.0': 1, 'ashgrove | 2991.0': 1, 'ashgrove | 2992.0': 1, 'ashgrove | 2999.0': 1, 'ashgrove | 2993.0': 1}
- run 1 s3 Q-14: got ['yes', 4.853] want (Ashgrove, 4.9)

## Wrong answers, run 2

- run 2 s1 Q-02: got ['Tarnvale', 0.471] want (Harrowfield, 1.69)
- run 2 s1 Q-03: got ['Lindenmoor', 0.501] want (Lindenmoor, 5.3)
- run 2 s1 Q-04: got ['Ashgrove', 10.429] want (Millbrook, 2.59)
- run 2 s1 Q-05: got ['Stonecairn', 1291.687] want (Coldharbour, 14235)
- run 2 s1 Q-07: got ['Stonecairn', 3.755] want (Coldharbour, 18.5)
- run 2 s1 Q-08: got ['Millbrook', 0.19] want (Brightwater, 72.46)
- run 2 s1 Q-09: got ['Brightwater', 8.968] want (Millbrook, 0.6)
- run 2 s1 Q-11: got ['Redfen', 120.0] want (Redfen, 56.1)
- run 2 s1 Q-12: got ['Harrowfield', 0.168] want (Tarnvale, 64.4)
- run 2 s1 Q-13: got None want (Coldharbour, 4.16)
- run 2 s1 Q-14: got ['Tarnvale', 0.062] want (Ashgrove, 4.9)
- run 2 s1 Q-15: got ['Kelmarsh', 16.765] want (Redfen, 17.61)
- run 2 s1 Q-17: got ['Harrowfield', 4.613] want (Harrowfield, 884)
- run 2 s1 Q-19: got ['Redfen', 0.055] want (Lindenmoor, 0.035)
- run 2 s1 Q-20: got ['Harrowfield', 18228.478] want (Ashgrove, 2993)
- run 2 s2 Q-05: got ['Coldharbour', 14207.0] want (Coldharbour, 14235) — {'coldharbour | 14207.0': 1, 'coldharbour | 14233.0': 1, 'coldharbour | 14208.0': 1, 'coldharbour | 14203.0': 1, 'coldharbour | 14348.0': 1}
- run 2 s2 Q-08: got ['Brightwater', 72.16] want (Brightwater, 72.46) — {'brightwater | 72.16': 2, 'brightwater | 72.23': 1, 'brightwater | 72.31': 1, 'brightwater | 72.52': 1}
- run 2 s2 Q-12: got ['Tarnvale', 64.1] want (Tarnvale, 64.4) — {'tarnvale | 64.1': 3, 'tarnvale | 64.4': 1, 'tarnvale | 64.6': 1}
- run 2 s2 Q-20: got ['Ashgrove', 3004.0] want (Ashgrove, 2993) — {'ashgrove | 3004.0': 1, 'ashgrove | 2994.0': 1, 'ashgrove | 2993.0': 1, 'ashgrove | 2998.0': 1, 'ashgrove | 2987.0': 1}
- run 2 s3 Q-15: got ['yes', 17.609] want (Redfen, 17.61)

## C1

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-03 | 7 | 7 | Lindenmoor \| 5.34 ✓ | Lindenmoor \| 5.34 ✓ |
| Q-08 | 6 | 4 | Brightwater \| 72.456 ✓ | Brightwater \| 72.456 ✓ |
| Q-09 | 7 | 5 | Millbrook \| 0.556 ✓ | Millbrook \| 0.556 ✓ |
| Q-13 | 9 | 9 | Coldharbour \| 4.159 ✓ | Coldharbour \| 4.159 ✓ |
| Q-17 | 8 | 6 | Harrowfield \| 884.457 ✓ | Harrowfield \| 884.457 ✓ |
