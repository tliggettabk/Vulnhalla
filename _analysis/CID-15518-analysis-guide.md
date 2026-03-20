# CID-15518 Analysis Guide
If Vulnhalla just ran and you are analyzing results, be sure you have the most recent results.  There have been multiple runs.

Provide an estimated cost in $ of the run and per finding.
## Issue Summary
**Vulnerability:** Array overrun - passing `layerIndex` value of 256 to callback operating on 256-element array  
**Valid indices:** 0-255, so index 256 = out-of-bounds access

## Expected Analysis Approach

### Key Questions to Verify:
1. **What constrains `layerCount` parameter?**
   - Can `layerCount` be set to values > 256?
   - What prevents caller from passing `layerCount = 257`?

2. **Loop guard effectiveness:**
   - Guard: `while (layerIndex < layerCount)` 
   - If `layerCount = 257` and `layerIndex = 256`, guard allows callback execution
   - Guard is NOT sufficient if `layerCount` itself isn't properly bounded

3. **Actual bounds verification:**
   - Investigate `layerMask.num_bits` - is it always exactly 256?
   - Trace parameter flow to verify runtime constraints
   - Don't assume constants prevent the issue - verify the constraint chain

### Common Analysis Mistakes:
- ❌ Assuming loop guard prevents all overruns without validating upper bound
- ❌ Relying on assertions (disabled in release builds) 
- ❌ Assuming `layerCount <= 256` without investigating constraint source

### Correct Assessment:
- ✅ **True Positive** if `layerCount` can exceed array size
- ✅ **False Positive** only if runtime constraints actually prevent `layerCount > 256`
- ✅ Must trace constraints, not assume them

## Bottom Line
The loop guard `layerIndex < layerCount` doesn't prevent overrun if `layerCount` itself isn't properly bounded to array size.