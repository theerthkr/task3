// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VerificationRegistry
 * @notice Stores SHA-256 verification fingerprints (bytes32) + source metadata on-chain.
 *         Designed for hackathon evidence anchoring: a post's hash (image/text/metadata)
 *         is stored tamper-evidently. Raw media is NOT stored on-chain.
 */
contract VerificationRegistry {

    struct Record {
        bytes32 dataHash;
        string  sourceUrl;
        uint256 timestamp;
        bool    exists;
    }

    mapping(bytes32 => Record) public records;

    event RecordStored(
        bytes32 indexed dataHash,
        string  sourceUrl,
        uint256 timestamp
    );

    /// @notice Store / overwrite a verification record.
    /// @param dataHash  SHA-256 fingerprint as bytes32 (0x... 32 bytes).
    /// @param sourceUrl Source/page URL or identifier for the evidence.
    function storeRecord(bytes32 dataHash, string calldata sourceUrl) external returns (bool) {
        require(dataHash != bytes32(0), "Data hash cannot be empty");
        records[dataHash] = Record({
            dataHash:  dataHash,
            sourceUrl: sourceUrl,
            timestamp: block.timestamp,
            exists:    true
        });
        emit RecordStored(dataHash, sourceUrl, block.timestamp);
        return true;
    }

    /// @notice Check whether a fingerprint exists on-chain.
    function verifyRecord(bytes32 dataHash) external view returns (bool) {
        return records[dataHash].exists;
    }

    /// @notice Retrieve full record for a fingerprint. Reverts if missing.
    function getRecord(bytes32 dataHash) external view returns (bytes32, string memory, uint256) {
        require(records[dataHash].exists, "Record does not exist on-chain");
        Record memory rec = records[dataHash];
        return (rec.dataHash, rec.sourceUrl, rec.timestamp);
    }
}
