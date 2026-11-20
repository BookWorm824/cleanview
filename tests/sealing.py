"""Seals for made-up updates in tests (1.18.147): a test key, never the owner's."""
import hashlib
import json
import sys

from support import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import sign_release  # noqa: E402

TEST_SEED = bytes(range(32))


def use_test_key(lm):
    """Make the launcher module lm trust the test key instead of the owner's."""
    lm.PUBLIC_KEY = sign_release.public_of(TEST_SEED, lm)


def sealed_release(lm, remote, files, seed=TEST_SEED):
    """version.json's bytes (with every file's fingerprint) and version.sig's text."""
    remote = dict(remote)
    remote["sha256"] = {n: hashlib.sha256(files[n] if isinstance(files[n], bytes)
                                          else files[n].encode("utf8")).hexdigest()
                        for n in remote["files"]}
    data = json.dumps(remote).encode("utf8")
    return data, sign_release.sign(seed, lm.SEAL_FOR.encode("utf8") + data, lm).hex()
