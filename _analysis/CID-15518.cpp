// CID 15518 - Array overrun in R_ST_IterateLayerMask
// Source: SuperTerrainDefines.h, lines 214-229
// Static analyzer: "Overrunning callee's array of size 256 by passing argument
//   'layerIndex' (which evaluates to 256) in call to 'operator ()'."
//
// Vulnerability: core_assert(layerCount <= layerMask.num_bits) is a NO-OP in
// release builds. If layerCount > num_bits (256), find_first_bit_from() can
// return the sentinel value num_bits (256), the guard 256 < 257 passes, and
// callback(256) overruns any 256-entry array (valid indices 0-255).
//
// Code below is ordered most-recently-requested first (by LLM tool calls).
// All code from: D:/mapped_drives/cod/trunk/code/

// ============================================================================
// ntl::bitset::find_first_bit_from_block — RETURNS SENTINEL num_bits
// file: common/libs/ntl/ntl/bitset/bitset.h, line 588
// ============================================================================
template <bool FIND_ON>
[[nodiscard]] NTL_FORCE_INLINE ntl_size_t find_first_bit_from_block( ntl_size_t startBlock ) const
{
    NTL_ASSERT( startBlock < num_blocks );

    for ( ntl_size_t i = startBlock; i < num_whole_blocks; i++ )
    {
        const T_TYPE block = FIND_ON ? m_data[i] : ~m_data[i];
        if ( const uint bitIndex = CountLeadingZeros( block ); bitIndex != bits_per_block )
        {
            return i * bits_per_block + bitIndex;
        }
    }

    if constexpr ( has_fringe_bits() )
    {
        const T_TYPE block = FIND_ON ? m_data[num_blocks - 1] : ~m_data[num_blocks - 1];
        constexpr ntl_size_t mask = fringe_bits_mask();
        if ( const uint bitIndex = CountLeadingZeros( block & mask ); bitIndex != bits_per_block )
        {
            return ( num_blocks - 1 ) * bits_per_block + bitIndex;
        }
    }

    return num_bits;  // <— SENTINEL: returns 256 when no bit found
}

// ============================================================================
// ntl::bitset::find_first_bit_from — delegates to find_first_bit_from_block
// file: common/libs/ntl/ntl/bitset/bitset.h, line 428
// ============================================================================
template <bool FIND_ON>
[[nodiscard]] NTL_FORCE_INLINE ntl_size_t find_first_bit_from( ntl_size_t pos ) const
{
    NTL_ASSERT( pos < num_bits );

    T_TYPE startWordIndex = static_cast<T_TYPE>( get_index( pos ) );

    const bool startsAtWordBoundary = ( pos & ( bits_per_block - 1 ) ) == 0;
    if ( !startsAtWordBoundary )
    {
        constexpr ntl_size_t fringeMask = fringe_bits_mask();
        const T_TYPE maskToStartBit = ALL_BITS_SET >> ( pos & ( bits_per_block - 1 ) );
        const T_TYPE maskedStartWordBits = ( FIND_ON ? m_data[startWordIndex] : ~m_data[startWordIndex] )
            & ( maskToStartBit & ( has_fringe_bits() && startWordIndex == num_blocks - 1 ? fringeMask : ALL_BITS_SET ) );
        const uint currWordShift = CountLeadingZeros( maskedStartWordBits );

        if ( currWordShift < bits_per_block )
        {
            return startWordIndex * bits_per_block + currWordShift;
        }
        if ( startWordIndex == num_blocks - 1 )
        {
            return num_bits; // not found — returns sentinel
        }

        ++startWordIndex;
    }

    return find_first_bit_from_block<FIND_ON>( startWordIndex );
}

// ============================================================================
// ntl::bitset::find_first_bit — entry point, calls find_first_bit_from_block(0)
// file: common/libs/ntl/ntl/bitset/bitset.h, line 422
// ============================================================================
template <bool FIND_ON>
[[nodiscard]] NTL_FORCE_INLINE ntl_size_t find_first_bit() const
{
    return find_first_bit_from_block<FIND_ON>( 0 );
}

// ============================================================================
// StLayerMaskOMPVRaw — the underlying struct
// file: src/gfx/r_st_db.h, line 157
// ============================================================================
struct ALIGN( 8 ) StLayerMaskOMPVRaw
{
    uint32_t data[ST_NUM_UINTS_FOR_LAYER_MASK];
};
// StLayerMaskOMPV is a typedef alias for ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>
// which inherits from StLayerMaskOMPVRaw

// ============================================================================
// Constants — the chain that resolves array size to 256
// file: common/libs/SuperTerrainCore/SuperTerrainCore/SuperTerrainDefines.h
// ============================================================================
inline constexpr uint ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256;                 // line 51
inline constexpr uint ST_MAX_LAYERS_PER_SURFACE_OMPV = ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS; // → 256
inline constexpr uint ST_NUM_UINTS_FOR_LAYER_MASK = ST_MAX_LAYERS_PER_SURFACE_OMPV / ( sizeof( uint32_t ) * 8 ); // line 150 → 8

// Therefore: ntl::bitset<256> → num_bits = 256, data[8]

// ============================================================================
// R_ST_IterateLayerMask — THE VULNERABLE FUNCTION (CID 15518)
// file: common/libs/SuperTerrainCore/SuperTerrainCore/SuperTerrainDefines.h, line 214
// ============================================================================
template <typename CB>
inline void R_ST_IterateLayerMask( const StLayerMaskOMPV &layerMask, ntl::ntl_size_t layerCount, CB callback )
{
    core_assert( layerCount <= layerMask.num_bits );  // NO-OP in release — layerCount is UNBOUNDED
    ntl::ntl_size_t layerIndex = layerMask.find_first_bit<true>();
    while ( layerIndex < layerCount )  // guard broken when layerCount > 256
    {
        callback( layerIndex );  // line 220 — OVERRUN when layerIndex == 256

        if ( layerIndex == layerCount - 1 )
        {
            break;
        }

        layerIndex = layerMask.find_first_bit_from<true>( layerIndex + 1 );  // returns sentinel 256 when exhausted
    }
}

// Exploit path:
//   1. Caller passes layerCount = 257 (core_assert is NO-OP, no runtime check)
//   2. layerMask is empty (no bits set)
//   3. find_first_bit<true>() → find_first_bit_from_block<true>(0) → returns num_bits = 256
//   4. Guard: 256 < 257 → TRUE
//   5. callback(256) → accesses array[256] → OFF-BY-ONE OVERRUN (valid: 0-255)
