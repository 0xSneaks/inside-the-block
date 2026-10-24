"""Static configuration for the Inside the Block measurement harness.

All spend limits live here and nowhere else. The fee cap is a hard stop
enforced by harness.fees.FeeAccountant, not a warning.
"""

# Dedicated measurement wallet for this study ONLY (public key is public data).
MEASUREMENT_WALLET = "2RCiezWiYHMULwXdn1MCxs82SDRWLK8QxQVAUGMFAXvJ"

# Hard cap: 0.05 SOL cumulative study spend, in lamports. The funded excess
# above the approved budget (0.008612973 SOL) is never touched; fees are the
# only spend (burst transactions are self-transfers, principal returns).
CAP_LAMPORTS = 50_000_000

BASE_FEE_LAMPORTS = 5_000  # per signature

# Compute budget: every burst tx requests this CU limit and a tier price.
# Priority fee = ceil(CU_LIMIT * price_micro_lamports / 1_000_000), charged on
# the REQUESTED limit, so fees are exactly computable before sending.
CU_LIMIT = 200_000

# Fee tiers: name -> SetComputeUnitPrice value (micro-lamports per CU).
# Resulting priority fees: zero=0, low=12_500, mid=50_000, high=100_000 lamports.
FEE_TIERS = {
    "zero": 0,
    "low": 62_500,
    "mid": 250_000,
    "high": 500_000,
}

# Tier pattern across the 16 send positions of a burst. Deliberately
# decorrelated from send order; reversed on alternate bursts (see burst.py).
TIER_PATTERN = [
    "zero", "high", "low", "mid",
    "zero", "high", "low", "mid",
    "zero", "high", "low", "mid",
    "zero", "high", "low", "mid",
]

BURST_SIZE = 16
BURSTS_PER_VALIDATOR = 3
MIN_VALIDATORS = 6
MIN_CLIENT_FAMILIES = 3

# Marker candidate (Phase 2 shakedown decides the final mechanism; see
# DESIGN.md): each burst tx is a self-transfer whose amount encodes the send
# index. Principal returns to the same wallet; only fees are spent.
MARKER_BASE_LAMPORTS = 10_000  # + send_index (0..15)

# RPC endpoints. One send path for the whole study, named in the report.
RPC_URL = "https://api.mainnet-beta.solana.com"
DEVNET_RPC_URL = "https://api.devnet.solana.com"

SYSTEM_PROGRAM = "11111111111111111111111111111111"
COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111"
