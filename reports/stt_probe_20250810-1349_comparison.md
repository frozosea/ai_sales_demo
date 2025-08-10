# STT Performance Degradation Analysis

**Idle Period:** 30 seconds

## Performance Impact Summary

| Metric | Before | After | Change | Status |
|--------|---------|--------|---------|---------|
| Handshake (avg) | 383.2 ms | 0.3 ms | -99.9% | ✅ Good |
| TTFP (avg) | 366.2 ms | 192.0 ms | -47.6% | ✅ Good |
| TTFF (avg) | 1102.1 ms | 719.8 ms | -34.7% | ✅ Good |

## Detailed Metrics

### Before Idle Period

| Metric | Average | p50 | p95 |
|--------|---------|-----|-----|
| Handshake | 383.2 ms | 0.4 ms | 1914.7 ms |
| TTFP | 366.2 ms | 287.1 ms | 612.3 ms |
| TTFF | 1102.1 ms | 1208.0 ms | 1517.5 ms |

### After Idle Period

| Metric | Average | p50 | p95 |
|--------|---------|-----|-----|
| Handshake | 0.3 ms | 0.3 ms | 0.5 ms |
| TTFP | 192.0 ms | 186.8 ms | 213.1 ms |
| TTFF | 719.8 ms | 698.9 ms | 796.9 ms |

## Analysis

1. **Handshake Impact:**
   - Average degradation: -99.9%
   - Status: ✅ Good
   - No significant impact on connection setup time.

2. **First Partial Recognition (TTFP):**
   - Average degradation: -47.6%
   - Status: ✅ Good
   - Model maintains good responsiveness after idle period.

3. **First Final Recognition (TTFF):**
   - Average degradation: -34.7%
   - Status: ✅ Good
   - Final recognition timing remains stable.

## Recommendations

✅ Current connection management strategy is effective for the given idle period.

