"""One display name per job method.

The queue identifies a job by the RPC entry point that created it -
`getMatchesForSample`, `combineMatchesToCross`. That is the right name for a log line
and the wrong one for a heading, and until now every page answered the question
differently: the job list wrote "Match 1vN", the job overview printed
`getMatchesForSample(0, 2)`, two result pages printed the bare method, and four more
printed `matching_result.method` - an attribute `MatchingResult` does not have, so those
headings rendered as nothing at all. See issue #39.

The names below are exactly the ones `templates/table/job_row.html` was already using,
so the job list reads the same as before; everything else now agrees with it. The RPC
name has not been hidden anywhere - `job_column_table` still shows the full
`parameters`, arguments and all, directly beneath every heading this feeds.

Kept free of Flask and mcrit imports on purpose (see issue #88): it is a lookup table,
and a test should not have to build an app to check it.
"""

JOB_METHOD_NAMES = {
    # matching
    "getMatchesForSample": "Match 1vN",
    "getMatchesForSampleVs": "Match 1v1",
    "getMatchesForSampleVsGroup": "Match 1vGroup",
    "combineMatchesToCross": "CrossCompare",
    # queries
    "getMatchesForUnmappedBinary": "Match Binary (unmapped)",
    "getMatchesForMappedBinary": "Match Binary (mapped)",
    "getMatchesForSmdaReport": "Match SMDA Report",
    # blocks
    "getUniqueBlocks": "UniqueBlocks",
    # minhashing and index maintenance
    "updateMinHashesForSample": "Update MinHash",
    "updateMinHashes": "Update all missing MinHashes",
    "rebuildIndex": "Rebuild full Index",
    "recalculatePicHashes": "Recalculate PicHashes",
    "recalculateMinHashes": "Recalculate MinHashes and Index",
    # collection changes
    "addBinarySample": "Add Binary",
    "deleteSample": "Delete Sample",
    "modifySample": "Modify Sample",
    "deleteFamily": "Delete Family",
    "modifyFamily": "Modify Family",
    # maintenance
    "doDbCleanup": "Database Cleanup",
}


def job_method_name(method):
    """The display name for a job method.

    A method this table does not know is shown as-is rather than as a placeholder: a
    new job type added in the backend should still be identifiable here, and the raw
    name is more use than "Unknown". An absent method is the only case with nothing to
    fall back on.
    """
    if not method:
        return "Unknown job"
    return JOB_METHOD_NAMES.get(method, method)
