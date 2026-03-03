//// VAMS Utility Functions
////
//// Shared helpers for math, validation, and common operations
//// used across all VAMS Cardano validators.

use aiken/collection/list

// ═══════════════════ Math Helpers ═══════════════════

/// Integer square root (Babylonian method)
/// Used for quadratic vote weighting: weight = sqrt(staked)
pub fn isqrt(n: Int) -> Int {
  if n < 0 {
    0
  } else if n == 0 {
    0
  } else if n == 1 {
    1
  } else {
    let initial_guess = n / 2
    isqrt_iterate(n, initial_guess)
  }
}

/// Newton's method iteration for integer square root
fn isqrt_iterate(n: Int, guess: Int) -> Int {
  let next = (guess + n / guess) / 2
  if next >= guess {
    guess
  } else {
    isqrt_iterate(n, next)
  }
}

/// Basis points calculation: (value * bps) / 10000
pub fn apply_bps(value: Int, bps: Int) -> Int {
  value * bps / 10000
}

// ═══════════════════ Validation Helpers ═══════════════════

/// Check if a verification key hash is in a list of signatories
pub fn is_signed_by(
  signatories: List<ByteArray>,
  vkh: ByteArray,
) -> Bool {
  list.has(signatories, vkh)
}

/// Count how many of the required signers have signed
pub fn count_signatures(
  signatories: List<ByteArray>,
  required: List<ByteArray>,
) -> Int {
  list.foldl(
    required,
    0,
    fn(vkh, acc) {
      if list.has(signatories, vkh) {
        acc + 1
      } else {
        acc
      }
    },
  )
}

/// Check if a value is within a valid range (inclusive)
pub fn in_range(value: Int, min: Int, max: Int) -> Bool {
  value >= min && value <= max
}

// ═══════════════════ Time Helpers ═══════════════════

/// Check if a POSIX timestamp has passed relative to validity range
pub fn has_deadline_passed(deadline: Int, current_time: Int) -> Bool {
  current_time > deadline
}

/// Check if timelock delay has elapsed
pub fn is_timelock_ready(execute_after: Int, current_time: Int) -> Bool {
  current_time >= execute_after
}

// ═══════════════════ Tests ═══════════════════

test isqrt_zero() {
  isqrt(0) == 0
}

test isqrt_one() {
  isqrt(1) == 1
}

test isqrt_four() {
  isqrt(4) == 2
}

test isqrt_nine() {
  isqrt(9) == 3
}

test isqrt_large() {
  // sqrt(10000) = 100
  isqrt(10000) == 100
}

test isqrt_non_perfect() {
  // sqrt(10) ≈ 3.16 → floor = 3
  isqrt(10) == 3
}

test apply_bps_5_percent() {
  // 5% of 1000 = 50
  apply_bps(1000, 500) == 50
}

test apply_bps_100_percent() {
  apply_bps(1000, 10000) == 1000
}

test in_range_within() {
  in_range(50, 0, 100) == True
}

test in_range_below() {
  in_range(-1, 0, 100) == False
}

test in_range_boundary() {
  in_range(0, 0, 100) == True && in_range(100, 0, 100) == True
}
