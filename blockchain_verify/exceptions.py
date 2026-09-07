"""Domain exceptions – import from here so callers can catch narrowly."""

class BlockchainVerifyError(Exception):
    """Base for all blockchain_verify errors."""

class ConnectionError(BlockchainVerifyError):
    """RPC unreachable or chain mismatch."""

class ConfigurationError(BlockchainVerifyError):
    """Missing env / ABI / address."""

class DeploymentError(BlockchainVerifyError):
    """Compile or deploy failed."""

class TransactionError(BlockchainVerifyError):
    """On-chain tx reverted or timed out."""

class RecordNotFoundError(BlockchainVerifyError):
    """getRecord called for unknown hash."""
