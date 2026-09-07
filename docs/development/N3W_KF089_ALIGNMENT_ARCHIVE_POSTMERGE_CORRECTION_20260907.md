# N3-W KF-089 Alignment Archive Post-Merge Correction — 2026-09-07

Status: `PUBLIC_SAFE_CORRECTION`

This note corrects one self-referential wording issue in:

`docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_ARCHIVE_20260907.md`

The archive was authored while repository `main` was:

```text
483ff1c662dc74d6e12529e27a69819e68160f9e
```

and then merged by PR #371. The act of merging the archive necessarily advanced `main` to a documentation-only descendant. Therefore any archive sentence that describes `483ff1c...` as the repository's permanently current `main` must be interpreted as:

```text
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
LAST_PRODUCT_SOURCE_CHANGE=PR_370
```

The PR #371 documentation merge itself was:

```text
ALIGNMENT_ARCHIVE_PR=371
ALIGNMENT_ARCHIVE_PR_MERGE=cb437a2103dda026271a98c2d2acb172205fd72d
ALIGNMENT_ARCHIVE_MERGE_TREE=261e6a19fd61016df3118e60f3dcce76de8ecea4
```

Subsequent documentation-only commits/merges may advance `main` again without changing the product source used to build the current observability artifact.

Accordingly:

- do not use a literal `CURRENT_MAIN=<sha>` stored in a live state document as permanent authority;
- resolve `origin/main` fresh whenever a task needs current repository authority;
- separately bind the product/source commit used for firmware/build evidence;
- the observability artifact built in the 2026-09-07 preclaim remains bound to `483ff1c...`, not to later documentation-only descendants;
- the next physical gate must not silently rebuild or reinterpret that artifact under a newer documentation-only `main`.

Current stable product/artifact facts remain:

```text
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
OBSERVABILITY_FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
OBSERVABILITY_FIRMWARE_SIZE=1114144
NEXT_GATE=KF089_OBSERVABILITY_TWO_BOARD_APP_REFRESH_AND_DIRECT_DIAGNOSTIC_BASELINE
```

This correction changes documentation semantics only. It does not alter product source, tests, physical boards, firmware artifacts, T1, Broker, Manager, Home Assistant, provisioning state, credentials or keys.
